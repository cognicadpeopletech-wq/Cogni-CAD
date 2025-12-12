#!/usr/bin/env python3
"""
Silent parametric CATIA wheel-rim generator.
car_wheel_rim_dynamic.py
- Builds full geometry: rim, spokes, center hole, lug holes.
- Takes CLI parameters (outer-radius, inner-radius, width, etc.).
- Prints ONLY one JSON object to stdout:
    {"mode": "wheel_rim", "ok": true/false, "params": {...}, "error": "..."}
"""
 
import argparse
import json
import sys
 
# ---------- CATIA availability ----------
try:
    from pycatia import catia
    from pycatia.mec_mod_interfaces.part_document import PartDocument
    from pycatia.enumeration.enumeration_types import (
        cat_limit_mode,
        cat_prism_orientation,
        cat_fillet_edge_propagation,
    )
    from pycatia.scripts.vba import vba_nothing
 
    HAS_CATIA = True
except Exception:
    HAS_CATIA = False
 
 
# ---------- CLI args ----------
def parse_args():
    p = argparse.ArgumentParser(description="Parametric CATIA wheel rim generator")
 
    # Rim
    p.add_argument("--outer-radius", type=float, default=245.0)
    p.add_argument("--inner-radius", type=float, default=220.0)
    p.add_argument("--rim-width", type=float, default=247.0)
    p.add_argument("--rim-thickness", type=float, default=5.0)
 
    # Spokes / sector
    p.add_argument("--revolve-angle", type=float, default=22.5)
    p.add_argument("--spoke-count", type=int, default=8)
 
    # Center & lug holes
    p.add_argument("--center-hole-radius", type=float, default=30.0)
    p.add_argument("--lug-hole-radius", type=float, default=5.0)
    p.add_argument("--lug-hole-count", type=int, default=5)
    p.add_argument("--lug-hole-offset", type=float, default=40.0)
 
    # Fillet
    p.add_argument("--fillet-radius", type=float, default=3.0)
 
    return p.parse_args()
 
 
