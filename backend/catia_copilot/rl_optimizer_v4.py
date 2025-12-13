
#!/usr/bin/env python3
"""
rl_optimizer_v4.py — lightweight RL-style optimizer (lighter-by-default)

Changes from previous:
 - Default material density is now steel (7850 kg/m^3) for realistic steel estimates.
 - Accepts material density override via parsed_goal["constraints"]["material_density"]
   or material name via parsed_goal["constraints"]["material"] ("steel", "aluminum", "titanium").
 - Increased thickness penalty so optimizer prefers thinner plates.
 - Keeps all previous outputs (weight_kg, capacity_proxy, strength_to_weight, penalty, score).
"""

import math
import random
import copy

# Default densities (kg/m^3)
DENSITY_ALUMINUM = 2700.0
DENSITY_STEEL = 7850.0
DENSITY_TITANIUM = 4500.0

DEFAULT_DENSITY = DENSITY_STEEL   # use steel as the default material

# helpers ------------------------------------------------
def _rect_plate_weight(length_mm, width_mm, thickness_mm, density=DEFAULT_DENSITY):
    vol_m3 = (length_mm * width_mm * thickness_mm) * 1e-9
    return density * vol_m3  # kg

def _cylinder_weight(diameter_mm, height_mm, thickness_mm, density=DEFAULT_DENSITY, hollow=False):
    r = diameter_mm / 2.0
    if hollow:
        outer_vol = math.pi * (r**2) * height_mm * 1e-9
        inner_r = max(r - thickness_mm, 0.0)
        inner_vol = math.pi * (inner_r**2) * height_mm * 1e-9
        vol_m3 = max(outer_vol - inner_vol, 0.0)
    else:
        vol_m3 = math.pi * (r**2) * height_mm * 1e-9
    return density * vol_m3

def _rect_tube_weight(outer_w_mm, outer_d_mm, height_mm, wall_mm, density=DEFAULT_DENSITY):
    outer_vol = outer_w_mm * outer_d_mm * height_mm * 1e-9
    inner_w = max(outer_w_mm - 2*wall_mm, 0.01)
    inner_d = max(outer_d_mm - 2*wall_mm, 0.01)
    inner_vol = inner_w * inner_d * height_mm * 1e-9
    vol_m3 = max(outer_vol - inner_vol, 0.0)
    return density * vol_m3

def _strength_proxy_area_rect(length_mm, width_mm, thickness_mm):
    # simple proxy: area of edges scaled (very rough)
    return (length_mm * thickness_mm) * 1e-6 + (width_mm * thickness_mm) * 1e-6

def _strength_proxy_circle(diameter_mm, thickness_mm):
    return (math.pi * diameter_mm * thickness_mm) * 1e-6

# mapping shapes to parameter bounds
SHAPE_BOUNDS = {
    "cylinder_solid": {
        "length_mm": (180.0, 200.0),
        "width_mm": (90.0, 100.0),
        "thickness_mm": (5.0, 20.0),
        "cyl_diameter": (20.0, 60.0),
        "cyl_height": (50.0, 60.0),
    },
    "cylinder_tube": {
        "length_mm": (150.0, 200.0),
        "width_mm": (100.0, 150.0),
        "thickness_mm": (5.0, 20.0),
        "cyl_diameter": (30.0, 60.0),
        "cyl_height": (50.0, 60.0),
        "wall_mm": (1.0, 6.0),
    },
    "rect_tube": {
        "length_mm": (100.0, 110.0),
        "width_mm": (150.0, 200.0),
        "thickness_mm": (5.0, 20.0),
        "rod_w_mm": (20.0, 60.0),
        "rod_d_mm": (10.0, 60.0),
        "rod_h_mm": (80.0, 160.0),
        "wall_mm": (1.0, 6.0),
    },
    "rect_rod": {
        "length_mm": (100.0, 130.0),
        "width_mm": (150.0, 200.0),
        "thickness_mm": (5.0, 20.0),
        "rod_w_mm": (20.0, 60.0),
        "rod_d_mm": (10.0, 60.0),
        "rod_h_mm": (80.0, 160.0),
    }
}

# objective/scoring -------------------------------------
def _resolve_density_from_goal(parsed_goal: dict):
    """Return density (kg/m^3) based on parsed_goal constraints if present."""
    try:
        if not parsed_goal or not isinstance(parsed_goal, dict):
            return DEFAULT_DENSITY
        cons = parsed_goal.get("constraints", {}) or {}
        # explicit numeric override
        if "material_density" in cons:
            d = float(cons["material_density"])
            if d > 0:
                return d
        mat = (cons.get("material") or "").lower()
        if mat in ("steel", "iron"):
            return DENSITY_STEEL
        if mat in ("aluminum", "aluminium"):
            return DENSITY_ALUMINUM
        if mat in ("titanium",):
            return DENSITY_TITANIUM
    except Exception:
        pass
    return DEFAULT_DENSITY

