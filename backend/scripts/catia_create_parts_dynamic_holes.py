#!/usr/bin/env python3
"""
catia_create_parts_dynamic_holes.py (CATIA-visible & NO POPUPS)

CATIA window opens visibly + all alert popups disabled.
All SaveAs prompts auto-confirm YES.
"""

import os
import sys
import json
import datetime
import traceback
import math

try:
    import pythoncom
    import win32com.client
    CATIA_AVAILABLE = True
except Exception:
    CATIA_AVAILABLE = False

DEFAULTS = {
    "WIDTH": 200.0,
    "HEIGHT": 150.0,
    "PAD_THICKNESS": 20.0,
    "CYL_RADIUS": 25.0,
    "CYL_HEIGHT": 120.0,
    "SAVE_DIR": os.getcwd(),
    "SAVE_TIMESTAMPED": True,
    "HOLES": 0,
    "HOLE_DIAMETER": 7.0,
}

def load_params(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return {k.upper(): v for k, v in json.load(f).items()}
    except Exception as e:
        print("Warning loading JSON:", e)
        return {}

def get_params():
    params = DEFAULTS.copy()
    if len(sys.argv) >= 2 and not sys.argv[1].startswith("--"):
        p = sys.argv[1]
        if os.path.exists(p):
            params.update(load_params(p))

    # CLI overrides
    for i, a in enumerate(sys.argv[1:]):
        if a.startswith("--"):
            key = a.lstrip("-").upper()
            if i+2 <= len(sys.argv)-1:
                val = sys.argv[i+2]
                if key in params:
                    try: params[key] = float(val)
                    except: params[key] = val
                elif key == "SAVE_DIR":
                    params["SAVE_DIR"] = val
                elif key == "SAVE_TIMESTAMPED":
                    params["SAVE_TIMESTAMPED"] = val.lower() in ("1","true","yes")

    # numeric fields
    for k in ["WIDTH","HEIGHT","PAD_THICKNESS","CYL_RADIUS","CYL_HEIGHT","HOLE_DIAMETER"]:
        try: params[k] = float(params[k])
        except: params[k] = DEFAULTS[k]

    try: params["HOLES"] = int(params["HOLES"])
    except: params["HOLES"] = DEFAULTS["HOLES"]

    try:
        os.makedirs(params["SAVE_DIR"], exist_ok=True)
    except:
        params["SAVE_DIR"] = DEFAULTS["SAVE_DIR"]

    params["SAVE_TIMESTAMPED"] = bool(params["SAVE_TIMESTAMPED"])
    return params


def safe_save(doc, path):
    try:
        doc.SaveAs(path)
        print("Saved:", path)
    except Exception as e:
        print("Warning: Save failed:", e)


# ======================== GEOMETRY ==========================

def create_rectangle_pad_with_center_pocket(part, width, height, pad_thickness, pocket_radius):
    try:
        bodies = part.Bodies
        body = bodies.Item("PartBody")
        sketches = body.Sketches
        origin = part.OriginElements
        plane_xy = origin.PlaneXY

        half_w = width/2
        half_h = height/2

        sk = sketches.Add(plane_xy)
        part.InWorkObject = sk
        ed = sk.OpenEdition()
        ed.CreateLine(half_w, half_h, half_w, -half_h)
        ed.CreateLine(half_w, -half_h, -half_w, -half_h)
        ed.CreateLine(-half_w, -half_h, -half_w, half_h)
        ed.CreateLine(-half_w, half_h, half_w, half_h)
        sk.CloseEdition()
        part.Update()

        factory = part.ShapeFactory
        factory.AddNewPad(sk, pad_thickness)
        part.Update()

        # pocket
        sk2 = sketches.Add(plane_xy)
        try: sk2.SetAbsoluteAxisData([0,0,pad_thickness,1,0,0,0,1,0])
        except: pass

        part.InWorkObject = sk2
        ed2 = sk2.OpenEdition()
        ed2.CreateClosedCircle(0,0,pocket_radius)
        sk2.CloseEdition()
        part.Update()

        factory.AddNewPocket(sk2, pad_thickness + 0.2)
        part.Update()

    except Exception:
        traceback.print_exc()


def create_holes_on_bolt_circle(part, hole_count, hole_diameter, pad_thickness, width, height):
    """Correct CATIA-safe hole creation on bolt circle."""
    try:
        if hole_count <= 0:
            return

        bodies = part.Bodies
        body = bodies.Item("PartBody")
        sketches = body.Sketches
        factory = part.ShapeFactory

        # -----------------------------------------
        # 1. GET PAD TOP FACE
        # -----------------------------------------
        main_pad = None
        for feat in body.Shapes:
            if feat.Name.startswith("Pad"):
                main_pad = feat
                break

        if main_pad is None:
            print("ERROR: Pad not found for hole creation")
            return

        # top face reference
        top_face_ref = main_pad.Limit2

        # bolt circle radius
        margin = max(10, max(width, height) * 0.05, hole_diameter * 2 + 5)
        radius = max(5, min(width, height) / 2 - margin)
        if radius < 5:
            radius = min(width, height) / 4

        # -----------------------------------------
        # 2. CREATE SKETCH ON TOP FACE
        # -----------------------------------------
        sketch = sketches.Add(top_face_ref)
        part.InWorkObject = sketch
        ed = sketch.OpenEdition()

        r = hole_diameter / 2.0

        for i in range(hole_count):
            ang = 2 * math.pi * i / hole_count
            x = radius * math.cos(ang)
            y = radius * math.sin(ang)
            ed.CreateClosedCircle(x, y, r)

        sketch.CloseEdition()
        part.Update()

        # -----------------------------------------
        # 3. POCKET DOWNWARD THROUGH PAD
        # -----------------------------------------
        depth = -(pad_thickness + 1)  # negative = downward
        pocket = factory.AddNewPocket(sketch, depth)

        try:
            pocket.ReverseSide()
        except:
            pass

        part.Update()

    except Exception as e:
        print("ERROR in hole creation:", e)
        traceback.print_exc()

    try:
        if hole_count <= 0:
            return

        bodies = part.Bodies
        body = bodies.Item("PartBody")
        sketches = body.Sketches
        origin = part.OriginElements
        plane_xy = origin.PlaneXY

        margin = max(10, max(width, height)*0.05, hole_diameter*2 + 5)
        radius = max(5, min(width,height)/2 - margin)
        if radius < 5:
            radius = min(width,height)/4

        sk = sketches.Add(plane_xy)
        try: sk.SetAbsoluteAxisData([0,0,pad_thickness,1,0,0,0,1,0])
        except: pass

        part.InWorkObject = sk
        ed = sk.OpenEdition()
        r = hole_diameter/2

        for i in range(hole_count):
            ang = 2*math.pi*i/hole_count
            x = radius*math.cos(ang)
            y = radius*math.sin(ang)
            ed.CreateClosedCircle(x, y, r)

        sk.CloseEdition()
        part.Update()

        factory = part.ShapeFactory
        pocket = factory.AddNewPocket(sk, -(pad_thickness + 0.5))

        try: pocket.ReverseSide()
        except: pass

        part.Update()

    except Exception:
        traceback.print_exc()


def create_cylinder_part(part, radius, height):
    try:
        bodies = part.Bodies
        body = bodies.Item("PartBody")
        sketches = body.Sketches
        origin = part.OriginElements
        plane_xy = origin.PlaneXY

        sk = sketches.Add(plane_xy)
        part.InWorkObject = sk
        ed = sk.OpenEdition()
        ed.CreateClosedCircle(0,0,radius)
        sk.CloseEdition()
        part.Update()

        factory = part.ShapeFactory
        factory.AddNewPad(sk, height)
        part.Update()

    except Exception:
        traceback.print_exc()


def set_component_translation_to(partComp, tx=0, ty=0, tz=0):
    try:
        pos = partComp.ReferenceProduct.Position
        comps = list(pos.GetComponents())
        comps[-4] = float(tx)
        comps[-3] = float(ty)
        comps[-2] = float(tz)
        pos.SetComponents(comps)
    except:
        pass


# ======================== MAIN ==========================

def main():
    params = get_params()
    width = params["WIDTH"]
    height = params["HEIGHT"]
    pad_thickness = params["PAD_THICKNESS"]
    cyl_radius = params["CYL_RADIUS"]
    cyl_height = params["CYL_HEIGHT"]
    holes = params["HOLES"]
    hole_diameter = params["HOLE_DIAMETER"]
    save_dir = params["SAVE_DIR"]
    timestamped = params["SAVE_TIMESTAMPED"]
    pocket_radius = cyl_radius

    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S") if timestamped else ""
    PART1 = os.path.join(save_dir, f"RectPlate_{ts}.CATPart")
    PART2 = os.path.join(save_dir, f"Cylinder_{ts}.CATPart")
    PROD = os.path.join(save_dir, f"Assembly_{ts}.CATProduct")

    if not CATIA_AVAILABLE:
        print("ERROR: CATIA not available.")
        return

    pythoncom.CoInitialize()

    # ====== OPEN CATIA WITH POPUPS DISABLED =======
    try:
        catia = win32com.client.Dispatch("CATIA.Application")
        catia.Visible = True

        # 🔥 Disable all popups
        try: catia.DisplayAlerts = False
        except: pass

        try: catia.DisplayFileAlerts = False
        except: pass

        try: catia.SystemService.SetUserInteraction(False)
        except: pass

        if hasattr(catia, "RefreshDisplay"):
            catia.RefreshDisplay = True

    except Exception as e:
        print("Cannot connect to CATIA:", e)
        pythoncom.CoUninitialize()
        return

    # ====== Create Assembly ======
    docs = catia.Documents
    product_doc = docs.Add("Product")
    product_doc.Activate()
    product = product_doc.Product

    # -------- Part 1 --------
    partComp1 = product.Products.AddNewComponent("Part", "RectPlate")
    try:
        partDoc1 = partComp1.GetMasterShapeRepresentation(True)
    except:
        partDoc1 = docs.Add("Part")

    partDoc1.Activate()
    create_rectangle_pad_with_center_pocket(partDoc1.Part, width, height, pad_thickness, pocket_radius)

    if holes > 0:
        create_holes_on_bolt_circle(partDoc1.Part, holes, hole_diameter, pad_thickness, width, height)

    safe_save(partDoc1, PART1)
    partDoc1.Activate()

    # -------- Part 2 --------
    partComp2 = product.Products.AddNewComponent("Part", "Cylinder")
    try:
        partDoc2 = partComp2.GetMasterShapeRepresentation(True)
    except:
        partDoc2 = docs.Add("Part")

    partDoc2.Activate()
    create_cylinder_part(partDoc2.Part, cyl_radius, cyl_height)
    safe_save(partDoc2, PART2)
    partDoc2.Activate()

    # Position cylinder
    set_component_translation_to(partComp2, tz=pad_thickness + 0.01)

    product.Update()
    product_doc.Activate()

    # Save assembly
    try:
        product_doc.SaveAs(PROD)
        print("Saved assembly:", PROD)
    except:
        pass

    # Reframe view
    try:
        catia.ActiveWindow.ActiveViewer.Reframe()
    except:
        pass

    print("\nCATIA model OPEN, VISIBLE, NO POPUPS.")
    pythoncom.CoUninitialize()


if __name__ == "__main__":
    main()
