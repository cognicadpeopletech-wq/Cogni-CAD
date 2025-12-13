#!/usr/bin/env python3
"""
L-Brac.py - Parametric L-bracket script (PyCATIA / COM)

Change: pocket (hole) depth now uses thick_top_offset (TopOffset) instead of extrude_length.
All other behavior preserved.
"""

import time
import pythoncom
import argparse
import json
import os
from win32com.client import Dispatch, constants

# ---------------------------
# Defaults (same behavior as original)
# ---------------------------
DEFAULTS = {
    "point1": [0.0, 0.0, 0.0],
    "point2": [0.0, 50.0, 0.0],
    "point3": [0.0, 50.0, 50.0],
    "poly_radius_index": 2,
    "poly_radius_value": 5.0,
    "polyline_closure": False,
    "extrude_length": 30.0,
    "thick_top_offset": 5.0,
    "circle1": [15.0, 32.5, 5.0],
    "circle2": [15.0, 12.5, 5.0],
    # pocket_depth default kept for backward compatibility but will be overridden by thick_top_offset
    "pocket_depth": 20.0,
    "pocket_firstlimit": 5.0,
    "do_chamfer": True,
    "chamfer_dim": 1.0,
    "chamfer_angle": 45.0,
    "step_delay": 0.5
}

# ---------------------------
def load_params_from_json(path="params.json"):
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r") as f:
            data = json.load(f)
        return data
    except Exception:
        return {}

def parse_cli_args():
    parser = argparse.ArgumentParser(description="Parametric PyCATIA L-bracket")
    parser.add_argument("--params-file", help="Optional JSON file with params", default="params.json")
    parser.add_argument("--point1", help="x,y,z for point1", type=str)
    parser.add_argument("--point2", help="x,y,z for point2", type=str)
    parser.add_argument("--point3", help="x,y,z for point3", type=str)
    parser.add_argument("--poly_radius_index", type=int)
    parser.add_argument("--poly_radius_value", type=float)
    parser.add_argument("--extrude_len", type=float, help="extrude length (plate thickness)")
    parser.add_argument("--thick_top_offset", type=float, help="thick surface top offset")
    parser.add_argument("--circle1", help="x,y,r for circle1", type=str)
    parser.add_argument("--circle2", help="x,y,r for circle2", type=str)
    parser.add_argument("--pocket_depth", type=float)
    parser.add_argument("--pocket_firstlimit", type=float)
    parser.add_argument("--do_chamfer", type=int, choices=[0,1], help="1 = do chamfer, 0 = skip")
    parser.add_argument("--step_delay", type=float, help="sleep between steps (seconds)")
    args = parser.parse_args()
    params = {}
    def parse_triplet(s):
        if s is None:
            return None
        parts = [p.strip() for p in s.split(",")]
        try:
            return [float(parts[i]) for i in range(len(parts))]
        except Exception:
            return None

    if args.point1:
        p = parse_triplet(args.point1)
        if p: params["point1"] = p
    if args.point2:
        p = parse_triplet(args.point2)
        if p: params["point2"] = p
    if args.point3:
        p = parse_triplet(args.point3)
        if p: params["point3"] = p
    if args.poly_radius_index is not None:
        params["poly_radius_index"] = args.poly_radius_index
    if args.poly_radius_value is not None:
        params["poly_radius_value"] = args.poly_radius_value
    if args.extrude_len is not None:
        params["extrude_length"] = args.extrude_len
    if args.thick_top_offset is not None:
        params["thick_top_offset"] = args.thick_top_offset
    if args.circle1:
        c = parse_triplet(args.circle1)
        if c: params["circle1"] = c
    if args.circle2:
        c = parse_triplet(args.circle2)
        if c: params["circle2"] = c
    if args.pocket_depth is not None:
        params["pocket_depth"] = args.pocket_depth
    if args.pocket_firstlimit is not None:
        params["pocket_firstlimit"] = args.pocket_firstlimit
    if args.do_chamfer is not None:
        params["do_chamfer"] = bool(args.do_chamfer)
    if args.step_delay is not None:
        params["step_delay"] = args.step_delay

    return args.params_file, params

