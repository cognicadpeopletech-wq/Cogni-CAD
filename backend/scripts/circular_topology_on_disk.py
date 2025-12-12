

# --- File: circular_topology_on_disk.py ---
"""
Places N holes on a circular path inside the disk (same as circular_topology but the base
body is a circular disk rather than a rectangle). Requires --diameter, --T, --n, and --circle_dia (or --radius)
"""

#!/usr/bin/env python3
import argparse
import math
import sys
from pycatia import catia


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


def clamp_inside_disk(x, y, R):
    d = math.hypot(x, y)
    if d <= R or d == 0:
        return x, y
    scale = (R - 0.001) / d
    return x * scale, y * scale


def circular_positions(n, circle_dia):
    if n <= 0:
        return []
    r = circle_dia / 2.0
    step = 360.0 / n
    pts = []
    for i in range(n):
        a = math.radians(i * step)
        pts.append((round(r*math.cos(a),6), round(r*math.sin(a),6)))
    return pts


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--diameter', type=float, required=True, help='disk diameter')
    parser.add_argument('--T', type=float, required=True, help='thickness')
    parser.add_argument('--n', type=int, required=True, help='number of holes')
    parser.add_argument('--circle_dia', type=float, default=None, help='hole circle diameter')
    parser.add_argument('--radius', type=float, default=None, help='hole circle radius')
    parser.add_argument('--dia', type=float, default=8.0, help='hole diameter')
    args = parser.parse_args()

    D = args.diameter
    T = args.T
    n = args.n
    circle_dia = args.circle_dia
    if not circle_dia and args.radius:
        circle_dia = args.radius * 2.0
    if circle_dia is None:
        print('Error: provide --circle_dia or --radius')
        sys.exit(2)
    hole_dia = args.dia

    R = D / 2.0

    caa = catia()
    docs = caa.documents
    doc = docs.add('Part')
    part = doc.part
    sf = part.shape_factory
    bodies = part.bodies
    body = bodies.item(1)
    origin = part.origin_elements
    plane = origin.plane_xy
    sketches = body.sketches

    disk_sk = sketches.add(plane)
    f2d = disk_sk.open_edition()
    f2d.create_closed_circle(0.0, 0.0, R)
    disk_sk.close_edition()
    pad = sf.add_new_pad(disk_sk, T)
    part.update()

    sketch_plane, top_ok = find_top_plane(origin, plane, pad, T)

    hole_positions = circular_positions(n, circle_dia)

    made = 0
    for i,(cx,cy) in enumerate(hole_positions, start=1):
        cx2, cy2 = clamp_inside_disk(cx, cy, R)
        skh = sketches.add(sketch_plane)
        fsk = skh.open_edition()
        fsk.create_closed_circle(cx2, cy2, hole_dia/2.0)
        skh.close_edition()
        depth = T if top_ok else -abs(T)
        sf.add_new_pocket(skh, depth)
        part.update()
        made += 1

    # print(f"Done: disk D={D}, circle_dia={circle_dia}, holes={made}")

if __name__ == '__main__':
    main()
