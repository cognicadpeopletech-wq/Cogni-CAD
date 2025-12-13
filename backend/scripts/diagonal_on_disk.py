# --- File: diagonal_on_disk.py ---
"""
Creates a circular disk and places holes along the two diagonals of a centered square inscribed
in the disk (TL->BR and TR->BL). Accepts --diameter, --T, --n, --offset, --dia, --cmd.
"""

#!/usr/bin/env python3
import argparse
import math
import sys
from pycatia import catia

# Helpers (shared)
def parse_args_common(parser):
    parser.add_argument("--diameter", type=float, required=True, help="Disk diameter (mm)")
    parser.add_argument("--T", type=float, required=True, help="Thickness (mm)")
    parser.add_argument("--n", type=int, default=4, help="Total holes (default 4)")
    parser.add_argument("--offset", type=float, default=0.0, help="Inset from inscribed square corner (mm)")
    parser.add_argument("--dia", type=float, default=6.0, help="Hole diameter (mm)")
    parser.add_argument("--cmd", type=str, default="", help="Original command (for legacy)")


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


def diagonal_positions_on_square_inscribed(n, diameter, offset):
    # Square inscribed in circle of diameter D has side s = D / sqrt(2)
    D = diameter
    s = D / math.sqrt(2.0)
    half = s / 2.0
    # corners of the inscribed square (centered)
    TL = (-half + offset, half - offset)
    TR = (half - offset, half - offset)
    BL = (-half + offset, -half + offset)
    BR = (half - offset, -half + offset)
    n1 = (n + 1) // 2
    n2 = n - n1
    def linspace(p1, p2, m):
        if m <= 1:
            return [((p1[0]+p2[0])/2.0, (p1[1]+p2[1])/2.0)]
        return [ (p1[0] + (p2[0]-p1[0])*(i/(m-1)), p1[1] + (p2[1]-p1[1])*(i/(m-1))) for i in range(m) ]
    pts = []
    if n1 > 0:
        pts += linspace(TL, BR, n1)
    if n2 > 0:
        pts += linspace(TR, BL, n2)
    uniq = []
    seen = set()
    for x,y in pts:
        key = (round(x,6), round(y,6))
        if key not in seen:
            seen.add(key)
            uniq.append((float(key[0]), float(key[1])))
    return uniq


def main():
    parser = argparse.ArgumentParser()
    parse_args_common(parser)
    args = parser.parse_args()

    D = args.diameter
    T = args.T
    n = args.n
    offset = args.offset
    hole_dia = args.dia

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
        disk_sk = sketches.Add(plane_xy)
        f2d = disk_sk.OpenEdition()
        R = float(D) / 2.0
        f2d.CreateClosedCircle(0.0, 0.0, float(R))
        disk_sk.CloseEdition()
        
        part.InWorkObject = disk_sk
        part.Update()
        
        sf = part.ShapeFactory
        pad = sf.AddNewPad(disk_sk, float(T))
        part.Update()
        
        # ------------------ Create Offset Plane for Holes (Top) ------------------
        hsf = part.HybridShapeFactory
        try:
            ref_xy = part.CreateReferenceFromObject(plane_xy)
            top_plane = hsf.AddNewPlaneOffset(ref_xy, float(T), False)
            body.InsertHybridShape(top_plane)
            part.Update()
            sketch_plane_ref = part.CreateReferenceFromObject(top_plane)
        except Exception:
            sketch_plane_ref = plane_xy

        hole_positions = diagonal_positions_on_square_inscribed(n, D, offset)

        made = 0
        for i,(cx,cy) in enumerate(hole_positions, start=1):
            cx2, cy2 = clamp_inside_disk(cx, cy, R)
            
            skh = sketches.Add(sketch_plane_ref)
            fsk = skh.OpenEdition()
            fsk.CreateClosedCircle(float(cx2), float(cy2), float(hole_dia)/2.0)
            skh.CloseEdition()
            
            part.InWorkObject = skh
            part.Update()
            
            # Pocket
            sf.AddNewPocket(skh, float(T))
            part.Update()
            made += 1

        print(f"Done: disk D={D} T={T} holes={made}")

    except Exception as e:
        print(f"ERROR: Failed to create geometry: {e}")
        return

    # print(f"Done: disk D={D} T={T} holes={made}")

if __name__ == '__main__':
    main()



