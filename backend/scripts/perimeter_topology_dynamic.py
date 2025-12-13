#!/usr/bin/env python3
"""
perimeter_topology_dynamic.py

Place N holes equally spaced around an inner rectangle offset from outer edges.

CLI flags:
  --n <int>       total holes (default 12)
  --L <float>     length X (mm) default 300
  --W <float>     width  Y (mm) default 200
  --T <float>     thickness (mm) default 16
  --offset <float> inner offset from outer edges (mm) default 20
  --dia <float>   hole diameter (mm) default 6
  --cmd "<text>"  original command (for legacy)
"""
import sys
import argparse
from pycatia import catia

def perimeter_positions(n, length, width, offset):
    half_L = length / 2.0
    half_W = width / 2.0
    inner_x1 = -half_L + offset
    inner_x2 =  half_L - offset
    inner_y1 = -half_W + offset
    inner_y2 =  half_W - offset

    # guard
    if inner_x2 <= inner_x1:
        inner_x2 = inner_x1 + 1.0
    if inner_y2 <= inner_y1:
        inner_y2 = inner_y1 + 1.0

    seg_top = inner_x2 - inner_x1
    seg_right = inner_y2 - inner_y1
    seg_bottom = seg_top
    seg_left = seg_right

    perimeter = 2.0 * (seg_top + seg_right)
    if perimeter <= 0 or n <= 0:
        return []

    step = perimeter / n
    pts = []
    for i in range(n):
        dist = i * step
        if dist < seg_top:
            x = inner_x1 + dist
            y = inner_y2
        elif dist < seg_top + seg_right:
            d = dist - seg_top
            x = inner_x2
            y = inner_y2 - d
        elif dist < seg_top + seg_right + seg_bottom:
            d = dist - (seg_top + seg_right)
            x = inner_x2 - d
            y = inner_y1
        else:
            d = dist - (seg_top + seg_right + seg_bottom)
            x = inner_x1
            y = inner_y1 + d
        pts.append((round(x,6), round(y,6)))
    return pts

def create_plate_with_holes(L, W, T, hole_dia, hole_depth, hole_positions):
    caa = catia()
    docs = caa.documents
    part_doc = docs.add("Part")
    part = part_doc.part

    bodies = part.bodies
    body = bodies.add()
    body.name = "PartBody"
    origin = part.origin_elements
    plane_xy = origin.plane_xy
    sketches = body.sketches

    # base rectangle
    half_L = L / 2.0
    half_W = W / 2.0
    sk = sketches.add(plane_xy)
    f2d = sk.open_edition()
    f2d.create_line(-half_L, -half_W, half_L, -half_W)
    f2d.create_line(half_L, -half_W, half_L, half_W)
    f2d.create_line(half_L, half_W, -half_L, half_W)
    f2d.create_line(-half_L, half_W, -half_L, -half_W)
    sk.close_edition()
    part.update()

    sf = part.shape_factory
    pad = sf.add_new_pad(sk, T)
    part.update()

    # holes: create each circle in its own sketch (robust)
    for idx, (cx, cy) in enumerate(hole_positions, start=1):
        skh = sketches.add(plane_xy)
        skh.name = f"Hole_{idx}"
        fsk = skh.open_edition()
        fsk.create_closed_circle(cx, cy, hole_dia / 2.0)
        skh.close_edition()
        part.update()
        pocket = sf.add_new_pocket(skh, -abs(hole_depth))
        part.update()

    caa.active_window.active_viewer.reframe()
    return part_doc

def main():
    parser = argparse.ArgumentParser(description="Perimeter holes generator for CATIA (pycatia).")
    parser.add_argument("--n", type=int, default=12)
    parser.add_argument("--L", type=float, default=300.0)
    parser.add_argument("--W", type=float, default=200.0)
    parser.add_argument("--T", type=float, default=16.0)
    parser.add_argument("--offset", type=float, default=20.0)
    parser.add_argument("--dia", type=float, default=6.0)
    parser.add_argument("--cmd", type=str, default="")
    args, rest = parser.parse_known_args()

    n = args.n
    L = args.L
    W = args.W
    T = args.T
    offset = args.offset
    hole_dia = args.dia
    hole_depth = T

    hole_positions = perimeter_positions(n, L, W, offset)
    create_plate_with_holes(L, W, T, hole_dia, hole_depth, hole_positions)

    # Print summary for the UI
    # print(f"Total holes generated: {len(hole_positions)}")
    # print(f"Hole diameter: {hole_dia}, Depth: {hole_depth}")
    # print("Hole positions (x,y):")
    # for i, (x,y) in enumerate(hole_positions, start=1):
    #     print(f"{i}: ({x:.3f}, {y:.3f})")

if __name__ == "__main__":
    main()
