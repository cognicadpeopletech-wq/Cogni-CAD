
import sys
import json
from pathlib import Path

# Add backend to sys.path
BASE_DIR = Path(__file__).parent
sys.path.append(str(BASE_DIR))

from catia_copilot.prompt_router import route_explicit_command

prompt = "Generate a manifold with inlet radius 30, mount radius 8, outlet height 200, pattern spacing 130, and shell thickness 3 mm"

print(f"--- Testing Manifold Routing ---")
print(f"Prompt: '{prompt}'")

try:
    script, flags = route_explicit_command(prompt, BASE_DIR)
    print(f"-> Script: {script}")
    print(f"-> Flags: {flags}")
    
    if script == "manifold_dynamic.py" and len(flags) == 2 and flags[0] == "--params":
        params = json.loads(flags[1])
        print(f"-> Parsed Params: {json.dumps(params, indent=2)}")
    else:
        print("-> ERROR: Script or flags mismatch!")

except Exception as e:
    print(f"-> EXCEPTION during routing: {e}")
