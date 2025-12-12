#!/usr/bin/env python3
"""
perimeter_SQURED_on_disk.py

Standalone script to create a circular disk, N square holes equally spaced
around a circle (radius or offset), and an optional circular hole at center.

Flags:
  --diameter DIAMETER   (required)
  --T T                 (required) thickness
  --n N                 (number of equally spaced perimeter holes)
  --radius RADIUS       (circle radius for hole centers)
  --offset OFFSET       (inward offset from disk edge; radius = diameter/2 - offset)
  --square_side SIDE    (side length of each square hole)
  --center_dia DIA      (optional center circular hole diameter)
"""
import argparse
import math
from pycatia import catia


def clamp_square_inside_disk(cx, cy, side, R):
    hs = side / 2.0
    corners = [
        (cx + hs, cy + hs),
        (cx + hs, cy - hs),
        (cx - hs, cy + hs),
        (cx - hs, cy - hs),
    ]
    max_d = max(math.hypot(x, y) for x, y in corners)
    if max_d <= R or max_d == 0:
        return cx, cy
    scale = (R - 0.001) / max_d
    return cx * scale, cy * scale


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
        pts.append((round(x, 6), round(y, 6)))
    return pts


def create_disk(diameter, thickness, n=12, radius=None, offset=20.0, square_side=6.0, center_dia=0.0):
    D = float(diameter)
    T = float(thickness)
    n = int(n)
    offset = float(offset)
    side = float(square_side)
    center_dia = float(center_dia)

    R = D / 2.0
    radius = float(radius) if (radius is not None and float(radius) > 0) else max(0.0, R - offset)

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

    # main disk sketch & pad
    disk_sk = sketches.add(plane)
    f2d = disk_sk.open_edition()
    try:
        f2d.create_closed_circle(0.0, 0.0, R)
    except Exception:
        try:
            f2d.create_circle(0.0, 0.0, R)
        except Exception:
            disk_sk.close_edition()
            raise
    disk_sk.close_edition()
    pad = sf.add_new_pad(disk_sk, T)
    part.update()

    sketch_plane, top_ok = find_top_plane(origin, plane, pad, T)

    hole_positions = circular_perimeter_positions(n, radius)
    made = 0
    for (cx, cy) in hole_positions:
        cx2, cy2 = clamp_square_inside_disk(cx, cy, side, R)
        skh = sketches.add(sketch_plane)
        fsk = skh.open_edition()
        # Try creating center rectangle or fallback to 4 lines
        created = False
        try:
            fsk.create_center_rectangle(cx2, cy2, side / 2.0, side / 2.0)
            created = True
        except Exception:
            try:
                fsk.create_centered_rectangle(cx2, cy2, side / 2.0, side / 2.0)
                created = True
            except Exception:
                pass
        if not created:
            x1 = cx2 - side / 2.0
            y1 = cy2 - side / 2.0
            x2 = cx2 + side / 2.0
            y2 = cy2 + side / 2.0
            try:
                fsk.create_line(x1, y1, x2, y1)
                fsk.create_line(x2, y1, x2, y2)
                fsk.create_line(x2, y2, x1, y2)
                fsk.create_line(x1, y2, x1, y1)
            except Exception:
                try:
                    fsk.CreateRectangle(x1, y1, x2, y2)
                except Exception:
                    skh.close_edition()
                    raise RuntimeError("Cannot create square geometry on this CATIA/pycatia version")

        skh.close_edition()
        depth = T if top_ok else -abs(T)
        sf.add_new_pocket(skh, depth)
        part.update()
        made += 1

    # center circular hole: sketch on the same top plane so pocket is created correctly
    if center_dia and center_dia > 0.0:
        skc = sketches.add(sketch_plane)           # <-- use sketch_plane (top) not origin plane
        fsc = skc.open_edition()
        try:
            fsc.create_closed_circle(0.0, 0.0, center_dia / 2.0)
        except Exception:
            try:
                fsc.create_circle(0.0, 0.0, center_dia / 2.0)
            except Exception:
                skc.close_edition()
                raise
        skc.close_edition()
        depth = T if top_ok else -abs(T)
        sf.add_new_pocket(skc, depth)             # pocket from top face through thickness
        part.update()

        return "Sucessfully Executed command"
        

    # return {'disk_diameter': D, 'thickness': T, 'perimeter_holes': made, 'perimeter_side': side, 'center_dia': center_dia}


def main():
    parser = argparse.ArgumentParser(description="Create circular disk with square perimeter holes + optional center circle")
    parser.add_argument('--diameter', type=float, required=True)
    parser.add_argument('--T', type=float, required=True)
    parser.add_argument('--n', type=int, default=12)
    parser.add_argument('--radius', type=float, default=None)
    parser.add_argument('--offset', type=float, default=0.0)
    parser.add_argument('--square_side', type=float, default=0.0)
    parser.add_argument('--center_dia', type=float, default=0.0)
    args = parser.parse_args()

    res = create_disk(args.diameter, args.T, args.n, args.radius, args.offset, args.square_side, args.center_dia)
    print(f"Done: {res}")


if __name__ == '__main__':
    main()
