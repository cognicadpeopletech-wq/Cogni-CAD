#!/usr/bin/env python3
"""
circular_topology_dynamic.py

Create a rectangular plate (L x W x T) with an arbitrary number of radial holes
arranged on a circular path (given diameter or radius).

USAGE (examples):
  python circular_topology_dynamic.py --L 400 --W 300 --T 40 --diameter 70 --n 10 --dia 8
  python circular_topology_dynamic.py --L 300 --W 200 --T 20 --radius 25 --n 6

Behavior:
 - The script will NOT execute geometry creation unless the following required
   parameters are present and valid: L, W, T, circle diameter (or radius), and n (hole count).
 - If any required parameter is missing or invalid, the script prints a clear
   error message and exits with code 2.
 - Accepts both flag-style arguments (preferred) and a free-text --cmd string
   (parsed for convenience), but still enforces required parameters.
"""

import sys
import re
import math
import argparse
from pathlib import Path

# optional: import CATIA only when we are actually going to run geometry creation
try:
    from pycatia import catia
except Exception:
    catia = None  # allow parsing & validation even if pycatia not available (useful for testing)

# ---------------------------
# Helpers: free-text extraction (fallback)
# ---------------------------
number_re = r"(\d+(?:\.\d+)?)"


def extract_value_from_text(text: str, keywords, default=None):
    if not text:
        return default
    s = text.lower()
    # try LxWxT triple like '400x300x40' or '400x300x40 mm'
    m = re.search(
        rf"(\d+(?:\.\d+)?)\s*(?:x|×|by)\s*(\d+(?:\.\d+)?)\s*(?:x|×|by)\s*(\d+(?:\.\d+)?)(?:\s*mm)?",
        s,
    )
    if m and ("length" in keywords or "len" in keywords or "plate" in keywords or "size" in keywords):
        try:
            return tuple(float(g) for g in m.groups())
        except Exception:
            pass

    for kw in keywords:
        p = rf"{kw}\s*[:=]?\s*{number_re}"
        m = re.search(p, s)
        if m:
            try:
                return float(m.group(1))
            except Exception:
                pass

    # look for patterns like '50 mm radius' or 'radius 50'
    for kw in keywords:
        p2 = rf"{number_re}\s*mm\s*(?:{kw})"
        m2 = re.search(p2, s)
        if m2:
            try:
                return float(m2.group(1))
            except Exception:
                pass

    return default


def extract_hole_count_from_text(text: str, default=None):
    if not text:
        return default
    s = text.lower()
    m = re.search(r"(\d+)\s*(?:holes|nos|no|pieces)", s)
    if m:
        try:
            return int(m.group(1))
        except Exception:
            pass
    # fallback: a lone small integer not part of LxWxT triple
    s2 = re.sub(r"\d+(?:\.\d+)?\s*(?:x|×|by)\s*\d+(?:\.\d+)?\s*(?:x|×|by)\s*\d+(?:\.\d+)?(?:\s*mm)?", "", s)
    m2 = re.search(r"\b(\d{1,3})\b", s2)
    if m2:
        try:
            return int(m2.group(1))
        except Exception:
            pass
    return default


# ---------------------------
# Argument parsing
# ---------------------------
parser = argparse.ArgumentParser(description="Create circular hole topology in CATIA (requires L,W,T, circle size and n).")
parser.add_argument("--L", type=float, help="Length / X (mm)")
parser.add_argument("--W", type=float, help="Width / Y (mm)")
parser.add_argument("--T", type=float, help="Thickness / Z (mm)")
parser.add_argument("--diameter", dest="circle_dia", type=float, help="Circle diameter (mm)")
parser.add_argument("--circle_dia", dest="circle_dia_alias", type=float, help="Circle diameter alias (mm)")
parser.add_argument("--radius", dest="circle_radius", type=float, help="Circle radius (mm)")
parser.add_argument("--n", type=int, help="Number of holes (integer)")
parser.add_argument("--dia", dest="hole_dia", type=float, default=8.0, help="Hole diameter (mm) - optional")
parser.add_argument("--offset", type=float, help="Offset from edges (mm) - optional")
parser.add_argument("--cmd", type=str, help="Free-text command (will be parsed for missing values) - optional")
parser.add_argument("--dryrun", action="store_true", help="Parse and validate only; do not attempt to connect to CATIA")
args = parser.parse_args()

# merge aliases
circle_dia = args.circle_dia or args.circle_dia_alias
circle_radius = args.circle_radius
hole_dia = args.hole_dia
L = args.L
W = args.W
T = args.T
n = args.n
cmd_text = args.cmd or ""

# fallback: try extract from free-text --cmd when flags missing
if (L is None) or (W is None) or (T is None):
    triple = extract_value_from_text(cmd_text, ["length", "len", "size", "plate", "l"])
    if isinstance(triple, tuple):
        try:
            L, W, T = map(float, triple)
        except Exception:
            pass
    else:
        if L is None:
            v = extract_value_from_text(cmd_text, ["length", "len", "l"])
            if v is not None:
                L = float(v)
        if W is None:
            v = extract_value_from_text(cmd_text, ["width", "breadth", "w", "b"])
            if v is not None:
                W = float(v)
        if T is None:
            v = extract_value_from_text(cmd_text, ["thickness", "height", "depth", "t"])
            if v is not None:
                T = float(v)

