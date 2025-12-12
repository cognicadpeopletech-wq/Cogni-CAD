#!/usr/bin/env python3
"""
create_cylinder_interactive.py

Create a cylinder in CATIA. Accepts:
  --diameter, --height, or free text like "diameter 80 height 150" or "80x150"
If flags are missing, the script will parse the --cmd legacy string (passed by main).
Note: short option for height is -H (capital H) to avoid argparse '-h' help conflict.
"""
import re
import sys
import argparse
from pycatia import catia

def parse_value_from_text(text: str, keywords, default=None):
    if not text:
        return default
    for kw in keywords:
        pattern = rf"{kw}\s*[:=]?\s*([0-9]+(?:\.[0-9]+)?)"
        m = re.search(pattern, text, flags=re.IGNORECASE)
        if m:
            try:
                return float(m.group(1))
            except:
                continue
    return default

def extract_combo(text):
    if not text:
        return None, None
    m = re.search(r"(\d+(?:\.\d+)?)\s*(?:x|×|by)\s*(\d+(?:\.\d+)?)", text)
    if m:
        try:
            return float(m.group(1)), float(m.group(2))
        except:
            pass
    return None, None

def parse_legacy(cmd_text):
    text = (cmd_text or "").lower()
    d, h = extract_combo(text)
    if d is None:
        d = parse_value_from_text(text, ["diameter", "dia", "d"])
    if h is None:
        h = parse_value_from_text(text, ["height", "h"])
    return d, h

def create_cylinder_in_catia(diameter: float, height: float):
    if diameter <= 0 or height <= 0:
        print("ERROR: diameter and height must be positive.")
        return 1
    
    import pythoncom
    from win32com.client import Dispatch
    
    try:
        pythoncom.CoInitialize()
        catia = Dispatch("CATIA.Application")
        catia.Visible = True
    except Exception as e:
        print(f"ERROR: Could not connect to CATIA: {e}")
        return 1

    try:
        documents = catia.Documents
        part_doc = documents.Add("Part")
        part = part_doc.Part
        bodies = part.Bodies
        body = bodies.Item("PartBody")
        sketches = body.Sketches
        origin = part.OriginElements
        plane_xy = origin.PlaneXY
        
        sketch = sketches.Add(plane_xy)
        f2d = sketch.OpenEdition()
        
        radius = diameter / 2.0
        # CreateClosedCircle: CenterX, CenterY, Radius
        circle = f2d.CreateClosedCircle(0.0, 0.0, float(radius))
        
        sketch.CloseEdition()
        part.InWorkObject = sketch
        part.Update()
        
        sf = part.ShapeFactory
        # Try Reference dispatch if object fails
        try:
             pad = sf.AddNewPad(sketch, float(height))
        except Exception:
             ref = part.CreateReferenceFromObject(sketch)
             pad = sf.AddNewPad(ref, float(height))
        
        part.Update()
        
    except Exception as e:
        print(f"ERROR: Failed to create geometry in CATIA: {e}")
        return 1
    
    print(f"SUCCESS: Cylinder created Ø{diameter} mm × {height} mm")
    return 0

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--diameter", "-d", type=float, default=None, help="Diameter in mm")
    parser.add_argument("--height", "-H", type=float, default=None, help="Height in mm (use -H to avoid -h help conflict)")
    parser.add_argument("--cmd", type=str, default="", help="(internal) original natural-language command")
    args, rest = parser.parse_known_args()

    diameter = args.diameter
    height = args.height

    if diameter is None or height is None:
        legacy_cmd = args.cmd or " ".join(rest) or ""
        d_legacy, h_legacy = parse_legacy(legacy_cmd)
        if diameter is None and d_legacy is not None:
            diameter = d_legacy
        if height is None and h_legacy is not None:
            height = h_legacy

    if diameter is None or height is None:
        print("ERROR: Please supply --diameter and --height (or include in the text). Example: --diameter 80 --height 150 or 'diameter 80 height 150'")
        return 2

    return create_cylinder_in_catia(float(diameter), float(height))

if __name__ == "__main__":
    sys.exit(main())
