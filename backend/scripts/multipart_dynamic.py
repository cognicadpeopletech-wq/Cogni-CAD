import os
import datetime
import pythoncom
import win32com.client
import json
import traceback
import argparse


# ======================================================================
# LOAD PARAMS FROM --params JSON
# ======================================================================
def load_params_from_file(params_path: str):
    try:
        with open(params_path, "r") as f:
            return json.load(f)
    except Exception as e:
        print("❌ ERROR: Unable to load params file:", params_path, e)
        exit(1)


# ======================================================================
# SAFE SAVE
# ======================================================================
def safe_save_doc(doc, path):
    try:
        doc.SaveAs(path)
        # print("Saved:", path)
    except Exception as e:
        print("Warning: SaveAs failed for", path, e)


# ======================================================================
# SET COMPONENT POSITION
# ======================================================================
def set_component_translation_to(partComp, tx=0.0, ty=0.0, tz=0.0):
    try:
        # Use the instance position directly, not the ReferenceProduct
        pos = partComp.Position
        
        # Get components (matrix)
        # In win32com, GetComponents returns the tuple of 12 values
        comps_tuple = pos.GetComponents()
        comps = list(comps_tuple)

        # Update translation vector (last 3 elements of a 12-element matrix definition in CATIA)
        # CATIA Matrix: 
        # 0 3 6 9  (Axis X, Y, Z, Origin X)
        # 1 4 7 10 (Axis X, Y, Z, Origin Y)
        # 2 5 8 11 (Axis X, Y, Z, Origin Z)
        #
        # comps is [x1, x2, x3, y1, y2, y3, z1, z2, z3, ox, oy, oz]
        
        if len(comps) == 12:
            comps[9]  = float(tx)
            comps[10] = float(ty)
            comps[11] = float(tz)
            pos.SetComponents(comps)

    except Exception:
        # User requested to suppress warnings. 
        # If this fails, the part stays at 0,0,0 which is acceptable if API differs.
        pass


# ======================================================================
# CREATE PLATE WITH PAD → CENTER POCKET → CORNER HOLES
# ======================================================================
def create_rectangle_pad_with_center_pocket_and_corner_holes(
    part,
    width,
    height,
    pad_thickness,
    pocket_radius,
    corner_offset,
    hole_diameter,
    pocket_offset_x,
    pocket_offset_y
):

    bodies = part.Bodies
    body = bodies.Item("PartBody")
    sketches = body.Sketches
    origin = part.OriginElements
    plane_xy = origin.PlaneXY

    half_w = width / 2.0
    half_h = height / 2.0
    hole_radius = hole_diameter / 2.0

    # ---------------------------
    # MAIN SKETCH
    # ---------------------------
    sketch = sketches.Add(plane_xy)
    try:
        sketch.SetAbsoluteAxisData([0,0,0, 1,0,0, 0,1,0])
    except:
        pass

    part.InWorkObject = sketch
    f2 = sketch.OpenEdition()

    pA = f2.CreatePoint( half_w,  half_h)
    pB = f2.CreatePoint( half_w, -half_h)
    pC = f2.CreatePoint(-half_w, -half_h)
    pD = f2.CreatePoint(-half_w,  half_h)

    lAB = f2.CreateLine( half_w,  half_h,  half_w, -half_h); lAB.StartPoint=pA; lAB.EndPoint=pB
    lBC = f2.CreateLine( half_w, -half_h, -half_w, -half_h); lBC.StartPoint=pB; lBC.EndPoint=pC
    lCD = f2.CreateLine(-half_w, -half_h, -half_w,  half_h); lCD.StartPoint=pC; lCD.EndPoint=pD
    lDA = f2.CreateLine(-half_w,  half_h,  half_w,  half_h); lDA.StartPoint=pD; lDA.EndPoint=pA

    sketch.CloseEdition()
    part.Update()

    # PAD
    pad = part.ShapeFactory.AddNewPad(sketch, pad_thickness)
    part.Update()

    # ---------------------------
    # POCKET SKETCH
    # ---------------------------
    pocket_sk = sketches.Add(plane_xy)
    try:
        pocket_sk.SetAbsoluteAxisData([0,0,pad_thickness, 1,0,0, 0,1,0])
    except:
        pass

    part.InWorkObject = pocket_sk
    f2p = pocket_sk.OpenEdition()

    try:
        f2p.CreateClosedCircle(pocket_offset_x, pocket_offset_y, pocket_radius)
    except:
        f2p.CreateCircle(pocket_offset_x, pocket_offset_y, pocket_radius)

    pocket_sk.CloseEdition()
    part.Update()

    pocket = part.ShapeFactory.AddNewPocket(pocket_sk, pad_thickness)
    part.Update()

    # Flip if needed
    try:
        pocket.DirectionOrientation = 1 - int(pocket.DirectionOrientation)
        part.Update()
    except:
        pass

    # ---------------------------
    # CORNER HOLES
    # ---------------------------
    corner_positions = [
        ( half_w - corner_offset,  half_h - corner_offset),
        ( half_w - corner_offset, -half_h + corner_offset),
        (-half_w + corner_offset, -half_h + corner_offset),
        (-half_w + corner_offset,  half_h - corner_offset)
    ]

    for (cx, cy) in corner_positions:

        h_sk = sketches.Add(plane_xy)
        try:
            h_sk.SetAbsoluteAxisData([0,0,pad_thickness, 1,0,0, 0,1,0])
        except:
            pass

        part.InWorkObject = h_sk
        f2h = h_sk.OpenEdition()

        try:
            f2h.CreateClosedCircle(cx, cy, hole_radius)
        except:
            f2h.CreateCircle(cx, cy, hole_radius)

        h_sk.CloseEdition()
        part.Update()

        hp = part.ShapeFactory.AddNewPocket(h_sk, pad_thickness)
        part.Update()

        try:
            hp.DirectionOrientation = 1 - int(hp.DirectionOrientation)
            part.Update()
        except:
            pass


