#!/usr/bin/env python3
"""
circular_squared_disk.py

Worker script for CATIA circular disk + N square-holes creation.

New:
 - Robust CATIA connection with retries and clearer error messages.
 - --preview flag: print actions and exit without calling CATIA (useful for debugging).
"""
import argparse
import math
import sys
import time
from typing import List, Tuple

# try multiple import styles used in different pycatia versions
try:
    from pycatia import CATIA
except Exception:
    try:
        from pycatia import catia as CATIA  # fallback name
    except Exception:
        CATIA = None


# -----------------------
# CLI ARG PARSER
# -----------------------
def parse_args():
    parser = argparse.ArgumentParser(description="Create circular disk with N square holes using PyCATIA")
    parser.add_argument("--diameter", type=float, required=True, help="Disk diameter (mm)")
    parser.add_argument("--T", type=float, required=True, help="Thickness (mm)")
    parser.add_argument("--hole", action="append", default=[], help="hole=x,y,side (repeatable). side = square side length in mm")
    parser.add_argument("--cmd", type=str, default="", help="Original user command")
    parser.add_argument("--detected", type=str, default="", help="Debug token from caller")
    parser.add_argument("--preview", action="store_true", help="Do not call CATIA; just print actions (for debug)")
    return parser.parse_args()


# -----------------------
# Helpers
# -----------------------
def parse_hole_token(token: str):
    parts = [p.strip() for p in token.split(",")]
    if len(parts) != 3:
        raise ValueError(f"Bad hole token: {token}  -- expected x,y,side")
    return float(parts[0]), float(parts[1]), float(parts[2])


def clamp_inside_disk(x, y, R):
    dist = math.hypot(x, y)
    if dist <= R or dist == 0:
        return x, y
    scale = (R - 0.001) / dist
    return x * scale, y * scale


def find_top_plane(origin, xy_plane, pad, thickness):
    # Try newer offset plane API
    try:
        p = origin.add_new_plane_offset(xy_plane, thickness)
        return p, True
    except Exception:
        pass

    # Try older offset plane creation
    try:
        p = origin.add_new_plane_offset(xy_plane)
        if hasattr(p, "distance"):
            p.distance = thickness
        elif hasattr(p, "set_distance"):
            p.set_distance(thickness)
        return p, True
    except Exception:
        pass

    # Detect pad top face (fallback)
    try:
        faces = pad.faces
        top_face = None
        max_z = None
        for i in range(1, faces.count + 1):
            f = faces.item(i)
            bb_fn = getattr(f, "GetBox", None) or getattr(f, "get_bounding_box", None)
            if callable(bb_fn):
                try:
                    bb = bb_fn()
                    zmax = bb[5]
                except Exception:
                    continue
            else:
                continue
            if max_z is None or zmax > max_z:
                max_z = zmax
                top_face = f
        if top_face is not None:
            return top_face, True
    except Exception:
        pass

    return xy_plane, False


def connect_to_catia(retries: int = 6, delay: float = 1.0):
    """
    Attempt to attach to a running CATIA via pycatia. Retry for (retries * delay) seconds.
    Returns 'caa' object on success or raises RuntimeError with helpful message.
    """
    if CATIA is None:
        raise RuntimeError("pycatia not found. Install with 'pip install pycatia' and ensure Python bitness matches CATIA.")
    last_exc = None
    for attempt in range(1, retries + 1):
        try:
            # try callable style (some versions expose class/function)
            if callable(CATIA):
                caa = CATIA()
            else:
                caa = CATIA
            # quick sanity access
            _ = getattr(caa, "documents", None)
            return caa
        except Exception as e:
            last_exc = e
            time.sleep(delay)
    # If we reach here, advise user the most common environment fixes
    msg = (
        "Unable to connect to CATIA via pycatia.\n"
        "Common causes:\n"
        " - CATIA is not running on this machine.\n"
        " - Python process runs as a different Windows user (or lacks admin rights).\n"
        " - Python bitness differs from CATIA (use 64-bit Python if CATIA is 64-bit).\n"
        " - pycatia not installed or incompatible version.\n"
        f"Last error: {last_exc}"
    )
    raise RuntimeError(msg)


