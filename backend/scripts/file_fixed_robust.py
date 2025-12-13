# file_fixed_robust.py
# Run on same Windows session as CATIA.
# Requires: pywin32 (pip install pywin32)
 
"""
This updated script accepts parameters dynamically via command-line arguments or a JSON parameter file.
By default it creates a NEW CATIA Part document for each run (so repeated runs don't reuse the same
ActiveDocument). If you prefer to use an already-open part, pass --use-active.
 
Usage examples:
  python file_fixed_robust.py --pad-height 20 --circle-radius 25 --pocket-depth 20 --pattern-instances 96 --pattern-spacing 3.75
  python file_fixed_robust.py --params params.json
  python file_fixed_robust.py --use-active  # use currently open Part (if any)
"""
 
import json
import argparse
from win32com.client import Dispatch, VARIANT, gencache
import pythoncom, traceback, sys, time
from pycatia import catia
 
 
def try_set_absolute_axis(sketch, arr):
    """
    Try several ways to call SetAbsoluteAxisData to handle differences
    in CATIA / win32com marshalling.
    Returns the method name that worked, or raises last exception.
    """
    last_exc = None
 
    # 1) Try passing python list/tuple directly (most natural)
    try:
        sketch.SetAbsoluteAxisData(tuple(arr))
        return "direct"
    except Exception as e:
        last_exc = e
 
    # 2) Try a VARIANT SAFEARRAY of R8
    try:
        v = VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, tuple(arr))
        sketch.SetAbsoluteAxisData(v)
        return "variant_r8"
    except Exception as e:
        last_exc = e
 
    # 3) Try SAFEARRAY of VARIANTs (each element is a VT_R8 VARIANT)
    try:
        inner = tuple(VARIANT(pythoncom.VT_R8, float(x)) for x in arr)
        outer = VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_VARIANT, inner)
        sketch.SetAbsoluteAxisData(outer)
        return "variant_of_variants"
    except Exception as e:
        last_exc = e
 
    # If all failed, re-raise the last exception for debugging
    raise last_exc
 
 
def load_params_from_file(path):
    with open(path, 'r') as f:
        return json.load(f)
 
 
def parse_args():
    p = argparse.ArgumentParser(description='Create pad, pocket and circular pattern in CATIA with dynamic params')
    p.add_argument('--params', type=str, help='Path to JSON file with parameters')
    p.add_argument('--circle-radius', type=float, default=25.0)
    p.add_argument('--pad-height', type=float, default=20.0)
    p.add_argument('--second-sketch-z', type=float, default=20.0)
    p.add_argument('--triangle-points', type=str, help='JSON list of 3 points: [[x1,y1],[x2,y2],[x3,y3]]')
    p.add_argument('--pocket-depth', type=float, default=20.0)
    p.add_argument('--pattern-instances', type=int, default=96)
    p.add_argument('--pattern-spacing', type=float, default=3.75)
    p.add_argument('--center-hole-dia', type=float, default=8.0)
    p.add_argument('--debug', action='store_true')
    p.add_argument('--use-active', action='store_true', help='Use currently active CATIA PartDocument instead of creating a new one')
    return p.parse_args()
 
 
def create_new_part(catia_app):
    """
    Create a new Part document and return (part_doc, part, bodies, body, sketches, origin, plane_xy)
    """
    docs = catia_app.Documents
    part_doc = docs.Add("Part")
    part = part_doc.Part
 
    # Ensure there's a PartBody to use (create if not present)
    bodies = part.Bodies
    try:
        # Some CATIA templates already have a PartBody at index 1
        body = bodies.Item("PartBody")
    except Exception:
        body = bodies.Add()
        try:
            body.Name = "PartBody"
        except Exception:
            pass
 
    sketches = body.Sketches
    origin = part.OriginElements
    plane_xy = origin.PlaneXY
    return part_doc, part, bodies, body, sketches, origin, plane_xy
 
 
def get_active_part(catia_app):
    """
    Try to get the current active PartDocument and its Part object.
    Returns same tuple as create_new_part except part_doc is the active document.
    Raises Exception if no usable PartDocument is available.
    """
    part_doc = catia_app.ActiveDocument
    if part_doc is None:
        raise RuntimeError("No active CATIA document found.")
    try:
        part = part_doc.Part
    except Exception:
        raise RuntimeError("Active document does not expose Part object.")
    # Try to find PartBody and Sketches in the existing part
    bodies = part.Bodies
    try:
        body = bodies.Item("PartBody")
    except Exception:
        # fallback to the first body
        try:
            body = bodies.Item(1)
        except Exception:
            # if no bodies exist, create one
            body = bodies.Add()
            try:
                body.Name = "PartBody"
            except Exception:
                pass
    sketches = body.Sketches
    origin = part.OriginElements
    plane_xy = origin.PlaneXY
    return part_doc, part, bodies, body, sketches, origin, plane_xy
 
 