def evaluate_candidate(candidate: dict, parsed_goal: dict, shape_tag: str):
    """
    Compute a score for candidate: lower is better.
    Returns (score, meta) where meta includes weight_kg, capacity_proxy, penalty.
    """
    load = parsed_goal.get("load_kg") or 0.0
    density = _resolve_density_from_goal(parsed_goal)
    constraints = parsed_goal.get("constraints", {})

    # estimate weight and capacity based on shape
    if shape_tag in ("cylinder_solid",):
        L = candidate.get("length_mm", 200.0)
        W = candidate.get("width_mm", 150.0)
        T = candidate.get("thickness_mm", 20.0)
        cyl_d = candidate.get("cyl_diameter", 50.0)
        cyl_h = candidate.get("cyl_height", 120.0)
        weight_plate = _rect_plate_weight(L, W, T, density=density)
        weight_cyl = _cylinder_weight(cyl_d, cyl_h, T, density=density, hollow=False)
        weight = weight_plate + weight_cyl
        capacity = _strength_proxy_area_rect(L, W, T) + _strength_proxy_circle(cyl_d, T)
    elif shape_tag in ("cylinder_tube",):
        L = candidate.get("length_mm", 200.0)
        W = candidate.get("width_mm", 150.0)
        T = candidate.get("thickness_mm", 20.0)
        cyl_d = candidate.get("cyl_diameter", 50.0)
        cyl_h = candidate.get("cyl_height", 120.0)
        wall = candidate.get("wall_mm", 2.0)
        weight_plate = _rect_plate_weight(L, W, T, density=density)
        weight_cyl = _cylinder_weight(cyl_d, cyl_h, wall, density=density, hollow=True)
        weight = weight_plate + weight_cyl
        capacity = _strength_proxy_area_rect(L, W, T) + _strength_proxy_circle(cyl_d, wall)
    elif shape_tag in ("rect_tube",):
        L = candidate.get("length_mm", 200.0)
        W = candidate.get("width_mm", 150.0)
        T = candidate.get("thickness_mm", 20.0)
        rw = candidate.get("rod_w_mm", 50.0)
        rd = candidate.get("rod_d_mm", 40.0)
        rh = candidate.get("rod_h_mm", 100.0)
        wall = candidate.get("wall_mm", 2.0)
        weight_plate = _rect_plate_weight(L, W, T, density=density)
        # pass density explicitly so rect tube uses the resolved material
        weight_rod = _rect_tube_weight(rw, rd, rh, wall, density=density)
        weight = weight_plate + weight_rod
        capacity = _strength_proxy_area_rect(L, W, T) + (rw * wall * 1e-6 + rd * wall * 1e-6)
    else:  # rect_rod or fallback
        L = candidate.get("length_mm", 200.0)
        W = candidate.get("width_mm", 150.0)
        T = candidate.get("thickness_mm", 20.0)
        rw = candidate.get("rod_w_mm", 50.0)
        rd = candidate.get("rod_d_mm", 40.0)
        rh = candidate.get("rod_h_mm", 100.0)
        weight_plate = _rect_plate_weight(L, W, T, density=density)
        weight_rod = rw * rd * rh * 1e-9 * density
        weight = weight_plate + weight_rod
        capacity = _strength_proxy_area_rect(L, W, T) + (rw * rd * 1e-6)

    # ensure non-zero
    cap_scalar = max(capacity, 1e-9)
    required_scalar = (load + 1.0)

    penalty = 0.0
    if required_scalar > 0 and cap_scalar < required_scalar:
        deficit = required_scalar - cap_scalar
        penalty = (deficit ** 2) * 50.0

    # stronger thickness penalty so thinner plates favored more aggressively
    thickness_penalty = max((candidate.get("thickness_mm", 0.0) - 5.0) * 0.10, 0.0)

    score = weight + penalty + thickness_penalty

    meta = {
        "weight_kg": float(weight),
        "capacity_proxy": float(cap_scalar),
        "penalty": float(penalty),
        "thickness_penalty": float(thickness_penalty),
        "score": float(score),
        "density_used": float(density)
    }
    return float(score), meta

# search algorithm -------------------------------------
def _sample_uniform(bounds, rng):
    return {k: rng.uniform(v[0], v[1]) for k, v in bounds.items()}

def _mutate(candidate, bounds, rng, scale=0.08):
    out = candidate.copy()
    for k, (lo, hi) in bounds.items():
        span = hi - lo
        delta = rng.uniform(-scale * span, scale * span)
        try:
            val = float(out.get(k, (lo + hi) / 2.0)) + delta
            val = max(min(val, hi), lo)
            out[k] = val
        except:
            out[k] = out.get(k, lo)
    return out