def merge_params(cli_params, file_params):
    merged = {}
    merged.update(DEFAULTS)
    for k, v in file_params.items():
        merged[k] = v
    for k, v in cli_params.items():
        merged[k] = v
    for key in ["point1","point2","point3","circle1","circle2"]:
        if key in merged and merged[key] is not None:
            merged[key] = [float(x) for x in merged[key]]
    merged["poly_radius_index"] = int(merged.get("poly_radius_index", DEFAULTS["poly_radius_index"]))
    merged["poly_radius_value"] = float(merged.get("poly_radius_value", DEFAULTS["poly_radius_value"]))
    merged["extrude_length"] = float(merged.get("extrude_length", DEFAULTS["extrude_length"]))
    merged["thick_top_offset"] = float(merged.get("thick_top_offset", DEFAULTS["thick_top_offset"]))
    merged["pocket_depth"] = float(merged.get("pocket_depth", DEFAULTS["pocket_depth"]))
    merged["pocket_firstlimit"] = float(merged.get("pocket_firstlimit", DEFAULTS["pocket_firstlimit"]))
    merged["do_chamfer"] = bool(merged.get("do_chamfer", DEFAULTS["do_chamfer"]))
    merged["step_delay"] = float(merged.get("step_delay", DEFAULTS["step_delay"]))
    return merged

# ---------------------------
def script1(catia_app, params):
    documents = catia_app.Documents
    part_document = documents.Add("Part")
    part = part_document.Part

    hybrid_shape_factory = part.HybridShapeFactory

    p1 = params["point1"]
    p2 = params["point2"]
    p3 = params["point3"]

    hybrid_shape_point_coord1 = hybrid_shape_factory.AddNewPointCoord(p1[0], p1[1], p1[2])
    bodies = part.Bodies
    body = bodies.Item("PartBody")
    body.InsertHybridShape(hybrid_shape_point_coord1)
    part.InWorkObject = hybrid_shape_point_coord1
    part.Update()

    hybrid_shape_point_coord2 = hybrid_shape_factory.AddNewPointCoord(p2[0], p2[1], p2[2])
    body.InsertHybridShape(hybrid_shape_point_coord2)
    part.InWorkObject = hybrid_shape_point_coord2
    part.Update()

    hybrid_shape_point_coord3 = hybrid_shape_factory.AddNewPointCoord(p3[0], p3[1], p3[2])
    body.InsertHybridShape(hybrid_shape_point_coord3)
    part.InWorkObject = hybrid_shape_point_coord3
    part.Update()

    hybrid_shape_polyline = hybrid_shape_factory.AddNewPolyline()
    reference1 = part.CreateReferenceFromObject(hybrid_shape_point_coord1)
    hybrid_shape_polyline.InsertElement(reference1, 1)
    reference2 = part.CreateReferenceFromObject(hybrid_shape_point_coord2)
    hybrid_shape_polyline.InsertElement(reference2, 2)
    try:
        hybrid_shape_polyline.SetRadius(params["poly_radius_index"], params["poly_radius_value"])
    except Exception:
        pass
    reference3 = part.CreateReferenceFromObject(hybrid_shape_point_coord3)
    hybrid_shape_polyline.InsertElement(reference3, 3)
    hybrid_shape_polyline.Closure = params.get("polyline_closure", False)
    body.InsertHybridShape(hybrid_shape_polyline)
    part.InWorkObject = hybrid_shape_polyline
    part.Update()

