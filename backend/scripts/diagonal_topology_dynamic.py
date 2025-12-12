#!/usr/bin/env python
"""
diagonal_topology_dynamic.py

Creates a rectangular plate and generates holes either:
 - around the inner perimeter (equally spaced), or
 - along the two diagonals (TL->BR and TR->BL).

Accepts CLI flags:
  --n <int>           total holes (default 4)
  --L <float>         length (X) in mm (default 300)
  --W <float>         width  (Y) in mm (default 200)
  --T <float>         thickness in mm (default 16)
  --offset <float>    offset from outer edges for inner path (default 20)
  --spacing <float>   spacing (used by linear flows) (default 50)
  --dia <float>       hole diameter (default 6)
  --perimeter 1       force perimeter distribution
  --diagonal 1        force diagonal distribution
  --cmd "<text>"      original command (kept for legacy)
"""

import sys
import argparse
import math
from pycatia import catia

def perimeter_positions(n, length, width, offset):
    half_L = length / 2.0
    half_W = width / 2.0
    inner_x1 = -half_L + offset
    inner_x2 =  half_L - offset
    inner_y1 = -half_W + offset
    inner_y2 =  half_W - offset

    if inner_x2 <= inner_x1:
        inner_x2 = inner_x1 + 1.0
    if inner_y2 <= inner_y1:
        inner_y2 = inner_y1 + 1.0

    seg_top = inner_x2 - inner_x1
    seg_right = inner_y2 - inner_y1
    perimeter = 2.0 * (seg_top + seg_right)
    if perimeter <= 0 or n <= 0:
        return []
    step = perimeter / n
    positions = []
    for i in range(n):
        dist = i * step
        if dist < seg_top:
            x = inner_x1 + dist
            y = inner_y2
        elif dist < seg_top + seg_right:
            d = dist - seg_top
            x = inner_x2
            y = inner_y2 - d
        elif dist < seg_top + seg_right + seg_top:
            d = dist - (seg_top + seg_right)
            x = inner_x2 - d
            y = inner_y1
        else:
            d = dist - (seg_top + seg_right + seg_top)
            x = inner_x1
            y = inner_y1 + d
        positions.append((round(x,6), round(y,6)))
    return positions

def linspace_pts(p1, p2, n):
    if n <= 1:
        return [((p1[0]+p2[0])/2.0, (p1[1]+p2[1])/2.0)]
    return [ (p1[0] + (p2[0]-p1[0])*(i/(n-1)), p1[1] + (p2[1]-p1[1])*(i/(n-1))) for i in range(n) ]

def diagonal_positions(n, length, width, offset):
    half_L = length / 2.0
    half_W = width / 2.0
    TL = (-half_L + offset,  half_W - offset)
    TR = ( half_L - offset,  half_W - offset)
    BL = (-half_L + offset, -half_W + offset)
    BR = ( half_L - offset, -half_W + offset)

    # split n into two roughly equal parts
    n1 = (n + 1) // 2
    n2 = n - n1

    pts = []
    if n1 > 0:
        pts += linspace_pts(TL, BR, n1)
    if n2 > 0:
        pts += linspace_pts(TR, BL, n2)

    # dedupe
    uniq = []
    seen = set()
    for x,y in pts:
        key = (round(x,6), round(y,6))
        if key not in seen:
            seen.add(key)
            uniq.append((float(key[0]), float(key[1])))
    return uniq

def create_plate_and_holes(L, W, T, hole_dia, hole_depth, hole_positions):
    caa = catia()
    docs = caa.documents
    part_doc = docs.add("Part")
    part = part_doc.part

    # create body
    body = part.bodies.add()
    body.name = "PartBody"
    origin = part.origin_elements
    plane_xy = origin.plane_xy
    sketches = body.sketches

    # base rectangle centered at origin
    half_L = L / 2.0
    half_W = W / 2.0

    sk_base = sketches.add(plane_xy)
    f2d = sk_base.open_edition()
    f2d.create_line(-half_L, -half_W, half_L, -half_W)
    f2d.create_line(half_L, -half_W, half_L, half_W)
    f2d.create_line(half_L, half_W, -half_L, half_W)
    f2d.create_line(-half_L, half_W, -half_L, -half_W)
    sk_base.close_edition()
    part.update()

    sf = part.shape_factory
    pad = sf.add_new_pad(sk_base, T)
    part.update()

    # create holes: each circle in its own sketch (safer)
    for i, (cx, cy) in enumerate(hole_positions, start=1):
        skh = sketches.add(plane_xy)
        skh.name = f"Hole_{i}"
        fsk = skh.open_edition()
        fsk.create_closed_circle(cx, cy, hole_dia / 2.0)
        skh.close_edition()
        part.update()
        # pocket through depth
        pocket = sf.add_new_pocket(skh, -abs(hole_depth))
        part.update()

    caa.active_window.active_viewer.reframe()
    return part_doc

def main():
    parser = argparse.ArgumentParser(description="Perimeter/Diagonal holes generator for CATIA (pycatia).")
    parser.add_argument("--n", type=int, default=None)
    parser.add_argument("--L", type=float, default=None)
    parser.add_argument("--W", type=float, default=None)
    parser.add_argument("--T", type=float, default=None)
    parser.add_argument("--offset", type=float, default=None)
    parser.add_argument("--spacing", type=float, default=None)
    parser.add_argument("--dia", type=float, default=None)
    parser.add_argument("--perimeter", type=int, default=0)
    parser.add_argument("--diagonal", type=int, default=0)
    parser.add_argument("--cmd", type=str, default="")
    args, rest = parser.parse_known_args()

    # fallback defaults (legacy)
    L = args.L or 300.0
    W = args.W or 200.0
    T = args.T or 16.0
    hole_dia = args.dia or 6.0
    hole_depth = T
    offset = args.offset if args.offset is not None else 20.0
    spacing = args.spacing or 50.0
    n = args.n or 4

    # decide distribution:
    # if --perimeter given or n > 4 prefer perimeter distribution
    use_perimeter = bool(args.perimeter) or (args.n is not None and args.n > 4 and not args.diagonal)
    use_diagonal = bool(args.diagonal) and not use_perimeter

    # choose positions
    if use_diagonal and n <= 16:
        hole_positions = diagonal_positions(n, L, W, offset)
        mode = "diagonal"
    else:
        hole_positions = perimeter_positions(n, L, W, offset)
        mode = "perimeter"

    # create part and holes
    create_plate_and_holes(L, W, T, hole_dia, hole_depth, hole_positions)

    # print details for UI
    # print(f"Total holes generated: {len(hole_positions)}")
    # print("Mode:", mode)
    # print("Hole coordinates (x,y):")
    # for i, (x, y) in enumerate(hole_positions, start=1):
        # print(f"{i}: ({x:.3f}, {y:.3f})")

if __name__ == "__main__":
    main()