# ---------- Main wheel builder ----------
def build_wheel(args):
    if not HAS_CATIA:
        return False, "CATIA not available (pycatia import failed)"
 
    try:
        # ----- Base setup -----
        caa = catia()
        app = caa.application
        docs = app.documents
 
        # close docs safely (reverse order)
        for i in range(docs.count, 0, -1):
            try:
                docs.item(i).close()
            except Exception:
                pass
 
        docs.add("Part")
        doc: PartDocument = app.active_document
        part = doc.part
        partbody = part.bodies[0]
        hybrid_bodies = part.hybrid_bodies
        hsf = part.hybrid_shape_factory
        shf = part.shape_factory
        sel = doc.selection
        try:
            while partbody.shapes.count > 0:
                partbody.shapes.item(1).delete()
        except Exception:
            pass
 
        # Delete all hybrid bodies (construction elements)
        try:
            for i in range(hybrid_bodies.count, 0, -1):
                hb = hybrid_bodies.item(i)
                hybrid_bodies.remove(hb)
        except Exception:
            pass
 
        doc.part.update()
        # Planes
        plane_XY = part.origin_elements.plane_xy
        plane_YZ = part.origin_elements.plane_yz
        plane_ZX = part.origin_elements.plane_zx
 
        # hide planes
        sel.clear()
        for pl in (plane_XY, plane_YZ, plane_ZX):
            sel.add(pl)
        sel.vis_properties.set_show(1)
        sel.clear()
 
        part.in_work_object = partbody
 
        # ---------- Scaling ----------
        REF_OUT = 245.0
        REF_IN = 220.0
        REF_Z = 247.0
 
        rad_scale = args.outer_radius / REF_OUT if REF_OUT else 1.0
        z_scale = args.rim_width / REF_Z if REF_Z else 1.0
 
        # construction hybrid body
        construction_elements = hybrid_bodies.add()
        construction_elements.name = "construction_elements"
 
        # helper point function
        def p(y, z):
            if abs(y - REF_IN) < 5.0:
                ry = args.inner_radius
            else:
                ry = rad_scale * y
            return hsf.add_new_point_coord(0, ry, z_scale * z)
 
        # ---------- Rim profile polyline ----------
        rim_line = hsf.add_new_polyline()
        pts = [
            (245, 0),
            (245, 3),
            (232, 20),
            (232, 40),
            (220, 60),
            (220, 138),
            (232, 158),
            (232, 222),
            (245, 242),
            (245, 247),
        ]
        for idx, (yy, zz) in enumerate(pts, 1):
            rim_line.insert_element(p(yy, zz), idx)
        rim_line.closure = False
        construction_elements.append_hybrid_shape(rim_line)
        doc.part.update()
 
        Zdir = hsf.add_new_direction_by_coord(0, 0, 1)
 
        rim_surface = hsf.add_new_revol(rim_line, 0, args.revolve_angle, Zdir)
        construction_elements.append_hybrid_shape(rim_surface)
        doc.part.update()
 
        # ---------- spoke / cap construction curves ----------
        line1 = hsf.add_new_polyline()
        line1.insert_element(p(220, 138), 1)
        line1.insert_element(p(232, 158), 2)
        line1.insert_element(p(232, 222), 3)
        line1.insert_element(p(245, 242), 4)
        line1.insert_element(p(245, 247), 5)
        construction_elements.append_hybrid_shape(line1)
 
        line2 = hsf.add_new_polyline()
        line2.insert_element(p(0, 270), 1)
        line2.insert_element(p(0, 138), 2)
        line2.insert_element(p(50, 138), 3)
        line2.insert_element(p(50, 148), 4)
        construction_elements.append_hybrid_shape(line2)
 
        spline1 = hsf.add_new_spline()
        spline1.add_point(p(0, 270))
        spline1.add_point(p(20, 270))
        spline1.add_point(p(121, 280))
        spline1.add_point(p(181, 271))
        spline1.add_point(p(245, 247))
        construction_elements.append_hybrid_shape(spline1)
 
        spline2 = hsf.add_new_spline()
        spline2.add_point_with_constraint_explicit(p(50, 148), Zdir, 1.0, False, vba_nothing, 1)
        spline2.add_point(p(110, 190))
        spline2.add_point(p(190, 180))
        spline2.add_point(p(220, 138))
        construction_elements.append_hybrid_shape(spline2)
 
        doc.part.update()
 
        joined = hsf.add_new_join(line1, line2)
        joined.add_element(spline1)
        joined.add_element(spline2)
        construction_elements.append_hybrid_shape(joined)
        doc.part.update()
 
        # hide some construction
        sel.clear()
        for el in (line1, line2, spline1, spline2):
            sel.add(el)
        sel.vis_properties.set_show(1)
        sel.clear()
 
        # ---------- base solid via shaft ----------
        part.in_work_object = partbody
        shaft1 = shf.add_new_shaft_from_ref(joined)
        shaft1.revolute_axis = Zdir
        shaft1.first_angle.value = 0
        shaft1.second_angle.value = args.revolve_angle
        doc.part.update()
 
        # ---------- spoke cutting profile ----------
        line_y = hsf.add_new_line_pt_pt(p(0, 0), p(500, 0))
        construction_elements.append_hybrid_shape(line_y)
        doc.part.update()
 
        line_ang = hsf.add_new_line_angle(
            line_y, plane_XY, p(0, 0), True,
            0, rad_scale * 500,
            -args.revolve_angle,
            False
        )
        construction_elements.append_hybrid_shape(line_ang)
        doc.part.update()
 
        arc1 = hsf.add_new_circle_ctr_pt_with_angles(
            p(100, 0), p(70, 0),
            plane_XY, True,
            0, 90
        )
        construction_elements.append_hybrid_shape(arc1)
        doc.part.update()
 
        tang1 = hsf.add_new_line_tangency(
            arc1,
            hsf.add_new_point_on_curve_from_percent(arc1, 1.0, False),
            0, rad_scale * 200, False
        )
        construction_elements.append_hybrid_shape(tang1)
        doc.part.update()
 
        arc2 = hsf.add_new_circle_ctr_pt_with_angles(
            hsf.add_new_point_on_curve_from_percent(line_ang, 0.3, False),
            hsf.add_new_point_on_curve_from_percent(line_ang, 0.265, False),
            plane_XY, False,
            0, args.revolve_angle - 90
        )
        construction_elements.append_hybrid_shape(arc2)
        doc.part.update()
 
        tang2 = hsf.add_new_line_tangency(
            arc2,
            hsf.add_new_point_on_curve_from_percent(arc2, 1.0, True),
            0, rad_scale * 200, True
        )
        construction_elements.append_hybrid_shape(tang2)
        doc.part.update()
 
        split1 = hsf.add_new_hybrid_split(line_y, p(70, 0), True)
        split1.both_sides_mode = False
        split1.invert_orientation()
        construction_elements.append_hybrid_shape(split1)
        doc.part.update()
 
        split2 = hsf.add_new_hybrid_split(
            line_ang,
            hsf.add_new_point_on_curve_from_percent(line_ang, 0.265, False),
            True
        )
        split2.both_sides_mode = False
        split2.invert_orientation()
        construction_elements.append_hybrid_shape(split2)
        doc.part.update()
 
        closure1 = hsf.add_new_line_pt_pt(
            hsf.add_new_point_on_curve_from_percent(line_ang, 1, False),
            hsf.add_new_point_on_curve_from_percent(line_y, 1, False)
        )
        construction_elements.append_hybrid_shape(closure1)
        doc.part.update()
 
        closure2 = hsf.add_new_line_pt_pt(
            hsf.add_new_point_on_curve_from_percent(tang1, 1, False),
            hsf.add_new_point_on_curve_from_percent(tang2, 1, True)
        )
        construction_elements.append_hybrid_shape(closure2)
        doc.part.update()
 
        half_prof = hsf.add_new_join(split1, split2)
        for el in (arc1, arc2, tang1, tang2, closure1, closure2):
            half_prof.add_element(el)
        construction_elements.append_hybrid_shape(half_prof)
        doc.part.update()
 
        # hide extra construction
        sel.clear()
        for el in (split1, split2, arc1, arc2, tang1, tang2,
                   line_y, line_ang, closure1, closure2):
            sel.add(el)
        sel.vis_properties.set_show(1)
        sel.clear()
 
        # ---------- spoke pocket cut ----------
        part.in_work_object = partbody
        pocket = shf.add_new_pocket_from_ref(half_prof, 100)
        pocket.direction_orientation = cat_prism_orientation.index("catRegularOrientation")
        pocket.first_limit.limit_mode = cat_limit_mode.index("catUpToLastLimit")
        pocket.second_limit.limit_mode = cat_limit_mode.index("catUpToLastLimit")
        doc.part.update()
 
        # ---------- rim solid via thick surface ----------
        part.in_work_object = partbody
        rim_solid = shf.add_new_thick_surface(rim_surface, 0, args.rim_thickness, 0)
        rim_solid.name = "rim_solid"
        doc.part.update()
 
        # ---------- fillets (soft fail) ----------
        try:
            edge1 = part.create_reference_from_name(
                "Edge:(Face:(Brp:(Shaft.1;0:(Brp:(GSMCurve.1)));None:();Cf11:());"
                "Face:(Brp:(Pocket.1;0:(Brp:(GSMLine.4)));None:();Cf11:());"
                "None:(Limits1:();Limits2:());Cf11:());ThickSurface.1_ResultOUT;Z0;G8226"
            )
            edge2 = part.create_reference_from_name(
                "Edge:(Face:(Brp:(Pocket.1;0:(Brp:(GSMLine.3)));None:();Cf11:());"
                "Face:(Brp:(Shaft.1;0:(Brp:(GSMCurve.1)));None:();Cf11:());"
                "None:(Limits1:();Limits2:());Cf11:());ThickSurface.1_ResultOUT;Z0;G8226"
            )
            fillet = shf.add_new_solid_edge_fillet_with_constant_radius(
                edge1,
                cat_fillet_edge_propagation.index("catTangencyFilletEdgePropagation"),
                args.fillet_radius
            )
            fillet.add_object_to_fillet(edge2)
            doc.part.update()
        except Exception:
            # ignore fillet failures due to topology changes
            pass
 
        # ---------- symmetry ----------
        mirror = shf.add_new_mirror(plane_YZ)
        doc.part.update()
 
        # ---------- circular pattern for spokes ----------
        part.in_work_object = partbody
        input_pattern = part.create_reference_from_object(partbody)
        ang_step = 360.0 / max(1, int(args.spoke_count))
 
        shf.add_new_circ_pattern(
            input_pattern,
            1,
            int(args.spoke_count),
            50,
            ang_step,
            1, 1,
            Zdir, Zdir,
            True, 0,
            True
        )
        doc.part.update()
 
        # ---------- center hole ----------
        center_pt = hsf.add_new_point_coord(0, 0, 0)
        main_hole = hsf.add_new_circle_ctr_rad_with_angles(
            center_pt,
            plane_XY,
            True,
            args.center_hole_radius,
            0, 360
        )
        construction_elements.append_hybrid_shape(main_hole)
        doc.part.update()
 
        part.in_work_object = partbody
        main_pocket = shf.add_new_pocket_from_ref(main_hole, 100)
        main_pocket.direction_orientation = cat_prism_orientation.index("catRegularOrientation")
        main_pocket.first_limit.limit_mode = cat_limit_mode.index("catUpToLastLimit")
        main_pocket.second_limit.limit_mode = cat_limit_mode.index("catUpToLastLimit")
        doc.part.update()
 
        # ---------- lug holes ----------
        lug_center = hsf.add_new_point_coord(0, args.lug_hole_offset, 0)
        lug_hole = hsf.add_new_circle_ctr_rad_with_angles(
            lug_center,
            plane_XY,
            True,
            args.lug_hole_radius,
            0, 360
        )
        construction_elements.append_hybrid_shape(lug_hole)
        doc.part.update()
 
        part.in_work_object = partbody
        lug_pocket = shf.add_new_pocket_from_ref(lug_hole, 100)
        lug_pocket.direction_orientation = cat_prism_orientation.index("catRegularOrientation")
        lug_pocket.first_limit.limit_mode = cat_limit_mode.index("catUpToLastLimit")
        lug_pocket.second_limit.limit_mode = cat_limit_mode.index("catUpToLastLimit")
        doc.part.update()
 
        # hide construction hybrid
        sel.clear()
        sel.add(construction_elements)
        sel.vis_properties.set_show(1)
        sel.clear()
 
        # circular pattern for lugs
        part.in_work_object = partbody
        lug_ang = 360.0 / max(1, int(args.lug_hole_count))
        shf.add_new_circ_pattern(
            lug_pocket,
            1,
            int(args.lug_hole_count),
            50,
            lug_ang,
            1, 1,
            Zdir, Zdir,
            True, 0,
            True
        )
        doc.part.update()
 
        return True, None
 
    except Exception as e:
        return False, str(e)
 
 
# ---------- MAIN: JSON only ----------
def main():
    args = parse_args()
 
    if not HAS_CATIA:
        print(json.dumps({
            "mode": "wheel_rim",
            "ok": False,
            "error": "CATIA / pycatia not available"
        }))
        return 1
 
    ok, err = build_wheel(args)
 
    if not ok:
        print(json.dumps({
            "mode": "wheel_rim",
            "ok": False,
            "error": str(err),
            "params": vars(args)
        }))
        return 1
 
    print(json.dumps({
        "mode": "wheel_rim",
        "ok": True,
        "params": vars(args)
    }))
    return 0
 
 
if __name__ == "__main__":
    sys.exit(main())
 
 