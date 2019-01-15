import json
import os
import argparse
import socket
from pprint import pprint
import sys

import gmsh

from boolean import complex_self
from complex_primitive import ComplexPrimitive
from cylinder import Cylinder
from divided_cylinder import DividedCylinder
from experiment import Experiment
from matrix import Matrix
from tunnel import Tunnel
from occ_workarounds import correct_and_transfinite_complex
from support import boundary_surfaces_to_six_side_groups, get_boundary_surfaces


class ComplexFactory:
    def __init__(self):
        pass

    @staticmethod
    def new(input_data):
        """
        Complex's child objects factory by item 'class_name':
        'Complex's child class name' in input_data['metadata'].
        :param dict input_data: dict should have at least two items:
        'metadata':dict and 'arguments':dict,
        'metadata' dict should be 'class_name' item and 'arguments' dict
        should coincide with child object __init__
        method arguments
        :return: Complex
        """
        class_name = input_data['metadata']['class_name']
        kwargs = input_data['arguments']
        if class_name == ComplexPrimitive.__name__:
            return ComplexPrimitive(**kwargs)
        if class_name == Cylinder.__name__:
            return Cylinder(**kwargs)
        if class_name == DividedCylinder.__name__:
            return DividedCylinder(**kwargs)
        if class_name == Matrix.__name__:
            return Matrix(**kwargs)
        if class_name == Tunnel.__name__:
            return Tunnel(**kwargs)
        if class_name == Experiment.__name__:
            return Experiment(**kwargs)

if __name__ == '__main__':
    print('Python: {0}'.format(sys.executable))
    print('Script: {0}'.format(__file__))
    print('Working Directory: {0}'.format(os.getcwd()))
    print('Host: {0}'.format(socket.gethostname()))
    print('PID: {0}'.format(os.getpid()))
    print('Arguments')
    parser = argparse.ArgumentParser()
    parser.add_argument('input', help='input filename')
    parser.add_argument('-o', '--output', help='output filename')
    parser.add_argument('-v', '--verbose', help='verbose', action='store_true')
    parser.add_argument('-t', '--test', help='test mode', action='store_true')
    parser.add_argument('-r', '--recombine', help='recombine', action='store_true')
    parser.add_argument('-b', '--boolean', help='boolean', action='store_true')
    parser.add_argument('-a', '--all_boundaries', help='all_boundaries', action='store_true')
    args = parser.parse_args()
    print(args)
    root, extension = os.path.splitext(args.input)
    basename = os.path.basename(root)
    if args.output is None:
        output_path = basename
    else:
        output_path = args.output
    is_test = args.test
    is_verbose = args.verbose
    input_path = args.input
    model_name = basename
    is_recombine = args.recombine
    is_boolean = args.boolean
    is_all_boundaries = args.all_boundaries
    gmsh.initialize()
    if is_verbose:
        gmsh.option.setNumber("General.Terminal", 1)
    else:
        gmsh.option.setNumber("General.Terminal", 0)
    gmsh.option.setNumber('Geometry.AutoCoherence', 0)  # No effect at occ
    gmsh.model.add(model_name)
    print('Input')
    with open(input_path) as f:
        input_data = json.load(f)
    pprint(input_data)
    print('Initialize')
    c = ComplexFactory.new(input_data)
    factory = c.factory
    print('Synchronize')
    factory.synchronize()
    if not is_test:
        print('Evaluate')
        c.evaluate_coordinates()  # for correct and transfinite
        c.evaluate_bounding_box()  # for boolean
        if is_boolean:
            print("Boolean")
            complex_self(factory, c)
        print('Remove Duplicates')
        factory.removeAllDuplicates()
        print('Synchronize')
        factory.synchronize()
        print('Correct and Transfinite')
        ss = set()
        cs = set()
        correct_and_transfinite_complex(c, ss, cs)
        if is_recombine:
            print('Recombine')
            c.recombine()
        print('Physical')
        print("Volumes")
        for name in c.map_physical_name_to_primitives_indices.keys():
            vs = c.get_volumes_by_physical_name(name)
            tag = gmsh.model.addPhysicalGroup(3, vs)
            gmsh.model.setPhysicalName(3, tag, name)
        print("Surfaces")
        if is_all_boundaries:
            print("All surfaces")
            boundary_surfaces = get_boundary_surfaces()
            for i, s in enumerate(boundary_surfaces):
                name = 'S{0}'.format(i)
                tag = gmsh.model.addPhysicalGroup(2, [s])
                gmsh.model.setPhysicalName(2, tag, name)
        else:
            print("6 surfaces")
            boundary_surfaces_groups = boundary_surfaces_to_six_side_groups()
            for i, (name, ss) in enumerate(boundary_surfaces_groups.items()):
                tag = gmsh.model.addPhysicalGroup(2, ss)
                gmsh.model.setPhysicalName(2, tag, name)
        print("Mesh")
        gmsh.model.mesh.generate(3)
        gmsh.model.mesh.removeDuplicateNodes()
        print("Write")
        gmsh.write(output_path + '.msh')
    else:
        print("Write")
        gmsh.write(output_path + '.brep')
    gmsh.finalize()