# -----------------------
# Main worker function
# -----------------------
def main():
    args = parse_args()
    disk_dia = args.diameter
    T = args.T
    hole_tokens = args.hole
    preview = args.preview
    R = disk_dia / 2.0

    if not hole_tokens:
        print("ERROR: No holes provided. Use --hole=x,y,side (repeatable)")
        sys.exit(2)

    # Parse hole tokens
    holes: List[Tuple[float, float, float]] = []
    for tok in hole_tokens:
        try:
            x, y, side = parse_hole_token(tok)
        except Exception as e:
            print(f"ERROR: {e}")
            sys.exit(3)
        if side <= 0:
            print(f"ERROR: Invalid side length for hole: {tok}  (side must be > 0)")
            sys.exit(4)
        holes.append((x, y, side))

    # PREVIEW mode: print what we would do and exit
    if preview:
        print("Preview mode - no CATIA calls will be made.")
        print(f"Disk: diameter={disk_dia} mm, thickness={T} mm, radius={R} mm")
        for i, (x, y, side) in enumerate(holes, 1):
            xc, yc = clamp_inside_disk(x, y, R)
            if (xc, yc) != (x, y):
                note = f"(clamped from {x},{y} to {xc:.3f},{yc:.3f})"
            else:
                note = ""
            print(f" Hole {i}: center=({xc:.3f},{yc:.3f}) side={side} mm {note}")
        if args.cmd:
            print("Command:", args.cmd)
        sys.exit(0)

    # Connect to CATIA (win32com)
    import pythoncom
    from win32com.client import Dispatch

    try:
        pythoncom.CoInitialize()
        catia = Dispatch("CATIA.Application")
        catia.Visible = True
    except Exception as e:
        print(f"ERROR: Could not connect to CATIA: {e}")
        return

    try:
        documents = catia.Documents
        doc = documents.Add("Part")
        part = doc.Part
        
        bodies = part.Bodies
        body = bodies.Item("PartBody")
        origin = part.OriginElements
        xy_plane = origin.PlaneXY
        sketches = body.Sketches
        
        # Disk
        disk_sketch = sketches.Add(xy_plane)
        f2d = disk_sketch.OpenEdition()
        f2d.CreateClosedCircle(0.0, 0.0, float(R))
        disk_sketch.CloseEdition()
        
        part.InWorkObject = disk_sketch
        part.Update()
        
        sf = part.ShapeFactory
        pad = sf.AddNewPad(disk_sketch, float(T))
        part.Update()
        
        # Offset Plane - Disabled to ensure Pocket direction is correct (Use XY)
        sketch_plane_ref = xy_plane

        # Determine top plane - Unused
        # sketch_plane, top_ok = find_top_plane(origin, xy_plane, pad, T)

    # Create square holes
    made = 0
    for x, y, side in holes:
        xc, yc = clamp_inside_disk(x, y, R)
        
        hole_sketch = sketches.Add(sketch_plane_ref)
        hf2d = hole_sketch.OpenEdition()

        # CreateCenteredRectangle(CenterX, CenterY, Width, Height)
        # Or manually if that fails (some licenses don't support it)
        half = float(side) / 2.0
        x1 = xc - half
        y1 = yc - half
        x2 = xc + half
        y2 = yc + half
        
        # Win32com CreateLine(x1, y1, x2, y2)
        hf2d.CreateLine(float(x1), float(y1), float(x2), float(y1))
        hf2d.CreateLine(float(x2), float(y1), float(x2), float(y2))
        hf2d.CreateLine(float(x2), float(y2), float(x1), float(y2))
        hf2d.CreateLine(float(x1), float(y2), float(x1), float(y1))

        hole_sketch.CloseEdition()
        
        part.InWorkObject = hole_sketch
        part.Update()
        
        sf.AddNewPocket(hole_sketch, float(T))
        part.Update()
        made += 1

    print(f"Done: Disk diameter={disk_dia} mm, thickness={T} mm, square_holes={made}")
    if args.cmd:
        print(f"Command: {args.cmd}")


if __name__ == "__main__":
    main()
