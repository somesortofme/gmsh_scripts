import logging
from pathlib import Path

import numpy as np

from support import volumes_surfaces_to_volumes_groups_surfaces
from transform import str2obj as transform_factory
from transform import BlockToCartesian
from transform import reduce_transforms
from registry import register_point, register_curve, register_curve_loop, \
    register_surface, register_surface_loop, register_volume, \
    register_curve_structure, register_surface_structure, \
    register_surface_quadrate, register_volume_structure, unregister_volume
from coordinate_system import Block as BlockCS
from point import Point
from curve import Curve
from curve_loop import CurveLoop
from surface import Surface
from surface_loop import SurfaceLoop
from volume import Volume
from structure import Structure
from quadrate import Quadrate


class Block:
    """Basic building block of the mesh

    Block is a cuboid with 8 points, 12 curves, 6 surfaces and 1 volume.

    | **Axes**
    | Y
    | Z X
    | NX, NY and NZ are negative X, Y and Z directions

    | **Points**
    | NZ:
    | P1 P0
    | P2 P3
    | Z:
    | P5 P4
    | P6 P7

    | **Curves**
    | X direction curves from P0 by right-hand rule:
    | C0: P1 -> P0
    | C1: P5 -> P4
    | C2: P6 -> P7
    | C3: P2 -> P3
    | Y direction curves from P0 by right-hand rule:
    | C4: P3 -> P0
    | C5: P2 -> P1
    | C6: P6 -> P5
    | C7: P7 -> P4
    | Z direction curves from P0 by right-hand rule:
    | C8:  P0 -> P4
    | C9:  P1 -> P5
    | C10: P2 -> P6
    | C11: P3 -> P7

    | **Surfaces**
    | NX surface
    | S0: C5  -> C9  -> -C6 -> -C10
    | X surface
    | S1: -C4 -> C11 -> C7  -> -C8
    | NY surface
    | S2: -C3 -> C10 -> C2  -> -C11
    | Y surface
    | S3: C0  -> C8  -> -C1 -> -C9
    | NZ surface
    | S4: -C0 -> -C5 ->  C3 -> C4
    | Z surface
    | S5: C1  -> -C7 -> -C2 -> C6

    Note:
        If boolean_level is not None then no internal volumes of children.

    Args:
        points (list of dict, list of list, list): 8 corner points of the block
        curves (list of dict, list of list, list, list of Curve): 12 edge curves of the block
        surfaces (list of dict, list of list, list, list of Surface): 6 boundary surfaces of the block
        volumes (list of dict, list of list, list, list of Volume): volumes of the block (1 by now, TODO several volumes)
        do_register (bool or int): register Block in the registry
        use_register_tag (bool or int): use tag from registry instead tag from gmsh
        do_unregister (bool): unregister Block from the registry
        do_register_children (bool): invoke register for children
        do_unregister_children (bool): invoke unregister for children
        transforms (list of dict, list of list, list of Transform): points and curves points transforms (Translation, Rotation, Coordinate Change, etc)
        quadrate (list of dict, bool): transform triangles to quadrangles for surfaces and tetrahedra to hexahedra for volumes
        structure (list of dict, list of list, list of Transform): make structured mesh instead of unstructured by some rule
        parent (Block): parent of the Block
        children (list of Block): children of the Block
        children_transforms (list of list of dict, list of list of list, list of list of Transform): transforms for children Blocks
        boolean_level (int): Block boolean level, if the Block level > another Block level, then intersected volume joins to the Block, if levels are equal third Block is created, if None - don't do boolean
    """

    def __init__(self, points=None, curves=None, surfaces=None, volumes=None,
                 do_register=True, use_register_tag=False, do_unregister=False,
                 do_register_children=True, do_unregister_children=True,
                 do_unregister_boolean=False, do_unregister_boolean_children=True,
                 transforms=None,
                 quadrate=None, structure=None, zone=None,
                 parent=None, children=None, children_transforms=None,
                 boolean_level=None, path=None, structure_type='LLL'):
        self.points = self.parse_points(points)
        self.curves = self.parse_curves(curves)
        self.surfaces = self.parse_surfaces(surfaces)
        self.volumes = self.parse_volumes(volumes)
        self.register_tag = use_register_tag
        self.do_register = do_register
        self.do_unregister = do_unregister
        self.do_register_children = do_register_children
        self.do_unregister_children = do_unregister_children
        self.do_unregister_boolean = do_unregister_boolean
        self.do_unregister_boolean_children = do_unregister_boolean_children
        self.transforms = self.parse_transforms(transforms, parent)
        # Structure and Quadrate
        self.curves_structures, self.surfaces_structures, \
        self.volumes_structures = self.parse_structure(structure)
        self.surfaces_quadrates = self.parse_quadrate(quadrate)
        # Zones
        self.points_zones, self.curves_zones, self.surfaces_zones, \
        self.volumes_zones = self.parse_zone(zone)
        for v in self.volumes:
            if v.zone is None:
                v.zone = self.volumes_zones[0]
        self.parent = parent
        self.children = [] if children is None else children
        if children_transforms is None:
            children_transforms = [[] for _ in self.children]
        for i, t in enumerate(children_transforms):
            children_transforms[i] = self.parse_transforms(t, parent)
        self.children_transforms = children_transforms
        self.boolean_level = boolean_level
        self.path = path
        self.surfaces_arrangement, self.surfaces_points, self.volume_points = \
            self.parse_structure_type(structure_type)
        # Support
        self.curves_loops = [CurveLoop() for _ in range(6)]
        self.surfaces_loops = [SurfaceLoop()]
        # Flags
        self.is_registered = False
        self.is_booleaned = False

    curves_points = [
        [1, 0], [5, 4], [6, 7], [2, 3],  # X1, X2, X3, X4
        [3, 0], [2, 1], [6, 5], [7, 4],  # Y1, Y2, Y3, Y4
        [0, 4], [1, 5], [2, 6], [3, 7]   # Z1, Z2, Z3, Z4
    ]

    surfaces_curves = [
        [5, 9, 6, 10],  # NX
        [4, 11, 7, 8],  # X
        # [11, 2, 10, 3],  # NY
        [10, 2, 11, 3],  # NY
        [0, 8, 1, 9],  # Y
        [0, 5, 3, 4],  # NZ
        # [1, 7, 2, 6],  # Z
        [7, 2, 6, 1],  # Z
    ]

    surfaces_curves_signs = [
        [1, 1, -1, -1],  # NX
        [-1, 1, 1, -1],  # X
        # [1, -1, -1, 1],  # NY
        [1, 1, -1, -1],  # NY
        [1, 1, -1, -1],  # Y
        [-1, -1, 1, 1],  # NZ
        # [1, -1, -1, 1],  # Z
        [-1, -1, 1, 1],  # Z
    ]

    @staticmethod
    def parse_points(points):
        if points is None:
            points = [[1, 1, -1], [-1, 1, -1], [-1, -1, -1], [1, -1, -1],
                      [1, 1, 1], [-1, 1, 1], [-1, -1, 1], [1, -1, 1]]
        if isinstance(points, (float, int)):  # lx/ly/lz
            a = 0.5 * points
            points = [[a, a, -a], [-a, a, -a], [-a, -a, -a], [a, -a, -a],
                      [a, a, a], [-a, a, a], [-a, -a, a], [a, -a, a]]
        elif isinstance(points, list):
            if len(points) == 0:
                pass
            # lx/ly/lz, coordinate_system
            elif len(points) == 2 and all((isinstance(points[0], (float, int)),
                                           isinstance(points[1], str))):
                a, cs_name = 0.5 * points[0], points[1]
                points = [[a, a, -a], [-a, a, -a], [-a, -a, -a], [a, -a, -a],
                          [a, a, a], [-a, a, a], [-a, -a, a], [a, -a, a],
                          cs_name]
            # lx, ly, lz
            elif len(points) == 3 and all(isinstance(x, (float, int))
                                          for x in points):
                a, b, c = 0.5 * points[0], 0.5 * points[1], 0.5 * points[2]
                points = [[a, b, -c], [-a, b, -c], [-a, -b, -c], [a, -b, -c],
                          [a, b, c], [-a, b, c], [-a, -b, c], [a, -b, c]]
            # lx, ly, lz, coordinate_system
            elif len(points) == 4 and all((isinstance(points[0], (float, int)),
                                           isinstance(points[1], (float, int)),
                                           isinstance(points[2], (float, int)),
                                           isinstance(points[3], str))):
                a, b, c = 0.5 * points[0], 0.5 * points[1], 0.5 * points[2]
                cs_name = points[3]
                points = [[a, b, -c], [-a, b, -c], [-a, -b, -c], [a, -b, -c],
                          [a, b, c], [-a, b, c], [-a, -b, c], [a, -b, c],
                          cs_name]
            # lx, ly, lz, mesh_size
            elif len(points) == 4 and all(isinstance(x, (float, int))
                                          for x in points):
                a, b, c = 0.5 * points[0], 0.5 * points[1], 0.5 * points[2]
                mesh_size = points[3]
                points = [[a, b, -c], [-a, b, -c], [-a, -b, -c], [a, -b, -c],
                          [a, b, c], [-a, b, c], [-a, -b, c], [a, -b, c],
                          mesh_size]
        else:
            raise ValueError(points)
        return Point.parse_points(points, do_deg2rad=True)

    @staticmethod
    def parse_curves(curves):
        if curves is None:
            new_curves = [Curve(name='line') for _ in range(12)]
        elif isinstance(curves, list):
            new_curves = []
            for c in curves:
                if isinstance(c, dict):
                    c['points'] = Point.parse_points(
                        points=c.get('points', None), do_deg2rad=True)
                    new_curves.append(Curve(**c))
                elif isinstance(c, list):
                    ss = [x for x in c if isinstance(x, str)]  # strings
                    ls = [x for x in c if isinstance(x, list)]  # lists
                    new_curves.append(Curve(
                        name=ss[0] if len(ss) > 0 else 'line',
                        points=Point.parse_points(points=ls[0], do_deg2rad=True)
                        if len(ls) > 0 else None))
                else:
                    raise ValueError(c)
        else:
            raise ValueError(curves)
        return new_curves

    @staticmethod
    def parse_surfaces(surfaces):
        if surfaces is None:
            return [Surface(name='fill') for _ in range(6)]
        elif isinstance(surfaces, list):  # list of dict
            return [Surface(**x) for x in surfaces]
        else:
            raise ValueError(surfaces)

    @staticmethod
    def parse_volumes(volumes):
        if volumes is None:
            return [Volume()]
        elif isinstance(volumes, list):  # list of dict
            return [Volume(**x) for x in volumes]
        elif isinstance(volumes, dict):
            return [Volume(**volumes)]
        else:
            raise ValueError(volumes)

    @staticmethod
    def parse_transforms(transforms, parent):
        if transforms is None:
            return []
        else:
            new_transforms = []
            for i, t in enumerate(transforms):
                if isinstance(t, str):
                    name, kwargs = t, {}
                elif isinstance(t, list):
                    if len(t) == 3:
                        name, kwargs = 'translate', {'delta': t}
                    elif len(t) == 4:
                        name = 'rotate'
                        kwargs = {'origin': [0, 0, 0],
                                  'direction': t[:3],
                                  'angle': t[3]}
                    elif len(t) == 7:
                        name = 'rotate'
                        kwargs = {'origin': t[:3],
                                  'direction': t[3:6],
                                  'angle': t[6]}
                    else:
                        raise ValueError(t)
                elif isinstance(t, dict):
                    name = t.pop('name')
                    kwargs = t
                else:
                    raise ValueError(t)
                if 'angle' in kwargs:
                    kwargs['angle'] = np.deg2rad(kwargs['angle'])
                if transform_factory[name] == BlockToCartesian:
                    ps = [x.coordinates for x in parent.points]
                    kwargs['cs_from'] = BlockCS(ps=ps)
                new_transforms.append(transform_factory[name](**kwargs))
            return new_transforms

    @staticmethod
    def parse_structure(structure):
        if structure is None or not structure:
            return [None for _ in range(12)], [None for _ in range(6)], [None]
        elif isinstance(structure, list):
            cs_ss = []  # Curves
            if len(structure) == 1:  # All directions
                for values in structure:
                    kwargs = {'nPoints': values[0],
                              'meshType': values[1],
                              'coef': values[2]}
                    cs_ss.append(Structure(name='curve', **kwargs))
            elif len(structure) == 3:  # X, Y and Z directions
                # Curves
                for values in structure:
                    if isinstance(values, list):
                        for _ in range(4):
                            kwargs = {'nPoints': values[0],
                                      'meshType': values[1],
                                      'coef': values[2]}
                            cs_ss.append(Structure(name='curve', **kwargs))
                    elif values is None:
                        for _ in range(4):
                            cs_ss.append(None)
                    else:
                        raise ValueError(values)
            else:
                raise ValueError(structure)
            ss_ss = [Structure(name='surface') for _ in range(6)]
            return cs_ss, ss_ss, [Structure(name='volume')]
        else:
            raise ValueError(structure)

    @staticmethod
    def parse_quadrate(quadrate):
        if quadrate is None or not quadrate:
            return [None for _ in range(6)]
        elif quadrate:
            return [Quadrate(name='surface') for _ in range(6)]
        else:
            raise ValueError(quadrate)

    @staticmethod
    def parse_zone(zone):
        default_ps_zs = ['X_Y_NZ', 'N_XY_NZ', 'NX_NY_NZ', 'X_NY_NZ',
                         'X_Y_Z', 'N_XY_Z', 'NX_NY_Z', 'X_NY_Z']
        default_cs_zs = ['X1', 'X2', 'X3', 'X4',
                         'Y1', 'Y2', 'Y3', 'Y4',
                         'Z1', 'Z2', 'Z3', 'Z4']
        default_ss_zs = ['NX', 'X', 'NY', 'Y', 'NZ', 'Z']
        default_vs_zs = ['V']
        if zone is None:
            return default_ps_zs, default_cs_zs, default_ss_zs, default_vs_zs
        elif isinstance(zone, str):
            return default_ps_zs, default_cs_zs, default_ss_zs, [zone]
        elif isinstance(zone, list):
            vs_zs = zone[0] if len(zone) > 0 else default_vs_zs
            ss_zs = zone[1] if len(zone) > 1 else default_ss_zs
            cs_zs = zone[2] if len(zone) > 2 else default_cs_zs
            ps_zs = zone[3] if len(zone) > 3 else default_ps_zs
            return ps_zs, cs_zs, ss_zs, vs_zs
        else:
            raise ValueError(zone)

    @staticmethod
    def parse_structure_type(structure_type):
        """Parse structure type

        # https://gitlab.onelab.info/gmsh/gmsh/-/blob/master/Mesh/meshGRegionTransfinite.cpp

        Transfinite surface meshes

            s4 +-----c3-----+ s3
               |            |
               |            |
              c4            c2
               |            |
               |            |
            s1 +-----c1-----+ s2

            f(u,v) = (1-u) c4(v) + u c2(v) + (1-v) c1(u) + v c3(u)
            - [ (1-u)(1-v) s1 + u(1-v) s2 + uv s3 + (1-u)v s4 ]

        Transfinite volume meshes

                              a0   s0 s1  f0  s0 s1 s5 s4              s6
            s7        s6      a1   s1 s2  f1  s1 s2 s6 s5              *
              *-------*       a2   s3 s2  f2  s3 s2 s6 s7             /|\
              |\s4    |\      a3   s0 s3  f3  s0 s3 s7 s4            / | \
              | *-------* s5  a4   s4 s5  f4  s0 s1 s2 s3      s7/s4/  |s2\
              | |   s2| |     a5   s5 s6  f5  s4 s5 s6 s7          *---*---* s5
           s3 *-|-----* |     a6   s7 s6                           |  / \  |
               \|      \|     a7   s4 s7                           | /   \ |
                *-------*     a8   s0 s4                           |/     \|
          v w  s0       s1    a9   s1 s5                           *-------*
           \|                 a10  s2 s6                  v w    s3/s0     s1
            *--u              a11  s3 s7                   \|
                                                            *--u

        TODO How to create other types? (RLL, LRL, LLR, RRR)
            Tried to rotate
            volume_points = [0, 1, 2, 3, 4, 5, 6, 7]  # LLL
            volume_points = [1, 2, 3, 0, 5, 6, 7, 4]  # LRR
            volume_points = [2, 3, 0, 1, 6, 7, 4, 5]  # RRL
            volume_points = [3, 0, 1, 2, 7, 4, 5, 6]  # RLR
            Tried to swap top and bottom
            volume_points = [4, 5, 6, 7, 0, 1, 2, 3]  # RRL
            volume_points = [5, 6, 7, 4, 1, 2, 3, 0]  # RLR
            volume_points = [6, 7, 4, 5, 2, 3, 0, 1]  # LLL
            volume_points = [7, 4, 5, 6, 3, 0, 1, 2]  # LRR
            Tried to reverse
            volume_points = [3, 2, 1, 0, 7, 6, 5, 4]  # RLR
            volume_points = [0, 3, 2, 1, 4, 7, 6, 5]  # LLL
            volume_points = [1, 0, 3, 2, 5, 4, 7, 6]  # LRR
            volume_points = [2, 1, 0, 3, 6, 5, 4, 7]  # RRL
            Tried to swap top and bottom with reverse after
            volume_points = [7, 6, 5, 4, 3, 2, 1, 0]  # LRR
            volume_points = [4, 7, 6, 5, 0, 3, 2, 1]  # RRL
            volume_points = [5, 4, 7, 6, 1, 0, 3, 2]  # RLR
            volume_points = [6, 5, 4, 7, 2, 1, 0, 3]  # LLL

        Args:
            structure_type (str): LLL, LRR, LRR or RRL, L/R - Left/Right
                triangles arrangement of X (NX), Y (NY), Z (NZ) surfaces
                respectively, e.g. LRR - Left arrangement for X and NX surfaces,
                Right for Y and NY, Right for Z and NZ

        Returns:
            tuple: tuple of:
                surfaces_arrangement (list of str): surfaces arrangement:
                    Left or Right (AlternateLeft and AlternateRight
                    are incompatible with structured meshes)
                surfaces_points (list of list of int): surfaces points tags
                    (s1, s2, s3, s4)
                volume_points (list of int): volume points tags
                    (s0, s1, s2, s3, s4, s5, s6, s7)
        """
        surfaces_points = [
            [1, 5, 6, 2],  # NX
            [0, 3, 7, 4],  # X
            [3, 2, 6, 7],  # NY
            [0, 4, 5, 1],  # Y
            [0, 1, 2, 3],  # NZ
            [4, 7, 6, 5]]  # Z
        if structure_type == 'LLL':
            surfaces_arrangement = ['Left', 'Left', 'Left',  # NX, X, NY
                                    'Left', 'Left', 'Left']  # Y, NZ, Z
            volume_points = [0, 1, 2, 3, 4, 5, 6, 7]
        elif structure_type == 'RRL':
            surfaces_arrangement = ['Right', 'Right', 'Right',  # NX, X, NY
                                    'Right', 'Left', 'Left']  # Y, NZ, Z
            volume_points = [2, 3, 0, 1, 6, 7, 4, 5]
        elif structure_type == 'LRR':
            surfaces_arrangement = ['Left', 'Left', 'Right',  # NX, X, NY
                                    'Right', 'Right', 'Right']  # Y, NZ, Z
            volume_points = [1, 2, 3, 0, 5, 6, 7, 4]
        elif structure_type == 'RLR':
            surfaces_arrangement = ['Right', 'Right', 'Left',  # NX, X, NY
                                    'Left', 'Right', 'Right']  # Y, NZ, Z
            volume_points = [3, 0, 1, 2, 7, 4, 5, 6]
        elif structure_type in ['RLL', 'LRL', 'LLR' 'RRR']:
            raise NotImplementedError(structure_type)
        else:
            raise ValueError(structure_type)
        return surfaces_arrangement, surfaces_points, volume_points

    def register(self):
        # Children
        if self.do_register_children:
            for i, c in enumerate(self.children):
                c.register()
        # Self
        if not self.do_register or self.is_registered:
            return
        self.register_points()
        self.register_curve_points()
        self.register_curves()
        self.register_curves_loops()
        self.register_surfaces()  # TODO Too long fill surface in occ factory!
        self.register_surfaces_loops()
        self.register_volumes()
        self.register_structure()
        self.register_quadrate()

    def add_child(self, child, transforms=None):
        transforms = [] if transforms is None else transforms
        self.children.append(child)
        transforms = self.parse_transforms(transforms, self.parent)
        self.children_transforms.append(transforms)

    def transform(self):
        # Children
        for i, c in enumerate(self.children):
            c.transforms.extend(self.children_transforms[i])
            c.transforms.extend(self.transforms)
            c.transform()
        for i, p in enumerate(self.points):
            if isinstance(p.coordinate_system, BlockCS):
                if self.parent is None:
                    raise ValueError(
                        'The parent must exist with Block Coordinate System!')
                p.coordinate_system.ps = [x.coordinates
                                          for x in self.parent.points]
            self.points[i] = reduce_transforms(self.transforms, p)
        # Curve Points
        for i, c in enumerate(self.curves):
            for j, p in enumerate(c.points):
                if isinstance(p.coordinate_system, BlockCS):
                    if self.parent is None:
                        raise ValueError(
                            'The parent must exist with Block Coordinate System!')
                    p.coordinate_system.ps = [x.coordinates
                                              for x in self.parent.points]
                self.curves[i].points[j] = reduce_transforms(self.transforms, p)

    def register_points(self):
        for i, p in enumerate(self.points):
            self.points[i] = register_point(p, self.register_tag)

    def register_curve_points(self):
        for i, c in enumerate(self.curves):
            for j, p in enumerate(c.points):
                c.points[j] = register_point(p, self.register_tag)
            # Add start and end points to curves
            p0 = self.points[self.curves_points[i][0]]
            p1 = self.points[self.curves_points[i][1]]
            c.points = [p0] + c.points + [p1]

    def register_curves(self):
        for i, c in enumerate(self.curves):
            self.curves[i] = register_curve(c, self.register_tag)

    def register_curves_loops(self):
        for i, cl in enumerate(self.curves_loops):
            self.curves_loops[i].curves = [self.curves[x] for x in
                                           self.surfaces_curves[i]]
            self.curves_loops[i].curves_signs = self.surfaces_curves_signs[i]
            self.curves_loops[i] = register_curve_loop(self.curves_loops[i],
                                                       self.register_tag)

    def register_surfaces(self):
        for i, s in enumerate(self.surfaces):
            self.surfaces[i].curves_loops = [self.curves_loops[i]]
            self.surfaces[i] = register_surface(self.surfaces[i],
                                                self.register_tag)

    def register_surfaces_loops(self):
        # External
        self.surfaces_loops[0].surfaces = self.surfaces
        self.surfaces_loops[0] = register_surface_loop(self.surfaces_loops[0],
                                                       self.register_tag)
        # Internal
        if self.boolean_level is None:
            internal_volumes = []
            for i, c in enumerate(self.children):
                if c.do_register:
                    if not c.is_registered:
                        raise ValueError('Register children before parent!')
                    internal_volumes.append(c.volumes)
            volumes_surfaces = [[z.tag for z in y.surfaces_loops[0].surfaces]
                                for x in internal_volumes
                                for y in x]
            surfaces_groups = volumes_surfaces_to_volumes_groups_surfaces(
                volumes_surfaces)
            for g in surfaces_groups:
                sl = SurfaceLoop(surfaces=[Surface(tag=x) for x in g])
                sl = register_surface_loop(sl, self.register_tag)
                self.surfaces_loops.append(sl)

    def register_volumes(self):
        v = self.volumes[0]
        v.surfaces_loops = self.surfaces_loops
        self.volumes[0] = register_volume(v, self.register_tag)
        self.is_registered = True

    def register_structure(self):
        for i, c in enumerate(self.curves):
            st = self.curves_structures[i]
            if st is not None:
                register_curve_structure(c.points, st)
        for i, s in enumerate(self.surfaces):
            st = self.surfaces_structures[i]
            if st is not None:
                st.kwargs['cornerTags'] = [
                    self.points[x].tag for x in self.surfaces_points[i]]
                st.kwargs['arrangement'] = self.surfaces_arrangement[i]
                ps_ids = self.surfaces_points[i]
                ps = [self.points[x] for x in ps_ids]
                register_surface_structure(ps, st)
        for i, v in enumerate(self.volumes):
            if i < len(self.volumes_structures):
                st = self.volumes_structures[i]
                if st is not None:
                    st.kwargs['cornerTags'] = [
                        self.points[x].tag for x in self.volume_points]
                    ps = self.points
                    register_volume_structure(ps, st)

    def register_quadrate(self):
        for i, s in enumerate(self.surfaces):
            q = self.surfaces_quadrates[i]
            if q is not None:
                ps_ids = self.surfaces_points[i]
                ps = [self.points[x] for x in ps_ids]
                register_surface_quadrate(ps, q)

    def unregister(self, zone_separator='-'):
        # Children
        if self.do_unregister_children:
            for i, c in enumerate(self.children):
                c.unregister()
        # Self
        if not self.do_unregister:
            return
        if not self.is_registered:
            return
        for i, v in enumerate(self.volumes):
            if v.zone is not None:
                if zone_separator not in v.zone:
                    self.volumes[i] = unregister_volume(v, self.register_tag)

    def unregister_boolean(self, zone_separator='-'):
        # Children
        if self.do_unregister_boolean_children:
            for i, c in enumerate(self.children):
                c.unregister_boolean()
        # Self
        if not self.is_registered or not self.do_unregister_boolean:
            return
        if self.boolean_level is None:
            return
        for i, v in enumerate(self.volumes):
            if zone_separator in v.zone:
                self.volumes[i] = unregister_volume(v, self.register_tag)

    def __iter__(self):
        """Iterate children of the block recursively

        Examples:
            Tree

            0
                00
                    001

                    002
                01
                    011

                    012

            Iterator

            0, 00, 001, 002, 01, 011, 012

        Returns:
            generator of Block: blocks
        """
        yield self
        for child in self.children:
            yield from iter(child)

    def __len__(self):
        return sum(1 for _ in self)

    def make_tree(self):
        """Tree of blocks

        Returns:
            dict: children of blocks
        """
        tree = {}
        for b in self:  # See __iter__
            tree.setdefault(b.parent, []).append(b)
        return tree

    def plot_tree(self, file_name=None, height='600px', width='600px',
                  hierarchical=True, show_buttons=True, label_type='file_name',
                  group_type='file_name', title_type='file_name',
                  bgcolor='black', font_color='white'):
        def get_value(b, t):
            if t == 'block':
                v = f'type: {type(b).__name__} <br> '
                v += f'id: {id(b)} <br> '
                v += f'parent_id: {id(b.parent) if b.parent is not None else None} <br> '
                zs = ", ".join({x.zone for x in b.volumes if x.zone is not None and x.tag is not None})
                v += f'volume zones: {zs} <br> '
                v += ' <br> '.join(f'{x}: {b.__getattribute__(x)}' for x in (
                    'file_name', 'factory', 'boolean_level', 'register_tag',
                    'do_register', 'do_register_children', 'do_unregister',
                    'do_unregister_boolean', 'do_unregister_boolean_children',
                    'is_registered', 'is_quadrated', 'is_structured'))
            elif t == 'file_name':
                v = b.path
            elif t == 'boolean_level':
                v = str(b.boolean_level)
            elif t == 'volume_zone':
                v = ", ".join({x.zone for x in b.volumes if x.zone is not None and x.tag is not None})
            elif t == 'id':
                v = id(b)
            elif t == 'type':
                v = type(b).__name__
            else:
                v = None
            return v

        if file_name is None:
            if self.path is not None:
                file_name = f"{self.path.with_suffix('').name}-tree"
            else:
                file_name = f'{id(self)}-tree'
        logging.info(f'Tree of {id(self)} with label by {label_type} '
                     f'title by {title_type} '
                     f'and group by {group_type}')
        prev_parent = None
        parent2depth = {prev_parent: 0}
        depth2nodes = {}
        parent2children = {}
        cnt = 0  # nodes counter
        for b in self:  # See __iter__
            cnt += 1
            parent = b.parent
            if parent not in parent2depth:
                parent2depth[parent] = parent2depth[prev_parent] + 1
            prev_parent = parent
            depth = parent2depth[parent]
            depth2nodes.setdefault(depth, []).append(b)
            parent2children.setdefault(parent, []).append(b)
            label = get_value(self, label_type)
            label = label if label is not None else ''
            logging.info(f'{"_" * depth}{id(b)} {label}')
        d2n = ", ".join(f"{k}-{len(v)}" for k, v in depth2nodes.items())
        logging.info(f'Number of nodes: {cnt}')
        logging.info(f'Nodes by depth: {d2n}')
        logging.info(f'Max depth: {max(depth2nodes)}')
        try:
            logging.info(f'pyvis network')
            from pyvis.network import Network

            n = Network(height=height, width=width, directed=True,
                        layout=hierarchical, bgcolor=bgcolor,
                        font_color=font_color)
            if show_buttons:
                n.show_buttons()
            nodes, edges, groups = set(), set(), {}
            for p, cs in parent2children.items():
                if p is None:  # Skip root
                    continue
                if p not in nodes:
                    g = get_value(p, group_type)
                    groups.setdefault(g, len(groups))
                    label = get_value(p, label_type)
                    label = label if label is not None else ' '
                    n.add_node(id(p), label=label, group=groups[g],
                               value=len(p.children), level=parent2depth[p.parent],
                               title=get_value(p, title_type))
                    nodes.add(p)
                for c in cs:
                    if c not in nodes:
                        g = get_value(c, group_type)
                        groups.setdefault(g, len(groups))
                        label = get_value(c, label_type)
                        label = label if label is not None else ' '
                        n.add_node(id(c), label=label, group=groups[g],
                                   value=len(c.children), level=parent2depth[c.parent],
                                   title=get_value(c, title_type))
                        nodes.add(c)
                    if (p, c) not in edges:
                        n.add_edge(id(p), id(c))
                        edges.add((p, c))
            p = Path(file_name).with_suffix('.html')
            logging.info(f'Writing pyvis network to {p}')
            n.write_html(str(p))
        except Exception as e:
            logging.warning(e)


str2obj = {
    Block.__name__: Block,
    Block.__name__.lower(): Block,
}
