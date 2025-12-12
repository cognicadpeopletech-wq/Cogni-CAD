#!/usr/bin/env python3
"""
equidistant_holes_dynamic.py

Places N holes equidistantly along X or Y on a centered rectangular plate.

Flags:
  --n, --L, --W, --T, --offset, --spacing, --dia, --orientation, --midpoint, --cmd
"""
import sys
import argparse
import re
from pycatia import catia

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

def create_plate_and_holes(L, W, T, hole_dia, hole_depth, positions_xy):
    c = catia()
    docs = c.documents
    part_doc = docs.add("Part")
    part = part_doc.part

    bodies = part.bodies
    body = bodies.add()
    body.name = "PartBody"
    origin = part.origin_elements
    plane_xy = origin.plane_xy
    sketches = body.sketches

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
    sf.add_new_pad(sk, T)
    part.update()

    for idx,(cx,cy) in enumerate(positions_xy, start=1):
        skh = sketches.add(plane_xy)
        skh.name = f"Hole_{idx}"
        fsk = skh.open_edition()
        fsk.create_closed_circle(cx, cy, hole_dia / 2.0)
        skh.close_edition()
        part.update()
        sf.add_new_pocket(skh, -abs(hole_depth))
        part.update()

    c.active_window.active_viewer.reframe()
    return part_doc

def parse_legacy(cmd_text):
    cmd = (cmd_text or "").lower()
    def findnum(keywords):
        for k in keywords:
            m = re.search(rf"{k}\s*[:\s]?\s*(\d+(?:\.\d+)?)", cmd)
            if m:
                try:
                    return float(m.group(1))
                except:
                    pass
            m2 = re.search(rf"(\d+(?:\.\d+)?)\s*mm\s*{k}", cmd)
            if m2:
                try:
                    return float(m2.group(1))
                except:
                    pass
        return None

    m3 = re.search(r"(\d+(?:\.\d+)?)\s*(?:x|×|by)\s*(\d+(?:\.\d+)?)\s*(?:x|×|by)\s*(\d+(?:\.\d+)?)", cmd)
    if m3:
        L = float(m3.group(1)); W = float(m3.group(2)); T = float(m3.group(3))
    else:
        L = findnum(["length","len"]) or findnum(["size"]) or 300.0
        W = findnum(["width","breadth","w"]) or 200.0
        T = findnum(["thickness","height","depth","t"]) or 16.0

    m_n = re.search(r"(\d+)\s*holes?", cmd)
    if m_n:
        n = int(m_n.group(1))
    else:
        m_n2 = re.search(r"\bn\s*[:=]\s*(\d+)\b", cmd)
        n = int(m_n2.group(1)) if m_n2 else 4

    offset = findnum(["offset","inward","edge"]) or 20.0
    spacing = findnum(["spacing","pitch"])
    dia = findnum(["dia","diameter","hole diameter"]) or 6.0

    orientation = "y" if ("vertical" in cmd or "along width" in cmd) else "x"
    midpoint = any(k in cmd for k in ["midpoint","center","centre","middle"])

    return {"L": L, "W": W, "T": T, "n": n, "offset": offset, "spacing": spacing, "dia": dia, "orientation": orientation, "midpoint": midpoint}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=None)
    parser.add_argument("--L", type=float, default=None)
    parser.add_argument("--W", type=float, default=None)
    parser.add_argument("--T", type=float, default=None)
    parser.add_argument("--offset", type=float, default=None)
    parser.add_argument("--spacing", type=float, default=None)
    parser.add_argument("--dia", type=float, default=None)
    parser.add_argument("--orientation", type=str, choices=["x","y"], default=None)
    parser.add_argument("--midpoint", type=int, choices=[0,1], default=None)
    parser.add_argument("--cmd", type=str, default="")
    args, rest = parser.parse_known_args()

    legacy = parse_legacy(args.cmd or " ".join(rest) or "")

    L = args.L if args.L is not None else legacy.get("L", 300.0)
    W = args.W if args.W is not None else legacy.get("W", 200.0)
    T = args.T if args.T is not None else legacy.get("T", 16.0)
    n = args.n if args.n is not None else int(legacy.get("n", 4))
    offset = args.offset if args.offset is not None else legacy.get("offset", 20.0)
    spacing = args.spacing if args.spacing is not None else legacy.get("spacing")
    dia = args.dia if args.dia is not None else legacy.get("dia", 6.0)
    orientation = args.orientation if args.orientation is not None else legacy.get("orientation", "x")
    midpoint = bool(args.midpoint) if args.midpoint is not None else legacy.get("midpoint", True)

    stroke = max(0.0, (L if orientation == "x" else W) - 2.0 * offset)
    positions_along = compute_linear_positions(int(n), stroke, spacing=spacing, midpoint=midpoint)
    positions_xy = [(float(s), 0.0) if orientation == "x" else (0.0, float(s)) for s in positions_along]
    hole_depth = T

    create_plate_and_holes(L, W, T, dia, hole_depth, positions_xy)

    # Print summary (this is the output displayed by main UI)
    # print("----- EQUISPACED HOLES CREATED -----")
    # print(f"Plate: {L} x {W} x {T} mm")
    # print(f"Holes: n={n}, dia={dia}, depth={hole_depth}, axis={orientation}, midpoint={midpoint}")
    # print(f"Offset (from outer edges): {offset} mm")
    # if spacing:
    #     print(f"Spacing used: {spacing} mm")
    # else:
    #     print(f"Computed stroke: {stroke} mm, computed spacing: { (stroke/(n-1)) if n>1 else 0.0 } mm")
    # print("Positions (x,y):")
    # for i,(x,y) in enumerate(positions_xy, start=1):
    #     print(f"{i}: ({x:.3f}, {y:.3f})")
    # print("------------------------------------")

if __name__ == "__main__":
    main()
