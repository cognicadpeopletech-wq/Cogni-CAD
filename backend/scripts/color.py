#!/usr/bin/env python3
"""
color.py - improved

- Colors an active CATProduct assembly (or CATPart bodies).
- Avoids red hues and duplicate RGBs within a run.
- Accepts optional `--offset <float>` to shift the hue sequence across invocations.
  If not provided, uses a time-based offset so subsequent runs produce different palettes.

Usage:
  python color.py --offset 0.1234
  OR
  set COLOR_OFFSET=0.1234 ; python color.py
"""

from pycatia import catia
import colorsys
import math
import traceback
import sys
import os
import time
from pathlib import Path
import argparse

# -------------------------
# Config / defaults
# -------------------------
MIN_RGB_DIST = 60  # minimal Euclidean distance between RGBs (0..255)
DEFAULT_MIN_DIST = MIN_RGB_DIST

# -------------------------
# Utilities
# -------------------------
def hue_to_rgb(hue, sat=1.0, val=1.0):
    rgb = colorsys.hsv_to_rgb(hue % 1.0, sat, val)
    return tuple(int(round(255 * c)) for c in rgb)

def is_red(hue, threshold_deg=20):
    deg = (hue * 360) % 360
    return deg < threshold_deg or deg > (360 - threshold_deg)

def rgb_distance(a, b):
    return math.sqrt((a[0]-b[0])**2 + (a[1]-b[1])**2 + (a[2]-b[2])**2)

