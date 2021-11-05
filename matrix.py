from itertools import product

import numpy as np

from block import Block


class Matrix(Block):
    """Matrix

    Args:
    """

    def __init__(self, factory, points,
                 parent=None,
                 transforms=None, use_register_tag=False,
                 do_register_map=None,
                 structure_all_map=None,
                 quadrate_all_map=None,
                 boolean_level_map=None,
                 zone_all_map=None,
                 # ts=None, txs=None, tys=None, tzs=None,
                 # lcs=None, lcs_map=None,
                 # types=None, type_map=None,
                 # volumes_names=None, volumes_map=None,
                 # surfaces_names=None, surfaces_map=None,
                 # in_surfaces_names=None, in_surfaces_map=None,
                 # in_surfaces_masks=None, in_surfaces_masks_map=None,
                 # transforms=None, transforms_map=None,
                 # inputs=None, inputs_map=None,
                 # kws=None, kws_map=None,
                 # recs_map=None, trans_map=None, trans_type_map=None,
                 # curve_types=None, curve_types_map=None,
                 # curve_data=None, curve_data_map=None,
                 # curve_data_coord_sys=None, curve_data_coord_sys_map=None,
                 # inputs_transforms=None, inputs_transforms_map=None,
                 # inputs_transforms_coord_sys=None,
                 # inputs_transforms_coord_sys_map=None,
                 # boolean_level_map=None,
                 # exists_map=None
                 ):
        transforms = [] if transforms is None else transforms
        blocks_points, new2old = Matrix.parse_matrix_points(points)
        do_register_map = Matrix.parse_map(do_register_map, True, new2old)
        structure_all_map = Matrix.parse_map(structure_all_map, None, new2old)
        quadrate_all_map = Matrix.parse_map(quadrate_all_map, None, new2old)
        boolean_level_map = Matrix.parse_map(boolean_level_map, None, new2old)
        zone_all_map = Matrix.parse_map(zone_all_map, None, new2old)
        children = [Block(factory=factory,
                          points=x,
                          use_register_tag=use_register_tag,
                          do_register=do_register_map[i],
                          structure_all=structure_all_map[i],
                          quadrate_all=quadrate_all_map[i],
                          boolean_level=boolean_level_map[i],
                          zone_all=zone_all_map[i],
                          parent=self) for i, x in enumerate(blocks_points)]
        super().__init__(factory=factory, parent=parent,
                         do_register=False,
                         children=children, transforms=transforms,
                         use_register_tag=use_register_tag)

    @staticmethod
    def parse_matrix_points(points):
        # Correct points
        for row_i, row in enumerate(points):
            if isinstance(row, list):
                if not isinstance(row[0], str):
                    row = ['value'] + row
                elif row[0] not in ['value', 'increment']:
                    row = ['value'] + row
                if not isinstance(row[1], (float, int)):
                    row = [row[0], 0] + row[1:]
                points[row_i] = row
        # Split rows into list and other
        list_rows = [x for x in points if isinstance(x, list)]
        other_rows = [x for x in points if not isinstance(x, list)]
        # Parse list rows and evaluate new to old maps for each row
        rows_coords = []
        rows_new2old, rows_old2new = [], []
        for row_i, row in enumerate(list_rows):
            new2old, old2new = {}, {}
            row_type, cur_c, cs = row[0], float(row[1]), row[2:]
            if row_type not in ['value', 'increment']:
                raise ValueError(row_type)
            new_cs = [cur_c]
            for col_i, c in enumerate(cs):
                if isinstance(c, (float, int)):
                    dc = c - cur_c if row_type == 'value' else c
                    cur_c += dc
                    new_cs.append(cur_c)
                    new_i, old_i = len(new_cs) - 2, col_i
                    old2new.setdefault(old_i, []).append(new_i)
                    new2old[new_i] = old_i
                elif isinstance(c, str):
                    vs = c.split(':')
                    if len(vs) == 2:
                        c, n = float(vs[0]), int(vs[1])
                        new_c = c if row_type == 'value' else cur_c + c
                        for x in np.linspace(cur_c, new_c, n)[1:]:
                            new_cs.append(x)
                            new_i, old_i = len(new_cs) - 2, col_i
                            old2new.setdefault(old_i, []).append(new_i)
                            new2old[new_i] = old_i
                        cur_c = new_c
                    elif len(vs) == 4:
                        c, n, = float(vs[0]), int(vs[1])
                        a, b = float(vs[2]), float(vs[3])
                        dc = c - cur_c if row_type == 'value' else c
                        nt = 10000
                        ts, dt = np.linspace(0, 1, nt, retstep=True)
                        ts = ts[1:-1]  # Exclude start and end step
                        t = np.sum(ts ** (a - 1) * (1 - ts) ** (b - 1) * dt)
                        prev_x, dcs = 0, []
                        for i in range(n):
                            u = (i + 1) / n
                            nu = int(np.ceil(u * nt))
                            us, du = np.linspace(0, u, nu, retstep=True)
                            us = us[1:] if u != 1 else us[1:-1]
                            u = np.sum(us ** (a - 1) * (1 - us) ** (b - 1) * du)
                            x = u / t
                            dx = x - prev_x
                            dci = dx * dc
                            prev_x = x
                            dcs.append(dci)
                        assert (np.isclose(dc, sum(dcs)))
                        for dc in dcs:
                            cur_c += dc
                            new_cs.append(cur_c)
                            new_i, old_i = len(new_cs) - 2, col_i
                            old2new.setdefault(old_i, []).append(new_i)
                            new2old[new_i] = old_i
                    else:
                        raise ValueError(c, vs, points)
            rows_coords.append(new_cs)
            rows_new2old.append(new2old)
            rows_old2new.append(old2new)
        # Parse other rows
        if len(other_rows) == 0:
            coordinate_system = 'cartesian'
            params_expand_type = 'trace'
        elif len(other_rows) == 1:
            coordinate_system = other_rows[0]
            params_expand_type = 'trace'
        else:
            coordinate_system = other_rows[0]
            params_expand_type = other_rows[1]
        # Split points into coordinates and parameters
        coords, params = rows_coords[:3], rows_coords[3:]
        if len(params) > 0:
            if params_expand_type == 'trace':
                min_len = min(len(x) for x in params)
                params = [[x[i] for x in params] for i in range(min_len)]
            elif params_expand_type == 'product':
                params = [list(x) for x in product(*params)]
            else:
                raise ValueError(params_expand_type)
        else:
            params = [[]]
        # Old global to old local
        old_g2l, old_l2g = {}, {}
        for pi, p in enumerate(params):
            xs, ys, zs = points[0][2:], points[1][2:], points[2][2:]
            nx, ny, nz = len(xs), len(ys), len(zs)
            for zi in range(nz):
                for yi in range(ny):
                    for xi in range(nx):
                        gi = pi * nx * ny * nz + zi * ny * nx + yi * nx + xi
                        li = (pi, zi, yi, xi)
                        old_g2l[gi] = li
                        old_l2g[li] = gi
        # Evaluate blocks points and new global to new local
        blocks_points = []
        new_g2l, new_l2g = {}, {}
        for pi, p in enumerate(params):
            xs, ys, zs = coords  # with start coordinate
            nx, ny, nz = len(xs) - 1, len(ys) - 1, len(zs) - 1
            for zi, z in enumerate(zs[1:], start=1):
                prev_z = zs[zi - 1]
                for yi, y in enumerate(ys[1:], start=1):
                    prev_y = ys[yi - 1]
                    for xi, x in enumerate(xs[1:], start=1):
                        prev_x = xs[xi - 1]
                        block_points = [
                            [x, y, prev_z] + p,
                            [prev_x, y, prev_z] + p,
                            [prev_x, prev_y, prev_z] + p,
                            [x, prev_y, prev_z] + p,
                            [x, y, z] + p,
                            [prev_x, y, z] + p,
                            [prev_x, prev_y, z] + p,
                            [x, prev_y, z] + p,
                            coordinate_system]
                        blocks_points.append(block_points)
                        gi = pi * nx * ny * nz + (zi - 1) * ny * nx + (yi - 1) * nx + (xi - 1)
                        li = (pi, zi - 1, yi - 1, xi - 1)
                        new_g2l[gi] = li
                        new_l2g[li] = gi
        # New global to old global
        new2old_g2g, old2new_g2g = {}, {}
        for new_gi, new_li in new_g2l.items():
            pi, zi, yi, xi = new_li
            new2old_z, new2old_y, new2old_x = rows_new2old[2], rows_new2old[1], rows_new2old[0],
            old_zi, old_yi, old_xi = new2old_z[zi], new2old_y[yi], new2old_x[xi]
            old_li = (pi, old_zi, old_yi, old_xi)
            old_gi = old_l2g[old_li]
            new2old_g2g[new_gi] = old_gi
            old2new_g2g.setdefault(old_gi, []).append(new_gi)
        return blocks_points, new2old_g2g

    @staticmethod
    def parse_map(m, default, new2old):
        if m is None:
            m = [default for _ in new2old]
        elif not isinstance(m, list):
            m = [m for _ in new2old]
        else:
            m = [m[old_i] for old_i in new2old.values()]
        return m