def main():
    args = parse_args()
 
    # default parameter dictionary
    params = {
        'circle_radius': args.circle_radius,
        'pad_height': args.pad_height,
        'second_sketch_z': args.second_sketch_z,
        'triangle_points': [[-2.503365, 26.437065], [0.0, 22.871666], [2.351646, 26.437065]],
        'pocket_depth': args.pocket_depth,
        'pattern_instances': args.pattern_instances,
        'pocket_depth': args.pocket_depth,
        'pattern_instances': args.pattern_instances,
        'pattern_spacing': args.pattern_spacing,
        'center_hole_dia': args.center_hole_dia
    }
 
    # override from params file if provided
    if args.params:
        file_params = load_params_from_file(args.params)
        params.update(file_params)
 
    # override triangle points if passed as JSON string
    if args.triangle_points:
        try:
            params['triangle_points'] = json.loads(args.triangle_points)
        except Exception:
            print('Failed to parse --triangle-points; using default')
 
    if args.debug:
        print('Parameters:')
        print(json.dumps(params, indent=2))
 
    # Connect to CATIA robustly
    try:
        catia_app = Dispatch('CATIA.Application')
    except Exception:
        try:
            # fallback to EnsureDispatch
            catia_app = gencache.EnsureDispatch('CATIA.Application')
        except Exception:
            print('ERROR: Could not connect to CATIA. Make sure CATIA is running in this user session.')
            return
 
    # Create new document or use active depending on flag
    try:
        if args.use_active:
            part_doc, part, bodies, body, sketches, origin, plane_xy = get_active_part(catia_app)
            if args.debug:
                print("Using active document:", getattr(part_doc, "Name", "<unknown>"))
        else:
            part_doc, part, bodies, body, sketches, origin, plane_xy = create_new_part(catia_app)
            if args.debug:
                print("Created new Part document:", getattr(part_doc, "Name", "<unknown>"))
    except Exception as e:
        print('ERROR while preparing Part document:', e)
        traceback.print_exc()
        return
 
    if part is None:
        print('ERROR: Part object not available.')
        return
 
    try:
        # 1) Sketch on PlaneXY -> circle -> Pad
        sketch1 = sketches.Add(plane_xy)
        abs_axis1 = [0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0, 0.0]
        method = try_set_absolute_axis(sketch1, abs_axis1)
        if args.debug:
            print('SetAbsoluteAxisData succeeded using:', method)
 
        part.InWorkObject = sketch1
        factory2d_1 = sketch1.OpenEdition()
        geomElems1 = sketch1.GeometricElements
        axis2d_1 = geomElems1.Item('AbsoluteAxis')
 
        circle2d = factory2d_1.CreateClosedCircle(0.0, 0.0, float(params['circle_radius']))
        origin_pt = axis2d_1.GetItem('Origin')
        circle2d.CenterPoint = origin_pt
 
        sketch1.CloseEdition()
        part.InWorkObject = sketch1
        part.Update()
 
        shape_factory = part.ShapeFactory
        pad1 = shape_factory.AddNewPad(sketch1, float(params['pad_height']))
        part.Update()
        print('Pad created.')
 
        # 2) Second sketch at Z = pad height (or given)
        sketch2 = sketches.Add(plane_xy)
        abs_axis2 = [0.0, 0.0, float(params['second_sketch_z']), 1.0, 0.0, 0.0, 0.0, 1.0, 0.0]
        method2 = try_set_absolute_axis(sketch2, abs_axis2)
        if args.debug:
            print('SetAbsoluteAxisData (sketch2) succeeded using:', method2)
 
        part.InWorkObject = sketch2
        factory2d_2 = sketch2.OpenEdition()
        geomElems2 = sketch2.GeometricElements
        axis2d_2 = geomElems2.Item('AbsoluteAxis')
 
        pts = params['triangle_points']
        if len(pts) != 3:
            raise ValueError('triangle_points must contain exactly 3 points')
 
        pA = factory2d_2.CreatePoint(float(pts[0][0]), float(pts[0][1]))
        pB = factory2d_2.CreatePoint(float(pts[1][0]), float(pts[1][1]))
        pC = factory2d_2.CreatePoint(float(pts[2][0]), float(pts[2][1]))
 
        lAB = factory2d_2.CreateLine(float(pts[0][0]), float(pts[0][1]), float(pts[1][0]), float(pts[1][1]))
        lAB.StartPoint = pA
        lAB.EndPoint = pB
 
        lBC = factory2d_2.CreateLine(float(pts[1][0]), float(pts[1][1]), float(pts[2][0]), float(pts[2][1]))
        lBC.StartPoint = pB
        lBC.EndPoint = pC
 
        lCA = factory2d_2.CreateLine(float(pts[2][0]), float(pts[2][1]), float(pts[0][0]), float(pts[0][1]))
        lCA.StartPoint = pC
        lCA.EndPoint = pA
 
        # best-effort constraint (non-critical)
        try:
            constraints2 = sketch2.Constraints
            ref_pB = part.CreateReferenceFromObject(pB)
            ref_line_V = part.CreateReferenceFromObject(axis2d_2.GetItem('VDirection'))
            constraints2.AddBiEltCst(0, ref_pB, ref_line_V)
        except Exception:
            pass
 
        sketch2.CloseEdition()
        part.InWorkObject = sketch2
        part.Update()
        print('Second sketch created.')
 
        # 3) Create pocket reversed (try negative depth first)
        pocket1 = None
        created = False
        pocket_depth = float(params['pocket_depth'])
        try:
            pocket1 = shape_factory.AddNewPocket(sketch2, -pocket_depth)
            part.Update()
            created = pocket1 is not None
        except Exception:
            created = False
 
        if not created:
            try:
                pocket1 = shape_factory.AddNewPocket(sketch2, pocket_depth)
                part.Update()
                try:
                    pocket1.Reverse = True
                    created = True
                except Exception:
                    created = True  # created but might not flip
            except Exception:
                created = False
 
        if not created or pocket1 is None:
            print('ERROR: Failed to create pocket in reversed direction.')
            return
 
        print('Pocket created (reversed direction attempted).')
 
        # 4) Circular pattern
        circPattern = None
        try:
            # Try the extended signature first (older/newer CATIA versions may differ)
            circPattern = shape_factory.AddNewCircPattern(None, 1, 2, 20.0, 45.0, 1, 1, None, None, True, 0.0, True)
        except Exception:
            try:
                circPattern = shape_factory.AddNewCircPattern(None)
            except Exception:
                circPattern = None
 
        if circPattern is not None:
            try:
                circPattern.ItemToCopy = pocket1
                try:
                    ang = circPattern.AngularRepartition
                    ang.InstancesCount.Value = int(params['pattern_instances'])
                    ang.AngularSpacing.Value = float(params['pattern_spacing'])
                except Exception:
                    pass
                try:
                    ref_plane = part.CreateReferenceFromObject(plane_xy)
                    circPattern.SetRotationAxis(ref_plane)
                except Exception:
                    pass
                part.UpdateObject(circPattern)
                part.Update()
                print('Circular pattern created.')
            except Exception as e:
                print('Warning configuring circular pattern:', e)
        else:
            print('Warning: circular pattern creation failed.')

        # 5) Center Hole (Optional) - Single Instance, NOT patterned
        center_dia = float(params.get('center_hole_dia', 0.0))
        if center_dia > 0.0:
            print(f"Creating Center Pocket with diameter {center_dia}...")
            try:
                # Create sketch on plane_xy
                sketch3 = sketches.Add(plane_xy)
                # axis setup (standard)
                abs_axis3 = [0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0, 0.0]
                try_set_absolute_axis(sketch3, abs_axis3)
                
                part.InWorkObject = sketch3
                f2d_3 = sketch3.OpenEdition()
                # Circle at 0,0
                c3 = f2d_3.CreateClosedCircle(0.0, 0.0, center_dia / 2.0)
                sketch3.CloseEdition()
                part.Update()
                
                # Pocket it
                # Use same depth as other pocket, or maybe pad height? 
                # User usually implies through-all or same depth. Let's use pocket_depth.
                pdepth = float(params['pocket_depth'])
                
                # Logic: Try negative depth first (often forces "reverse" direction into the pad)
                # If that fails, try positive depth and explicit Reverse propery.
                pocket2 = None
                try:
                    pocket2 = shape_factory.AddNewPocket(sketch3, -pdepth)
                    part.Update()
                except Exception:
                    pocket2 = None
                
                if pocket2 is None:
                    try:
                        pocket2 = shape_factory.AddNewPocket(sketch3, pdepth)
                        try:
                            pocket2.Reverse = True
                        except Exception:
                            pass
                        part.Update()
                    except Exception as e:
                        print("Error in fallback pocket creation:", e)
                
                print("Center pocket created.")
            except Exception as e:
                print("Error creating center pocket:", e)
 
        # Reframe view if possible (helpful when automatically creating new parts)
        try:
            catia_app.ActiveWindow.ActiveViewer.Reframe()
        except Exception:
            pass
 
        print('Script finished OK.')
    except Exception:
        print('Unhandled exception in main:')
        traceback.print_exc()
 
 
if __name__ == '__main__':
    main()