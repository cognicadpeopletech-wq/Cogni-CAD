# equidistant_line_holes.py
"""
Create a centered rectangular plate and add N equidistant holes along the plate centerline.

Usage:
    python equidistant_line_holes.py
"""
import sys
import time
import subprocess
import shutil
from win32com.client import Dispatch, gencache

# ------------------------- connect (robust) -------------------------
def connect_to_catia():
    candidates = ["CNEXT.exe", "CATIA.exe", "CATStart.exe"]
    try:
        return Dispatch("CATIA.Application")
    except Exception:
        pass
    try:
        return gencache.EnsureDispatch("CATIA.Application")
    except Exception:
        pass
    found_exec = None
    for exe in candidates:
        path = shutil.which(exe)
        if path:
            found_exec = path
            break
    if found_exec:
        try:
            subprocess.Popen([found_exec])
        except Exception:
            try:
                subprocess.Popen(found_exec, shell=True)
            except Exception:
                pass
    else:
        raise RuntimeError("Could not connect to CATIA; no start executable found on PATH.")
    timeout = 30.0
    poll_interval = 0.7
    waited = 0.0
    while waited < timeout:
        try:
            return Dispatch("CATIA.Application")
        except Exception:
            time.sleep(poll_interval)
            waited += poll_interval
    return gencache.EnsureDispatch("CATIA.Application")

# ------------------------- USER PARAMETERS -------------------------
LENGTH = 300.0
WIDTH = 120.0
THICKNESS = 16.0

NUM_HOLES = 4
HOLE_DIA = 16
HOLE_DEPTH = 16
HOLE_SPACING = 75

# ------------------------- CATIA helpers -------------------------
def new_part(catia):
    docs = catia.Documents
    part_doc = docs.Add("Part")
    part = part_doc.Part
    bodies = part.Bodies
    body = bodies.Add()
    body.Name = "PartBody"
    sketches = body.Sketches
    origin = part.OriginElements
    plane = origin.PlaneXY
    return part_doc, part, body, sketches, plane

def create_centered_rectangle_and_pad(part, sketches, plane, length, width, thickness):
    hx = length/2.0
    hy = width/2.0
    base_sketch = sketches.Add(plane)
    f2d = base_sketch.OpenEdition()
    f2d.CreateLine(-hx, -hy, hx, -hy)
    f2d.CreateLine(hx, -hy, hx, hy)
    f2d.CreateLine(hx, hy, -hx, hy)
    f2d.CreateLine(-hx, hy, -hx, -hy)
    base_sketch.CloseEdition()
    part.Update()
    sf = part.ShapeFactory
    sf.AddNewPad(base_sketch, thickness)
    part.Update()
    return sf

def add_equidistant_holes(part, sketches, plane, sf, num_holes, dia, depth, spacing):
    sk = sketches.Add(plane)
    try:
        sk.Name = "Holes_Line"
    except Exception:
        pass
    fsk = sk.OpenEdition()
    startX = -spacing * (num_holes - 1) / 2.0
    for i in range(num_holes):
        x = startX + i * spacing
        fsk.CreateClosedCircle(x, 0.0, dia/2.0)
    sk.CloseEdition()
    part.Update()
    sf.AddNewPocket(sk, -abs(depth))
    part.Update()

# ------------------------- MAIN -------------------------
def main():
    catia = connect_to_catia()
    part_doc, part, body, sketches, plane = new_part(catia)
    sf = create_centered_rectangle_and_pad(part, sketches, plane, LENGTH, WIDTH, THICKNESS)
    add_equidistant_holes(part, sketches, plane, sf, NUM_HOLES, HOLE_DIA, HOLE_DEPTH, HOLE_SPACING)
    try:
        catia.ActiveWindow.ActiveViewer.Reframe()
    except Exception:
        pass
    print(f"Created plate with {NUM_HOLES} holes spaced {HOLE_SPACING} mm along centerline.")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("Error:", e)
        sys.exit(1)