#             # Update maps
#             if isinstance(txs, list):
#                 txs = [txs[n2o_xs[xi]] for xi in range(nx)]
#             if isinstance(tys, list):
#                 tys = [tys[n2o_ys[yi]] for yi in range(ny)]
#             if isinstance(tzs, list):
#                 tzs = [tzs[n2o_zs[zi]] for zi in range(nz)]
#             if isinstance(lcs_map, list):
#                 lcs_map = [lcs_map[n2o_gs[gi]] for gi in range(ni)]
#             if isinstance(transforms_map, list):
#                 transforms_map = [transforms_map[n2o_gs[gi]] for gi in range(ni)]
#             if isinstance(type_map, list):
#                 type_map = [type_map[n2o_gs[gi]] for gi in range(ni)]
#             if isinstance(transforms_map, list):
#                 transforms_map = [transforms_map[n2o_gs[gi]] for gi in range(ni)]
#             if isinstance(volumes_map, list):
#                 volumes_map = [volumes_map[n2o_gs[gi]] for gi in range(ni)]
#             if isinstance(surfaces_map, list):
#                 surfaces_map = [surfaces_map[n2o_gs[gi]] for gi in range(ni)]
#             if isinstance(in_surfaces_map, list):
#                 in_surfaces_map = [in_surfaces_map[n2o_gs[gi]] for gi in range(ni)]
#             if isinstance(inputs_map, list):
#                 inputs_map = [inputs_map[n2o_gs[gi]] for gi in range(ni)]
#             if isinstance(kws_map, list):
#                 kws_map = [kws_map[n2o_gs[gi]] for gi in range(ni)]
#             if isinstance(recs_map, list):
#                 recs_map = [recs_map[n2o_gs[gi]] for gi in range(ni)]
#             if isinstance(trans_map, list):
#                 trans_map = [trans_map[n2o_gs[gi]] for gi in range(ni)]
#             if isinstance(curve_types_map, list):
#                 curve_types_map = [curve_types_map[n2o_gs[gi]] for gi in range(ni)]
#             if isinstance(curve_data_map, list):
#                 curve_data_map = [curve_data_map[n2o_gs[gi]] for gi in range(ni)]
#             if isinstance(curve_data_coord_sys_map, list):
#                 curve_data_coord_sys_map = [curve_data_coord_sys_map[n2o_gs[gi]] for gi in range(ni)]
#             if isinstance(inputs_transforms_coord_sys_map, list):
#                 inputs_transforms_coord_sys_map = [inputs_transforms_coord_sys_map[n2o_gs[gi]] for gi in range(ni)]
#             if isinstance(boolean_level_map, list):
#                 boolean_level_map = [boolean_level_map[n2o_gs[gi]] for gi in range(ni)]
#         else:  # No indexing
#             if coordinates_type == 'delta':
#                 x0, y0, z0 = 0, 0, 0
#             elif coordinates_type == 'direct':  # convert to delta
#                 x0, y0, z0 = xs[0], ys[0], zs[0]
#                 xs = [xs[i] - xs[i - 1] for i in range(1, len(xs))]
#                 ys = [ys[i] - ys[i - 1] for i in range(1, len(ys))]
#                 zs = [zs[i] - zs[i - 1] for i in range(1, len(zs))]
#             else:
#                 raise ValueError(f'coordinates_type: {coordinates_type}')
#             nx, ny, nz = len(xs), len(ys), len(zs)
#             ni = nx * ny * nz  # number of matrix items
#         # Coordinates
#         l2g = {}  # local index (xi, yj, zk) -> global index (gi) map
#         g2l = {}  # global index (gi) map -> local index (xi, yj, zk)
#         for zi in range(nz):
#             for yi in range(ny):
#                 for xi in range(nx):
#                     gi = xi + nx * yi + ny * nx * zi
#                     l2g[(xi, yi, zi)] = gi
#                     g2l[gi] = (xi, yi, zi)
#         x0s, x1s, xcs = [], [], []  # items starts X, Y, Z
#         y0s, y1s, ycs = [], [], []  # items ends X, Y, Z
#         z0s, z1s, zcs = [], [], []  # items centers X, Y, Z
#         for k in range(nz):
#             for j in range(ny):
#                 for i in range(nx):
#                     x0s.append(x0 + sum(xs[:i]))
#                     x1s.append(x0 + sum(xs[:i + 1]))
#                     xcs.append(0.5 * (x0s[-1] + x1s[-1]))
#                     y0s.append(y0 + sum(ys[:j]))
#                     y1s.append(y0 + sum(ys[:j + 1]))
#                     ycs.append(0.5 * (y0s[-1] + y1s[-1]))
#                     z0s.append(z0 + sum(zs[:k]))
#                     z1s.append(z0 + sum(zs[:k + 1]))
#                     zcs.append(0.5 * (z0s[-1] + z1s[-1]))
#         # transform (default [])
#         if transform_data is None:
#             transform_data = []
#         if transforms is None:
#             transforms = [[]]
#         if transforms_map is None:
#             transforms_map = [0 for _ in range(ni)]
#         elif not isinstance(transforms_map, list):
#             transforms_map = [transforms_map for _ in range(ni)]
#         # transfinite (default [3, 0, 1])
#         if ts is None:
#             ts = [[3, 0, 1]]
#         if txs is None:
#             txs = [0 for _ in range(nx)]
#         elif not isinstance(txs, list):
#             txs = [txs for _ in range(nx)]
#         if tys is None:
#             tys = [0 for _ in range(ny)]
#         elif not isinstance(tys, list):
#             tys = [tys for _ in range(ny)]
#         if tzs is None:
#             tzs = [0 for _ in range(nz)]
#         elif not isinstance(tzs, list):
#             tzs = [tzs for _ in range(nz)]
#         if trans_map is None:
#             trans_map = [1 for _ in range(ni)]
#         if trans_type_map is None:
#             trans_type_map = [0 for _ in range(ni)]
#         elif not isinstance(trans_type_map, list):
#             trans_type_map = [trans_type_map for _ in range(ni)]
#         # characteristic length (default 1)
#         if lcs is None:
#             lcs = [1 for _ in range(ni)]
#         elif not isinstance(lcs, list):
#             lcs = [lcs for _ in range(ni)]
#         if lcs_map is None:
#             lcs_map = [0 for _ in range(ni)]
#         elif not isinstance(lcs_map, list):
#             lcs_map = [lcs_map for _ in range(ni)]
#         # types
#         if types is None:
#             types = ['primitive']
#         if type_map is None:
#             type_map = [0 for _ in range(ni)]
#         elif not isinstance(type_map, list):
#             type_map = [type_map for _ in range(ni)]
#         # volumes
#         if volumes_names is None:
#             volumes_names = [None]
#         if volumes_map is None:
#             volumes_map = [0 for _ in range(ni)]
#         elif not isinstance(volumes_map, list):
#             volumes_map = [volumes_map for _ in range(ni)]
#         # surfaces
#         if surfaces_names is None:
#             surfaces_names = [None]
#         elif isinstance(surfaces_names, str):
#             surfaces_names = [[surfaces_names for _ in range(6)]]
#         if surfaces_map is None:
#             surfaces_map = [0 for _ in range(ni)]
#         elif not isinstance(surfaces_map, list):
#             surfaces_map = [surfaces_map for _ in range(ni)]
#         if in_surfaces_names is None:
#             in_surfaces_names = [None]
#         elif isinstance(in_surfaces_names, str):
#             in_surfaces_names = [[in_surfaces_names for _ in range(6)]]
#         if in_surfaces_masks is None:
#             in_surfaces_masks = [None]
#         elif isinstance(in_surfaces_masks, str):
#             in_surfaces_masks = [[in_surfaces_masks for _ in range(6)]]
#         if in_surfaces_map is None:
#             in_surfaces_map = [0 for _ in range(ni)]
#         elif isinstance(in_surfaces_map, int):
#             in_surfaces_map = [in_surfaces_map for _ in range(ni)]
#         if in_surfaces_masks_map is None:
#             in_surfaces_masks_map = [0 for _ in range(ni)]
#         elif isinstance(in_surfaces_masks_map, int):
#             in_surfaces_masks_map = [in_surfaces_masks_map for _ in range(ni)]
#         # inputs
#         if inputs is None:
#             inputs = []
#         elif not isinstance(inputs, list):
#             inputs = [inputs]
#         if inputs_map is None:
#             inputs_map = [0 for _ in range(ni)]
#         elif not isinstance(inputs_map, list):
#             inputs_map = [inputs_map for _ in range(ni)]
#         if inputs_transforms is None:
#             inputs_transforms = [[[0.5, 0.5, 0.5]]]  # center of the cell
#         if inputs_transforms_map is None:
#             inputs_transforms_map = [0 for _ in range(ni)]
#         elif not isinstance(inputs_transforms_map, list):
#             inputs_transforms_map = [inputs_transforms_map for _ in range(ni)]
#         if inputs_transforms_coord_sys is None:
#             inputs_transforms_coord_sys = ['local']
#         if inputs_transforms_coord_sys_map is None:
#             inputs_transforms_coord_sys_map = [0 for _ in range(ni)]
#         elif not isinstance(curve_data_coord_sys_map, list):
#             inputs_transforms_coord_sys_map = [
#                 inputs_transforms_coord_sys_map for _ in range(ni)]
#         # download inputs
#         inputs_datas = []
#         for i in inputs:
#             result = check_file(i)
#             with open(result['path']) as f:
#                 d = json.load(f)
#             inputs_datas.append(d)
#         # recombine
#         if recs_map is None:
#             recs_map = [1 for _ in range(ni)]
#         elif not isinstance(recs_map, list):
#             recs_map = [recs_map for _ in range(ni)]
#         # kws
#         if kws is None:
#             kws = [{}]
#         elif not isinstance(kws, list):
#             kws = [kws]
#         if kws_map is None:
#             kws_map = [0 for _ in range(ni)]
#         elif not isinstance(kws_map, list):
#             kws_map = [kws_map for _ in range(ni)]
#         # curve_types
#         curve_types = [None] if curve_types is None else curve_types
#         if curve_types_map is None:
#             curve_types_map = [0 for _ in range(ni)]
#         elif not isinstance(curve_types_map, list):
#             curve_types_map = [curve_types_map for _ in range(ni)]
#         # curve_data
#         curve_data = [None] if curve_data is None else curve_data
#         if curve_data_map is None:
#             curve_data_map = [0 for _ in range(ni)]
#         elif not isinstance(curve_data_map, list):
#             curve_data_map = [curve_data_map for _ in range(ni)]
#         if curve_data_coord_sys is None:
#             curve_data_coord_sys = ['local']
#         if curve_data_coord_sys_map is None:
#             curve_data_coord_sys_map = [0 for _ in range(ni)]
#         elif not isinstance(curve_data_coord_sys_map, list):
#             curve_data_coord_sys_map = [curve_data_coord_sys_map for _ in range(ni)]
#         # boolean
#         if boolean_level_map is None:
#             boolean_level_map = [0 for _ in range(ni)]
#         elif not isinstance(boolean_level_map, list):
#             boolean_level_map = [boolean_level_map for _ in range(ni)]
#         # boolean
#         if exists_map is None:
#             exists_map = [1 for _ in range(ni)]
#         elif not isinstance(exists_map, list):
#             exists_map = [exists_map for _ in range(ni)]
#         # Process
#         primitives = []
#         for ci, gi in l2g.items():
#             # t0 = time.time()
#             globals()[types[type_map[gi]]](**locals())
#             # print(f'type: {types[type_map[gi]]}, time {time.time() - t0}')
#         Complex.__init__(self, factory, primitives)
#
#     @staticmethod
#     def parse_indexing(cs, coordinates_type):
#         """
#         Parse coordinates indexing (xs, ys, zs) of 2 types:
#         1. start:end:number of steps
#         2. delta:number of steps
#         """
#         new_cs = []  # new coordinates
#         n2o = {}  # new to old local map
#         ni = 0  # new index
#         for oi, c in enumerate(cs):  # old index
#             if isinstance(c, (int, float)):
#                 new_cs.append(c)
#                 n2o[ni] = oi
#                 ni += 1
#             elif isinstance(c, str):
#                 vs = [float(x) for x in c.split(':')]  # values
#                 if len(vs) == 3:
#                     c0, c1, nc = vs  # start, end, number of steps
#                     dc = (c1 - c0) / nc
#                     if coordinates_type == 'direct':
#                         new_cs.append(c0)
#                         n2o[ni] = oi
#                         ni += 1
#                         for _ in range(int(nc)):
#                             new_cs.append(new_cs[ni - 1] + dc)
#                             n2o[ni] = oi
#                             ni += 1
#                     else:
#                         raise NotImplementedError(coordinates_type)
#                 elif len(vs) == 2:
#                     dc, nc = vs  # delta, number of steps
#                     if coordinates_type == 'delta':
#                         for _ in range(int(nc)):
#                             new_cs.append(dc)
#                             n2o[ni] = oi
#                             ni += 1
#                     else:
#                         raise NotImplementedError(coordinates_type)
#                 else:
#                     raise ValueError(c)
#         return new_cs, n2o
#
#
# # Empty
# def empty(**kwargs):
#     pass
#
#
# # Primitive
# def primitive(primitives, ci, gi, factory,
#               x0s, x1s, y0s, y1s, z0s, z1s, ts, txs, tys, tzs, lcs, lcs_map,
#               volumes_names, volumes_map, surfaces_names, surfaces_map,
#               transforms, transforms_map,
#               in_surfaces_names, in_surfaces_map,
#               in_surfaces_masks, in_surfaces_masks_map,
#               recs_map, trans_map, trans_type_map, transform_data,
#               curve_types, curve_types_map,
#               curve_data, curve_data_map,
#               curve_data_coord_sys, curve_data_coord_sys_map,
#               boolean_level_map, exists_map,
#               **kwargs):
#     # Primitive curves data
#     cd = copy.deepcopy(curve_data[curve_data_map[gi]])
#     cd_cs = curve_data_coord_sys[curve_data_coord_sys_map[gi]]
#     if cd is not None and cd_cs == 'local':  # local to global coordinates
#         for i, points in enumerate(cd):
#             for j, p in enumerate(points):  # [xj, yj, zj, lcj]
#                 cd[i][j][0] = x0s[gi] + cd[i][j][0]*(x1s[gi] - x0s[gi])
#                 cd[i][j][1] = y0s[gi] + cd[i][j][1]*(y1s[gi] - y0s[gi])
#                 cd[i][j][2] = z0s[gi] + cd[i][j][2]*(z1s[gi] - z0s[gi])
#     # Create Primitive
#     # TODO bug with cylinder curve_types [1, 1, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0]
#     xi, yi, zi = ci  # local coordinates by axes
#     primitives.append(Primitive(
#         factory=factory,
#         point_data=[
#             [x1s[gi], y1s[gi], z0s[gi], lcs[lcs_map[gi]]],
#             [x0s[gi], y1s[gi], z0s[gi], lcs[lcs_map[gi]]],
#             [x0s[gi], y0s[gi], z0s[gi], lcs[lcs_map[gi]]],
#             [x1s[gi], y0s[gi], z0s[gi], lcs[lcs_map[gi]]],
#             [x1s[gi], y1s[gi], z1s[gi], lcs[lcs_map[gi]]],
#             [x0s[gi], y1s[gi], z1s[gi], lcs[lcs_map[gi]]],
#             [x0s[gi], y0s[gi], z1s[gi], lcs[lcs_map[gi]]],
#             [x1s[gi], y0s[gi], z1s[gi], lcs[lcs_map[gi]]],
#         ],
#         transform_data=transform_data + transforms[transforms_map[gi]],
#         curve_types=curve_types[curve_types_map[gi]],
#         curve_data=cd,
#         transfinite_data=[ts[txs[xi]], ts[tys[yi]], ts[tzs[zi]]],
#         volume_name=volumes_names[volumes_map[gi]],
#         surfaces_names=surfaces_names[surfaces_map[gi]],
#         in_surfaces_names=in_surfaces_names[in_surfaces_map[gi]],
#         in_surfaces_mask=in_surfaces_masks[in_surfaces_masks_map[gi]],
#         rec=recs_map[gi],
#         trans=trans_map[gi],
#         transfinite_type=trans_type_map[gi],
#         boolean_level=boolean_level_map[gi],
#         exists=exists_map[gi]
#     ))
#
#
# # Complex
# def complex(primitives, gi, factory, transform_data,
#             x0s, x1s, y0s, y1s, z0s, z1s,
#             inputs_datas, inputs_map,
#             inputs_transforms, inputs_transforms_map,
#             inputs_transforms_coord_sys, inputs_transforms_coord_sys_map,
#             **kwargs):
#     # Complex transforms
#     in_ts = copy.deepcopy(inputs_transforms[inputs_transforms_map[gi]])
#     ts_cs = inputs_transforms_coord_sys[inputs_transforms_coord_sys_map[gi]]
#     for i, t in enumerate(in_ts):
#         if ts_cs == 'local':  # local to global coordinates
#             if len(t) == 3:  # Displacement
#                 in_ts[i][0] = x0s[gi] + t[0] * (x1s[gi] - x0s[gi])  # dx
#                 in_ts[i][1] = y0s[gi] + t[1] * (y1s[gi] - y0s[gi])  # dy
#                 in_ts[i][2] = z0s[gi] + t[2] * (z1s[gi] - z0s[gi])  # dz
#             elif len(t) == 7:  # Rotation with origin and direction
#                 in_ts[i][0] = x0s[gi] + t[0] * (x1s[gi] - x0s[gi])  # origin x
#                 in_ts[i][1] = y0s[gi] + t[1] * (y1s[gi] - y0s[gi])  # origin y
#                 in_ts[i][2] = z0s[gi] + t[2] * (z1s[gi] - z0s[gi])  # origin z
#             else:  # Rotation with direction only
#                 pass
#     # Complex input data
#     input_data = copy.deepcopy(inputs_datas[inputs_map[gi]])
#     if input_data['arguments'].get('transform_data', None) is None:
#         input_data['arguments']['transform_data'] = []
#     input_data['arguments']['transform_data'].extend(in_ts)
#     input_data['arguments']['transform_data'].extend(transform_data)
#     input_data['arguments']['factory'] = factory
#     # Create Complex
#     from complex_factory import ComplexFactory
#     c = ComplexFactory.new(input_data)
#     primitives.extend(c.primitives)
#
#
# # Complex in Primitive
# def complex_in_primitive(primitives, ci, gi, factory, transform_data,
#                          x0s, x1s, y0s, y1s, z0s, z1s,
#                          ts, txs, tys, tzs, lcs, lcs_map,
#                          volumes_names, volumes_map, surfaces_names,
#                          surfaces_map,
#                          in_surfaces_names, in_surfaces_map,
#                          in_surfaces_masks, in_surfaces_masks_map,
#                          recs_map, trans_map, inputs_datas, inputs_map,
#                          curve_types, curve_types_map,
#                          curve_data, curve_data_map,
#                          curve_data_coord_sys, curve_data_coord_sys_map,
#                          inputs_transforms, inputs_transforms_map,
#                          inputs_transforms_coord_sys,
#                          inputs_transforms_coord_sys_map,
#                          boolean_level_map, exists_map,
#                          **kwargs):
#     # Primitive curves data
#     cd = copy.deepcopy(curve_data[curve_data_map[gi]])
#     cd_cs = curve_data_coord_sys[curve_data_coord_sys_map[gi]]
#     if cd is not None and cd_cs == 'local':  # local to global coordinates
#         for i, points in enumerate(cd):
#             for j, p in enumerate(points):  # [xj, yj, zj, lcj]
#                 cd[i][j][0] = x0s[gi] + cd[i][j][0] * (x1s[gi] - x0s[gi])
#                 cd[i][j][1] = y0s[gi] + cd[i][j][1] * (y1s[gi] - y0s[gi])
#                 cd[i][j][2] = z0s[gi] + cd[i][j][2] * (z1s[gi] - z0s[gi])
#     # Complex transforms
#     c_ts = copy.deepcopy(inputs_transforms[inputs_transforms_map[gi]])
#     c_cs = inputs_transforms_coord_sys[inputs_transforms_coord_sys_map[gi]]
#     for i, t in enumerate(c_ts):
#         if c_cs == 'local':  # local to global coordinates
#             if len(t) == 3:  # Displacement
#                 c_ts[i][0] = x0s[gi] + t[0] * (x1s[gi] - x0s[gi])  # dx
#                 c_ts[i][1] = y0s[gi] + t[1] * (y1s[gi] - y0s[gi])  # dy
#                 c_ts[i][2] = z0s[gi] + t[2] * (z1s[gi] - z0s[gi])  # dz
#             elif len(t) == 7:  # Rotation with origin and direction
#                 c_ts[i][0] = x0s[gi] + t[0] * (x1s[gi] - x0s[gi])  # origin x
#                 c_ts[i][1] = y0s[gi] + t[1] * (y1s[gi] - y0s[gi])  # origin y
#                 c_ts[i][2] = z0s[gi] + t[2] * (z1s[gi] - z0s[gi])  # origin z
#             else:  # Rotation with direction only
#                 pass
#     # Complex input data
#     input_data = copy.deepcopy(inputs_datas[inputs_map[gi]])
#     if input_data['arguments'].get('transform_data', None) is None:
#         input_data['arguments']['transform_data'] = []
#     input_data['arguments']['transform_data'].extend(c_ts)
#     input_data['arguments']['transform_data'].extend(transform_data)
#     input_data['arguments']['factory'] = factory
#     # Create Complex
#     from complex_factory import ComplexFactory
#     c = ComplexFactory.new(input_data)
#     primitives.extend(c.primitives)
#     # Create Primitive
#     xi, yi, zi = ci  # local coordinates by axes
#     primitives.append(Primitive(
#         factory=factory,
#         point_data=[
#             [x1s[gi], y1s[gi], z0s[gi], lcs[lcs_map[gi]]],
#             [x0s[gi], y1s[gi], z0s[gi], lcs[lcs_map[gi]]],
#             [x0s[gi], y0s[gi], z0s[gi], lcs[lcs_map[gi]]],
#             [x1s[gi], y0s[gi], z0s[gi], lcs[lcs_map[gi]]],
#             [x1s[gi], y1s[gi], z1s[gi], lcs[lcs_map[gi]]],
#             [x0s[gi], y1s[gi], z1s[gi], lcs[lcs_map[gi]]],
#             [x0s[gi], y0s[gi], z1s[gi], lcs[lcs_map[gi]]],
#             [x1s[gi], y0s[gi], z1s[gi], lcs[lcs_map[gi]]],
#         ],
#         transform_data=transform_data,
#         transfinite_data=[ts[txs[xi]], ts[tys[yi]], ts[tzs[zi]]],
#         curve_types=curve_types[curve_types_map[gi]],
#         curve_data=cd,
#         volume_name=volumes_names[volumes_map[gi]],
#         inner_volumes=c.get_volumes(),
#         surfaces_names=surfaces_names[surfaces_map[gi]],
#         in_surfaces_names=in_surfaces_names[in_surfaces_map[gi]],
#         in_surfaces_mask=in_surfaces_masks[in_surfaces_masks_map[gi]],
#         rec=recs_map[gi],
#         trans=trans_map[gi],
#         boolean_level=boolean_level_map[gi],
#         exists=exists_map[gi]
#     ))
#
#
# # Complex and Primitive (for boolean)
# def complex_and_primitive(primitives, ci, gi, factory, transform_data,
#                           x0s, x1s, y0s, y1s, z0s, z1s,
#                           ts, txs, tys, tzs, lcs, lcs_map,
#                           volumes_names, volumes_map, surfaces_names,
#                           surfaces_map,
#                           in_surfaces_names, in_surfaces_map,
#                           in_surfaces_masks, in_surfaces_masks_map,
#                           recs_map, trans_map, inputs_datas, inputs_map,
#                           curve_types, curve_types_map,
#                           curve_data, curve_data_map,
#                           curve_data_coord_sys, curve_data_coord_sys_map,
#                           inputs_transforms, inputs_transforms_map,
#                           inputs_transforms_coord_sys,
#                           inputs_transforms_coord_sys_map,
#                           boolean_level_map, exists_map,
#                           **kwargs):
#     # Primitive curves data
#     cd = copy.deepcopy(curve_data[curve_data_map[gi]])
#     cd_cs = curve_data_coord_sys[curve_data_coord_sys_map[gi]]
#     if cd is not None and cd_cs == 'local':  # local to global coordinates
#         for i, points in enumerate(cd):
#             for j, p in enumerate(points):  # [xj, yj, zj, lcj]
#                 cd[i][j][0] = x0s[gi] + cd[i][j][0] * (x1s[gi] - x0s[gi])
#                 cd[i][j][1] = y0s[gi] + cd[i][j][1] * (y1s[gi] - y0s[gi])
#                 cd[i][j][2] = z0s[gi] + cd[i][j][2] * (z1s[gi] - z0s[gi])
#     # Complex transforms
#     in_ts = copy.deepcopy(inputs_transforms[inputs_transforms_map[gi]])
#     ts_cs = inputs_transforms_coord_sys[inputs_transforms_coord_sys_map[gi]]
#     for i, t in enumerate(in_ts):
#         if ts_cs == 'local':  # local to global coordinates
#             if len(t) == 3:  # Displacement
#                 in_ts[i][0] = x0s[gi] + t[0] * (x1s[gi] - x0s[gi])  # dx
#                 in_ts[i][1] = y0s[gi] + t[1] * (y1s[gi] - y0s[gi])  # dy
#                 in_ts[i][2] = z0s[gi] + t[2] * (z1s[gi] - z0s[gi])  # dz
#             elif len(t) == 7:  # Rotation with origin and direction
#                 in_ts[i][0] = x0s[gi] + t[0] * (x1s[gi] - x0s[gi])  # origin x
#                 in_ts[i][1] = y0s[gi] + t[1] * (y1s[gi] - y0s[gi])  # origin y
#                 in_ts[i][2] = z0s[gi] + t[2] * (z1s[gi] - z0s[gi])  # origin z
#             else:  # Rotation with direction only
#                 pass
#     # Complex input data
#     input_data = copy.deepcopy(inputs_datas[inputs_map[gi]])
#     if input_data['arguments'].get('transform_data', None) is None:
#         input_data['arguments']['transform_data'] = []
#     input_data['arguments']['transform_data'].extend(in_ts)
#     input_data['arguments']['transform_data'].extend(transform_data)
#     input_data['arguments']['factory'] = factory
#     # Create Complex
#     from complex_factory import ComplexFactory
#     c = ComplexFactory.new(input_data)
#     primitives.extend(c.primitives)
#     # Create Primitive
#     xi, yi, zi = ci  # local coordinates by axes
#     primitives.append(Primitive(
#         factory=factory,
#         point_data=[
#             [x1s[gi], y1s[gi], z0s[gi], lcs[lcs_map[gi]]],
#             [x0s[gi], y1s[gi], z0s[gi], lcs[lcs_map[gi]]],
#             [x0s[gi], y0s[gi], z0s[gi], lcs[lcs_map[gi]]],
#             [x1s[gi], y0s[gi], z0s[gi], lcs[lcs_map[gi]]],
#             [x1s[gi], y1s[gi], z1s[gi], lcs[lcs_map[gi]]],
#             [x0s[gi], y1s[gi], z1s[gi], lcs[lcs_map[gi]]],
#             [x0s[gi], y0s[gi], z1s[gi], lcs[lcs_map[gi]]],
#             [x1s[gi], y0s[gi], z1s[gi], lcs[lcs_map[gi]]],
#         ],
#         transform_data=transform_data,
#         transfinite_data=[ts[txs[xi]], ts[tys[yi]], ts[tzs[zi]]],
#         curve_types=curve_types[curve_types_map[gi]],
#         curve_data=cd,
#         volume_name=volumes_names[volumes_map[gi]],
#         surfaces_names=surfaces_names[surfaces_map[gi]],
#         in_surfaces_names=in_surfaces_names[in_surfaces_map[gi]],
#         in_surfaces_mask=in_surfaces_masks[in_surfaces_masks_map[gi]],
#         rec=recs_map[gi],
#         trans=trans_map[gi],
#         boolean_level=boolean_level_map[gi],
#         exists=exists_map[gi]
#     ))
#
#
# def axisymmetric_core(primitives, ci, gi, l2g, factory,
#                       x0s, x1s, y0s, y1s, z0s, z1s,
#                       ts, txs, tys, tzs, lcs, lcs_map,
#                       volumes_names, volumes_map, surfaces_names, surfaces_map,
#                       recs_map, trans_map, xs, ys, zs, transform_data,
#                       in_surfaces_names, in_surfaces_map,
#                       in_surfaces_masks, in_surfaces_masks_map,
#                       kws, kws_map, **kwargs):
#     # print(x0s)
#     # print(x1s)
#     i, j, k = ci
#     cxi, cyj = len(xs) // 2, len(ys) // 2
#     cx = sum(xs[:cxi]) + xs[cxi] / 2
#     cy = sum(ys[:cyj]) + ys[cyj] / 2
#     rx, rnx, ry, rny = x1s[gi] - cx, cx - x0s[gi], y1s[gi] - cy, cy - y0s[gi]
#     ct0 = kws[kws_map[gi]].get('ct0', 0)
#     # ct1 = kws[kws_map[gi]].get('ct1', 0)
#     ct = kws[kws_map[gi]].get('ct', 3)
#     # print(ct0)
#     if not ct0:  # straight
#         pd = [[x1s[gi], y1s[gi], z0s[gi], lcs[lcs_map[gi]]],
#               [x0s[gi], y1s[gi], z0s[gi], lcs[lcs_map[gi]]],
#               [x0s[gi], y0s[gi], z0s[gi], lcs[lcs_map[gi]]],
#               [x1s[gi], y0s[gi], z0s[gi], lcs[lcs_map[gi]]],
#               [x1s[gi], y1s[gi], z1s[gi], lcs[lcs_map[gi]]],
#               [x0s[gi], y1s[gi], z1s[gi], lcs[lcs_map[gi]]],
#               [x0s[gi], y0s[gi], z1s[gi], lcs[lcs_map[gi]]],
#               [x1s[gi], y0s[gi], z1s[gi], lcs[lcs_map[gi]]]]
#         cts = None
#         cd = None
#         # print(pd)
#     else:  # curved
#         dxrx = rx / 2 ** 0.5
#         dyry = ry / 2 ** 0.5
#         dxrnx = -rnx / 2 ** 0.5
#         dyrny = -rny / 2 ** 0.5
#         pd = [
#             [cx + dxrx, cy + dyry, z0s[gi], lcs[lcs_map[gi]]],
#             [cx + dxrnx, cy + dyry, z0s[gi], lcs[lcs_map[gi]]],
#             [cx + dxrnx, cy + dyrny, z0s[gi], lcs[lcs_map[gi]]],
#             [cx + dxrx, cy + dyrny, z0s[gi], lcs[lcs_map[gi]]],
#             [cx + dxrx, cy + dyry, z1s[gi], lcs[lcs_map[gi]]],
#             [cx + dxrnx, cy + dyry, z1s[gi], lcs[lcs_map[gi]]],
#             [cx + dxrnx, cy + dyrny, z1s[gi], lcs[lcs_map[gi]]],
#             [cx + dxrx, cy + dyrny, z1s[gi], lcs[lcs_map[gi]]],
#         ]
#         if np.allclose(rx, [ry, rnx, rny], atol=registry.point_tol, rtol=0):
#             cts = [ct0, ct0, ct0, ct0, ct0, ct0, ct0, ct0, 0, 0, 0, 0]
#             cd = [
#                 [[cx, cy, z0s[gi], lcs[lcs_map[gi]]]],
#                 [[cx, cy, z1s[gi], lcs[lcs_map[gi]]]],
#                 [[cx, cy, z1s[gi], lcs[lcs_map[gi]]]],
#                 [[cx, cy, z0s[gi], lcs[lcs_map[gi]]]],
#                 [[cx, cy, z0s[gi], lcs[lcs_map[gi]]]],
#                 [[cx, cy, z0s[gi], lcs[lcs_map[gi]]]],
#                 [[cx, cy, z1s[gi], lcs[lcs_map[gi]]]],
#                 [[cx, cy, z1s[gi], lcs[lcs_map[gi]]]],
#                 [], [], [], []
#             ]
#         else:
#             cts = [ct, ct, ct, ct, ct, ct, ct, ct, 0, 0, 0, 0]
#             cd = [
#                 [[cx, cy + ry, z0s[gi], lcs[lcs_map[gi]]]],
#                 [[cx, cy + ry, z1s[gi], lcs[lcs_map[gi]]]],
#                 [[cx, cy - rny, z1s[gi], lcs[lcs_map[gi]]]],
#                 [[cx, cy - rny, z0s[gi], lcs[lcs_map[gi]]]],
#                 [[cx + rx, cy, z0s[gi], lcs[lcs_map[gi]]]],
#                 [[cx - rnx, cy, z0s[gi], lcs[lcs_map[gi]]]],
#                 [[cx - rnx, cy, z1s[gi], lcs[lcs_map[gi]]]],
#                 [[cx + rx, cy, z1s[gi], lcs[lcs_map[gi]]]],
#                 [], [], [], []
#             ]
#     primitives.append(Primitive(
#         factory=factory,
#         point_data=pd,
#         transform_data=transform_data,
#         curve_types=cts,
#         curve_data=cd,
#         transfinite_data=[ts[txs[i]], ts[tys[j]], ts[tzs[k]]],
#         transfinite_type=2,
#         volume_name=volumes_names[volumes_map[gi]],
#         surfaces_names=surfaces_names[surfaces_map[gi]],
#         in_surfaces_names=in_surfaces_names[in_surfaces_map[gi]],
#         in_surfaces_mask=in_surfaces_masks[in_surfaces_masks_map[gi]],
#         rec=recs_map[gi],
#         trans=trans_map[gi]
#     ))
#
#
# def axisymmetric_x(primitives, ci, gi, l2g, factory,
#                    x0s, x1s, y0s, y1s, z0s, z1s,
#                    ts, txs, tys, tzs, lcs, lcs_map,
#                    volumes_names, volumes_map, surfaces_names, surfaces_map,
#                    in_surfaces_names, in_surfaces_map,
#                    in_surfaces_masks, in_surfaces_masks_map,
#                    recs_map, trans_map, xs, ys, zs, transform_data,
#                    kws, kws_map, **kwargs):
#     i, j, k = ci
#     cxi, cyj = len(xs) // 2, len(ys) // 2  # center indices
#     cx = sum(xs[:cxi]) + xs[cxi] / 2  # center x
#     cy = sum(ys[:cyj]) + ys[cyj] / 2  # center y
#     giy0, giy1 = l2g[(i, j - (i - cxi), k)], l2g[(i, j + (i - cxi), k)]
#     r0, r1 = abs(x0s[gi] - cx), abs(x1s[gi] - cx)  # inner and outer radii
#     r1y0, r1y1 = abs(y0s[giy0] - cy), abs(y1s[giy1] - cy)
#     r0y0, r0y1 = abs(y1s[giy0] - cy), abs(y0s[giy1] - cy)
#     ct0 = kws[kws_map[gi]].get('ct0', 0)
#     ct1 = kws[kws_map[gi]].get('ct1', 0)
#     ct = kws[kws_map[gi]].get('ct', 3)
#     dr1_z0 = kws[kws_map[gi]].get('dr1_z0', 0)
#     dxr1_z0 = dr1_z0 / 2 ** 0.5
#     if ct1 and ct0:
#         dxr1 = r1 / 2 ** 0.5
#         dxr0 = r0 / 2 ** 0.5
#         dyr1y1 = r1y1 / 2 ** 0.5
#         dyr1y0 = -r1y0 / 2 ** 0.5
#         dyr0y1 = r0y1 / 2 ** 0.5
#         dyr0y0 = -r0y0 / 2 ** 0.5
#     elif ct0:
#         dxr1 = r1
#         dxr0 = r0 / 2 ** 0.5
#         dyr1y1 = r1y1
#         dyr1y0 = -r1y0
#         dyr0y1 = r0y1 / 2 ** 0.5
#         dyr0y0 = -r0y0 / 2 ** 0.5
#     elif ct1:
#         dxr1 = r1 / 2 ** 0.5
#         dxr0 = r0
#         dyr1y1 = r1y1 / 2 ** 0.5
#         dyr1y0 = -r1y0 / 2 ** 0.5
#         dyr0y1 = r0y1
#         dyr0y0 = -r0y0
#     else:
#         dxr1 = r1
#         dxr0 = r0
#         dyr1y1 = r1y1
#         dyr1y0 = -r1y0
#         dyr0y1 = r0y1
#         dyr0y0 = -r0y0
#     pd = [
#         [cx + dxr1 + dxr1_z0, cy + dyr1y1 + dxr1_z0, z0s[gi], lcs[lcs_map[gi]]],
#         [cx + dxr0, cy + dyr0y1, z0s[gi], lcs[lcs_map[gi]]],
#         [cx + dxr0, cy + dyr0y0, z0s[gi], lcs[lcs_map[gi]]],
#         [cx + dxr1 + dxr1_z0, cy + dyr1y0 - dxr1_z0, z0s[gi], lcs[lcs_map[gi]]],
#         [cx + dxr1, cy + dyr1y1, z1s[gi], lcs[lcs_map[gi]]],
#         [cx + dxr0, cy + dyr0y1, z1s[gi], lcs[lcs_map[gi]]],
#         [cx + dxr0, cy + dyr0y0, z1s[gi], lcs[lcs_map[gi]]],
#         [cx + dxr1, cy + dyr1y0, z1s[gi], lcs[lcs_map[gi]]]
#     ]
#     r0_equal = np.allclose(r0, [r0y1, r0y0], atol=registry.point_tol, rtol=0)
#     r1_equal = np.allclose(r1, [r1y1, r1y0], atol=registry.point_tol, rtol=0)
#     if r0_equal and r1_equal:
#         cts = [0, 0, 0, 0, ct1, ct0, ct0, ct1,
#                1 if dxr1_z0 != 0 else 0, 0, 0, 1 if dxr1_z0 != 0 else 0]
#         cd = [
#             [], [], [], [],
#             [[cx, cy, z0s[gi], lcs[lcs_map[gi]]]],
#             [[cx, cy, z0s[gi], lcs[lcs_map[gi]]]],
#             [[cx, cy, z1s[gi], lcs[lcs_map[gi]]]],
#             [[cx, cy, z1s[gi], lcs[lcs_map[gi]]]],
#             [[cx + dxr1 + dxr1_z0, cy + dyr1y1 + dxr1_z0, z1s[gi], lcs[lcs_map[gi]]]],
#             [],
#             [],
#             [[cx + dxr1 + dxr1_z0, cy + dyr1y0 - dxr1_z0, z1s[gi], lcs[lcs_map[gi]]]]
#         ]
#     elif r1_equal:
#         cts = [0, 0, 0, 0, ct1, ct * ct0, ct * ct0, ct1, 0, 0, 0, 0]
#         cd = [
#             [], [], [], [],
#             [[cx, cy, z0s[gi], lcs[lcs_map[gi]]]],
#             [[x0s[gi], cy, z0s[gi], lcs[lcs_map[gi]]]],
#             [[x0s[gi], cy, z1s[gi], lcs[lcs_map[gi]]]],
#             [[cx, cy, z1s[gi], lcs[lcs_map[gi]]]],
#             [], [], [], []
#         ]
#     elif r0_equal:
#         cts = [0, 0, 0, 0, ct * ct1, ct0, ct0, ct * ct1, 0, 0, 0, 0]
#         cd = [
#             [], [], [], [],
#             [[x1s[gi], cy, z0s[gi], lcs[lcs_map[gi]]]],
#             [[cx, cy, z0s[gi], lcs[lcs_map[gi]]]],
#             [[cx, cy, z1s[gi], lcs[lcs_map[gi]]]],
#             [[x1s[gi], cy, z1s[gi], lcs[lcs_map[gi]]]],
#             [], [], [], []
#         ]
#     else:
#         cts = [0, 0, 0, 0, ct * ct1, ct * ct0, ct * ct0, ct * ct1, 0, 0, 0, 0]
#         cd = [
#             [], [], [], [],
#             [[x1s[gi], cy, z0s[gi], lcs[lcs_map[gi]]]],
#             [[x0s[gi], cy, z0s[gi], lcs[lcs_map[gi]]]],
#             [[x0s[gi], cy, z1s[gi], lcs[lcs_map[gi]]]],
#             [[x1s[gi], cy, z1s[gi], lcs[lcs_map[gi]]]],
#             [], [], [], []
#         ]
#     primitives.append(Primitive(
#         factory=factory,
#         point_data=pd,
#         transform_data=transform_data,
#         curve_types=cts,
#         curve_data=cd,
#         transfinite_data=[ts[txs[i]], ts[tys[j]], ts[tzs[k]]],
#         transfinite_type=3,
#         volume_name=volumes_names[volumes_map[gi]],
#         surfaces_names=surfaces_names[surfaces_map[gi]],
#         in_surfaces_names=in_surfaces_names[in_surfaces_map[gi]],
#         in_surfaces_mask=in_surfaces_masks[in_surfaces_masks_map[gi]],
#         rec=recs_map[gi],
#         trans=trans_map[gi]
#     ))
#
#
# def axisymmetric_y(primitives, ci, gi, l2g, factory,
#                    x0s, x1s, y0s, y1s, z0s, z1s,
#                    ts, txs, tys, tzs, lcs, lcs_map,
#                    volumes_names, volumes_map, surfaces_names, surfaces_map,
#                    in_surfaces_names, in_surfaces_map,
#                    in_surfaces_masks, in_surfaces_masks_map,
#                    recs_map, trans_map, xs, ys, zs, transform_data,
#                    kws, kws_map, **kwargs):
#     i, j, k = ci
#     cxi, cyj = len(xs) // 2, len(ys) // 2
#     cx = sum(xs[:cxi]) + xs[cxi] / 2
#     cy = sum(ys[:cyj]) + ys[cyj] / 2
#     gix0, gix1 = l2g[(i - (j - cyj), j, k)], l2g[(i + (j - cyj), j, k)]
#     r0, r1 = abs(y0s[gi] - cy), abs(y1s[gi] - cy)
#     r1x0, r1x1 = abs(x0s[gix0] - cx), abs(x1s[gix1] - cx)
#     r0x0, r0x1 = abs(x1s[gix0] - cx), abs(x0s[gix1] - cx)
#     ct0 = kws[kws_map[gi]].get('ct0', 0)
#     ct1 = kws[kws_map[gi]].get('ct1', 0)
#     ct = kws[kws_map[gi]].get('ct', 3)
#     dr1_z0 = kws[kws_map[gi]].get('dr1_z0', 0)
#     dyr1_z0 = dr1_z0 / 2 ** 0.5
#     if ct1 and ct0:
#         dyr1 = r1 / 2 ** 0.5
#         dyr0 = r0 / 2 ** 0.5
#         dxr1x1 = r1x1 / 2 ** 0.5
#         dxr1x0 = -r1x0 / 2 ** 0.5
#         dxr0x1 = r0x1 / 2 ** 0.5
#         dxr0x0 = -r0x0 / 2 ** 0.5
#     elif ct0:
#         dyr1 = r1
#         dyr0 = r0 / 2 ** 0.5
#         dxr1x1 = r1x1
#         dxr1x0 = -r1x0
#         dxr0x1 = r0x1 / 2 ** 0.5
#         dxr0x0 = -r0x0 / 2 ** 0.5
#     elif ct1:
#         dyr1 = r1 / 2 ** 0.5
#         dyr0 = r0
#         dxr1x1 = r1x1 / 2 ** 0.5
#         dxr1x0 = -r1x0 / 2 ** 0.5
#         dxr0x1 = r0x1
#         dxr0x0 = -r0x0
#     else:
#         dyr1 = r1
#         dyr0 = r0
#         dxr1x1 = r1x1
#         dxr1x0 = -r1x0
#         dxr0x1 = r0x1
#         dxr0x0 = -r0x0
#     pd = [
#         [cx + dxr1x1 + dyr1_z0, cy + dyr1 + dyr1_z0, z0s[gi], lcs[lcs_map[gi]]],
#         [cx + dxr1x0 - dyr1_z0, cy + dyr1 + dyr1_z0, z0s[gi], lcs[lcs_map[gi]]],
#         [cx + dxr0x0, cy + dyr0, z0s[gi], lcs[lcs_map[gi]]],
#         [cx + dxr0x1, cy + dyr0, z0s[gi], lcs[lcs_map[gi]]],
#         [cx + dxr1x1, cy + dyr1, z1s[gi], lcs[lcs_map[gi]]],
#         [cx + dxr1x0, cy + dyr1, z1s[gi], lcs[lcs_map[gi]]],
#         [cx + dxr0x0, cy + dyr0, z1s[gi], lcs[lcs_map[gi]]],
#         [cx + dxr0x1, cy + dyr0, z1s[gi], lcs[lcs_map[gi]]]
#     ]
#     r0_equal = np.allclose(r0, [r0x1, r0x0], atol=registry.point_tol, rtol=0)
#     r1_equal = np.allclose(r1, [r1x1, r1x0], atol=registry.point_tol, rtol=0)
#     if r1_equal and r0_equal:
#         cts = [ct1, ct1, ct0, ct0, 0, 0, 0, 0,
#                1 if dyr1_z0 != 0 else 0, 1 if dyr1_z0 != 0 else 0, 0, 0]
#         cd = [
#             [[cx, cy, z0s[gi], lcs[lcs_map[gi]]]],
#             [[cx, cy, z1s[gi], lcs[lcs_map[gi]]]],
#             [[cx, cy, z1s[gi], lcs[lcs_map[gi]]]],
#             [[cx, cy, z0s[gi], lcs[lcs_map[gi]]]],
#             [], [], [], [],
#             [[cx + dxr1x1 + dyr1_z0, cy + dyr1 + dyr1_z0, z1s[gi], lcs[lcs_map[gi]]]],
#             [[cx + dxr1x0 - dyr1_z0, cy + dyr1 + dyr1_z0, z1s[gi], lcs[lcs_map[gi]]]],
#             [], []
#         ]
#     elif r1_equal:
#         cts = [ct1, ct1, ct * ct0, ct * ct0, 0, 0, 0, 0, 0, 0, 0, 0]
#         cd = [
#             [[cx, cy, z0s[gi], lcs[lcs_map[gi]]]],
#             [[cx, cy, z1s[gi], lcs[lcs_map[gi]]]],
#             [[cx, y0s[gi], z1s[gi], lcs[lcs_map[gi]]]],
#             [[cx, y0s[gi], z0s[gi], lcs[lcs_map[gi]]]],
#             [], [], [], []
#         ]
#     elif r0_equal:
#         cts = [ct * ct1, ct * ct1, ct0, ct0, 0, 0, 0, 0, 0, 0, 0, 0]
#         cd = [
#             [[cx, y1s[gi], z0s[gi], lcs[lcs_map[gi]]]],
#             [[cx, y1s[gi], z1s[gi], lcs[lcs_map[gi]]]],
#             [[cx, cy, z1s[gi], lcs[lcs_map[gi]]]],
#             [[cx, cy, z0s[gi], lcs[lcs_map[gi]]]],
#             [], [], [], [],
#             [], [], [], []
#         ]
#     else:
#         cts = [ct * ct1, ct * ct1, ct * ct0, ct * ct0, 0, 0, 0, 0, 0, 0, 0, 0]
#         cd = [
#             [[cx, y1s[gi], z0s[gi], lcs[lcs_map[gi]]]],
#             [[cx, y1s[gi], z1s[gi], lcs[lcs_map[gi]]]],
#             [[cx, y0s[gi], z1s[gi], lcs[lcs_map[gi]]]],
#             [[cx, y0s[gi], z0s[gi], lcs[lcs_map[gi]]]],
#             [], [], [], [],
#             [], [], [], []
#         ]
#     primitives.append(Primitive(
#         factory=factory,
#         point_data=pd,
#         transform_data=transform_data,
#         curve_types=cts,
#         curve_data=cd,
#         transfinite_data=[ts[txs[i]], ts[tys[j]], ts[tzs[k]]],
#         transfinite_type=1,
#         volume_name=volumes_names[volumes_map[gi]],
#         surfaces_names=surfaces_names[surfaces_map[gi]],
#         in_surfaces_names=in_surfaces_names[in_surfaces_map[gi]],
#         in_surfaces_mask=in_surfaces_masks[in_surfaces_masks_map[gi]],
#         rec=recs_map[gi],
#         trans=trans_map[gi]
#     ))
#
#
# def axisymmetric_nx(primitives, ci, gi, l2g, factory,
#                    x0s, x1s, y0s, y1s, z0s, z1s,
#                    ts, txs, tys, tzs, lcs, lcs_map,
#                    volumes_names, volumes_map, surfaces_names, surfaces_map,
#                    in_surfaces_names, in_surfaces_map,
#                    in_surfaces_masks, in_surfaces_masks_map,
#                    recs_map, trans_map, xs, ys, zs, transform_data,
#                    kws, kws_map, **kwargs):
#     i, j, k = ci
#     cxi, cyj = len(xs) // 2, len(ys) // 2
#     cx = sum(xs[:cxi]) + xs[cxi] / 2
#     cy = sum(ys[:cyj]) + ys[cyj] / 2
#     giy0, giy1 = l2g[(i, j - (cxi - i), k)], l2g[(i, j + (cxi - i), k)]
#     r0, r1 = abs(x1s[gi] - cx), abs(x0s[gi] - cx)
#     r1y0, r1y1 = abs(y0s[giy0] - cy), abs(y1s[giy1] - cy)
#     r0y0, r0y1 = abs(y1s[giy0] - cy), abs(y0s[giy1] - cy)
#     ct0 = kws[kws_map[gi]].get('ct0', 0)
#     ct1 = kws[kws_map[gi]].get('ct1', 0)
#     ct = kws[kws_map[gi]].get('ct', 3)
#     dr1_z0 = kws[kws_map[gi]].get('dr1_z0', 0)
#     dxr1_z0 = dr1_z0 / 2 ** 0.5
#     if ct1 and ct0:
#         dxr1 = -r1 / 2 ** 0.5
#         dxr0 = -r0 / 2 ** 0.5
#         dyr1y1 = r1y1 / 2 ** 0.5
#         dyr1y0 = -r1y0 / 2 ** 0.5
#         dyr0y1 = r0y1 / 2 ** 0.5
#         dyr0y0 = -r0y0 / 2 ** 0.5
#     elif ct0:
#         dxr1 = -r1
#         dxr0 = -r0 / 2 ** 0.5
#         dyr1y1 = r1y1
#         dyr1y0 = -r1y0
#         dyr0y1 = r0y1 / 2 ** 0.5
#         dyr0y0 = -r0y0 / 2 ** 0.5
#     elif ct1:
#         dxr1 = -r1 / 2 ** 0.5
#         dxr0 = -r0
#         dyr1y1 = r1y1 / 2 ** 0.5
#         dyr1y0 = -r1y0 / 2 ** 0.5
#         dyr0y1 = r0y1
#         dyr0y0 = -r0y0
#     else:
#         dxr1 = -r1
#         dxr0 = -r0
#         dyr1y1 = r1y1
#         dyr1y0 = -r1y0
#         dyr0y1 = r0y1
#         dyr0y0 = -r0y0
#     pd = [
#         [cx + dxr0, cy + dyr0y1, z0s[gi], lcs[lcs_map[gi]]],
#         [cx + dxr1 - dxr1_z0, cy + dyr1y1 + dxr1_z0, z0s[gi], lcs[lcs_map[gi]]],
#         [cx + dxr1 - dxr1_z0, cy + dyr1y0 - dxr1_z0, z0s[gi], lcs[lcs_map[gi]]],
#         [cx + dxr0, cy + dyr0y0, z0s[gi], lcs[lcs_map[gi]]],
#         [cx + dxr0, cy + dyr0y1, z1s[gi], lcs[lcs_map[gi]]],
#         [cx + dxr1, cy + dyr1y1, z1s[gi], lcs[lcs_map[gi]]],
#         [cx + dxr1, cy + dyr1y0, z1s[gi], lcs[lcs_map[gi]]],
#         [cx + dxr0, cy + dyr0y0, z1s[gi], lcs[lcs_map[gi]]]
#     ]
#     r0_equal = np.allclose(r0, [r0y1, r0y0], atol=registry.point_tol, rtol=0)
#     r1_equal = np.allclose(r1, [r1y1, r1y0], atol=registry.point_tol, rtol=0)
#     if r1_equal and r0_equal:
#         cts = [0, 0, 0, 0, ct0, ct1, ct1, ct0,
#                0, 1 if dxr1_z0 != 0 else 0, 1 if dxr1_z0 != 0 else 0, 0]
#         cd = [
#             [], [], [], [],
#             [[cx, cy, z0s[gi], lcs[lcs_map[gi]]]],
#             [[cx, cy, z0s[gi], lcs[lcs_map[gi]]]],
#             [[cx, cy, z1s[gi], lcs[lcs_map[gi]]]],
#             [[cx, cy, z1s[gi], lcs[lcs_map[gi]]]],
#             [],
#             [[cx + dxr1 - dxr1_z0, cy + dyr1y1 + dxr1_z0, z1s[gi], lcs[lcs_map[gi]]]],
#             [[cx + dxr1 - dxr1_z0, cy + dyr1y0 - dxr1_z0, z1s[gi], lcs[lcs_map[gi]]]],
#             []
#         ]
#     elif r1_equal:
#         cts = [0, 0, 0, 0, ct * ct0, ct1, ct1, ct * ct0, 0, 0, 0, 0]
#         cd = [
#             [], [], [], [],
#             [[x1s[gi], cy, z0s[gi], lcs[lcs_map[gi]]]],
#             [[cx, cy, z0s[gi], lcs[lcs_map[gi]]]],
#             [[cx, cy, z1s[gi], lcs[lcs_map[gi]]]],
#             [[x1s[gi], cy, z1s[gi], lcs[lcs_map[gi]]]],
#             [], [], [], []
#         ]
#     elif r0_equal:
#         cts = [0, 0, 0, 0, ct0, ct * ct1, ct * ct1, ct0, 0, 0, 0, 0]
#         cd = [
#             [], [], [], [],
#             [[cx, cy, z0s[gi], lcs[lcs_map[gi]]]],
#             [[x0s[gi], cy, z0s[gi], lcs[lcs_map[gi]]]],
#             [[x0s[gi], cy, z1s[gi], lcs[lcs_map[gi]]]],
#             [[cx, cy, z1s[gi], lcs[lcs_map[gi]]]],
#             [], [], [], []
#         ]
#     else:
#         cts = [0, 0, 0, 0, ct * ct0, ct * ct1, ct * ct1, ct * ct0, 0, 0, 0, 0]
#         cd = [
#             [], [], [], [],
#             [[x1s[gi], cy, z0s[gi], lcs[lcs_map[gi]]]],
#             [[x0s[gi], cy, z0s[gi], lcs[lcs_map[gi]]]],
#             [[x0s[gi], cy, z1s[gi], lcs[lcs_map[gi]]]],
#             [[x1s[gi], cy, z1s[gi], lcs[lcs_map[gi]]]],
#             [], [], [], []
#         ]
#     primitives.append(Primitive(
#         factory=factory,
#         point_data=pd,
#         transform_data=transform_data,
#         curve_types=cts,
#         curve_data=cd,
#         transfinite_data=[ts[txs[i]], ts[tys[j]], ts[tzs[k]]],
#         transfinite_type=2,
#         volume_name=volumes_names[volumes_map[gi]],
#         surfaces_names=surfaces_names[surfaces_map[gi]],
#         in_surfaces_names=in_surfaces_names[in_surfaces_map[gi]],
#         in_surfaces_mask=in_surfaces_masks[in_surfaces_masks_map[gi]],
#         rec=recs_map[gi],
#         trans=trans_map[gi]
#     ))
#
#
# def axisymmetric_ny(primitives, ci, gi, l2g, factory,
#                     x0s, x1s, y0s, y1s, z0s, z1s,
#                     ts, txs, tys, tzs, lcs, lcs_map,
#                     volumes_names, volumes_map, surfaces_names, surfaces_map,
#                     in_surfaces_names, in_surfaces_map,
#                     in_surfaces_masks, in_surfaces_masks_map,
#                     recs_map, trans_map, xs, ys, zs, transform_data,
#                     kws, kws_map, **kwargs):
#     i, j, k = ci
#     cxi, cyj = len(xs) // 2, len(ys) // 2
#     cx = sum(xs[:cxi]) + xs[cxi] / 2
#     cy = sum(ys[:cyj]) + ys[cyj] / 2
#     gix0, gix1 = l2g[(i - (cyj - j), j, k)], l2g[(i + (cyj - j), j, k)]
#     r0, r1 = abs(y1s[gi] - cy), abs(y0s[gi] - cy)
#     r1x0, r1x1 = abs(x0s[gix0] - cx), abs(x1s[gix1] - cx)
#     r0x0, r0x1 = abs(x1s[gix0] - cx), abs(x0s[gix1] - cx)
#     ct0 = kws[kws_map[gi]].get('ct0', 0)
#     ct1 = kws[kws_map[gi]].get('ct1', 0)
#     ct = kws[kws_map[gi]].get('ct', 3)
#     dr1_z0 = kws[kws_map[gi]].get('dr1_z0', 0)
#     dyr1_z0 = dr1_z0 / 2 ** 0.5
#     if ct1 and ct0:
#         dyr1 = -r1 / 2 ** 0.5
#         dyr0 = -r0 / 2 ** 0.5
#         dxr1x1 = r1x1 / 2 ** 0.5
#         dxr1x0 = -r1x0 / 2 ** 0.5
#         dxr0x1 = r0x1 / 2 ** 0.5
#         dxr0x0 = -r0x0 / 2 ** 0.5
#     elif ct0:
#         dyr1 = -r1
#         dyr0 = -r0 / 2 ** 0.5
#         dxr1x1 = r1x1
#         dxr1x0 = -r1x0
#         dxr0x1 = r0x1 / 2 ** 0.5
#         dxr0x0 = -r0x0 / 2 ** 0.5
#     elif ct1:
#         dyr1 = -r1 / 2 ** 0.5
#         dyr0 = -r0
#         dxr1x1 = r1x1 / 2 ** 0.5
#         dxr1x0 = -r1x0 / 2 ** 0.5
#         dxr0x1 = r0x1
#         dxr0x0 = -r0x0
#     else:
#         dyr1 = -r1
#         dyr0 = -r0
#         dxr1x1 = r1x1
#         dxr1x0 = -r1x0
#         dxr0x1 = r0x1
#         dxr0x0 = -r0x0
#     pd = [
#         [cx + dxr0x1, cy + dyr0, z0s[gi], lcs[lcs_map[gi]]],
#         [cx + dxr0x0, cy + dyr0, z0s[gi], lcs[lcs_map[gi]]],
#         [cx + dxr1x0 - dyr1_z0, cy + dyr1 - dyr1_z0, z0s[gi], lcs[lcs_map[gi]]],
#         [cx + dxr1x1 + dyr1_z0, cy + dyr1 - dyr1_z0, z0s[gi], lcs[lcs_map[gi]]],
#         [cx + dxr0x1, cy + dyr0, z1s[gi], lcs[lcs_map[gi]]],
#         [cx + dxr0x0, cy + dyr0, z1s[gi], lcs[lcs_map[gi]]],
#         [cx + dxr1x0, cy + dyr1, z1s[gi], lcs[lcs_map[gi]]],
#         [cx + dxr1x1, cy + dyr1, z1s[gi], lcs[lcs_map[gi]]]
#     ]
#     r0_equal = np.allclose(r0, [r0x1, r0x0], atol=registry.point_tol, rtol=0)
#     r1_equal = np.allclose(r1, [r1x1, r1x0], atol=registry.point_tol, rtol=0)
#     if r1_equal and r0_equal:
#         cts = [ct0, ct0, ct1, ct1, 0, 0, 0, 0,
#                0, 0, 1 if dyr1_z0 != 0 else 0, 1 if dyr1_z0 != 0 else 0]
#         cd = [
#             [[cx, cy, z0s[gi], lcs[lcs_map[gi]]]],
#             [[cx, cy, z1s[gi], lcs[lcs_map[gi]]]],
#             [[cx, cy, z1s[gi], lcs[lcs_map[gi]]]],
#             [[cx, cy, z0s[gi], lcs[lcs_map[gi]]]],
#             [], [], [], [],
#             [], [],
#             [[cx + dxr1x0 - dyr1_z0, cy + dyr1 - dyr1_z0, z1s[gi], lcs[lcs_map[gi]]]],
#             [[cx + dxr1x1 + dyr1_z0, cy + dyr1 - dyr1_z0, z1s[gi], lcs[lcs_map[gi]]]]
#         ]
#     elif r1_equal:
#         cts = [ct * ct0, ct * ct0, ct1, ct1, 0, 0, 0, 0, 0, 0, 0, 0]
#         cd = [
#             [[cx, y1s[gi], z0s[gi], lcs[lcs_map[gi]]]],
#             [[cx, y1s[gi], z1s[gi], lcs[lcs_map[gi]]]],
#             [[cx, cy, z1s[gi], lcs[lcs_map[gi]]]],
#             [[cx, cy, z0s[gi], lcs[lcs_map[gi]]]],
#             [], [], [], []
#         ]
#     elif r0_equal:
#         cts = [ct0, ct0, ct * ct1, ct * ct1, 0, 0, 0, 0, 0, 0, 0, 0]
#         cd = [
#             [[cx, cy, z0s[gi], lcs[lcs_map[gi]]]],
#             [[cx, cy, z1s[gi], lcs[lcs_map[gi]]]],
#             [[cx, y0s[gi], z1s[gi], lcs[lcs_map[gi]]]],
#             [[cx, y0s[gi], z0s[gi], lcs[lcs_map[gi]]]],
#             [], [], [], [],
#             [], [], [], []
#         ]
#     else:
#         cts = [ct * ct0, ct * ct0, ct * ct1, ct * ct1, 0, 0, 0, 0, 0, 0, 0, 0]
#         cd = [
#             [[cx, y1s[gi], z0s[gi], lcs[lcs_map[gi]]]],
#             [[cx, y1s[gi], z1s[gi], lcs[lcs_map[gi]]]],
#             [[cx, y0s[gi], z1s[gi], lcs[lcs_map[gi]]]],
#             [[cx, y0s[gi], z0s[gi], lcs[lcs_map[gi]]]],
#             [], [], [], [],
#             [], [], [], []
#         ]
#     primitives.append(Primitive(
#         factory=factory,
#         point_data=pd,
#         transform_data=transform_data,
#         curve_types=cts,
#         curve_data=cd,
#         transfinite_data=[ts[txs[i]], ts[tys[j]], ts[tzs[k]]],
#         transfinite_type=2,
#         volume_name=volumes_names[volumes_map[gi]],
#         surfaces_names=surfaces_names[surfaces_map[gi]],
#         in_surfaces_names=in_surfaces_names[in_surfaces_map[gi]],
#         in_surfaces_mask=in_surfaces_masks[in_surfaces_masks_map[gi]],
#         rec=recs_map[gi],
#         trans=trans_map[gi]
#     ))
