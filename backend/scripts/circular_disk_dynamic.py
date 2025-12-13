#!/usr/bin/env python3
"""
circular_disk_dynamic.py

Worker script for CATIA circular disk + N-hole creation.
"""

import argparse
import math
import sys
from pycatia import catia


# -------------------------------------------------------
# CLI ARGUMENT PARSER
# -------------------------------------------------------
def parse_args():
    parser = argparse.ArgumentParser(description="Create circular disk with N holes using PyCATIA")
    parser.add_argument("--diameter", type=float, required=True, help="Disk diameter (mm)")
    parser.add_argument("--T", type=float, required=True, help="Thickness (mm)")
    parser.add_argument("--hole", action="append", default=[], help="hole=x,y,d (repeatable)")
    parser.add_argument("--cmd", type=str, default="", help="Original user command")
    return parser.parse_args()


# -------------------------------------------------------
# HELPERS
# -------------------------------------------------------
def parse_hole(s: str):
    parts = [p.strip() for p in s.split(",")]
    if len(parts) != 3:
        raise ValueError(f"Bad hole format: {s}")
    return float(parts[0]), float(parts[1]), float(parts[2])


def clamp_inside_disk(x, y, R):
    dist = math.hypot(x, y)
    if dist <= R or dist == 0:
        return x, y
    scale = (R - 0.001) / dist
    return x * scale, y * scale


def find_top_plane(origin, xy_plane, pad, thickness):
    # Try offset plane (newer CATIA)
    try:
        p = origin.add_new_plane_offset(xy_plane, thickness)
        return p, True
    except:
        pass

    # Try older-style offset plane creation
    try:
        p = origin.add_new_plane_offset(xy_plane)
        if hasattr(p, "distance"):
            p.distance = thickness
        elif hasattr(p, "set_distance"):
            p.set_distance(thickness)
        return p, True
    except:
        pass

    # Try detecting pad top face
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
                except:
                    continue
            else:
                continue

            if max_z is None or zmax > max_z:
                max_z = zmax
                top_face = f

        if top_face is not None:
            return top_face, True
    except:
        pass

    # Fallback: XY plane
    return xy_plane, False


# -------------------------------------------------------
# MAIN LOGIC
# -------------------------------------------------------
# -------------------------------------------------------
# MAIN LOGIC (win32com)
# -------------------------------------------------------
def main():
    args = parse_args()

    disk_dia = args.diameter
    T = args.T
    hole_tokens = args.hole
    R = disk_dia / 2.0

    if not hole_tokens:
        print("ERROR: No holes provided. Use --hole=x,y,d")
        return # Safe exit

    # Parse holes
    holes = []
    for h in hole_tokens:
        try:
            x, y, d = parse_hole(h)
            if d <= 0:
                print(f"ERROR: Invalid diameter for hole: {h}")
                return
            holes.append((x, y, d))
        except:
            continue

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
        sketches = body.Sketches
        origin = part.OriginElements
        plane_xy = origin.PlaneXY
        
        # ------------------ Create disk ------------------
        disk_sketch = sketches.Add(plane_xy)
        f2d = disk_sketch.OpenEdition()
        f2d.CreateClosedCircle(0.0, 0.0, float(R))
        disk_sketch.CloseEdition()
        
        part.InWorkObject = disk_sketch
        part.Update()
        
        sf = part.ShapeFactory
        pad = sf.AddNewPad(disk_sketch, float(T))
        part.Update()
        
        # ------------------ Create Offset Plane for Holes (Top) ------------------
        # Improve hole visibility by sketching on top
        hsf = part.HybridShapeFactory
        try:
            ref_xy = part.CreateReferenceFromObject(plane_xy)
            top_plane = hsf.AddNewPlaneOffset(ref_xy, float(T), False)
            body.InsertHybridShape(top_plane)
            part.Update()
            sketch_plane_ref = part.CreateReferenceFromObject(top_plane)
        except Exception:
            # Fallback to XY if GSD fails
            sketch_plane_ref = plane_xy

        # ------------------ Create Holes ------------------
        made = 0
        for (x, y, d) in holes:
            x2, y2 = clamp_inside_disk(x, y, R)
            
            hole_sketch = sketches.Add(sketch_plane_ref)
            hf2d = hole_sketch.OpenEdition()
            hf2d.CreateClosedCircle(float(x2), float(y2), float(d) / 2.0)
            hole_sketch.CloseEdition()
            
            part.InWorkObject = hole_sketch
            part.Update()
            
            # Pocket
            # If on top plane, pocket goes down (default direction is usually normal inverted?)
            # Actually default Pad goes +Z, Pocket usually goes -Z from sketch plane? 
            # Or "Into material". 
            # Let's try AddNewPocket.
            pocket = sf.AddNewPocket(hole_sketch, float(T))
            part.Update()
            
            made += 1

        print(f"Done: Disk diameter={disk_dia} mm, thickness={T} mm, holes={made}")
        if args.cmd:
            print(f"Command: {args.cmd}")

    except Exception as e:
        print(f"ERROR: Failed to create geometry: {e}")
        return

if __name__ == "__main__":
    main()