if not circle_dia and circle_radius:
    circle_dia = float(circle_radius) * 2.0

if not circle_dia:
    v = extract_value_from_text(cmd_text, ["circle diameter", "circle dia", "circular dia", "diameter", "dia", "d", "radius", "r"])
    if isinstance(v, tuple):
        # shouldn't happen, but ignore
        pass
    elif v is not None:
        circle_dia = float(v)

if not n:
    n = extract_hole_count_from_text(cmd_text, default=None)

# ---------------------------
# Validation of required params
# ---------------------------
missing = []
if L is None:
    missing.append("L (length)")
if W is None:
    missing.append("W (width)")
if T is None:
    missing.append("T (thickness)")
if circle_dia is None:
    missing.append("circle diameter or radius")
if n is None:
    missing.append("n (number of holes)")

# numeric sanity checks
bad = []
if L is not None and L <= 0:
    bad.append("L must be > 0")
if W is not None and W <= 0:
    bad.append("W must be > 0")
if T is not None and T <= 0:
    bad.append("T must be > 0")
if circle_dia is not None and circle_dia <= 0:
    bad.append("circle diameter must be > 0")
if n is not None and (not isinstance(n, int) or n < 1):
    bad.append("n must be an integer >= 1")
if hole_dia is not None and hole_dia <= 0:
    bad.append("hole diameter must be > 0")

if missing or bad:
    if missing:
        print("ERROR Missing required parameter(s): " + ", ".join(missing))
    if bad:
        print("ERROR Invalid parameter(s): " + "; ".join(bad))
    print("\nProvide required parameters (examples):")
    # print("  python circular_topology_dynamic.py --L 400 --W 300 --T 40 --diameter 70 --n 10 --dia 8")
    print("  OR provide a free-text command: --cmd \"Create circular topology: 10 holes on a 70 mm diameter circle for a 400x300x40 mm block.\"")
    sys.exit(2)

# At this point all required params are present and valid
# Print parsed values for clarity (safe unicode printing)
def safe_print_check(message: str):
    """
    Try to print message containing Unicode. If the terminal encoding
    can't handle it, fall back to ASCII-only message.
    """
    try:
        print(message)
    except UnicodeEncodeError:
        # remove non-ascii characters and print fallback
        ascii_only = re.sub(r"[^\x00-\x7F]+", "", message)
        print(ascii_only)

# safe_print_check("✔ Parameters validated:" if True else "Parameters validated:")
# print(f"   Plate (L x W x T)  = {L} x {W} x {T} mm")
# print(f"   Circle diameter    = {circle_dia} mm")
# print(f"   Hole count (n)     = {n}")
# print(f"   Hole diameter      = {hole_dia} mm")
# if args.offset is not None:
#     print(f"   Offset              = {args.offset} mm")
# print("")

# If --dryrun, stop here (useful for testing)
if args.dryrun:
    print("Dry-run requested; exiting without creating geometry.")
    sys.exit(0)

# ---------------------------
# Create geometry in CATIA
# ---------------------------
if catia is None:
    print("❌ pycatia (CATIA automation) is not available in this environment.")
    print("   If you intend to create geometry, run this script where pycatia is installed and CATIA is accessible.")
    sys.exit(3)

try:
    ca = catia()
    docs = ca.documents
    doc = docs.add("Part")
    part = doc.part

    bodies = part.bodies
    body = bodies.add()
    body.name = "PartBody"

    origin = part.origin_elements
    plane = origin.plane_xy
    sketches = body.sketches

    # Base rectangle (centered at origin)
    half_L = L / 2.0
    half_W = W / 2.0

    sk = sketches.add(plane)
    f2d = sk.open_edition()

    f2d.create_line(-half_L, -half_W, half_L, -half_W)
    f2d.create_line(half_L, -half_W, half_L, half_W)
    f2d.create_line(half_L, half_W, -half_L, half_W)
    f2d.create_line(-half_L, half_W, -half_L, -half_W)

    sk.close_edition()
    part.update()

    # Pad the sketch to create the plate
    sf = part.shape_factory
    pad = sf.add_new_pad(sk, T)
    part.update()

    # Compute hole positions on circle (centered at origin)
    circle_radius = circle_dia / 2.0
    angles = [i * (360.0 / n) for i in range(n)]
    hole_positions = [
        (circle_radius * math.cos(math.radians(a)),
         circle_radius * math.sin(math.radians(a)))
        for a in angles
    ]

    # Create holes (sketch -> pocket) one per position
    for i, (hx, hy) in enumerate(hole_positions, start=1):
        skl = sketches.add(plane)
        skl.name = f"Hole_{i}"
        fsk = skl.open_edition()
        fsk.create_closed_circle(hx, hy, hole_dia / 2.0)
        skl.close_edition()
        part.update()

        # pocket depth: through-thickness (negative value for pocket direction)
        pocket = sf.add_new_pocket(skl, -abs(T))
        part.update()

    # Final view
    try:
        ca.active_window.active_viewer.reframe()
    except Exception:
        # viewer may not be available in some headless/test contexts
        pass

    # safe_print_check(f"✔ Circular hole pattern created successfully with {n} holes on {circle_dia} mm circle.")
    sys.exit(0)

except Exception as e:
    print("ERROR during CATIA automation:")
    print(str(e))
    sys.exit(4)
