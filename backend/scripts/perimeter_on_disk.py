
# --- File: perimeter_on_disk.py ---
"""
Places N holes equally spaced around a circular path inside the disk.
This is equivalent to perimeter but projected onto a circle of given radius.
Flags: --diameter, --T, --n, --radius (optional), --offset (inward from disk edge), --dia
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


def circular_perimeter_positions(n, radius):
    if n <= 0:
        return []
    step = 360.0 / n
    pts = []
    for i in range(n):
        a = math.radians(i * step)
        x = radius * math.cos(a)
        y = radius * math.sin(a)
        pts.append((round(x,6), round(y,6)))
    return pts


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--diameter', type=float, required=True)
    parser.add_argument('--T', type=float, required=True)
    parser.add_argument('--n', type=int, default=12)
    parser.add_argument('--radius', type=float, default=None, help='Circle radius for holes (mm)')
    parser.add_argument('--offset', type=float, default=20.0)
    parser.add_argument('--dia', type=float, default=6.0)
    parser.add_argument("--cmd", type=str, default="", help="Original command")
    args = parser.parse_args()

    D = args.diameter
    T = args.T
    n = args.n
    offset = args.offset
    hole_dia = args.dia

    R = D / 2.0
    # radius logic
    radius = args.radius if args.radius is not None else max(0.0, R - offset)

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
        plane = origin.PlaneXY
        sketches = body.Sketches
        
        # Disk
        disk_sk = sketches.Add(plane)
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
            ref_xy = part.CreateReferenceFromObject(plane)
            top_plane = hsf.AddNewPlaneOffset(ref_xy, float(T), False)
            body.InsertHybridShape(top_plane)
            part.Update()
            sketch_plane_ref = part.CreateReferenceFromObject(top_plane)
        except Exception:
            sketch_plane_ref = plane
            
        hole_positions = circular_perimeter_positions(n, radius)
        
        made = 0
        for i,(cx,cy) in enumerate(hole_positions, start=1):
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

        print(f"Done: disk D={D}, holes={made} on radius={radius}")
        if args.cmd:
            print(f"Command: {args.cmd}")

    except Exception as e:
        print(f"ERROR: Failed to create geometry: {e}")
        return

if __name__ == '__main__':
    main()