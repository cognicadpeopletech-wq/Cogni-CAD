
# --- File: equidistant_on_disk.py ---
"""
Places N holes equidistantly along X or Y (centered) but constrained to lie inside a circular disk.
Accepts --diameter, --T, --n, --orientation (x|y), --spacing, --midpoint, --offset, --dia
"""

#!/usr/bin/env python3
import argparse
import math
import sys
from pycatia import catia


def clamp_inside_disk(x, y, R):
    d = math.hypot(x, y)
    if d <= R or d == 0:
        return x, y
    scale = (R - 0.001) / d
    return x * scale, y * scale


def find_top_plane(origin, xy_plane, pad, thickness):
    try:
        p = origin.add_new_plane_offset(xy_plane, thickness)
        return p, True
    except Exception:
        pass
    try:
        p = origin.add_new_plane_offset(xy_plane)
        if hasattr(p, "distance"):
            p.distance = thickness
        elif hasattr(p, "set_distance"):
            p.set_distance(thickness)
        return p, True
    except Exception:
        pass
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


def compute_linear_positions(n, stroke_length, spacing=None, midpoint=True):
    if n <= 0:
        return []
    if spacing is not None:
        span = spacing * (n - 1)
        if span > stroke_length and n > 1:
            spacing = stroke_length / (n - 1)
            span = spacing * (n - 1)
    else:
        spacing = 0.0 if n == 1 else stroke_length / (n - 1)
        span = spacing * (n - 1)
    start = -span / 2.0 if midpoint else -stroke_length / 2.0
    return [round(start + i * spacing, 6) for i in range(n)]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--diameter', type=float, required=True)
    parser.add_argument('--T', type=float, required=True)
    parser.add_argument('--n', type=int, default=4)
    parser.add_argument('--orientation', choices=['x','y'], default='x')
    parser.add_argument('--spacing', type=float, default=None)
    parser.add_argument('--midpoint', type=int, choices=[0,1], default=1)
    parser.add_argument('--offset', type=float, default=20.0)
    parser.add_argument('--dia', type=float, default=6.0)
    parser.add_argument("--cmd", type=str, default="", help="Original command")
    args = parser.parse_args()

    D = args.diameter
    T = args.T
    n = args.n
    orientation = args.orientation
    spacing = args.spacing
    midpoint = bool(args.midpoint)
    offset = args.offset
    hole_dia = args.dia

    R = D / 2.0

    # stroke is limited by the square inscribed or full diameter minus 2*offset depending on orientation
    if orientation == 'x':
        stroke = max(0.0, D - 2.0*offset)
        xs = compute_linear_positions(n, stroke, spacing, midpoint)
        positions = [(x - 0.0, 0.0) for x in xs]
    else:
        stroke = max(0.0, D - 2.0*offset)
        ys = compute_linear_positions(n, stroke, spacing, midpoint)
        positions = [(0.0, y) for y in ys]

    # create disk and holes in CATIA (win32com)
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
        doc = documents.Add('Part')
        part = doc.Part
        bodies = part.Bodies
        body = bodies.Item("PartBody")
        origin = part.OriginElements
        xy_plane = origin.PlaneXY
        sketches = body.Sketches
        
        # Disk
        disk_sk = sketches.Add(xy_plane)
        f2d = disk_sk.OpenEdition()
        f2d.CreateClosedCircle(0.0,0.0,float(R))
        disk_sk.CloseEdition()
        
        part.InWorkObject = disk_sk
        part.Update()
        
        sf = part.ShapeFactory
        pad = sf.AddNewPad(disk_sk, float(T))
        part.Update()
        
        # Offset Plane
        hsf = part.HybridShapeFactory
        try:
            ref_xy = part.CreateReferenceFromObject(xy_plane)
            top_plane = hsf.AddNewPlaneOffset(ref_xy, float(T), False)
            body.InsertHybridShape(top_plane)
            part.Update()
            sketch_plane_ref = part.CreateReferenceFromObject(top_plane)
        except Exception:
            sketch_plane_ref = xy_plane
            
        made = 0
        for i,(cx,cy) in enumerate(positions, start=1):
            cx2, cy2 = clamp_inside_disk(cx, cy, R)
            
            skh = sketches.Add(sketch_plane_ref)
            fsk = skh.OpenEdition()
            fsk.CreateClosedCircle(float(cx2), float(cy2), float(hole_dia)/2.0)
            skh.CloseEdition()
            
            part.InWorkObject = skh
            part.Update()
            
            sf.AddNewPocket(skh, float(T))
            part.Update()
            made += 1
            
        # print(f"Done: disk D={D}, T={T}, holes={made}")
        # if args.cmd:
            # print(f"Command: {args.cmd}")
            
    except Exception as e:
        print(f"ERROR: Failed to create geometry: {e}")
        return

if __name__ == '__main__':
    main()