def script2(catia_app, params):
    part_document = catia_app.ActiveDocument
    part = part_document.Part

    hybrid_shape_factory = part.HybridShapeFactory
    hybrid_shape_direction = hybrid_shape_factory.AddNewDirectionByCoord(0.0, 0.0, 0.0)

    bodies = part.Bodies
    body = bodies.Item("PartBody")
    hybrid_shapes = body.HybridShapes
    try:
        hybrid_shape_polyline = hybrid_shapes.Item("Polyline.1")
    except Exception:
        hybrid_shape_polyline = None
        for i in range(1, hybrid_shapes.Count + 1):
            try:
                sh = hybrid_shapes.Item(i)
                if getattr(sh, "Name", "").lower().startswith("polyline"):
                    hybrid_shape_polyline = sh
                    break
            except Exception:
                continue
        if hybrid_shape_polyline is None:
            return

    reference = part.CreateReferenceFromObject(hybrid_shape_polyline)
    extr_len = params.get("extrude_length", DEFAULTS["extrude_length"])
    try:
        hybrid_shape_extrude = hybrid_shape_factory.AddNewExtrude(reference, extr_len, 0.0, hybrid_shape_direction)
        hybrid_shape_extrude.SymmetricalExtension = 0
        body.InsertHybridShape(hybrid_shape_extrude)
        part.InWorkObject = hybrid_shape_extrude
        part.Update()
    except Exception:
        pass

def script3(catia_app, params):
    part_document = catia_app.ActiveDocument
    part = part_document.Part
    shape_factory = part.ShapeFactory
    reference_empty = part.CreateReferenceFromName("")
    try:
        thick_surface = shape_factory.AddNewThickSurface(reference_empty, 0, 1.0, 0.0)
    except Exception:
        return
    bodies = part.Bodies
    body = bodies.Item("PartBody")
    hybrid_shapes = body.HybridShapes
    try:
        hybrid_shape_extrude = hybrid_shapes.Item("Extrude.1")
    except Exception:
        hybrid_shape_extrude = None
        for i in range(1, hybrid_shapes.Count + 1):
            try:
                sh = hybrid_shapes.Item(i)
                if getattr(sh, "Name", "").lower().startswith("extrude"):
                    hybrid_shape_extrude = sh
                    break
            except Exception:
                continue
        if hybrid_shape_extrude is None:
            return

    try:
        reference2 = part.CreateReferenceFromObject(hybrid_shape_extrude)
        thick_surface.Surface = reference2
        length_top = thick_surface.TopOffset
        try:
            length_top.Value = params.get("thick_top_offset", DEFAULTS["thick_top_offset"])
        except Exception:
            pass
        part.Update()
    except Exception:
        pass

    selection = part_document.Selection
    vis_props = selection.VisProperties
    try:
        for item_name in ["Point.1", "Point.2", "Point.3", "Polyline.1", "Extrude.1"]:
            try:
                hybrid_item = hybrid_shapes.Item(item_name)
                selection.Add(hybrid_item)
            except Exception:
                pass
        try:
            vis_props.SetShow(1)
        except Exception:
            pass
    except Exception:
        pass
    selection.Clear()
    part.Update()

def _create_circle_in_sketch(factory2d, cx, cy, r):
    try:
        pt = factory2d.CreatePoint(float(cx), float(cy))
        circle = factory2d.CreateClosedCircle(float(cx), float(cy), float(r))
        circle.CenterPoint = pt
        return circle
    except Exception:
        return None

