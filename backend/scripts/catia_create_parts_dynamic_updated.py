
#!/usr/bin/env python3
"""
catia_create_parts_dynamic_updated.py (CATIA-visible + NO POPUPS + HOLLOW CYLINDER)
✦ Pocket Direction configurable via params ("UP" or "DOWN")
✦ Hole diameter EXACTLY equals outer tube diameter
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


# ---------------- DEFAULT DIMENSIONS ---------------- #
DEFAULTS = {
    "WIDTH": 200.0,         # Plate width
    "HEIGHT": 150.0,        # Plate height
    "PAD_THICKNESS": 20.0,  # Plate thickness

    "CYL_RADIUS": 25.0,     # Tube outer radius
    "WALL_THICKNESS": 2.0,  # Tube wall thickness
    "CYL_HEIGHT": 120.0,    # Tube height

    # Pocket direction for the *center* pocket on the plate: "UP" or "DOWN"
    # "UP" means cut goes upward from the sketch plane (your previous behaviour)
    "POCKET_DIRECTION": "UP",

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

    # Simple CLI flag parsing: --KEY value
    argv = sys.argv[1:]
    i = 0
    while i < len(argv):
        a = argv[i]
        if a.startswith("--"):
            key = a.lstrip("-").upper()
            if i + 1 < len(argv):
                val = argv[i + 1]
                # try to coerce to existing param types
                if key in params:
                    try:
                        # numeric conversion for numeric params
                        if isinstance(params[key], (int, float)):
                            params[key] = float(val)
                        else:
                            params[key] = val
                    except:
                        params[key] = val
                else:
                    params[key] = val
                i += 2
                continue
        i += 1

    # Ensure numeric keys are floats
    for k in ["WIDTH", "HEIGHT", "PAD_THICKNESS", "CYL_RADIUS", "CYL_HEIGHT", "WALL_THICKNESS"]:
        try:
            params[k] = float(params[k])
        except:
            params[k] = DEFAULTS[k]

    # Normalize pocket direction to string
    try:
        params["POCKET_DIRECTION"] = str(params.get("POCKET_DIRECTION", "UP")).upper()
        if params["POCKET_DIRECTION"] not in ("UP", "DOWN"):
            params["POCKET_DIRECTION"] = "UP"
    except:
        params["POCKET_DIRECTION"] = "UP"

    os.makedirs(params["SAVE_DIR"], exist_ok=True)
    params["SAVE_TIMESTAMPED"] = bool(params["SAVE_TIMESTAMPED"])
    return params


def safe_save(doc, path):
    try:
        doc.SaveAs(path)
        print("Saved:", path)
    except Exception as e:
        print("⚠ Warning during SaveAs:", e)


# --------------- GEOMETRY CREATION ---------------- #

def create_rectangle_pad_with_center_pocket(part, width, height, pad_t, exact_outer_radius, pocket_direction="UP"):
    """
    Creates a baseplate and center hole
    Hole radius == tube outer radius (PERFECT FIT)
    pocket_direction: "UP" or "DOWN"  (UP = cut upward from sketch plane)
    """
    try:
        body = part.Bodies.Item("PartBody")
        sketches = body.Sketches
        plane_xy = part.OriginElements.PlaneXY
        factory = part.ShapeFactory

        half_w = width / 2
        half_h = height / 2

        # Base Plate
        sk = sketches.Add(plane_xy)
        part.InWorkObject = sk
        ed = sk.OpenEdition()
        ed.CreateLine(half_w, half_h, half_w, -half_h)
        ed.CreateLine(half_w, -half_h, -half_w, -half_h)
        ed.CreateLine(-half_w, -half_h, -half_w, half_h)
        ed.CreateLine(-half_w, half_h, half_w, half_h)
        sk.CloseEdition()
        part.Update()

        factory.AddNewPad(sk, pad_t)
        part.Update()

        # Hole with configurable cut direction
        sk2 = sketches.Add(plane_xy)
        part.InWorkObject = sk2
        ed2 = sk2.OpenEdition()
        try:
            ed2.CreateClosedCircle(0, 0, exact_outer_radius)
        except Exception:
            ed2.CreateCircle(0, 0, exact_outer_radius)
        sk2.CloseEdition()
        part.Update()

        # Create pocket. Default depth uses pad_t so it cuts through the pad thickness.
        pocket = factory.AddNewPocket(sk2, pad_t)

        # Configure Reverse flag based on requested direction.
        # Mapping preserved: Reverse=False => UP (cut upwards from sketch plane)
        try:
            if str(pocket_direction).strip().upper() == "DOWN":
                pocket.Reverse = True
            else:  # default to UP
                pocket.Reverse = False
        except Exception:
            # If .Reverse not supported, fallback: recreate pocket with inverted depth sign
            try:
                # best-effort: add a pocket with negative depth
                factory.AddNewPocket(sk2, -abs(pad_t))
            except Exception:
                pass

        part.Update()

    except:
        traceback.print_exc()


def create_hollow_cylinder(part, outer_r, height, wall_t):
    """Creates a tube fully parametric"""
    try:
        body = part.Bodies.Item("PartBody")
        sketches = body.Sketches
        plane_xy = part.OriginElements.PlaneXY
        factory = part.ShapeFactory

        # Outer cylinder (Tube OD)
        sk = sketches.Add(plane_xy)
        part.InWorkObject = sk
        ed = sk.OpenEdition()
        try:
            ed.CreateClosedCircle(0, 0, outer_r)
        except Exception:
            ed.CreateCircle(0, 0, outer_r)
        sk.CloseEdition()
        part.Update()

        factory.AddNewPad(sk, height)
        part.Update()

        # Inner cylinder (Tube ID)
        inner_r = max(outer_r - wall_t, 0.1)
        sk2 = sketches.Add(plane_xy)
        part.InWorkObject = sk2
        ed2 = sk2.OpenEdition()
        try:
            ed2.CreateClosedCircle(0, 0, inner_r)
        except Exception:
            ed2.CreateCircle(0, 0, inner_r)
        sk2.CloseEdition()
        part.Update()

        pocket2 = factory.AddNewPocket(sk2, height)
        # We keep the existing behaviour: Reverse=True to remove inner material
        try:
            pocket2.Reverse = True
        except Exception:
            # fallback: recreate with negative depth if Reverse not available
            try:
                factory.AddNewPocket(sk2, -abs(height))
            except Exception:
                pass
        part.Update()

    except:
        traceback.print_exc()


def set_component_translation_to(partComp, tx=0, ty=0, tz=0):
    """Moves components visually in assembly"""
    try:
        pos = partComp.ReferenceProduct.Position
        comps = list(pos.GetComponents())
        # Work with a typical 16-element transform; fall back if shorter
        if len(comps) < 16:
            base = [1.0,0.0,0.0,0.0,
                    0.0,1.0,0.0,0.0,
                    0.0,0.0,1.0,0.0,
                    0.0,0.0,0.0,1.0]
            for i, v in enumerate(comps):
                try:
                    base[i] = float(v)
                except:
                    base[i] = base[i]
            comps = base
        else:
            comps = [float(v) for v in comps]

        # translation indices in 4x4 row-major: 12,13,14
        comps[12] = float(tx)
        comps[13] = float(ty)
        comps[14] = float(tz)
        pos.SetComponents(comps)
    except:
        pass


# ------------------------- MAIN ------------------------ #

def main():
    params = get_params()
    width = params["WIDTH"]
    height = params["HEIGHT"]
    pad = params["PAD_THICKNESS"]
    R = params["CYL_RADIUS"]
    H = params["CYL_HEIGHT"]
    W = params["WALL_THICKNESS"]
    save_dir = params["SAVE_DIR"]
    timestamped = params["SAVE_TIMESTAMPED"]
    pocket_dir = params.get("POCKET_DIRECTION", "UP")

    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S") if timestamped else ""
    PART1 = os.path.join(save_dir, f"RectPlate_{ts}.CATPart")
    PART2 = os.path.join(save_dir, f"HollowCylinder_{ts}.CATPart")
    PROD  = os.path.join(save_dir, f"Assembly_{ts}.CATProduct")

    if not CATIA_AVAILABLE:
        print("ERROR: CATIA is not available on this machine")
        return

    pythoncom.CoInitialize()

    catia = win32com.client.Dispatch("CATIA.Application")
    catia.Visible = True
    try: catia.SystemService.SetUserInteraction(False)
    except: pass

    docs = catia.Documents
    product_doc = docs.Add("Product")
    product = product_doc.Product

    # Baseplate
    p1 = product.Products.AddNewComponent("Part", "RectPlate")
    pd1 = p1.GetMasterShapeRepresentation(True)
    pd1.Activate()
    create_rectangle_pad_with_center_pocket(pd1.Part, width, height, pad, R, pocket_dir)
    safe_save(pd1, PART1)

    # Hollow Tube
    p2 = product.Products.AddNewComponent("Part", "HollowCylinder")
    pd2 = p2.GetMasterShapeRepresentation(True)
    pd2.Activate()
    create_hollow_cylinder(pd2.Part, R, H, W)
    safe_save(pd2, PART2)

    # Align tube on the base (place tube base at plate top)
    set_component_translation_to(p2, tz=pad)
    product.Update()

    product_doc.SaveAs(PROD)
    pythoncom.CoUninitialize()

    print("\n[SUCCESS] Pocket direction set (configurable) + Fit diameters MATCH perfectly\n")


if __name__ == "__main__":
    main()
