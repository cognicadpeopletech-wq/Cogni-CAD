
#!/usr/bin/env python3
"""
catia_create_parts_dynamic_rectrod_updated.py  (CATIA-visible + No Popups)

Creates:
 - Rectangular baseplate
 - Vertical hollow rectangular cut centered on the plate top (hollow extends above the plate)
 - Rectangular hollow rod (tube) of fixed height 100 mm that fits into the hollow
 - Assembly with rod positioned above plate

Notes:
 - Script auto-accepts CATIA Save As confirmation dialogs (clicks "Yes") so SaveAs won't block.
 - Use with caution: existing files will be overwritten when SAVE_TIMESTAMPED is False.
"""
import os
import sys
import json
import datetime
import traceback
import threading
import time

try:
    import pythoncom
    import win32com.client
    import win32gui
    import win32con
    CATIA_AVAILABLE = True
except Exception:
    # If pywin32 parts missing, CATIA automation will still attempt to run but dialog auto-press will fail.
    CATIA_AVAILABLE = False


# ----------------------------------------------------
# DEFAULT PARAMETERS
# ----------------------------------------------------
DEFAULTS = {
    "WIDTH": 200.0,
    "HEIGHT": 150.0,
    "PAD_THICKNESS": 20.0,

    # Rectangular rod parameters (outer dims)
    "ROD_WIDTH": 50.0,
    "ROD_DEPTH": 40.0,
    "ROD_HEIGHT": 100.0,       # fixed per requirement

    # Wall thickness for hollow rod
    "ROD_WALL_THICKNESS": 2.0,  # mm (default as requested)

    # Hollow on top of plate (vertical hollow rectangle height above plate)
    "HOLLOW_HEIGHT": 60.0,

    # Optional small clearance so the rod fits into the hollow if needed
    "CLEARANCE": 0.1,

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

    # CLI overrides (simple parser)
    argv = sys.argv[1:]
    i = 0
    while i < len(argv):
        a = argv[i]
        if a.startswith("--"):
            key = a.lstrip("-").upper()
            if i + 1 < len(argv):
                val = argv[i + 1]
                if key in params:
                    try:
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
    for k in ["WIDTH", "HEIGHT", "PAD_THICKNESS", "ROD_WIDTH", "ROD_DEPTH", "ROD_HEIGHT", "HOLLOW_HEIGHT", "CLEARANCE", "ROD_WALL_THICKNESS"]:
        try:
            params[k] = float(params[k])
        except:
            params[k] = DEFAULTS[k]

    try:
        os.makedirs(params["SAVE_DIR"], exist_ok=True)
    except:
        params["SAVE_DIR"] = DEFAULTS["SAVE_DIR"]

    params["SAVE_TIMESTAMPED"] = bool(params["SAVE_TIMESTAMPED"])

    return params


# ----------------- Dialog auto-accept helper -----------------
def _find_and_click_yes_in_dialog(target_title_snippets=None, timeout=6.0, poll_interval=0.08):
    """
    Polls top-level windows for a dialog whose title contains any of the strings
    in target_title_snippets (case-insensitive). When found, searches for a child button
    with text 'Yes' or 'OK' and clicks it (BM_CLICK). Returns True if clicked.
    """
    if target_title_snippets is None:
        target_title_snippets = ["save as", "saveas", "save as -"]

    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            windows = []
            def enum_top(hwnd, l):
                text = win32gui.GetWindowText(hwnd) or ""
                cls  = win32gui.GetClassName(hwnd) or ""
                windows.append((hwnd, text, cls))
            win32gui.EnumWindows(enum_top, None)

            for hwnd, text, cls in windows:
                title_lower = text.lower()
                if any(snippet in title_lower for snippet in target_title_snippets) or ("save as" in title_lower):
                    # Found candidate dialog window
                    # enumerate child windows to find buttons
                    clicked = False
                    def enum_child(h, param):
                        nonlocal clicked
                        try:
                            ch_text = win32gui.GetWindowText(h) or ""
                            if ch_text.strip().lower() in ("yes", "&yes", "ok", "&ok"):
                                # click it
                                win32gui.SendMessage(h, win32con.BM_CLICK, 0, 0)
                                clicked = True
                        except Exception:
                            pass
                    try:
                        win32gui.EnumChildWindows(hwnd, enum_child, None)
                    except Exception:
                        pass
                    if clicked:
                        return True
                    # if not found by text, try to click the first button child (best-effort)
                    try:
                        child_hwnds = []
                        def enum_collect(h, l):
                            child_hwnds.append(h)
                        win32gui.EnumChildWindows(hwnd, enum_collect, None)
                        for ch in child_hwnds:
                            try:
                                clsn = win32gui.GetClassName(ch)
                                if clsn and ("Button" in clsn or clsn.lower().startswith("button")):
                                    win32gui.SendMessage(ch, win32con.BM_CLICK, 0, 0)
                                    return True
                            except Exception:
                                continue
                    except Exception:
                        pass
        except Exception:
            pass
        time.sleep(poll_interval)
    return False


def start_auto_accept_thread(timeout=6.0):
    """
    Start background thread that will attempt to find and click the SaveAs confirmation dialog.
    Returns the Thread object. The thread auto-exits after timeout seconds.
    """
    t = threading.Thread(target=_find_and_click_yes_in_dialog, kwargs={"timeout": timeout}, daemon=True)
    t.start()
    return t


# ----------------- Safe save wrapper that auto-accepts dialog -----------------
def safe_save(doc, path, dialog_timeout=6.0):
    """
    Save document to `path` without prompting:
     - ensures directory exists
     - removes existing file (best-effort) to reduce prompting
     - starts an auto-accept thread, then calls SaveAs()
    """
    try:
        d = os.path.dirname(path)
        if d and not os.path.exists(d):
            os.makedirs(d, exist_ok=True)

        if os.path.exists(path):
            try:
                os.remove(path)
            except Exception as e:
                print("Warning: could not remove existing file before SaveAs:", e)

        # Start helper that will accept the SaveAs dialog while SaveAs runs
        if CATIA_AVAILABLE:
            start_auto_accept_thread(timeout=dialog_timeout)

        doc.SaveAs(path)
        print("Saved:", path)
    except Exception as e:
        print("Warning: SaveAs failed:", e)


# ----------------------------------------------------
# GEOMETRY (same as before)
# ----------------------------------------------------

def create_rectangle_pad_with_vertical_hollow(part, width, height, pad_thickness, hollow_w, hollow_d, hollow_height, clearance=0.0):
    """Create a base plate and a vertical hollow rectangular cut centered on the plate top.

    The hollow is produced by a single pocket using a rectangle sketch; the pocket depth equals
    pad_thickness + hollow_height so it removes material from the plate and extends above it.
    """
    try:
        body = part.Bodies.Item("PartBody")
        sketches = body.Sketches
        plane_xy = part.OriginElements.PlaneXY

        half_w = width / 2
        half_h = height / 2

        hollow_half_w = (hollow_w / 2) + clearance
        hollow_half_d = (hollow_d / 2) + clearance

        # ---- Main plate rectangle sketch ----
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
        pad = factory.AddNewPad(sk, pad_thickness)
        part.Update()

        # ---- Hollow rectangle sketch (centered) ----
        sk2 = sketches.Add(plane_xy)
        part.InWorkObject = sk2
        ed2 = sk2.OpenEdition()
        ed2.CreateLine(hollow_half_w, hollow_half_d, hollow_half_w, -hollow_half_d)
        ed2.CreateLine(hollow_half_w, -hollow_half_d, -hollow_half_w, -hollow_half_d)
        ed2.CreateLine(-hollow_half_w, -hollow_half_d, -hollow_half_w, hollow_half_d)
        ed2.CreateLine(-hollow_half_w, hollow_half_d, hollow_half_w, hollow_half_d)
        sk2.CloseEdition()
        part.Update()

        # ---- Create pocket that removes material through the plate and extends above it ----
        pocket_depth = pad_thickness + abs(hollow_height)
        pocket = factory.AddNewPocket(sk2, pocket_depth)

        # Attempt to set pocket direction to go UP from the plate top face
        try:
            pad_feature = body.Shapes.Item("Pad.1")
            top_face = pad_feature.Limits.TopFace
            ref_top = part.CreateReferenceFromObject(top_face)
            pocket.SetDirection(ref_top)
            part.Update()
        except Exception as e:
            try:
                pocket.Reverse = False
                part.Update()
            except Exception:
                try:
                    factory.AddNewPocket(sk2, -abs(pocket_depth))
                    part.Update()
                except Exception:
                    print("Warning: Could not enforce pocket direction precisely:", e)

    except Exception:
        traceback.print_exc()


def create_rect_rod_hollow(part, outer_w, outer_d, h, wall_t):
    """Rectangular hollow rod (rectangular tube) centered on origin, created upwards from sketch plane."""
    try:
        body = part.Bodies.Item("PartBody")
        sketches = body.Sketches
        plane_xy = part.OriginElements.PlaneXY

        half_w = outer_w / 2
        half_d = outer_d / 2

        # Ensure wall thickness is not excessive
        max_wall = min(outer_w, outer_d) / 2 - 0.1
        wall = min(max(wall_t, 0.01), max_wall)

        # Outer rectangle sketch
        sk_outer = sketches.Add(plane_xy)
        part.InWorkObject = sk_outer
        edo = sk_outer.OpenEdition()
        edo.CreateLine(half_w, half_d, half_w, -half_d)
        edo.CreateLine(half_w, -half_d, -half_w, -half_d)
        edo.CreateLine(-half_w, -half_d, -half_w, half_d)
        edo.CreateLine(-half_w, half_d, half_w, half_d)
        sk_outer.CloseEdition()
        part.Update()

        factory = part.ShapeFactory
        outer_pad = factory.AddNewPad(sk_outer, h)
        part.Update()

        # Inner rectangle dimensions
        inner_w = max(outer_w - 2 * wall, 0.1)
        inner_d = max(outer_d - 2 * wall, 0.1)
        half_in_w = inner_w / 2
        half_in_d = inner_d / 2

        # Inner rectangle sketch (same plane) - centered
        sk_inner = sketches.Add(plane_xy)
        part.InWorkObject = sk_inner
        edi = sk_inner.OpenEdition()
        edi.CreateLine(half_in_w, half_in_d, half_in_w, -half_in_d)
        edi.CreateLine(half_in_w, -half_in_d, -half_in_w, -half_in_d)
        edi.CreateLine(-half_in_w, -half_in_d, -half_in_w, half_in_d)
        edi.CreateLine(-half_in_w, half_in_d, half_in_w, half_in_d)
        sk_inner.CloseEdition()
        part.Update()

        # Pocket the inner rectangle through the full rod height to hollow it out
        inner_pocket = factory.AddNewPocket(sk_inner, h)

        try:
            inner_pocket.Reverse = True
            part.Update()
        except Exception:
            try:
                factory.AddNewPocket(sk_inner, -abs(h))
                part.Update()
            except Exception:
                pass

    except Exception:
        traceback.print_exc()


def set_component_translation_to(partComp, tx=0, ty=0, tz=0):
    try:
        pos = partComp.ReferenceProduct.Position
        comps = list(pos.GetComponents())
        if len(comps) >= 16:
            comps[12] = float(tx)
            comps[13] = float(ty)
            comps[14] = float(tz)
        else:
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

    wall_thickness = params.get("ROD_WALL_THICKNESS", 2.0)

    hollow_h = params["HOLLOW_HEIGHT"]
    clearance = params.get("CLEARANCE", 0.0)

    save_dir = params["SAVE_DIR"]
    timestamped = params["SAVE_TIMESTAMPED"]

    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S") if timestamped else ""

    PART1 = os.path.join(save_dir, f"RectPlate_{ts}.CATPart")
    PART2 = os.path.join(save_dir, f"RectRod_{ts}.CATPart")
    PROD = os.path.join(save_dir, f"Assembly_{ts}.CATProduct")

    if not CATIA_AVAILABLE:
        print("CATIA not available or pywin32 missing!")
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

    # ---------------- PART 1: Baseplate with vertical hollow ----------------
    partComp1 = product.Products.AddNewComponent("Part", "RectPlate")
    try:
        partDoc1 = partComp1.GetMasterShapeRepresentation(True)
    except:
        partDoc1 = docs.Add("Part")

    partDoc1.Activate()
    create_rectangle_pad_with_vertical_hollow(
        partDoc1.Part,
        width, height, pad_thickness,
        rod_w, rod_d, hollow_h,
        clearance
    )
    # save part document (auto-accept SaveAs dialog)
    safe_save(partDoc1, PART1)

    # ---------------- PART 2: Rectangular Hollow Rod ----------------
    partComp2 = product.Products.AddNewComponent("Part", "RectRod")
    try:
        partDoc2 = partComp2.GetMasterShapeRepresentation(True)
    except:
        partDoc2 = docs.Add("Part")

    partDoc2.Activate()
    create_rect_rod_hollow(partDoc2.Part, rod_w, rod_d, rod_h, wall_thickness)
    safe_save(partDoc2, PART2)

    # Position rod exactly above base so it sits into the hollow area (if hollow exists)
    set_component_translation_to(partComp2, tz=pad_thickness)

    product.Update()

    # Save product (auto-accept SaveAs dialog)
    try:
        if os.path.exists(PROD):
            try:
                os.remove(PROD)
            except Exception as e:
                print("Warning: could not remove existing assembly file before SaveAs:", e)
    except Exception:
        
        pass

    # Start auto-accept thread and save product
    start_auto_accept_thread(timeout=6.0)
    try:
        product_doc.SaveAs(PROD)
        print("Saved assembly:", PROD)
    except Exception as e:
        print("Save warning:", e)

    pythoncom.CoUninitialize()
    print("\nCATIA model created successfully.")


if __name__ == "__main__":
    main()