# -------------------------
# Palette generator
# -------------------------
def generate_distinct_colors_rgb(num_colors, offset=0.0, min_dist=DEFAULT_MIN_DIST):
    """
    Generate `num_colors` distinct RGB tuples (0..255).
    offset: float 0..1 to shift starting hue so repeated runs create different palettes.
    Ensures no red hue (within threshold) and minimal euclidean distance between rgb tuples.
    """
    if num_colors <= 0:
        return []

    # Build candidate hues excluding red region
    base_hues = [i/360.0 for i in range(0, 360) if not is_red(i/360.0)]
    if not base_hues:
        raise ValueError("No hue candidates available after excluding red.")

    # Apply offset by rotating the hue list
    # offset is a float in [0,1); convert to number of steps in base_hues
    step_offset = int((offset % 1.0) * len(base_hues))
    base_hues = base_hues[step_offset:] + base_hues[:step_offset]

    # We will vary saturation and value slightly to create more distinct colors if needed
    sats = [1.0, 0.92, 0.85, 0.95]
    vals = [1.0, 0.95, 0.9]

    used = []
    results = []
    attempts = 0
    max_attempts = max(2000, num_colors * 1000)
    idx = 0

    # iterate candidate combinations
    while len(results) < num_colors and attempts < max_attempts:
        attempts += 1
        hue = base_hues[idx % len(base_hues)]
        s = sats[(idx // len(base_hues)) % len(sats)]
        v = vals[(idx // (len(base_hues) * len(sats))) % len(vals)]

        rgb = hue_to_rgb(hue, sat=s, val=v)

        # check minimal distance
        if all(rgb_distance(rgb, u) >= min_dist for u in used):
            used.append(rgb)
            results.append(rgb)

        idx += 1

        # after cycling through base_hues multiple times, nudge the base_hues to avoid patterns
        if idx % (len(base_hues) * 4) == 0:
            base_hues = [(h + 0.031) % 1.0 for h in base_hues]

    if len(results) < num_colors:
        # graceful fallback: reduce min_dist and try again
        if min_dist > 30:
            return generate_distinct_colors_rgb(num_colors, offset=offset, min_dist=max(30, int(min_dist * 0.7)))
        raise ValueError(f"Could not generate {num_colors} distinct non-red colors (found {len(results)})")

    return results[:num_colors]

# -------------------------
# Selection application
# -------------------------
def color_selection(document, target, rgb):
    sel = document.selection
    sel.clear()
    try:
        sel.add(target)
        vis_properties = sel.vis_properties
        vis_properties.set_real_color(rgb[0], rgb[1], rgb[2], 1)
    except Exception:
        # fallback: try target.reference or target.part
        try:
            sel.clear()
            if hasattr(target, "reference") and target.reference is not None:
                sel.add(target.reference)
                sel.vis_properties.set_real_color(rgb[0], rgb[1], rgb[2], 1)
            elif hasattr(target, "part") and target.part is not None:
                sel.add(target.part)
                sel.vis_properties.set_real_color(rgb[0], rgb[1], rgb[2], 1)
            else:
                print(f"Could not select target {target} for coloring; skipping.")
        except Exception as e:
            print(f"Fallback coloring failed for {target}: {e}")
    finally:
        sel.clear()

# -------------------------
# CATIA helpers
# -------------------------
def connect_to_catia():
    try:
        return catia()
    except Exception as e:
        raise RuntimeError(f"Failed to connect to CATIA via pycatia: {e}")

def find_active_document(ca):
    # try multiple access patterns
    try:
        doc = getattr(ca, "active_document", None)
        if doc:
            return doc
    except Exception:
        pass
    try:
        doc = getattr(ca, "ActiveDocument", None)
        if doc:
            return doc
    except Exception:
        pass
    try:
        aw = getattr(ca, "ActiveWindow", None)
        if aw:
            doc = getattr(aw, "ActiveDocument", None) or getattr(aw, "active_document", None)
            if doc:
                return doc
    except Exception:
        pass
    try:
        docs = getattr(ca, "Documents", None) or getattr(ca, "documents", None)
        if docs:
            cnt = getattr(docs, "Count", None) or getattr(docs, "count", None) or 0
            if cnt and int(cnt) > 0:
                return docs.Item(1)
    except Exception:
        pass
    raise RuntimeError("No active document found in CATIA.")

# -------------------------
# Main
# -------------------------
def main():
    parser = argparse.ArgumentParser(prog="color.py", add_help=False)
    parser.add_argument("--offset", type=float, default=None, help="Hue offset (0..1) to shift palette")
    parser.add_argument("--min_dist", type=int, default=DEFAULT_MIN_DIST, help="Minimum RGB distance")
    args, _ = parser.parse_known_args()

    # offset precedence: CLI arg -> ENV var -> time-based value
    offset = args.offset
    if offset is None:
        env_off = os.environ.get("COLOR_OFFSET") or os.environ.get("CATIA_COLOR_OFFSET")
        if env_off:
            try:
                offset = float(env_off)
            except Exception:
                offset = None
    if offset is None:
        # time-based offset for different runs (sub-second precision)
        offset = (time.time() % 1.0)

    min_dist = args.min_dist if args.min_dist is not None else DEFAULT_MIN_DIST

    try:
        ca = connect_to_catia()
    except Exception as e:
        print("COLOR_SCRIPT_RESULT: ERROR", file=sys.stderr)
        traceback.print_exc()
        return 1

    try:
        document = find_active_document(ca)
    except Exception as e:
        print("COLOR_SCRIPT_RESULT: ERROR", file=sys.stderr)
        print("No active document found. Make sure CATIA has a drawing/product or part open and active.", file=sys.stderr)
        traceback.print_exc()
        return 1

    # Try product (assembly) first
    product = None
    try:
        product = getattr(document, "product", None)
    except Exception:
        product = None

    # If drawing with linked product, try to use that
    if product is None:
        try:
            drawing_links = getattr(document, "drawing_links", None) or getattr(document, "DrawingLinks", None)
            if drawing_links:
                cnt = getattr(drawing_links, "count", None) or getattr(drawing_links, "Count", None) or 0
                if cnt and int(cnt) > 0:
                    first = drawing_links.item(1)
                    linked_doc = getattr(first, "linked_document", None) or getattr(first, "LinkedDocument", None)
                    if linked_doc:
                        product = getattr(linked_doc, "product", None) or getattr(linked_doc, "Product", None)
        except Exception:
            product = None

    # Try part if no product
    part = None
    try:
        part = getattr(document, "part", None)
    except Exception:
        part = None

    try:
        if product is not None:
            # get number of top-level children
            children = getattr(product, "products", None) or getattr(product, "Products", None)
            count = getattr(children, "count", None) or getattr(children, "Count", None) or 0
            count = int(count) if count else 0

            if count > 0:
                rgbs = generate_distinct_colors_rgb(count, offset=offset, min_dist=min_dist)
                colored = 0
                for i in range(1, count+1):
                    try:
                        child = product.products.item(i)
                    except Exception:
                        try:
                            child = product.Products.Item(i)
                        except Exception:
                            continue
                    target = getattr(child, "part", None) or getattr(child, "reference", None) or child
                    rgb = rgbs[i-1]
                    color_selection(document, target, rgb)
                    colored += 1
                print(f"Successfully colored {colored} child components in product.")
                print("COLOR_SCRIPT_RESULT: SUCCESS")
                return 0
            else:
                # fallthrough to part bodies
                pass

        if part is not None:
            bodies = getattr(part, "bodies", None) or getattr(part, "Bodies", None)
            cnt = getattr(bodies, "count", None) or getattr(bodies, "Count", None) or 0
            cnt = int(cnt) if cnt else 0
            if cnt == 0:
                print("No bodies found inside the active Part to color.")
                print("COLOR_SCRIPT_RESULT: ERROR", file=sys.stderr)
                return 1

            rgbs = generate_distinct_colors_rgb(cnt, offset=offset, min_dist=min_dist)
            colored_bodies = 0
            for i in range(1, cnt+1):
                try:
                    body = bodies.item(i)
                except Exception:
                    try:
                        body = bodies.Item(i)
                    except Exception:
                        continue
                rgb = rgbs[i-1]
                color_selection(document, body, rgb)
                colored_bodies += 1
            print(f"Successfully colored {colored_bodies} bodies in active Part.")
            print("COLOR_SCRIPT_RESULT: SUCCESS")
            return 0

        print("Active document is not a Product or Part - cannot color.")
        print("COLOR_SCRIPT_RESULT: ERROR", file=sys.stderr)
        return 1

    except Exception:
        print("COLOR_SCRIPT_RESULT: ERROR", file=sys.stderr)
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    rc = main()
    sys.exit(rc)
