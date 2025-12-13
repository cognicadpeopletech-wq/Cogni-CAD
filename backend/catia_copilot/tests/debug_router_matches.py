
import sys
import os
import re

# Setup path
current = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(current, "..", "..")) # backend
sys.path.append(os.path.join(current, "..")) # catia_copilot

try:
    from catia_copilot.block_parser import normalize
except ImportError:
    print("ImportError")
    sys.exit(1)

cmds = [
    "Create baseplate length 200 width 150 thickness 20 with cylinder tube diameter 50 height 120 wall 2",
    "Create baseplate length 200 width 150 thickness 20 with rectangular rod width 60 depth 40 height 100",
    "Create baseplate length 200 width 150 thickness 20 with rectangular tube width 60 depth 40 height 100 wall 3"
]

for cmd in cmds:
    s = normalize(cmd)
    print(f"CMD: {cmd}")
    print(f"NORM: '{s}'")
    
    match_cyl_tube = re.search(r"cylinder.*tube", s) or re.search(r"tube", s)
    match_rect_rod = re.search(r"rect.*rod", s) or re.search(r"rectangular.*rod", s)
    # The router uses: 
    # if matches(r"rect.*tube") or matches(r"rectangular.*tube"):
    # elif matches(r"rect.*rod") or matches(r"rectangular.*rod"):
    # elif matches(r"cylinder.*tube") or matches(r"tube"):
    
    print(f"  Match Rect Tube: {re.search(r'rect.*tube', s)}")
    print(f"  Match Rect Rod:  {re.search(r'rect.*rod', s)}")
    print(f"  Match Cyl Tube:  {re.search(r'cylinder.*tube', s) or re.search(r'tube', s)}")
    print("-" * 20)
