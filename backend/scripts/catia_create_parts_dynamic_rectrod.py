#!/usr/bin/env python3
"""
catia_create_parts_dynamic_rectrod.py  (CATIA-visible + No Popups)

Creates:
 - Rectangular baseplate
 - Rectangular hole (same footprint as rod)
 - Rectangular rod (block) of fixed height 100 mm
 - Assembly with rod positioned above plate
"""

import os
import sys
import json
import datetime
import traceback

try:
    import pythoncom
    import win32com.client
    CATIA_AVAILABLE = True
except:
    CATIA_AVAILABLE = False


# ----------------------------------------------------
# DEFAULT PARAMETERS
# ----------------------------------------------------
DEFAULTS = {
    "WIDTH": 200.0,
    "HEIGHT": 150.0,
    "PAD_THICKNESS": 20.0,

    # NEW rectangular rod parameters
    "ROD_WIDTH": 50.0,
    "ROD_DEPTH": 40.0,
    "ROD_HEIGHT": 100.0,       # fixed per requirement

    "SAVE_DIR": os.path.join(os.getcwd(), "generated_files"),
    "SAVE_TIMESTAMPED": True,
}


def load_params(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return {k.upper(): v for k, v in json.load(f).items()}
    except:
        return {}


def get_params():
    params = DEFAULTS.copy()

    # Load JSON if provided
    if len(sys.argv) >= 2 and not sys.argv[1].startswith("--"):
        js = sys.argv[1]
        if os.path.exists(js):
            params.update(load_params(js))

    # CLI overrides
    for i, a in enumerate(sys.argv[1:]):
        if a.startswith("--"):
            key = a.lstrip("-").upper()
            if i + 2 <= len(sys.argv) - 1:
                val = sys.argv[i + 2]
                if key in params:
                    try: params[key] = float(val)
                    except: params[key] = val

    # Convert required numerics
    for k in ["WIDTH", "HEIGHT", "PAD_THICKNESS", "ROD_WIDTH", "ROD_DEPTH", "ROD_HEIGHT"]:
        try: params[k] = float(params[k])
        except: params[k] = DEFAULTS[k]

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
        print("Warning: SaveAs failed:", e)


# ----------------------------------------------------
# GEOMETRY
# ----------------------------------------------------

def create_rectangle_pad_with_center_pocket(part, width, height, pad_thickness, pocket_w, pocket_d):
    try:
        body = part.Bodies.Item("PartBody")
        sketches = body.Sketches
        plane_xy = part.OriginElements.PlaneXY

        half_w = width / 2.0
        half_h = height / 2.0

        pocket_half_w = pocket_w / 2.0
        pocket_half_d = pocket_d / 2.0

        # ---- Main rectangle sketch ----
        sk = sketches.Add(plane_xy)
        
        # Force sketch to XY plane clearly
        try:
             sk.SetAbsoluteAxisData([0,0,0, 1,0,0, 0,1,0])
        except: pass
        
        part.InWorkObject = sk
        f2d = sk.OpenEdition() # WIN32COM
        
        l1 = f2d.CreateLine(half_w, half_h, half_w, -half_h)
        l2 = f2d.CreateLine(half_w, -half_h, -half_w, -half_h)
        l3 = f2d.CreateLine(-half_w, -half_h, -half_w, half_h)
        l4 = f2d.CreateLine(-half_w, half_h, half_w, half_h)
        
        l1.StartPoint = l4.EndPoint
        l1.EndPoint = l2.StartPoint
        l2.EndPoint = l3.StartPoint
        l3.EndPoint = l4.StartPoint
        
        sk.CloseEdition()
        part.Update()

        # AddNewPad
        factory = part.ShapeFactory
        pad = factory.AddNewPad(sk, pad_thickness)
        part.Update()

        # ---- Pocket rectangle sketch ----
        sk2 = sketches.Add(plane_xy)
        try:
             sk2.SetAbsoluteAxisData([0,0,pad_thickness, 1,0,0, 0,1,0]) # Sketch on top face
        except: pass

        part.InWorkObject = sk2
        f2d2 = sk2.OpenEdition()
        
        pl1 = f2d2.CreateLine(pocket_half_w, pocket_half_d, pocket_half_w, -pocket_half_d)
        pl2 = f2d2.CreateLine(pocket_half_w, -pocket_half_d, -pocket_half_w, -pocket_half_d)
        pl3 = f2d2.CreateLine(-pocket_half_w, -pocket_half_d, -pocket_half_w, pocket_half_d)
        pl4 = f2d2.CreateLine(-pocket_half_w, pocket_half_d, pocket_half_w, pocket_half_d)
        
        pl1.StartPoint = pl4.EndPoint
        pl1.EndPoint = pl2.StartPoint
        pl2.EndPoint = pl3.StartPoint
        pl3.EndPoint = pl4.StartPoint

        sk2.CloseEdition()
        part.Update()

        # AddNewPocket - usually Inverted if sketched on top
        pocket = factory.AddNewPocket(sk2, pad_thickness)
        part.Update()
        
    except Exception:
        traceback.print_exc()


def create_rect_rod(part, w, d, h):
    """Rectangular block rod"""
    try:
        body = part.Bodies.Item("PartBody")
        sketches = body.Sketches
        plane_xy = part.OriginElements.PlaneXY

        half_w = w / 2.0
        half_d = d / 2.0

        sk = sketches.Add(plane_xy)
        part.InWorkObject = sk
        
        f2d = sk.OpenEdition()
        
        l1 = f2d.CreateLine(half_w, half_d, half_w, -half_d)
        l2 = f2d.CreateLine(half_w, -half_d, -half_w, -half_d)
        l3 = f2d.CreateLine(-half_w, -half_d, -half_w, half_d)
        l4 = f2d.CreateLine(-half_w, half_d, half_w, half_d)
        
        l1.StartPoint = l4.EndPoint
        l1.EndPoint = l2.StartPoint
        l2.EndPoint = l3.StartPoint
        l3.EndPoint = l4.StartPoint
        
        sk.CloseEdition()
        part.Update()

        factory = part.ShapeFactory
        factory.AddNewPad(sk, h)
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


# ----------------------------------------------------
# MAIN PROGRAM
# ----------------------------------------------------

def main():
    params = get_params()

    width = params["WIDTH"]
    height = params["HEIGHT"]
    pad_thickness = params["PAD_THICKNESS"]

    rod_w = params["ROD_WIDTH"]
    rod_d = params["ROD_DEPTH"]
    rod_h = params["ROD_HEIGHT"]   # fixed = 100 mm

    save_dir = params["SAVE_DIR"]
    timestamped = params["SAVE_TIMESTAMPED"]

    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S") if timestamped else ""

    PART1 = os.path.join(save_dir, f"RectPlate_{ts}.CATPart")
    PART2 = os.path.join(save_dir, f"RectRod_{ts}.CATPart")
    PROD = os.path.join(save_dir, f"Assembly_{ts}.CATProduct")

    if not CATIA_AVAILABLE:
        print("CATIA not available!")
        return

    pythoncom.CoInitialize()

    # Start CATIA with no popups
    catia = win32com.client.Dispatch("CATIA.Application")
    catia.Visible = True
    try:
        catia.DisplayAlerts = False
        catia.DisplayFileAlerts = False
        catia.SystemService.SetUserInteraction(False)
    except:
        pass

    docs = catia.Documents
    product_doc = docs.Add("Product")
    product = product_doc.Product

    # ---------------- PART 1: Baseplate ----------------
    partComp1 = product.Products.AddNewComponent("Part", "RectPlate")
    try:
        partDoc1 = partComp1.GetMasterShapeRepresentation(True)
    except:
        partDoc1 = docs.Add("Part")

    partDoc1.Activate()
    create_rectangle_pad_with_center_pocket(
        partDoc1.Part, width, height, pad_thickness, rod_w, rod_d
    )
    safe_save(partDoc1, PART1)

    # ---------------- PART 2: Rectangular Rod ----------------
    partComp2 = product.Products.AddNewComponent("Part", "RectRod")
    try:
        partDoc2 = partComp2.GetMasterShapeRepresentation(True)
    except:
        partDoc2 = docs.Add("Part")

    partDoc2.Activate()
    create_rect_rod(partDoc2.Part, rod_w, rod_d, rod_h)
    safe_save(partDoc2, PART2)

    # Position rod exactly above base
    set_component_translation_to(partComp2, tz=pad_thickness)

    product.Update()

    try:
        product_doc.SaveAs(PROD)
        print("Saved assembly:", PROD)
    except Exception as e:
        print("Save warning:", e)

    pythoncom.CoUninitialize()
    print("\nCATIA model created successfully.")


if __name__ == "__main__":
    main()


