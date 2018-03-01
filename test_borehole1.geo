Include "macro_borehole1.geo";
Include "macro_hexahedron.geo";

Geometry.AutoCoherence = 0;

borehole1_ox = 0; borehole1_oy = 0; borehole1_oz = 0; // Origin: x, y, z (bottom)
borehole1_rax = 0; borehole1_ray = 0; borehole1_raz = 0;  // Local Rotation Angle: x, y, z
borehole1_t1 = 4; // Number of circumferential nodes
borehole1_t2s = {3, 3, 3}; // Number of radial nodes
borehole1_t2t1s = {0, 0, 0}; // Radial nodes progression
borehole1_t2t2s = {0, 0, 0}; // Radial nodes bump
borehole1_t3s = {5, 3, 3, 25, 3, 3, 5}; // Number of height nodes
borehole1_t3t1s = {0, 0, 0, 0, 0, 0, 0}; // Height nodes progression
borehole1_t3t2s = {0, 0, 0, 0.07, 0, 0, 0}; // Height nodes progression bump
cylitive_t6 = 1; // Full boundary surfaces?

Call borehole1;

hexahedron_lc = 50; // Points characteristic length
hexahedron_a = 1000; // X length
hexahedron_b = 1000; // Y length
hexahedron_c = 487.5*2; // Z length
hexahedron_ox = borehole2_ox; hexahedron_oy = borehole2_oy; hexahedron_oz = borehole2_oz+37.5; // Origin: x, y, z
hexahedron_rox = 0; hexahedron_roy = 0; hexahedron_roz = 0; // Local Rotation Origin: x, y, z
hexahedron_rax = 0; hexahedron_ray = 0; hexahedron_raz = 0; // Local Rotation Angle: x, y, z
// Parameters
hexahedron_t_1 = 0; hexahedron_t_1_1 = 0; hexahedron_t_1_2 = 0; // Number of X nodes, progression, bump
hexahedron_t_2 = 0; hexahedron_t_2_1 = 0; hexahedron_t_2_2 = 0; // Number of Y nodes, progression, bump
hexahedron_t_3 = 0; hexahedron_t_3_1 = 0; hexahedron_t_3_2 = 0; // Number of Z nodes, progression, bump
hexahedron_t_4 = 0; // Hex (1) or tet (0) mesh?
hexahedron_t_6 = 0; // Type of hex to tet splitting
hexahedron_t_7s = {borehole1_bss[]}; // Inner Surfaces

Call hexahedron;

Physical Surface ("NX") = {hexahedron_nxss[]};
Physical Surface ("X") = {hexahedron_xss[]};
Physical Surface ("NY") = {hexahedron_nyss[]};
Physical Surface ("Y") = {hexahedron_yss[]};
Physical Surface ("NZ") = {hexahedron_nzss[]};
Physical Surface ("Z") = {hexahedron_zss[]};

If(#borehole1_pvs[] > 0)
  Printf("Global Physical Volumes = %g", #borehole1_pvns[]);
  For pvns_i In {0 : #borehole1_pvns[]-1}
    Printf(borehole1_pvns[pvns_i]);
    vs = {};
    start_idx = 0;
    For pvs_i In {0 : #borehole1_pvs[]-1}
      If (pvs_i == start_idx)
        nvs = borehole1_pvs[pvs_i+1];
        start_idx += 1+nvs+1;
        If (borehole1_pvs[pvs_i] == pvns_i)
          For pvsj In {pvs_i+2 : pvs_i+2+nvs-1}
            vs += borehole1_pvs[pvsj];
          EndFor
        EndIf
      EndIf
    EndFor
    If (StrCmp(Str(borehole1_pvns[pvns_i]), "Environment") == 0) // If physical name is "Environment"
      Physical Volume (Str(borehole1_pvns[pvns_i])) = {vs[], hexahedron_vs[]};
    Else
      Physical Volume (Str(borehole1_pvns[pvns_i])) = {vs[]};
    EndIf
  EndFor
EndIf

Coherence;