def run_rl_optimizer(command_text, parsed_goal=None, shape=None, top_k=3, seed=None, n_samples=200, n_local_steps=20):
    """
    Main entrypoint.

    Returns: dict {'candidates': [...], 'scores': [...], 'shape_tag':..., 'parsed_goal': ...}
    Each candidate dict will contain additional keys: weight_kg, capacity_proxy, strength_to_weight, penalty, score.
    """
    rng = random.Random(seed or 0)

    # backward compat: if first arg is parsed_goal
    if parsed_goal is None and isinstance(command_text, dict):
        parsed_goal = command_text
        command_text = ""

    parsed_goal = parsed_goal or {}
    shape_tag = (shape or parsed_goal.get("constraints", {}).get("shape") or parsed_goal.get("constraints", {}).get("preferred_shapes", [None])[0] or "cylinder_solid")

    # normalize
    if shape_tag in ("cylinder", "cyl", "cylinder_solid"):
        shape_tag = "cylinder_solid"
    if shape_tag in ("cylinder_tube", "cylinder_pipe", "tube", "pipe"):
        shape_tag = "cylinder_tube"
    if shape_tag in ("rect_tube", "rectangle_tube", "rectangular_tube"):
        shape_tag = "rect_tube"
    if shape_tag in ("rect_rod", "rectangle_rod", "rectangular_rod", "rectrod"):
        shape_tag = "rect_rod"

    bounds = SHAPE_BOUNDS.get(shape_tag, SHAPE_BOUNDS["cylinder_solid"])

    # stage 1: global random search
    raw_candidates = []
    for _ in range(n_samples):
        cand = _sample_uniform(bounds, rng)
        # ensure rod_h_mm exists with reasonable fallback if present in bounds
        if "rod_h_mm" in bounds and "rod_h_mm" not in cand:
            rh_bounds = bounds.get("rod_h_mm", (80, 160))
            cand["rod_h_mm"] = rng.uniform(rh_bounds[0], rh_bounds[1])

        score, meta = evaluate_candidate(cand, parsed_goal, shape_tag)
        raw_candidates.append((score, cand, meta))

    raw_candidates.sort(key=lambda x: x[0])
    survivors = raw_candidates[:max(6, top_k*2)]

    # stage 2: local hill-climb
    refined = []
    for score0, cand0, meta0 in survivors:
        best = cand0
        best_score = score0
        best_meta = meta0
        for _ in range(n_local_steps):
            cand_try = _mutate(best, bounds, rng, scale=0.12)
            sc, meta_try = evaluate_candidate(cand_try, parsed_goal, shape_tag)
            if sc < best_score:
                best = cand_try
                best_score = sc
                best_meta = meta_try
        refined.append((best_score, best, best_meta))

    all_candidates = raw_candidates + refined

    # deduplicate
    uniq = {}
    for sc, cand, meta in all_candidates:
        key = tuple(sorted((k, round(float(v), 3)) for k, v in cand.items()))
        if key not in uniq or sc < uniq[key][0]:
            uniq[key] = (sc, cand, meta)

    sorted_final = sorted(uniq.values(), key=lambda x: x[0])
    top_list = sorted_final[:top_k]

    result_candidates = []
    scores = []
    for sc, cand, meta in top_list:
        weight = meta.get("weight_kg", 0.0)
        capacity = meta.get("capacity_proxy", 1e-9)
        st_w = float(capacity / (weight + 1e-9))

        c_out = {k: (float(v) if isinstance(v, (int, float)) else v) for k, v in cand.items()}
        c_out["weight_kg"] = round(float(meta.get("weight_kg", 0.0)), 6)
        c_out["capacity_proxy"] = round(float(meta.get("capacity_proxy", 0.0)), 6)
        c_out["penalty"] = round(float(meta.get("penalty", 0.0)), 6)
        c_out["thickness_penalty"] = round(float(meta.get("thickness_penalty", 0.0)), 6)
        c_out["strength_to_weight"] = round(st_w, 6)
        c_out["score"] = round(float(sc), 6)
        c_out["density_used"] = round(float(meta.get("density_used", DEFAULT_DENSITY)), 2)

        result_candidates.append(c_out)
        scores.append(float(sc))

    return {
        "candidates": result_candidates,
        "scores": scores,
        "shape_tag": shape_tag,
        "parsed_goal": parsed_goal,
    }

# demo
if __name__ == "__main__":
    example_goal_text = "Design the lightest baseplate + rectangular tube assembly that can support a 10kg load, use steel."
    parsed = {"objective": "minimize_weight", "load_kg": 10.0, "constraints": {"preferred_shapes": ["rect_tube"], "material": "steel"}}
    out = run_rl_optimizer(example_goal_text, parsed_goal=parsed, shape="rect_tube", top_k=3, seed=1)
    import pprint
    pprint.pprint(out)