def script4(catia_app, params):
    part_document = catia_app.ActiveDocument
    part = part_document.Part

    bodies = part.Bodies
    body = bodies.Item("PartBody")
    sketches = body.Sketches

    face_ref_string = (
        "Selection_RSur:(Face:(Brp:(ThickSurface.1;1:(Brp:(GSMExtrude.1;0:"
        "(Brp:(GSMLineCorner.1;(Brp:(GSMPoint.1);Brp:(GSMPoint.2)))))));None:();Cf12:());"
        "ThickSurface.1_ResultOUT;Z0;G9219)"
    )
    try:
        reference1 = part.CreateReferenceFromName(face_ref_string)
        sketch1 = sketches.Add(reference1)
    except Exception:
        sketch1 = None
        try:
            shapes = body.Shapes
            for i in range(1, shapes.Count + 1):
                try:
                    shp = shapes.Item(i)
                    faces = getattr(shp, "Faces", None)
                    if faces and faces.Count >= 1:
                        face = faces.Item(1)
                        ref_face = part.CreateReferenceFromObject(face)
                        sketch1 = sketches.Add(ref_face)
                        break
                except Exception:
                    continue
        except Exception:
            pass
    if sketch1 is None:
        return

    abs_axis = [0.0, 0.0, 0.0, 1.0, 0.0, 0.0, -0.0, 1.0, 0.0]
    try:
        sketch1.SetAbsoluteAxisData(abs_axis)
    except Exception:
        pass
    part.InWorkObject = sketch1

    factory2d = sketch1.OpenEdition()
    c1 = params.get("circle1", DEFAULTS["circle1"])
    c2 = params.get("circle2", DEFAULTS["circle2"])

    circle1 = None
    circle2 = None
    try:
        if c1 and len(c1) >= 3 and float(c1[2]) >= 0:
            circle1 = _create_circle_in_sketch(factory2d, c1[0], c1[1], c1[2])
    except Exception:
        circle1 = None

    try:
        if c2 and len(c2) >= 3 and float(c2[2]) >= 0:
            circle2 = _create_circle_in_sketch(factory2d, c2[0], c2[1], c2[2])
    except Exception:
        circle2 = None

    sketch1.CloseEdition()
    part.InWorkObject = sketch1
    part.Update()

    # --------- CHANGED: use thick_top_offset as pocket depth ----------
    shape_factory = part.ShapeFactory
    # pocket depth is now taken from thick_top_offset (TopOffset)
    pocket_depth_to_use = float(params.get("thick_top_offset", DEFAULTS["thick_top_offset"]))
    try:
        if circle1 is not None:
            pocket1 = shape_factory.AddNewPocket(sketch1, pocket_depth_to_use)
            try:
                pocket1.FirstLimit.Dimension.Value = pocket_depth_to_use
            except Exception:
                pass
            part.Update()
        if circle2 is not None:
            pocket2 = shape_factory.AddNewPocket(sketch1, pocket_depth_to_use)
            try:
                pocket2.FirstLimit.Dimension.Value = pocket_depth_to_use
            except Exception:
                pass
            part.Update()
    except Exception:
        pass
    # ----------------------------------------------------------------

    if params.get("do_chamfer", DEFAULTS["do_chamfer"]):
        try:
            ref_empty = part.CreateReferenceFromName("")
            chamfer1 = shape_factory.AddNewChamfer(
                ref_empty,
                constants.catTangencyChamfer,
                constants.catLengthAngleChamfer,
                constants.catNoReverseChamfer,
                float(params.get("chamfer_dim", DEFAULTS["chamfer_dim"])),
                float(params.get("chamfer_angle", DEFAULTS["chamfer_angle"]))
            )
            part.Update()
        except Exception:
            pass

