import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

from catia_copilot.block_generator import build_wheel_flags

def test_extraction():
    prompt = "Create a wheel rim with outer radius 300 mm, inner radius 200 mm, rim width 247 mm and rim thickness 5 mm add a center hole radius 35 mm and 7 lug holes of radius 8 mm on a bolt circle offset 40 mm; apply fillets of 3 mm."
    print(f"Testing Prompt: {prompt}")
    
    flags = build_wheel_flags(prompt)
    print("Generated Flags:", flags)
    
    expected = {
        "--outer-radius": "300.0",
        "--inner-radius": "200.0",
        "--rim-width": "247.0",
        "--rim-thickness": "5.0",
        "--center-hole-radius": "35.0",
        "--lug-hole-count": "7",
        "--lug-hole-radius": "8.0",
        "--lug-hole-offset": "40.0",
        "--fillet-radius": "3.0"
    }
    
    flag_dict = {}
    for i in range(len(flags)):
        if flags[i].startswith("--") and i+1 < len(flags):
            if flags[i] != "--cmd":
                flag_dict[flags[i]] = flags[i+1]
                
    success = True
    for k, v in expected.items():
        if k not in flag_dict:
            print(f"MISSING: {k}")
            success = False
        elif float(flag_dict[k]) != float(v):
             print(f"MISMATCH: {k} Expected {v}, got {flag_dict[k]}")
             success = False
             
    if success:
        print("SUCCESS: All parameters extracted correctly.")
    else:
        print("FAILURE: Some parameters missing or incorrect.")

if __name__ == "__main__":
    test_extraction()
