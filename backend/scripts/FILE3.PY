#!/usr/bin/env python3
import sys
import os
import datetime
import pythoncom
import win32com.client
import traceback

DEFAULTS = {
    "WIDTH": 200.0,
    "HEIGHT": 150.0,
    "PAD_THICKNESS": 20.0,
    "CYL_RADIUS": 25.0,
    "CYL_HEIGHT": 120.0,
    "SAVE_DIR": os.getcwd(),
}

DEFAULTS["POCKET_RADIUS"] = DEFAULTS["CYL_RADIUS"]   # pocket = cylinder radius

# -------------------------------------------------------------
# Save helper
# -------------------------------------------------------------
def safe_save_doc(doc, path):
    try:
        doc.SaveAs(path)
        print("Saved:", path)
    except Exception as e:
        print("Save failed:", e)

# -------------------------------------------------------------
# Place component
# -------------------------------------------------------------
def set_translation(partComp, tx=0, ty=0, tz=0):
    try:
        pos = partComp.ReferenceProduct.Position
        comps = list(pos.GetComponents())
        comps[12] = tx
        comps[13] = ty
        comps[14] = tz
        pos.SetComponents(comps)
    except:
        pass

# -------------------------------------------------------------
# Rectangle plate with center pocket
# -------------------------------------------------------------
def create_plate(part, W, H, T, pocket_r):

    body = part.Bodies.Item("PartBody")
    sketches = body.Sketches
    xy = part.OriginElements.PlaneXY

    # RECTANGLE
    s = sketches.Add(xy)
    part.InWorkObject = s
    f = s.OpenEdition()

    hw, hh = W / 2.0, H / 2.0
    f.CreateLine( hw,  hh,  hw, -hh)
    f.CreateLine( hw, -hh, -hw, -hh)
    f.CreateLine(-hw, -hh, -hw,  hh)
    f.CreateLine(-hw,  hh,  hw,  hh)
    s.CloseEdition()
    part.Update()

    part.ShapeFactory.AddNewPad(s, T)
    part.Update()

    # CENTER POCKET (cylinder diameter)
    s2 = sketches.Add(xy)
    part.InWorkObject = s2
    f2 = s2.OpenEdition()

    f2.CreateClosedCircle(0, 0, pocket_r)
    s2.CloseEdition()
    part.Update()

    part.ShapeFactory.AddNewPocket(s2, T)
    part.Update()


# -------------------------------------------------------------
# Cylinder creation
# -------------------------------------------------------------
def create_cylinder(part, r, h):

    body = part.Bodies.Item("PartBody")
    sketches = body.Sketches
    xy = part.OriginElements.PlaneXY

    s = sketches.Add(xy)
    part.InWorkObject = s
    f = s.OpenEdition()

    f.CreateClosedCircle(0, 0, r)
    s.CloseEdition()
    part.Update()

    part.ShapeFactory.AddNewPad(s, h)
    part.Update()

# -------------------------------------------------------------
# MAIN
# -------------------------------------------------------------
def main():

    p = DEFAULTS
    W = p["WIDTH"]
    H = p["HEIGHT"]
    T = p["PAD_THICKNESS"]
    CR = p["CYL_RADIUS"]
    CH = p["CYL_HEIGHT"]
    PR = p["POCKET_RADIUS"]
    SAVE = p["SAVE_DIR"]

    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

    part1_path = os.path.join(SAVE, f"RectPlate_{ts}.CATPart")
    part2_path = os.path.join(SAVE, f"Cylinder_{ts}.CATPart")
    product_path = os.path.join(SAVE, f"Assembly_{ts}.CATProduct")

    pythoncom.CoInitialize()
    catia = win32com.client.Dispatch("CATIA.Application")
    docs = catia.Documents

    # ASSEMBLY
    product_doc = docs.Add("Product")
    product = product_doc.Product

    # ------------------- PART 1 INSIDE ASSEMBLY -------------------
    comp1 = product.Products.AddNewComponent("Part", "RectPlate")

    try:
        partDoc1 = comp1.GetMasterShapeRepresentation(True)
    except:
        print("Error creating Part1 doc")
        return

    create_plate(partDoc1.Part, W, H, T, PR)
    safe_save_doc(partDoc1, part1_path)
    partDoc1.Close()

    # ------------------- PART 2 INSIDE ASSEMBLY -------------------
    comp2 = product.Products.AddNewComponent("Part", "Cylinder")

    try:
        partDoc2 = comp2.GetMasterShapeRepresentation(True)
    except:
        print("Error creating Part2 doc")
        return

    create_cylinder(partDoc2.Part, CR, CH)
    safe_save_doc(partDoc2, part2_path)
    partDoc2.Close()

    # Position cylinder above plate
    set_translation(comp2, 0, 0, T)

    product.Update()
    product_doc.SaveAs(product_path)
    print("Assembly saved:", product_path)

    pythoncom.CoUninitialize()


if __name__ == "__main__":
    main()
