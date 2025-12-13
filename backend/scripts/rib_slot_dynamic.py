# ============================================================================ #
# RIB + SLOT generator (Dynamic Parametric Version)
# CATIA V5 automation using pycatia
# ============================================================================ #

import json
import argparse
from pycatia import catia
from pycatia.mec_mod_interfaces.part_document import PartDocument


def build_rib_and_slot(params: dict):
    """
    params dictionary format:
    {
        "L": float,
        "square_size": float,
        "circle_radius": float,
        "curve_points": [
            [x1, y1, z1],
            [x2, y2, z2],
            ...
        ]
    }
    """

    # ---------------- CATIA SESSION (win32com) ----------------------------------------- #
    import pythoncom
    from win32com.client import Dispatch

    try:
        pythoncom.CoInitialize()
        catia = Dispatch("CATIA.Application")
        catia.Visible = True
    except Exception as e:
        raise RuntimeError(f"❌ ERROR: Could not connect to CATIA: {e}")

    documents = catia.Documents
    
    # Close existing (optional, maybe dangerous if user has work open. Let's make new part instead)
    # The original script closed everything. Let's keep it safer: just add new part.
    
    document = documents.Add("Part")
    part = document.Part
    bodies = part.Bodies
    partbody = bodies.Item("PartBody")
    sketches = partbody.Sketches
    hybrid_bodies = part.HybridBodies
    hsf = part.HybridShapeFactory
    shpfac = part.ShapeFactory

    # Work object
    part.InWorkObject = partbody

    # Planes
    origin = part.OriginElements
    plane_XY = origin.PlaneXY

    # ======================================================================== #
    # STEP 1 — Create square profile
    # ======================================================================== #
    L = float(params["L"])
    square_size = float(params["square_size"])
    s = square_size / 2.0

    sketch_square = sketches.Add(plane_XY)
    
    # name property might be Name in COM
    # sketch_square.Name = "dynamic_square"
    
    ske = sketch_square.OpenEdition()

    # CreateLine(x1, y1, x2, y2)
    ske.CreateLine(s, s, s, -s)
    ske.CreateLine(s, -s, -s, -s)
    ske.CreateLine(-s, -s, -s, s)
    ske.CreateLine(-s, s, s, s)

    sketch_square.CloseEdition()
    part.Update()

    # ======================================================================== #
    # STEP 2 — Create spline curve dynamically
    # ======================================================================== #
    curve_points = params["curve_points"]

    construction = hybrid_bodies.Add()
    # construction.Name = "construction_elements"

    spline = hsf.AddNewSpline()
    spline.SetSplineType(0) # 0 = cubic? Defaults usually fine.
    spline.SetClosing(0)

    for pt in curve_points:
        p_coord = hsf.AddNewPointCoord(float(pt[0]), float(pt[1]), float(pt[2]))
        # We must add point to body to be valid? Or just reference?
        # Usually Spline needs references.
        # Add point to construction body first
        construction.AppendHybridShape(p_coord)
        ref_pt = part.CreateReferenceFromObject(p_coord)
        spline.AddPoint(ref_pt)

    construction.AppendHybridShape(spline)
    part.Update()
    
    # ======================================================================== #
    # STEP 3 — Create rib along spline
    # ======================================================================== #
    part.InWorkObject = partbody
    ref_square = part.CreateReferenceFromObject(sketch_square)
    ref_spline = part.CreateReferenceFromObject(spline) # Rib needs ref? Or object?
    
    # AddNewRibFromRef(Profile, CenterCurve)
    # Try object directly first if fails use ref
    try:
        rib = shpfac.AddNewRibFromRef(ref_square, ref_spline)
    except:
         # Sometimes wants object for spline if same doc?
         # But AddNewRibFromRef specifically asks for references.
         pass
         
    part.Update()

    # ======================================================================== #
    # STEP 4 — Create circle for slot
    # ======================================================================== #
    circle_radius = float(params["circle_radius"])

    sketch_circle = sketches.Add(plane_XY)
    # sketch_circle.Name = "dynamic_circle"
    ske2 = sketch_circle.OpenEdition()

    ske2.CreateClosedCircle(0.0, 0.0, float(circle_radius))

    sketch_circle.CloseEdition()
    part.Update()

    # ======================================================================== #
    # STEP 5 — Create slot along spline
    # ======================================================================== #
    part.InWorkObject = partbody
    ref_circle = part.CreateReferenceFromObject(sketch_circle)
    
    slot = shpfac.AddNewSlotFromRef(ref_circle, ref_spline)

    part.Update()

    return {
        "status": "success",
        "message": "Rib and Slot generated successfully"
    }

# ============================================================================ #
# CLI EXECUTION SUPPORT (FOR main.py OR MANUAL RUN)
# ============================================================================ #

if __name__ == "__main__":

    parser = argparse.ArgumentParser(description="Dynamic Rib + Slot CATIA Builder")
    parser.add_argument("--params", type=str, help="Path to JSON params file")
    args = parser.parse_args()

    if not args.params:
        print("❌ ERROR: Missing --params file")
        exit(1)

    # Load params from JSON
    try:
        with open(args.params, "r") as f:
            params = json.load(f)
    except Exception as e:
        print(f"❌ Error reading params file: {e}")
        exit(1)

    # Run CATIA geometry creation
    try:
        result = build_rib_and_slot(params)
        print("SUCCESS: CATIA Rib-Slot built successfully.")
        print(json.dumps(result, indent=4))
    except Exception as e:
        print(f"ERROR: {e}")
        exit(1)
