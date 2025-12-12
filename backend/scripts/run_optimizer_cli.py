#!/usr/bin/env python3
"""
CLI Wrapper for RL Optimizer.
Routes user query to the optimization logic and returns JSON for Frontend Cards.
"""

import sys
import json
import argparse
import re
from pathlib import Path

# Fix path to import from catia_copilot
sys.path.append(str(Path(__file__).resolve().parent.parent))

try:
    from catia_copilot.rl_optimizer_v4 import run_rl_optimizer
except ImportError:
    # Fallback if path issue
    sys.stderr.write("Error: Could not import optimization engine.\n")
    sys.exit(1)

def parse_load_kg(text):
    m = re.search(r"(\d+(\.\d+)?)\s*kg", text.lower())
    if m:
        return float(m.group(1))
    return 10.0 # Default

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--goal", required=True, help="Full user prompt")
    parser.add_argument("--all-shapes", action="store_true", help="Compare all shapes")
    args = parser.parse_args()

    command_text = args.goal.lower()
    load_kg = parse_load_kg(command_text)

    # SHAPE MAPPING
    # 4 distinct types: Cylinder Rod, Cylinder Tube, Rect Rod, Rect Tube
    # But for "Single Shape" query, we need to detect which one.
    
    # Heuristic Detection
    detected_shape = "cylinder_solid" # default
    if "cylinder" in command_text:
        if "tube" in command_text or "pipe" in command_text:
            detected_shape = "cylinder_tube"
        else:
            detected_shape = "cylinder_solid"
    elif "rect" in command_text: # rectangle, rectangular
        if "tube" in command_text:
            detected_shape = "rect_tube"
        else:
            detected_shape = "rect_rod"
    
    parsed_goal = {
        "objective": "minimize_weight",
        "load_kg": load_kg,
        "constraints": {}
    }

    results = []

    # WING OPTIMIZATION CHECK
    if "wing" in command_text:
        try:
            from catia_copilot.rl_optimize_wing import run_rl_optimize as run_wing_opt
            # Wing optimization usually implies single objective
            # But user said "Optimize wing... low drag... single card"
            # We will ask for top_k=1 
            res = run_wing_opt(command_text, parsed_goal={"objective": command_text}, top_k=1)
            
            for i, cand in enumerate(res["candidates"]):
                 # cand has m, p, t, c_t, sweep, score
                 cand["shape_type"] = "wing"
                 cand["design_name"] = f"Optimized Wing #{i+1}"
                 results.append(cand)
                 
        except ImportError:
            sys.stderr.write("Error: Could not import wing optimizer.\n")
    
    elif args.all_shapes or "among all shapes" in command_text:
        # COMPARE MODE: One best design per shape
        shapes = ["cylinder_solid", "cylinder_tube", "rect_rod", "rect_tube"]
        
        for i, shape in enumerate(shapes):
            res = run_rl_optimizer(
                command_text, 
                parsed_goal=parsed_goal, 
                shape=shape, 
                top_k=1, 
                seed=42+i,
                n_samples=200
            )
            if res["candidates"]:
                best = res["candidates"][0]
                # MAP KEYS (Fixing NaN issue)
                mapped = {
                    "base_length_mm": best.get("length_mm", 0),
                    "base_width_mm": best.get("width_mm", 0),
                    "base_thickness_mm": best.get("thickness_mm", 0),
                    "cylinder_diameter_mm": best.get("cyl_diameter", 0),
                    "cylinder_height_mm": best.get("cyl_height", 0),
                    "rod_w_mm": best.get("rod_w_mm", 0), # if present
                    "rod_d_mm": best.get("rod_d_mm", 0),
                    "rod_h_mm": best.get("rod_h_mm", 0),
                    "wall_mm": best.get("wall_mm", 0),
                    "weight_kg": best.get("weight_kg", 0),
                    "score": best.get("score", 0),
                    "shape_type": shape,
                    "design_name": shape.replace("_", " ").title()
                }
                results.append(mapped)
    
    else:
        # SINGLE SHAPE MODE: Top 3 designs for one shape
        res = run_rl_optimizer(
            command_text, 
            parsed_goal=parsed_goal, 
            shape=detected_shape, 
            top_k=3, 
            seed=42, 
            n_samples=500
        )
        for i, card in enumerate(res["candidates"]):
            mapped = {
                "base_length_mm": card.get("length_mm", 0),
                "base_width_mm": card.get("width_mm", 0),
                "base_thickness_mm": card.get("thickness_mm", 0),
                "cylinder_diameter_mm": card.get("cyl_diameter", 0),
                "cylinder_height_mm": card.get("cyl_height", 0),
                "rod_w_mm": card.get("rod_w_mm", 0),
                "rod_d_mm": card.get("rod_d_mm", 0),
                "rod_h_mm": card.get("rod_h_mm", 0),
                "wall_mm": card.get("wall_mm", 0),
                "weight_kg": card.get("weight_kg", 0),
                "score": card.get("score", 0),
                "shape_type": detected_shape,
                "design_name": f"Design #{i+1}"
            }
            results.append(mapped)

    # Output JSON for Frontend
    output = {
        "mode": "optimization_cards",
        "options": results,
        "raw_text": "Optimization Complete. Select a design."
    }
    
    print(json.dumps(output))

if __name__ == "__main__":
    main()
