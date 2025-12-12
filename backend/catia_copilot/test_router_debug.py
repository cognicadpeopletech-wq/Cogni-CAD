
from pathlib import Path
import sys
import os

# Add backend to path so imports work
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

try:
    import catia_copilot.prompt_router
    print(f"Prompt Router File: {catia_copilot.prompt_router.__file__}")
    from catia_copilot.prompt_router import route_explicit_command
except ImportError as e:
    print(f"ImportError: {e}")
    sys.exit(1)

def test(cmd):
    print(f"\nTesting: {cmd}")
    try:
        script, flags = route_explicit_command(cmd, Path("."))
        print(f"Result: {script} {flags}")
    except Exception as e:
        print(f"CRASH: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    # Crash Candidate 1: Block Holes matching
    test("Create a 200x200x50 block with three holes — 5 mm at (25,25), 8 mm at (100,100), 12 mm at (175,175)")
    
    # Crash Candidate 2: Plate Topology
    test("Make a plate of 300x200x16 mm with 4 equidistant holes from the midpoint, 75 mm apart with hole dia 20 mm")

    # Cylinder Debug
    cmd_cyl = "create cylinder radius 25 pad height 20 pocket depth 20 instances 100"
    test(cmd_cyl)
    
    try:
        from catia_copilot.cylinder_helpers import build_flags_for_fixed_robust
        f, _ = build_flags_for_fixed_robust({}, cmd_cyl)
        print(f"Direct Helper Call Result: {f}")
    except Exception as e:
        print(f"Direct Helper Import/Call Failed: {e}")
