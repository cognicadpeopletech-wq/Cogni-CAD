# circular_topology_holes.py
"""
Create a centered rectangular plate and add 4 equidistant holes arranged on a circle
(angles 0°, 90°, 180°, 270°).

Usage:
    python circular_topology_holes.py
"""
import math
import sys
import time
import subprocess
import shutil
from win32com.client import Dispatch, gencache

# ------------------------- connect (robust) -------------------------
def connect_to_catia():
    """Try to connect to a running CATIA; try to launch common executables if needed and poll."""
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
        raise RuntimeError(
            "Could not connect to CATIA via COM and no CATIA executable found on PATH. "
            "Start CATIA manually or edit this script to point to the CATIA start executable."
        )
    timeout = 30.0
    poll_interval = 0.7
    waited = 0.0
    while waited < timeout:
        try:
            return Dispatch("CATIA.Application")
        except Exception:
            time.sleep(poll_interval)
            waited += poll_interval
    try:
        return gencache.EnsureDispatch("CATIA.Application")
    except Exception:
        raise RuntimeError("Unable to start/connect to CATIA after attempts.")

# ------------------------- USER PARAMETERS -------------------------
LENGTH = 400.0      # mm
WIDTH = 300.0       # mm
THICKNESS = 50.0    # mm

CIRCLE_DIAMETER = 200.0
HOLE_DIA = 30.0
HOLE_DEPTH = THICKNESS

# ------------------------- CATIA functions -------------------------
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
    hx = length / 2.0
    hy = width / 2.0
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

def make_hole(part, sketches, plane, sf, pos_x, pos_y, dia, depth, sketch_name=None):
    sk = sketches.Add(plane)
    if sketch_name:
        try:
            sk.Name = sketch_name
        except Exception:
            pass
    fsk = sk.OpenEdition()
    fsk.CreateClosedCircle(pos_x, pos_y, dia/2.0)
    sk.CloseEdition()
    part.Update()
    sf.AddNewPocket(sk, -abs(depth))
    part.Update()

def add_circle_holes(part, sketches, plane, sf, circle_dia, hole_dia, hole_depth):
    radius = circle_dia/2.0
    angles = [0, 90, 180, 270]
    for idx, angle in enumerate(angles, start=1):
        rad = math.radians(angle)
        px = radius * math.cos(rad)
        py = radius * math.sin(rad)
        make_hole(part, sketches, plane, sf, px, py, hole_dia, hole_depth, sketch_name=f"Hole_Circle_{idx}")

# ------------------------- MAIN -------------------------
def main():
    catia = connect_to_catia()
    part_doc, part, body, sketches, plane = new_part(catia)
    sf = create_centered_rectangle_and_pad(part, sketches, plane, LENGTH, WIDTH, THICKNESS)
    add_circle_holes(part, sketches, plane, sf, CIRCLE_DIAMETER, HOLE_DIA, HOLE_DEPTH)
    try:
        catia.ActiveWindow.ActiveViewer.Reframe()
    except Exception:
        pass
    print(f"Created plate {LENGTH}x{WIDTH}x{THICKNESS} with circle-topology holes.")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("Error:", e)
        sys.exit(1)
