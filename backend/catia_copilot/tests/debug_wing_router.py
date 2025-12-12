
import sys
import os
from pathlib import Path

# Setup path
current = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(current, "..", ".."))

try:
    from catia_copilot.prompt_router import route_explicit_command
    from catia_copilot.block_parser import normalize
except ImportError as e:
    print(f"ImportError: {e}")
    sys.exit(1)

cmd = "Generate optimized wing m=8 p=4 t=10 ct=0.8 sweep=10"
print(f"Original: '{cmd}'")
print(f"Normalized: '{normalize(cmd)}'")

script, flags = route_explicit_command(cmd, Path("."))
print(f"Script: {script}")
print(f"Flags: {flags}")

if script == "wing_structure_winglet_transparent.py":
    print("SUCCESS: Routed correctly.")
else:
    print("FAILURE: Did not route to wing script.")