def script4b(catia_app, params):
    part_document = catia_app.ActiveDocument
    part = part_document.Part

    bodies = part.Bodies
    body = bodies.Item("PartBody")
    sketches = body.Sketches
    shape_factory = part.ShapeFactory

    try:
        shapes = body.Shapes
    except Exception:
        return

    horiz_face_ref_string = (
        "Selection_RSur:(Face:(Brp:(ThickSurface.1;1:(Brp:(GSMExtrude.1;0:"
        "(Brp:(GSMLineCorner.1;(Brp:(GSMPoint.1);Brp:(GSMPoint.2)))))));None:();Cf12:());"
        "ThickSurface.1_ResultOUT;Z0;G9219)"
    )

    # ---------- CHANGED: pocket depth uses thick_top_offset ----------
    pocket_depth_for_vertical = float(params.get("thick_top_offset", DEFAULTS["thick_top_offset"]))
    # ----------------------------------------------------------------

    for s_idx in range(1, shapes.Count + 1):
        try:
            shape = shapes.Item(s_idx)
        except Exception:
            continue

        try:
            faces = shape.Faces
        except Exception:
            continue

        for f_idx in range(1, faces.Count + 1):
            try:
                face = faces.Item(f_idx)
            except Exception:
                continue

            try:
                face_ref_name = ""
                try:
                    face_ref = part.CreateReferenceFromObject(face)
                    face_ref_name = str(face_ref)
                except Exception:
                    face_ref_name = ""
                if horiz_face_ref_string in face_ref_name:
                    continue
            except Exception:
                pass

            try:
                ref_face = part.CreateReferenceFromObject(face)
            except Exception:
                continue

            try:
                sketch_try = sketches.Add(ref_face)
            except Exception:
                continue

            try:
                abs_axis = [0.0, 0.0, 0.0, 1.0, 0.0, 0.0, -0.0, 1.0, 0.0]
                sketch_try.SetAbsoluteAxisData(abs_axis)
                part.InWorkObject = sketch_try

                factory2d = sketch_try.OpenEdition()
                c1 = params.get("circle1", DEFAULTS["circle1"])
                c2 = params.get("circle2", DEFAULTS["circle2"])

                circle1 = None
                circle2 = None
                try:
                    if c1 and len(c1) >= 3 and float(c1[2]) >= 0:
                        circle1 = _create_circle_in_sketch(factory2d, c1[0], c1[1], c1[2])
                except Exception:
                    circle1 = None

                try:
                    if c2 and len(c2) >= 3 and float(c2[2]) >= 0:
                        circle2 = _create_circle_in_sketch(factory2d, c2[0], c2[1], c2[2])
                except Exception:
                    circle2 = None

                sketch_try.CloseEdition()
                part.InWorkObject = sketch_try
                part.Update()

                try:
                    if circle1 is not None:
                        pocket_try1 = shape_factory.AddNewPocket(sketch_try, pocket_depth_for_vertical)
                        try:
                            pocket_try1.FirstLimit.Dimension.Value = pocket_depth_for_vertical
                        except Exception:
                            pass
                        part.Update()
                    if circle2 is not None:
                        pocket_try2 = shape_factory.AddNewPocket(sketch_try, pocket_depth_for_vertical)
                        try:
                            pocket_try2.FirstLimit.Dimension.Value = pocket_depth_for_vertical
                        except Exception:
                            pass
                        part.Update()
                except Exception:
                    try:
                        sel = part_document.Selection
                        sel.Add(sketch_try)
                        sel.Delete()
                        sel.Clear()
                    except Exception:
                        pass
                    part.Update()
                    continue

                if params.get("do_chamfer", DEFAULTS["do_chamfer"]):
                    try:
                        ref_empty = part.CreateReferenceFromName("")
                        chamfer_try = shape_factory.AddNewChamfer(
                            ref_empty,
                            constants.catTangencyChamfer,
                            constants.catLengthAngleChamfer,
                            constants.catNoReverseChamfer,
                            float(params.get("chamfer_dim", DEFAULTS["chamfer_dim"])),
                            float(params.get("chamfer_angle", DEFAULTS["chamfer_angle"]))
                        )
                        part.Update()
                    except Exception:
                        pass

                return

            except Exception:
                try:
                    sel = part_document.Selection
                    sel.Add(sketch_try)
                    sel.Delete()
                    sel.Clear()
                except Exception:
                    pass
                part.Update()
                continue

    return

def main():
    pythoncom.CoInitialize()
    try:
        catia_app = Dispatch("CATIA.Application")
    except Exception as e:
        raise RuntimeError("Could not connect to CATIA. Make sure CATIA is running.") from e

    params_file_cli, cli_params = parse_cli_args()
    file_params = load_params_from_json(params_file_cli) if params_file_cli else {}
    params = merge_params(cli_params, file_params)

    script1(catia_app, params)
    time.sleep(params.get("step_delay", 0.5))
    script2(catia_app, params)
    time.sleep(params.get("step_delay", 0.5))
    script3(catia_app, params)
    time.sleep(params.get("step_delay", 0.5))
    script4(catia_app, params)
    time.sleep(params.get("step_delay", 0.5))
    script4b(catia_app, params)

if __name__ == "__main__":
    main()
