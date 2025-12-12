#!/usr/bin/env python3
"""
goal_parser.py (FINAL PATCHED)

Extracts:
 - objective:
       minimize_weight
       even_distribution
       improve_stiffness
       max_strength_to_weight

 - load_kg
 - constraints: {
       stiffness_improve_pct,
       max_weight_increase_pct,
       holes,
       hole_diameter_mm,
       hint_length_mm,
       hint_width_mm
   }
"""

import re


def parse_goal(text: str) -> dict:
    s = (text or "").lower()

    goal = {
        "objective": None,
        "load_kg": None,
        "constraints": {}
    }

    # ---------------------------------------------------------
    # LOAD (kg)
    # ---------------------------------------------------------
    m = re.search(r"(\d+(\.\d+)?)\s*(kg|kilogram|kgs|kilograms)", s)
    if m:
        try:
            goal["load_kg"] = float(m.group(1))
        except:
            goal["load_kg"] = None

    # ---------------------------------------------------------
    # EVEN DISTRIBUTION MODE
    # ---------------------------------------------------------
    dist_words = ["distribute", "even", "uniform", "equal", "balanced"]
    hole_words = ["hole", "holes", "bolt", "bolts", "bolt circle"]

    if any(w in s for w in dist_words) and any(w in s for w in hole_words):
        goal["objective"] = "even_distribution"

    # ---------------------------------------------------------
    # IMPROVE STIFFNESS
    # ---------------------------------------------------------
    stiff_match = re.search(
        r"(improve|increase|raise)\s+(stiffness|stiff)\s*(by)?\s*(\d+(\.\d+)?)\s*%?",
        s
    )
    if stiff_match:
        try:
            pct = float(stiff_match.group(4))
            goal["constraints"]["stiffness_improve_pct"] = pct
            goal["objective"] = "improve_stiffness"
        except:
            pass

        # weight bound phrase
        wt_match = re.search(
            r"(weight|mass).{0,25}?(no(t)?\s*more\s*than|<=|under|less than)\s*(\d+(\.\d+)?)\s*%?",
            s
        )
        if wt_match:
            try:
                goal["constraints"]["max_weight_increase_pct"] = float(wt_match.group(4))
            except:
                pass

        # alternate: "without increasing weight by more than 5%"
        wt2 = re.search(r"without\s+increasing\s+weight\s+by\s+more\s+than\s+(\d+(\.\d+)?)\s*%?", s)
        if wt2:
            try:
                goal["constraints"]["max_weight_increase_pct"] = float(wt2.group(1))
            except:
                pass

    # ---------------------------------------------------------
    # MAX STRENGTH-TO-WEIGHT MODE
    # ---------------------------------------------------------
    if goal["objective"] is None:
        if ("strength-to-weight" in s) or \
           ("strength to weight" in s) or \
           ("maximize" in s and "strength" in s and "weight" in s):
            goal["objective"] = "max_strength_to_weight"

            # load extraction fallback
            if goal["load_kg"] is None:
                m2 = re.search(r"for\s+a\s+(\d+(\.\d+)?)\s*(kg|kilogram|kgs|kilograms)", s)
                if m2:
                    try:
                        goal["load_kg"] = float(m2.group(1))
                    except:
                        pass

    # ---------------------------------------------------------
    # MINIMIZE / LIGHTEST
    # ---------------------------------------------------------
    if goal["objective"] is None:
        if any(w in s for w in ["lightest", "minimize", "minimum weight", "light weight", "optimal weight"]):
            goal["objective"] = "minimize_weight"

    # default
    if goal["objective"] is None:
        goal["objective"] = "minimize_weight"

    # ---------------------------------------------------------
    # HOLE COUNT
    # ---------------------------------------------------------
    hc = re.search(r"(\d+)\s*(hole|holes)", s)
    if hc:
        try:
            goal["constraints"]["holes"] = int(hc.group(1))
        except:
            pass

    # ---------------------------------------------------------
    # HOLE DIAMETER
    # ---------------------------------------------------------
    hd = re.search(r"hole diameter\s*(\d+(\.\d+)?)\s*mm", s)
    if hd:
        try:
            goal["constraints"]["hole_diameter_mm"] = float(hd.group(1))
        except:
            pass

    # ---------------------------------------------------------
    # LENGTH + WIDTH HINTS
    # ---------------------------------------------------------
    nums = re.findall(r"(\d+(\.\d+)?)\s*mm", s)
    if nums:
        if len(nums) >= 1:
            goal["constraints"]["hint_length_mm"] = float(nums[0][0])
        if len(nums) >= 2:
            goal["constraints"]["hint_width_mm"] = float(nums[1][0])

    return goal


if __name__ == "__main__":
    tests = [
        "Design the lightest baseplate for 10kg load",
        "Improve stiffness by 30% without increasing weight by more than 5%",
        "Maximize strength-to-weight ratio for a 2kg mounted load",
        "Distribute 50kg evenly across 8 holes"
    ]
    for t in tests:
        print(t)
        print(parse_goal(t))
        print("-----")

