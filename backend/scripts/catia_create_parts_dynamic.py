#!/usr/bin/env python3
"""
catia_create_parts_dynamic.py (CATIA-visible + NO POPUPS)

CATIA opens visibly, all dialogs disabled, SaveAs auto-select YES.
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

DEFAULTS = {
    "WIDTH": 200.0,
    "HEIGHT": 150.0,
    "PAD_THICKNESS": 20.0,
    "CYL_RADIUS": 25.0,
    "CYL_HEIGHT": 120.0,
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

    if len(sys.argv) >= 2 and not sys.argv[1].startswith("--"):
        js = sys.argv[1]
        if os.path.exists(js):
            params.update(load_params(js))

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

    # normalize numerics
    for k in ["WIDTH","HEIGHT","PAD_THICKNESS","CYL_RADIUS","CYL_HEIGHT"]:
        try: params[k] = float(params[k])
        except: params[k] = DEFAULTS[k]

    # ensure save dir
    try:
        os.makedirs(params["SAVE_DIR"], exist_ok=True)
    except:
        params["SAVE_DIR"] = DEFAULTS["SAVE_DIR"]

    params["SAVE_TIMESTAMPED"] = bool(params["SAVE_TIMESTAMPED"])
    return params


def safe_save(doc, path):
    try:
        doc.SaveAs(path)
        # print("Saved:", path)
    except Exception as e:
        print("Warning: SaveAs failed:", e)


# -----------------------------------------------------------
# GEOMETRY
# -----------------------------------------------------------

def create_rectangle_pad_with_center_pocket(part, width, height, pad_thickness, pocket_radius):
    try:
        body = part.Bodies.Item("PartBody")
        sketches = body.Sketches
        plane_xy = part.OriginElements.PlaneXY

        half_w = width/2
        half_h = height/2

        # rectangle
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
        part.InWorkObject = sk2
        ed2 = sk2.OpenEdition()
        ed2.CreateClosedCircle(0,0,pocket_radius)
        sk2.CloseEdition()
        part.Update()

        factory.AddNewPocket(sk2, pad_thickness + 0.2)
        part.Update()

    except Exception:
        traceback.print_exc()


def create_cylinder_part(part, radius, height):
    try:
        body = part.Bodies.Item("PartBody")
        sketches = body.Sketches
        plane_xy = part.OriginElements.PlaneXY

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


# -----------------------------------------------------------
# MAIN
# -----------------------------------------------------------

def main():
    params = get_params()

    width = params["WIDTH"]
    height = params["HEIGHT"]
    pad_thickness = params["PAD_THICKNESS"]
    cyl_radius = params["CYL_RADIUS"]
    cyl_height = params["CYL_HEIGHT"]
    save_dir = params["SAVE_DIR"]
    timestamped = params["SAVE_TIMESTAMPED"]

    pocket_radius = cyl_radius
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S") if timestamped else ""

    PART1 = os.path.join(save_dir, f"RectPlate_{ts}.CATPart")
    PART2 = os.path.join(save_dir, f"Cylinder_{ts}.CATPart")
    PROD = os.path.join(save_dir, f"Assembly_{ts}.CATProduct")

    if not CATIA_AVAILABLE:
        print("CATIA not available")
        return

    pythoncom.CoInitialize()

    # -------------------------------------------------------
    # OPEN CATIA + DISABLE ALL POPUPS
    # -------------------------------------------------------
    try:
        catia = win32com.client.Dispatch("CATIA.Application")
        catia.Visible = True

        # POPUP SUPPRESSION (AUTO-YES)
        try: catia.DisplayAlerts = False
        except: pass
        try: catia.DisplayFileAlerts = False
        except: pass
        try: catia.SystemService.SetUserInteraction(False)
        except: pass

        if hasattr(catia, "RefreshDisplay"):
            catia.RefreshDisplay = True

    except Exception as e:
        print("Connection error:", e)
        pythoncom.CoUninitialize()
        return

    docs = catia.Documents
    product_doc = docs.Add("Product")
    product_doc.Activate()
    product = product_doc.Product

    # ------------------ PART 1 ------------------
    partComp1 = product.Products.AddNewComponent("Part", "RectPlate")
    try:
        partDoc1 = partComp1.GetMasterShapeRepresentation(True)
    except:
        partDoc1 = docs.Add("Part")

    partDoc1.Activate()
    create_rectangle_pad_with_center_pocket(partDoc1.Part, width, height, pad_thickness, pocket_radius)
    safe_save(partDoc1, PART1)
    partDoc1.Activate()

    # ------------------ PART 2 ------------------
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

    try:
        product_doc.SaveAs(PROD)
        # print("Saved assembly:", PROD)
    except Exception as e:
        # print("Save warning:", e)

    pythoncom.CoUninitialize()

    # print("\nCATIA model OPEN, VISIBLE, and NO POPUPS.")


if __name__ == "__main__":
    main()


