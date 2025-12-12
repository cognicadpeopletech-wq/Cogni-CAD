
"""
manifold_dynamic.py
Dynamic CATIA manifold generator using PyCATIA.

This is a parameterised version of your original working script.
All geometry steps are the same, including:
- Inlet mounting points
- Rectangular pattern
- Outlet creation
- Pipe curves
- Pipe surfaces
- Solid walls (shell)

Only the key numeric values are taken from cfg (with safe defaults),
so topology / BRep references stay valid.

Usage:
    from manifold_dynamic import generate_manifold
    generate_manifold()              # use defaults
    generate_manifold(custom_cfg)    # override some parameters
"""

import numpy as np
from pycatia import catia
from pycatia.mec_mod_interfaces.part_document import PartDocument
from pycatia.enumeration.enumeration_types import (
    cat_prism_orientation,
    cat_fillet_edge_propagation,
)
from pycatia.in_interfaces.camera_3d import Camera3D
from pycatia.in_interfaces.viewer_3d import Viewer3D


def generate_manifold(cfg: dict | None = None) -> None:
    """
    Generate the exhaust manifold in CATIA.

    Parameters are taken from cfg, but all have defaults that reproduce
    your original script exactly.

    cfg keys (all optional):
        exhaust_rad        : float
        mnt_rad            : float
        mnt_angle_deg      : float
        mnt_dist           : float
        dmnd_DIST          : float
        dmnd_dist          : float
        pad_thickness_in   : float   # inlet support pad thickness
        pad_thickness_out  : float   # outlet support pad thickness
        pattern_spacing_Y  : float   # rectangular pattern spacing
        plane_outlet_offset: float
        outlet_h           : float
        mnt_out_dist       : float
        mnt_out_angle_deg  : float
        triang_dist        : float
        z_offset_inlet_top : float   # point above inlet
        meet_offset_x      : float   # common point offset from outlet
        turn_rad           : float   # bend radius for corners
        sweep_exhaust_rad  : float   # radius for sweep circles (inlets)
        shell_thickness    : float   # shell thickness
    """

    if cfg is None:
        cfg = {}

    # ------------------------------------------------------------------ #
    # Parameters (with safe defaults = original values)
    # ------------------------------------------------------------------ #
   
    user_inlet_radius = cfg.get("exhaust_rad", 34.0)
    shell_thickness   = cfg.get("shell_thickness", 1.0)

    # Inlet pad radius = user + shell
    exhaust_rad = user_inlet_radius + shell_thickness

    # Mount radius logic (safe shell compensation)
    user_mnt_rad = cfg.get("mnt_rad", 8.0)

    if user_mnt_rad > shell_thickness:
        mnt_rad = user_mnt_rad + shell_thickness
    else:
        mnt_rad = user_mnt_rad

    mnt_angle_deg = cfg.get("mnt_angle_deg", 38.0)
    mnt_angle = mnt_angle_deg * np.pi / 180.0
    mnt_dist = cfg.get("mnt_dist", 65.0)

    dmnd_DIST = cfg.get("dmnd_DIST", 100.0)
    dmnd_dist = cfg.get("dmnd_dist", 45.0)

    pad_thickness_in = cfg.get("pad_thickness_in", 10.0)
    pad_thickness_out = cfg.get("pad_thickness_out", 10.0)

    pattern_spacing_Y = cfg.get("pattern_spacing_Y", 120.0)

    plane_outlet_offset = cfg.get("plane_outlet_offset", 230.0)
    outlet_h = cfg.get("outlet_h", 150.0)
    mnt_out_dist = cfg.get("mnt_out_dist", 60.0)
    mnt_out_angle_deg = cfg.get("mnt_out_angle_deg", 30.0)
    mnt_out_angle = mnt_out_angle_deg * np.pi / 180.0

    triang_dist = cfg.get("triang_dist", 85.0)

    z_offset_inlet_top = cfg.get("z_offset_inlet_top", 80.0)
    meet_offset_x = cfg.get("meet_offset_x", 50.0)

    turn_rad = cfg.get("turn_rad", 60.0)
    sweep_exhaust_rad = user_inlet_radius 



    # ------------------------------------------------------------------ #
    # CATIA setup (same as your original script)
    # ------------------------------------------------------------------ #
    caa = catia()
    application = caa.application
    documents = application.documents

    # Close all open docs
    if documents.count > 0:
        for document in documents:
            document.close()

    # Create Part
    documents.add("Part")

    # Get references
    document: PartDocument = application.active_document
    part = document.part
    partbody = part.bodies[0]
    sketches = partbody.sketches
    hybrid_bodies = part.hybrid_bodies
    hsf = part.hybrid_shape_factory
    shpfac = part.shape_factory
    selection = document.selection

    # Camera (kept as in original)
    active_window = application.active_window
    viewer_3d = Viewer3D(active_window.active_viewer.com_object)
    camera_3d = Camera3D(document.cameras.item(1).com_object)  # noqa: F841
    viewpoint_3d = viewer_3d.viewpoint_3d

    # Main planes
    plane_XY = part.origin_elements.plane_xy
    plane_YZ = part.origin_elements.plane_yz
    plane_ZX = part.origin_elements.plane_zx

    # Hide main planes
    selection.clear()
    selection.add(plane_XY)
    selection.add(plane_YZ)
    selection.add(plane_ZX)
    selection.vis_properties.set_show(1)  # 0: Show / 1: Hide
    selection.clear()

    # Empty reference
    nothing = part.create_reference_from_name("")

    # Set PartBody as work object
    part.in_work_object = partbody

    # Construction hybrid body
    construction_elements = hybrid_bodies.add()
    construction_elements.name = "construction_elements"
    # store inlet points and elevated points
    pt1 = {}
    pt2 = {}
    pipe_sec_1 = {}
    pipe_sec_2 = {}
    pipe_sec_3 = {}
    sweep_circle = {}
    corner_2 = {}
    pipe_surface = {}
    close_surf = {}




    # ------------------------------------------------------------------ #
    # Camera global view (same values as original script)
    # ------------------------------------------------------------------ #
    sight = (-0.570774495601654, -0.493804931640625, -0.6560283899307251)
    origin = (563.5750732421875, 690.8805541992188, 799.2341918945312)
    up_direction = (-0.5215290188789368, -0.3990810215473175, 0.7541497945785522)
    viewpoint_3d.zoom = 0.0038752122782170773
    viewpoint_3d.put_up_direction(up_direction)
    viewpoint_3d.put_sight_direction(sight)
    viewpoint_3d.put_origin(origin)
    viewer_3d.update()

    # ------------------------------------------------------------------ #
    # ----- Generating manifold (same prints as original)
    # ------------------------------------------------------------------ #
    # print(chr(27) + "[2J")
    # print("")
    # print("# --------------------------- #")
    # print("# ----- Generating maifold")
    # print("# --------------------------- #")
    # print("")

    # ------------------------------------------------------------------ #
    # Create mounting points sketch (inlet side)
    # ------------------------------------------------------------------ #
    mnt_top_xy = (-mnt_dist * np.cos(mnt_angle), mnt_dist * np.sin(mnt_angle))
    mnt_bot_xy = (mnt_dist * np.cos(mnt_angle), -mnt_dist * np.sin(mnt_angle))

    dmnd_angle = (90.0 - mnt_angle_deg) * np.pi / 180.0
    dmnd_p1 = (-dmnd_DIST * np.cos(mnt_angle), dmnd_DIST * np.sin(mnt_angle))
    dmnd_p2 = (dmnd_dist * np.cos(dmnd_angle), dmnd_dist * np.sin(dmnd_angle))
    dmnd_p3 = (dmnd_DIST * np.cos(mnt_angle), -dmnd_DIST * np.sin(mnt_angle))
    dmnd_p4 = (-dmnd_dist * np.cos(dmnd_angle), -dmnd_dist * np.sin(dmnd_angle))

    part.in_work_object = partbody
    sketch_1 = sketches.add(plane_XY)
    sketch_1.name = "mouting_points"
    ske2D_1 = sketch_1.open_edition()

    # Exhaust inlet circle
    ske2D_1.create_closed_circle(0, 0, exhaust_rad )

    # Mounting points
    ske2D_1.create_closed_circle(mnt_top_xy[0], mnt_top_xy[1], mnt_rad)
    ske2D_1.create_closed_circle(mnt_bot_xy[0], mnt_bot_xy[1], mnt_rad)

    # Diamond support
    ske2D_1.create_line(*dmnd_p1, *dmnd_p2)
    ske2D_1.create_line(*dmnd_p2, *dmnd_p3)
    ske2D_1.create_line(*dmnd_p3, *dmnd_p4)
    ske2D_1.create_line(*dmnd_p4, *dmnd_p1)

    sketch_1.close_edition()
    document.part.update()

    # ------------------------------------------------------------------ #
    # Extrude inlet support and fillet (unchanged topology)
    # ------------------------------------------------------------------ #
    exhaust = shpfac.add_new_pad(sketch_1, pad_thickness_in)
    exhaust.direction_orientation = cat_prism_orientation.index("catRegularOrientation")
    exhaust.name = "exhaust"
    document.part.update()

    # The following reference strings are exactly as in your original,
    # so topology must stay the same (do not change feature order/count).
    EDGE_1 = part.create_reference_from_name(
        "Edge:(Face:(Brp:(Pad.1;0:(Brp:(Sketch.1;4)));None:();Cf12:());"
        "Face:(Brp:(Pad.1;0:(Brp:(Sketch.1;5)));None:();Cf12:());"
        "None:(Limits1:();Limits2:());Cf12:());Pad.1_ResultOUT;Z0;G8782"
    )
    EDGE_2 = part.create_reference_from_name(
        "Edge:(Face:(Brp:(Pad.1;0:(Brp:(Sketch.1;6)));None:();Cf12:());"
        "Face:(Brp:(Pad.1;0:(Brp:(Sketch.1;7)));None:();Cf12:());"
        "None:(Limits1:();Limits2:());Cf12:());Pad.1_ResultOUT;Z0;G8782"
    )
    exhaust_FILLET = shpfac.add_new_solid_edge_fillet_with_constant_radius(
        EDGE_1,
        cat_fillet_edge_propagation.index("catTangencyFilletEdgePropagation"),
        40.0,
    )
    exhaust_FILLET.add_object_to_fillet(EDGE_2)
    document.part.update()

    edge_1 = part.create_reference_from_name(
        "Edge:(Face:(Brp:(Pad.1;0:(Brp:(Sketch.1;5)));None:();Cf12:());"
        "Face:(Brp:(Pad.1;0:(Brp:(Sketch.1;6)));None:();Cf12:());"
        "None:(Limits1:();Limits2:());Cf12:());EdgeFillet.1_ResultOUT;Z0;G8782"
    )
    edge_2 = part.create_reference_from_name(
        "Edge:(Face:(Brp:(Pad.1;0:(Brp:(Sketch.1;7)));None:();Cf12:());"
        "Face:(Brp:(Pad.1;0:(Brp:(Sketch.1;4)));None:();Cf12:());"
        "None:(Limits1:();Limits2:());Cf12:());EdgeFillet.1_ResultOUT;Z0;G8782"
    )
    exhaust_fillet = shpfac.add_new_solid_edge_fillet_with_constant_radius(
        edge_1,
        cat_fillet_edge_propagation.index("catTangencyFilletEdgePropagation"),
        15.0,
    )
    exhaust_fillet.add_object_to_fillet(edge_2)
    document.part.update()

    # print("# ----- Inlet mounting point created")

    # ------------------------------------------------------------------ #
    # Rectangular pattern of inlets (still 4 instances!)
    # ------------------------------------------------------------------ #
    Ydir = hsf.add_new_direction_by_coord(0, 1, 0)

    selection.clear()
    selection.add(exhaust)
    selection.add(exhaust_FILLET)
    selection.add(exhaust_fillet)

    FILLET_pattern_Y = shpfac.add_new_rect_pattern(
        selection,
        4,          # number of instances (fixed to keep topology)
        0,
        pattern_spacing_Y,
        1,
        1,
        1,
        Ydir,
        nothing,
        True,
        True,
        0,
    )
    selection.clear()
    document.part.update()

    # print("# ----- Inlet patern created")

    # ------------------------------------------------------------------ #
    # Center points for each exhaust (as in original)
    # ------------------------------------------------------------------ #
    exhaust_pts_1 = []

    exhaust_hole_1 = part.create_reference_from_name(
        "Edge:(Face:(Brp:(Pad.1;2);None:();Cf12:());"
        "Face:(Brp:(Pad.1;0:(Brp:(Sketch.1;1)));None:();Cf12:());"
        "None:(Limits1:();Limits2:());Cf12:());RectPattern.1_ResultOUT;Z0;G8782"
    )
    exhaust_hole_2 = part.create_reference_from_name(
        "Edge:(Face:(Brp:(RectPattern.1_ResultOUT;1-0:(Brp:(Pad.1;2)));None:();Cf12:());"
        "Face:(Brp:(RectPattern.1_ResultOUT;1-0:(Brp:(Pad.1;0:(Brp:(Sketch.1;1)))));None:();Cf12:());"
        "None:(Limits1:();Limits2:());Cf12:());RectPattern.1_ResultOUT;Z0;G8782"
    )
    exhaust_hole_3 = part.create_reference_from_name(
        "Edge:(Face:(Brp:(RectPattern.1_ResultOUT;2-0:(Brp:(Pad.1;2)));None:();Cf12:());"
        "Face:(Brp:(RectPattern.1_ResultOUT;2-0:(Brp:(Pad.1;0:(Brp:(Sketch.1;1)))));None:();Cf12:());"
        "None:(Limits1:();Limits2:());Cf12:());RectPattern.1_ResultOUT;Z0;G8782"
    )
    exhaust_hole_4 = part.create_reference_from_name(
        "Edge:(Face:(Brp:(RectPattern.1_ResultOUT;3-0:(Brp:(Pad.1;2)));None:();Cf12:());"
        "Face:(Brp:(RectPattern.1_ResultOUT;3-0:(Brp:(Pad.1;0:(Brp:(Sketch.1;1)))));None:();Cf12:());"
        "None:(Limits1:();Limits2:());Cf12:());RectPattern.1_ResultOUT;Z0;G8782"
    )


    exhaust_holes = [
        exhaust_hole_1,
        exhaust_hole_2,
        exhaust_hole_3,
        exhaust_hole_4
    ]

    for i in range(4):
        hole_ref = exhaust_holes[i]  
        pt = hsf.add_new_point_center(hole_ref)
        pt.name = f"exhaust_{i+1}_pt_1"
        construction_elements.append_hybrid_shape(pt)

        exhaust_pts_1.append(pt)
        pt1[i+1] = pt                           # FIXED
             # global reference
       # variable form (REQUIRED)



    document.part.update()

    # ------------------------------------------------------------------ #
    # Outlet support (plane, sketch, pad, fillet) – unchanged
    # ------------------------------------------------------------------ #
    plane_outlet = hsf.add_new_plane_offset(plane_YZ, plane_outlet_offset, True)
    plane_outlet.name = "plane_outlet"
    construction_elements.append_hybrid_shape(plane_outlet)
    document.part.update()

    part.in_work_object = partbody
    sketch_2 = sketches.add(plane_outlet)
    sketch_2.name = "outlet"
    ske2D_2 = sketch_2.open_edition()

    # mid X between inlets 2 and 3
    exhaust_2_pt_1_coor = exhaust_pts_1[1].get_coordinates()
    exhaust_3_pt_1_coor = exhaust_pts_1[2].get_coordinates()

    x_mid = (exhaust_3_pt_1_coor[1] + exhaust_2_pt_1_coor[1]) / 2.0

    # Outlet circle
    ske2D_2.create_closed_circle(x_mid, outlet_h, exhaust_rad)

    # Outlet mounting points
    ske2D_2.create_closed_circle(x_mid, outlet_h + mnt_dist - 5.0, mnt_rad)
    ske2D_2.create_closed_circle(
        x_mid + mnt_out_dist * np.cos(mnt_out_angle),
        outlet_h - mnt_out_dist * np.sin(mnt_out_angle),
        mnt_rad,
    )
    ske2D_2.create_closed_circle(
        x_mid - mnt_out_dist * np.cos(mnt_out_angle),
        outlet_h - mnt_out_dist * np.sin(mnt_out_angle),
        mnt_rad,
    )

    # Triangle
    triang_p1 = (x_mid, outlet_h + triang_dist)
    triang_p2 = (
        x_mid + triang_dist * np.cos(mnt_out_angle),
        outlet_h - triang_dist * np.sin(mnt_out_angle),
    )
    triang_p3 = (
        x_mid - triang_dist * np.cos(mnt_out_angle),
        outlet_h - triang_dist * np.sin(mnt_out_angle),
    )

    ske2D_2.create_line(*triang_p1, *triang_p2)
    ske2D_2.create_line(*triang_p2, *triang_p3)
    ske2D_2.create_line(*triang_p3, *triang_p1)

    sketch_2.close_edition()
    document.part.update()

    # Hide outlet plane, pad outlet, fillet edges – all as original
    selection.clear()
    selection.add(plane_outlet)
    selection.vis_properties.set_show(1)
    selection.clear()

    outlet = shpfac.add_new_pad(sketch_2, pad_thickness_out)
    outlet.direction_orientation = cat_prism_orientation.index("catRegularOrientation")
    outlet.name = "outlet"
    document.part.update()

    outlet_edge_1 = part.create_reference_from_name(
        "Edge:(Face:(Brp:(Pad.2;0:(Brp:(Sketch.2;7)));None:();Cf12:());"
        "Face:(Brp:(Pad.2;0:(Brp:(Sketch.2;5)));None:();Cf12:());"
        "None:(Limits1:();Limits2:());Cf12:());Pad.2_ResultOUT;Z0;G8782"
    )
    outlet_edge_2 = part.create_reference_from_name(
        "Edge:(Face:(Brp:(Pad.2;0:(Brp:(Sketch.2;5)));None:();Cf12:());"
        "Face:(Brp:(Pad.2;0:(Brp:(Sketch.2;6)));None:();Cf12:());"
        "None:(Limits1:();Limits2:());Cf12:());Pad.2_ResultOUT;Z0;G8782"
    )
    outlet_edge_3 = part.create_reference_from_name(
        "Edge:(Face:(Brp:(Pad.2;0:(Brp:(Sketch.2;6)));None:();Cf12:());"
        "Face:(Brp:(Pad.2;0:(Brp:(Sketch.2;7)));None:();Cf12:());"
        "None:(Limits1:();Limits2:());Cf12:());Pad.2_ResultOUT;Z0;G8782"
    )
    outlet_fillet = shpfac.add_new_solid_edge_fillet_with_constant_radius(
        outlet_edge_1,
        cat_fillet_edge_propagation.index("catTangencyFilletEdgePropagation"),
        10.0,
    )
    outlet_fillet.add_object_to_fillet(outlet_edge_2)
    outlet_fillet.add_object_to_fillet(outlet_edge_3)
    document.part.update()

    outlet_hole = part.create_reference_from_name(
        "Edge:(Face:(Brp:(Pad.2;2);None:();Cf12:());"
        "Face:(Brp:(Pad.2;0:(Brp:(Sketch.2;1)));None:();Cf12:());"
        "None:(Limits1:();Limits2:());Cf12:());EdgeFillet.3_ResultOUT;Z0;G8782"
    )
    outlet_pt = hsf.add_new_point_center(outlet_hole)
    outlet_pt.name = "outlet_pt"
    construction_elements.append_hybrid_shape(outlet_pt)
    document.part.update()

    # print("# ----- Exhaust outlet created")

    # ------------------------------------------------------------------ #
    # Points along pipes & corners, sweeps, close surface & shell
    # ------------------------------------------------------------------ #
    # Create points above each inlet (FIXED)
    for i in range(4):
        idx = i + 1

        pt2_up = hsf.add_new_point_coord_with_reference(
            0, 0, z_offset_inlet_top, pt1[idx]    # <-- MUST use pt1
        )
        pt2_up.name = f"exhaust_{idx}_pt_2"
        construction_elements.append_hybrid_shape(pt2_up)

        pt2[idx] = pt2_up                        # save in dictionary
          # global reference


    exhaust_pt_3 = hsf.add_new_point_coord_with_reference(
        meet_offset_x, 0, 0, outlet_pt
    )
    exhaust_pt_3.name = "exhaust_pt_3"
    construction_elements.append_hybrid_shape(exhaust_pt_3)
    document.part.update()

    # Lines + corners
    for i in range(4):
        ii = str(i + 1)

        sec1 = hsf.add_new_line_pt_pt(
           pt1[int(ii)], pt2[int(ii)]
        )
        sec1.name = f"pipe_{ii}_sec_1"
        construction_elements.append_hybrid_shape(sec1)
        pipe_sec_1[int(ii)] = sec1

        sec2 = hsf.add_new_line_pt_pt(pt2[int(ii)], exhaust_pt_3)
        sec2.name = f"pipe_{ii}_sec_2"
        construction_elements.append_hybrid_shape(sec2)
        pipe_sec_2[int(ii)] = sec2

        sec3 = hsf.add_new_line_pt_pt(exhaust_pt_3, outlet_pt)
        sec3.name = f"pipe_{ii}_sec_3"
        construction_elements.append_hybrid_shape(sec3)
        pipe_sec_3[int(ii)] = sec3

    document.part.update()

    # Corners
    for i in range(4):
        ii = str(i + 1)

        plane_c1 = hsf.add_new_plane2_lines(
            pipe_sec_1[int(ii)], pipe_sec_2[int(ii)]

        )
        plane_c1.name = f"plane_corner_{ii}_1"
        construction_elements.append_hybrid_shape(plane_c1)
        vars()[f"plane_corner_{ii}_1"] = plane_c1

        corner1 = hsf.add_new_corner(
            pipe_sec_1[int(ii)],
            pipe_sec_2[int(ii)],
            plane_c1,
            turn_rad,
            1,
            1,
            True,
        )
        corner1.name = f"corner_{ii}_1"
        construction_elements.append_hybrid_shape(corner1)
        vars()[f"corner_{ii}_1"] = corner1

        plane_c2 = hsf.add_new_plane2_lines(
            pipe_sec_2[int(ii)], pipe_sec_3[int(ii)]
        )
        plane_c2.name = f"plane_corner_{ii}_2"
        construction_elements.append_hybrid_shape(plane_c2)
        vars()[f"plane_corner_{ii}_2"] = plane_c2

        corner2 = hsf.add_new_corner(
            corner1,
            pipe_sec_3[int(ii)],
            plane_c2,
            turn_rad,
            1,
            1,
            True,
        )
        corner2.name = f"corner_{ii}_2"
        construction_elements.append_hybrid_shape(corner2)
        corner_2[int(ii)] = corner2

        # Hide construction elements same as original
        selection.clear()
        selection.add(plane_c1)
        selection.add(plane_c2)
        selection.add(pipe_sec_1[int(ii)])
        selection.add(pipe_sec_2[int(ii)])
        selection.add(pipe_sec_3[int(ii)])
        selection.add(corner1)
        selection.vis_properties.set_show(1)
        selection.clear()

    document.part.update()
    # print("# ----- Pipe curves created")

    # Larger circles at inlet
    plane_inlet_holes = hsf.add_new_plane1_curve(exhaust_hole_1)
    plane_inlet_holes.name = "plane_inlet_holes"
    construction_elements.append_hybrid_shape(plane_inlet_holes)

    for i in range(4):
        ii = str(i + 1)
        circ = hsf.add_new_circle_ctr_rad(
            pt1[int(ii)], plane_inlet_holes, False, sweep_exhaust_rad
        )
        circ.name = f"exhaust_{ii}_sweep"
        construction_elements.append_hybrid_shape(circ)
        sweep_circle[int(ii)] = circ

    document.part.update()

    # Pipe surfaces
    for i in range(4):
        ii = str(i + 1)
        pipe_surf = hsf.add_new_sweep_explicit(
            sweep_circle[int(ii)], corner_2[int(ii)]
        )
        pipe_surface[int(ii)] = pipe_surf

        construction_elements.append_hybrid_shape(pipe_surf)
        vars()[f"pipe_{ii}"] = pipe_surf

    document.part.update()
    # print("# ----- Pipe surfaces created")

    # Hide construction
    selection.clear()
    for i in range(4):
        ii = str(i + 1)
        selection.add(pt1[int(ii)])
        selection.add(pt2[int(ii)])
        selection.add(corner_2[int(ii)])
        selection.add(pipe_surface[int(ii)])
        selection.add(sweep_circle[int(ii)])
    selection.add(exhaust_pt_3)
    selection.add(outlet_pt)
    selection.add(plane_inlet_holes)
    selection.vis_properties.set_show(1)
    selection.clear()

    # Solid from surfaces
    part.in_work_object = partbody
    for i in range(4):
        ii = str(i + 1)
        cs = shpfac.add_new_close_surface(pipe_surface[int(ii)])
        cs.name = f"close_surf_{ii}"
        close_surf[int(ii)] = cs

    document.part.update()

    # Shell (faces references from original script)
    exhaust_face_1 = part.create_reference_from_name(
        "Face:(Brp:(CloseSurface.1;(Brp:(GSMSweep.1;(Brp:(GSMLine.1;1);"
        "Brp:(GSMSweep.1_GSMPositionTransfo.1;(Brp:(GSMCircle.1)))))));"
        "None:();Cf12:());CloseSurface.4_ResultOUT;Z0;G8782"
    )
    exhaust_face_2 = part.create_reference_from_name(
        "Face:(Brp:(CloseSurface.2;(Brp:(GSMSweep.2;(Brp:(GSMLine.4;1);"
        "Brp:(GSMSweep.2_GSMPositionTransfo.1;(Brp:(GSMCircle.2)))))));"
        "None:();Cf12:());CloseSurface.4_ResultOUT;Z0;G8782"
    )
    exhaust_face_3 = part.create_reference_from_name(
        "Face:(Brp:(CloseSurface.3;(Brp:(GSMSweep.3;(Brp:(GSMLine.7;1);"
        "Brp:(GSMSweep.3_GSMPositionTransfo.1;(Brp:(GSMCircle.3)))))));"
        "None:();Cf12:());CloseSurface.4_ResultOUT;Z0;G8782"
    )
    exhaust_face_4 = part.create_reference_from_name(
        "Face:(Brp:(CloseSurface.4;(Brp:(GSMSweep.4;(Brp:(GSMLine.10;1);"
        "Brp:(GSMSweep.4_GSMPositionTransfo.1;(Brp:(GSMCircle.4)))))));"
        "None:();Cf12:());CloseSurface.4_ResultOUT;Z0;G8782"
    )
    outlet_face = part.create_reference_from_b_rep_name(
        "RSur:(Face:(Brp:((Brp:(CloseSurface.4;(Brp:(GSMSweep.4;(Brp:(GSMLine.12;2);"
        "Brp:(GSMSweep.4_GSMPositionTransfo.1;(Brp:(GSMCircle.4)))))));"
        "Brp:(CloseSurface.3;(Brp:(GSMSweep.3;(Brp:(GSMLine.9;2);"
        "Brp:(GSMSweep.3_GSMPositionTransfo.1;(Brp:(GSMCircle.3)))))));"
        "Brp:(CloseSurface.2;(Brp:(GSMSweep.2;(Brp:(GSMLine.6;2);"
        "Brp:(GSMSweep.2_GSMPositionTransfo.1;(Brp:(GSMCircle.2)))))));"
        "Brp:(CloseSurface.1;(Brp:(GSMSweep.1;(Brp:(GSMLine.3;2);"
        "Brp:(GSMSweep.1_GSMPositionTransfo.1;(Brp:(GSMCircle.1)))))))));"
        "None:();Cf12:());WithPermanentBody;WithoutBuildError;"
        "WithSelectingFeatureSupport;MFBRepVersion_CXR29)",
        close_surf[4],  # type: ignore[name-defined]
    )

    shell_pipes = shpfac.add_new_shell(exhaust_face_1, shell_thickness, shell_thickness)
    shell_pipes.add_face_to_remove(exhaust_face_2)
    shell_pipes.add_face_to_remove(exhaust_face_3)
    shell_pipes.add_face_to_remove(exhaust_face_4)
    shell_pipes.add_face_to_remove(outlet_face)
    document.part.update()

    # print("# ----- Solid walls created")
    # print("")
    # print("# --------------------------- #")
    # print("# ----- End of execution")
    # print("# --------------------------- #")
    # print("")

if __name__ == "__main__":
    import argparse
    import json
    import sys

    parser = argparse.ArgumentParser(description="Generate Manifold with specific parameters.")
    parser.add_argument("--params", type=str, help="JSON string of parameters", default="{}")
    args = parser.parse_args()

    try:
        cfg = json.loads(args.params)
    except Exception as e:
        print(f"Error parsing params: {e}")
        cfg = {}

    generate_manifold(cfg)