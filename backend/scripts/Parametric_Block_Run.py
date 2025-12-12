#!/usr/bin/env python3
"""
Parametric_Block_Run.py

Create a rectangular block with multiple circular holes.

Flags:
  --length L               (or --width/--height synonyms described below)
  --width W
  --thickness T            (also accepted as --height or --depth)
  --num_holes N            (optional; default 0)
  --hole_i_x X
  --hole_i_y Y
  --hole_i_d D

Examples:
  # Create block WITHOUT holes
  python Parametric_Block_Run.py --length 200 --width 100 --thickness 10

  # Create block WITH 2 holes
  python Parametric_Block_Run.py --length 200 --width 100 --thickness 10 --num_holes 2 \
    --hole_1_x 20 --hole_1_y 30 --hole_1_d 10 \
    --hole_2_x 60 --hole_2_y 30 --hole_2_d 12

Notes:
- You may specify thickness using --thickness, --height or --depth (they are synonyms).
- Numeric values like "20mm" are accepted and parsed.
"""

import argparse
import re
import sys
from pycatia import catia

# helper to parse numeric strings like "20", "20.0", "20mm"
def parse_numeric_token(token: str) -> float:
    if isinstance(token, (int, float)):
        return float(token)
    s = str(token).strip().lower()
    # remove trailing units like mm, m, cm if present (we assume mm if provided)
    s = re.sub(r"(mm|cm|m|in|\"|'| )+$", "", s)
    try:
        return float(s)
    except ValueError:
        raise argparse.ArgumentTypeError(f"Could not parse numeric value: '{token}'")

def create_block(length, width, thickness, holes):
    length = float(length)
    width = float(width)
    thickness = float(thickness)

    # ---------------------------
    # VALIDATION
    # ---------------------------
    for i, (x, y, d) in enumerate(holes, 1):
        x = float(x); y = float(y); d = float(d)
        # ensure hole center is inside block with radius clearance
        if not (d/2 < x < length - d/2):
            raise ValueError(f"Hole {i}: X={x} OUTSIDE block (needs {d/2} < x < {length - d/2})!")

        if not (d/2 < y < width - d/2):
            raise ValueError(f"Hole {i}: Y={y} OUTSIDE block (needs {d/2} < y < {width - d/2})!")

    # ---------------------------
    # CATIA AUTOMATION
    # ---------------------------
    # ---------------------------
    # CATIA AUTOMATION (win32com)
    # ---------------------------
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
        
        # Base sketch
        sk = sketches.Add(plane_xy)
        f2d = sk.OpenEdition()
        
        # outer rectangle
        # Using CreateLine for win32com
        # Note: CreateLine(x1, y1, x2, y2)
        f2d.CreateLine(0.0, 0.0, float(length), 0.0)
        f2d.CreateLine(float(length), 0.0, float(length), float(width))
        f2d.CreateLine(float(length), float(width), 0.0, float(width))
        f2d.CreateLine(0.0, float(width), 0.0, 0.0)
        
        # holes
        for (x, y, d) in holes:
            f2d.CreateClosedCircle(float(x), float(y), float(d) / 2.0)
            
        sk.CloseEdition()
        
        part.InWorkObject = sk
        part.Update()
        
        sf = part.ShapeFactory
        # Try object or reference
        try:
            sf.AddNewPad(sk, float(thickness))
        except Exception:
            try:
                ref = part.CreateReferenceFromObject(sk)
                sf.AddNewPad(ref, float(thickness))
            except Exception as e:
                print(f"ERROR: AddNewPad failed even with reference: {e}")
                # Try Extrude fallback? No, Pad is better.
                raise e
        
        part.Update()

    except Exception as e:
        print(f"ERROR: Failed to create geometry: {e}")
        return

    # summary
    print("\n==============================")
    print("PARAMETRIC BLOCK CREATED")
    print(f"Block: {length} x {width} x {thickness}")
    print(f"Total Holes: {len(holes)}")
    for i, (x, y, d) in enumerate(holes, 1):
        print(f"Hole {i}: X={x}, Y={y}, Dia={d}")
    print("==============================\n")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Parametric Block with Holes (PyCATIA)")

    parser.add_argument("--length", type=parse_numeric_token, required=True,
                        help="Block length in user units (e.g. 200 or 200mm)")
    parser.add_argument("--width", type=parse_numeric_token, required=True,
                        help="Block width in user units (e.g. 100 or 100mm)")

    # accept synonyms for thickness
    thickness_group = parser.add_mutually_exclusive_group(required=True)
    thickness_group.add_argument("--thickness", type=parse_numeric_token,
                                 help="Block thickness (pad depth) e.g. 10 or 10mm")
    thickness_group.add_argument("--height", type=parse_numeric_token,
                                 help="Alias for --thickness")
    thickness_group.add_argument("--depth", type=parse_numeric_token,
                                 help="Alias for --thickness")

    parser.add_argument("--num_holes", type=int, default=0,
                        help="Number of holes (default 0 — no holes)")

    # parse known args to allow dynamic hole flags
    args, unknown = parser.parse_known_args(argv)

    # resolve thickness alias
    thickness_val = None
    if args.thickness is not None:
        thickness_val = args.thickness
    elif args.height is not None:
        thickness_val = args.height
    elif args.depth is not None:
        thickness_val = args.depth

    num_holes = int(args.num_holes)

    # gather holes
    holes = []
    if num_holes > 0:
        # unknown contains remaining tokens; we'll search for each hole flag
        # e.g. --hole_1_x 20 --hole_1_y 30 --hole_1_d 10 ...
        unknown_list = list(unknown)
        for i in range(1, num_holes + 1):
            hx_flag = f"--hole_{i}_x"
            hy_flag = f"--hole_{i}_y"
            hd_flag = f"--hole_{i}_d"

            missing = []
            try:
                hx_idx = unknown_list.index(hx_flag)
                hx_val = unknown_list[hx_idx + 1]
            except ValueError:
                missing.append(hx_flag)
                hx_val = None
            except IndexError:
                missing.append(hx_flag)
                hx_val = None

            try:
                hy_idx = unknown_list.index(hy_flag)
                hy_val = unknown_list[hy_idx + 1]
            except ValueError:
                missing.append(hy_flag)
                hy_val = None
            except IndexError:
                missing.append(hy_flag)
                hy_val = None

            try:
                hd_idx = unknown_list.index(hd_flag)
                hd_val = unknown_list[hd_idx + 1]
            except ValueError:
                missing.append(hd_flag)
                hd_val = None
            except IndexError:
                missing.append(hd_flag)
                hd_val = None

            if missing:
                raise ValueError(f"Missing hole parameters for hole {i}: {', '.join(missing)}")

            # parse numbers (accept mm tokens)
            hx = parse_numeric_token(hx_val)
            hy = parse_numeric_token(hy_val)
            hd = parse_numeric_token(hd_val)

            holes.append((hx, hy, hd))

    # finally call create
    create_block(args.length, args.width, thickness_val, holes)


if __name__ == "__main__":
    main()