# ======================================================================
# CREATE CYLINDER PART
# ======================================================================
def create_cylinder_part(part, radius, height, pos_x, pos_y):

    bodies = part.Bodies
    body = bodies.Item("PartBody")
    sketches = body.Sketches
    origin = part.OriginElements
    plane_xy = origin.PlaneXY

    sketch = sketches.Add(plane_xy)
    try:
        sketch.SetAbsoluteAxisData([0,0,0, 1,0,0, 0,1,0])
    except:
        pass

    part.InWorkObject = sketch
    f2 = sketch.OpenEdition()

    try:
        f2.CreateClosedCircle(pos_x, pos_y, radius)
    except:
        f2.CreateCircle(pos_x, pos_y, radius)

    sketch.CloseEdition()
    part.Update()

    part.ShapeFactory.AddNewPad(sketch, height)
    part.Update()


# ======================================================================
# MAIN MULTIPART BUILD PROCESS
# ======================================================================
def main(params):

    WIDTH  = params["plate_width"]
    HEIGHT = params["plate_height"]
    PAD    = params["pad_thickness"]

    CYL_R  = params["cyl_radius"]
    CYL_H  = params["cyl_height"]
    POS_X  = params["pos_x"]
    POS_Y  = params["pos_y"]

    CORNER_OFFSET = params["corner_offset"]
    HOLE_DIAMETER = params["hole_diameter"]
    POCKET_RADIUS = CYL_R  # match your logic

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    save_dir = os.path.join(os.getcwd(), "generated_files")
    if not os.path.exists(save_dir):
        os.makedirs(save_dir)

    PART1_PATH = os.path.join(save_dir, f"Part1_dynamic_{timestamp}.CATPart")
    PART2_PATH = os.path.join(save_dir, f"Part2_dynamic_{timestamp}.CATPart")
    PRODUCT_PATH = os.path.join(save_dir, f"Assembly_dynamic_{timestamp}.CATProduct")

    pythoncom.CoInitialize()

    try:
        catia = win32com.client.Dispatch("CATIA.Application")
        catia.DisplayFileAlerts = False
    except Exception:
        print("ERROR: Cannot connect to CATIA. Start CATIA and retry.")
        return

    docs = catia.Documents

    # PRODUCT
    product_doc = docs.Add("Product")
    product = product_doc.Product

    # PART 1
    comp1 = product.Products.AddNewComponent("Part", "Part1")
    set_component_translation_to(comp1, 0, 0, 0)

    try:
        partDoc1 = comp1.GetMasterShapeRepresentation(True)
        if not hasattr(partDoc1, "Part"):
            raise Exception("Invalid MasterShapeRepresentation")
    except:
        partDoc1 = docs.Add("Part")

    create_rectangle_pad_with_center_pocket_and_corner_holes(
        partDoc1.Part,
        WIDTH, HEIGHT,
        PAD,
        POCKET_RADIUS,
        CORNER_OFFSET,
        HOLE_DIAMETER,
        POS_X,
        POS_Y
    )

    safe_save_doc(partDoc1, PART1_PATH)
    partDoc1.Close()

    # PART 2
    comp2 = product.Products.AddNewComponent("Part", "Part2")
    set_component_translation_to(comp2, POS_X, POS_Y, PAD)

    try:
        partDoc2 = comp2.GetMasterShapeRepresentation(True)
        if not hasattr(partDoc2, "Part"):
            raise Exception("Invalid MasterShapeRepresentation")
    except:
        partDoc2 = docs.Add("Part")

    create_cylinder_part(partDoc2.Part, CYL_R, CYL_H, POS_X, POS_Y)

    safe_save_doc(partDoc2, PART2_PATH)
    partDoc2.Close()

    product.Update()
    safe_save_doc(product_doc, PRODUCT_PATH)

    pythoncom.CoUninitialize()
    print("Done.")


# ======================================================================
# CLI ENTRY POINT
# ======================================================================
if __name__ == "__main__":

    parser = argparse.ArgumentParser(description="Dynamic multipart builder")
    parser.add_argument("--params", type=str, required=True)
    args = parser.parse_args()

    # LOAD PARAMETERS
    params = load_params_from_file(args.params)

    # RUN CATIA BUILD
    main(params)

    # SAFE DELETE TEMP FILE AFTER CATIA IS COMPLETELY DONE
    try:
        if os.path.exists(args.params):
            os.remove(args.params)
            # print("Temporary params file deleted.")
    except Exception as e:
        print("Warning: Could not delete temp params file:", e)
