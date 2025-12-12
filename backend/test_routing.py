
import sys
from pathlib import Path
import os

# Add backend to sys.path
BASE_DIR = Path(__file__).parent
sys.path.append(str(BASE_DIR))

from catia_copilot.prompt_router import route_explicit_command

prompts = [
    "Colour the assembly",
    "Generate an 80x55 L-bracket, width 40 mm, thickness 12 mm, bend radius 5, with holes (28,10) dia 8 and (28,38) dia 5.",
    "Close all catia files",
    "open catia application"
]

print("--- Testing Routing ---")
for p in prompts:
    print(f"\nPrompt: '{p}'")
    try:
        script, flags = route_explicit_command(p, BASE_DIR)
        print(f"-> Script: {script}")
        print(f"-> Flags: {flags}")
    except Exception as e:
        print(f"-> ERROR: {e}")
