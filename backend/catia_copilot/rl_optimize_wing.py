#!/usr/bin/env python3
"""
rl_optimize_wing.py

Q-learning based RL optimizer for your NACA wing PyCATIA script.

Features:
 - Tabular Q-learning on discrete grids for (m,p,t,c_t,sweep)
 - Fast proxy physics evaluator (no CFD) used as reward proxy
 - Returns `top_k` candidate designs ranked by proxy score
 - Safe update of wing_structure_winglet_transparent.py (backup .bak)
 - Optionally run the wing script after updating (launches as subprocess)
 - CLI and programmatic API: run_rl_optimize(...)

Usage (programmatic):
    from rl_optimize_wing import run_rl_optimize
    out = run_rl_optimize("Optimize wing for endurance", parsed_goal={"objective":"low_drag"}, top_k=3)

Usage (CLI):
    python rl_optimize_wing.py --episodes 800 --top_k 2 --update-script --run-catia
"""

from __future__ import annotations
import re
import math
import random
import json
import shutil
import argparse
import os
import subprocess
import time
from collections import defaultdict
from typing import Tuple, Dict, Any, List, Optional

# ------------------------- Design grids (discrete spaces) -------------------------
M_VALUES      = [2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0]          # max camber (%)
P_VALUES      = [2.0, 3.0, 4.0, 5.0, 6.0]                    # camber position (tenths)
T_VALUES      = [10.0, 12.0, 14.0, 16.0, 18.0]               # thickness (%)
CT_VALUES     = [0.3, 0.35, 0.4, 0.45, 0.5, 0.6, 0.7, 0.8]   # tip chord (m)
SWEEP_VALUES  = [10.0, 15.0, 20.0, 25.0, 30.0, 35.0, 40.0]   # sweep angle (deg)

C_R_DEFAULT = 1.75   # root chord (m)
S_DEFAULT   = 3.0    # span (m)

# Actions: +/- index on one parameter
ACTIONS = [
    "inc_M", "dec_M",
    "inc_P", "dec_P",
    "inc_T", "dec_T",
    "inc_CT", "dec_CT",
    "inc_SWEEP", "dec_SWEEP"
]

# Default path to wing script (relative)
DEFAULT_WING_SCRIPT = "wing_structure_winglet_transparent.py"
# Timeout for running external wing script (seconds)
DEFAULT_RUN_TIMEOUT = 240

# ---------------------- Proxy physics evaluator ----------------------
def evaluate_wing_proxy(m: float, p: float, t: float, c_r: float, c_t: float, s: float, sweep_deg: float,
                        weights: Optional[Dict[str, float]] = None) -> float:
    """
    Fast proxy evaluator returning a scalar score (higher is better).
    Replace or extend with higher-fidelity metric (CFD/FEM) if available.
    """
    if weights is None:
        weights = {"w_l": 1.0, "w_strength": 0.5, "w_weight_pen": 0.2}

    area = 0.5 * (c_r + c_t) * s
    lift = (m / 100.0) * area
    sweep_factor = 1.0 + (sweep_deg / 40.0)
    drag = ((t / 100.0) ** 2) * sweep_factor
    strength = (t / 100.0) * c_r
    weight = area * (t / 100.0)
    ld_ratio = lift / (drag + 1e-9)
    score = weights["w_l"] * ld_ratio + weights["w_strength"] * strength - weights["w_weight_pen"] * weight

    # Soft penalties to keep designs reasonable
    if t < min(T_VALUES) or t > max(T_VALUES):
        score -= 5.0
    if m > max(M_VALUES):
        score -= 3.0
    if abs(c_r - c_t) > 1.5:
        score -= 2.0
    if area < 1.0:
        score -= 3.0

    return float(score)

# ---------------------- State & action utilities ----------------------
def random_state() -> Dict[str, int]:
    return {
        "M_i": random.randrange(len(M_VALUES)),
        "P_i": random.randrange(len(P_VALUES)),
        "T_i": random.randrange(len(T_VALUES)),
        "CT_i": random.randrange(len(CT_VALUES)),
        "SW_i": random.randrange(len(SWEEP_VALUES)),
    }

def state_to_tuple(s: Dict[str, int]) -> Tuple[int, int, int, int, int]:
    return (s["M_i"], s["P_i"], s["T_i"], s["CT_i"], s["SW_i"])

def apply_action(state: Dict[str, int], action: str) -> Dict[str, int]:
    s = state.copy()
    if action == "inc_M":
        s["M_i"] = min(s["M_i"] + 1, len(M_VALUES) - 1)
    elif action == "dec_M":
        s["M_i"] = max(s["M_i"] - 1, 0)
    elif action == "inc_P":
        s["P_i"] = min(s["P_i"] + 1, len(P_VALUES) - 1)
    elif action == "dec_P":
        s["P_i"] = max(s["P_i"] - 1, 0)
    elif action == "inc_T":
        s["T_i"] = min(s["T_i"] + 1, len(T_VALUES) - 1)
    elif action == "dec_T":
        s["T_i"] = max(s["T_i"] - 1, 0)
    elif action == "inc_CT":
        s["CT_i"] = min(s["CT_i"] + 1, len(CT_VALUES) - 1)
    elif action == "dec_CT":
        s["CT_i"] = max(s["CT_i"] - 1, 0)
    elif action == "inc_SWEEP":
        s["SW_i"] = min(s["SW_i"] + 1, len(SWEEP_VALUES) - 1)
    elif action == "dec_SWEEP":
        s["SW_i"] = max(s["SW_i"] - 1, 0)
    return s

def decode_state(state: Dict[str, int], c_r: float = C_R_DEFAULT, s: float = S_DEFAULT) -> Dict[str, float]:
    return {
        "m": M_VALUES[state["M_i"]],
        "p": P_VALUES[state["P_i"]],
        "t": T_VALUES[state["T_i"]],
        "c_r": c_r,
        "c_t": CT_VALUES[state["CT_i"]],
        "s": s,
        "sweep": SWEEP_VALUES[state["SW_i"]],
    }

# ---------------------- Q-learning trainer ----------------------
def train_rl_wing(episodes: int = 800, steps_per_episode: int = 25,
                  alpha: float = 0.2, gamma: float = 0.9, epsilon: float = 0.25,
                  seed: Optional[int] = None, verbose: bool = False,
                  weights: Optional[Dict[str, float]] = None) -> Tuple[Dict[str, int], Dict[str, float], float, Dict]:
    """
    Train tabular Q-learning and return best state + params + score + Q-table.
    """
    if seed is not None:
        random.seed(seed)

    Q = defaultdict(lambda: {a: 0.0 for a in ACTIONS})
    best_state = None
    best_params = None
    best_score = -1e9

    for ep in range(episodes):
        state = random_state()
        for step in range(steps_per_episode):
            s_key = state_to_tuple(state)
            # epsilon-greedy
            if random.random() < epsilon:
                action = random.choice(ACTIONS)
            else:
                action = max(Q[s_key], key=Q[s_key].get)

            new_state = apply_action(state, action)
            params = decode_state(new_state)
            score = evaluate_wing_proxy(params["m"], params["p"], params["t"], params["c_r"], params["c_t"], params["s"], params["sweep"], weights=weights)
            reward = score

            if reward > best_score:
                best_score = reward
                best_state = new_state.copy()
                best_params = params.copy()

            # Q update
            new_key = state_to_tuple(new_state)
            max_next = max(Q[new_key].values()) if Q[new_key] else 0.0
            old_q = Q[s_key][action]
            Q[s_key][action] = old_q + alpha * (reward + gamma * max_next - old_q)

            state = new_state

        if verbose and ((ep + 1) % max(1, episodes // 5) == 0):
            print(f"[train] Episode {ep+1}/{episodes} — best_score: {best_score:.4f}")

    return best_state, best_params, best_score, Q

# ---------------------- Utilities: top-k extraction & formatting ----------------------
def collect_top_k_candidates(Q: Dict, num_candidates: int = 3, seed: Optional[int] = None,
                             episodes: int = 800, steps_per_episode: int = 25, weights: Optional[Dict[str,float]]=None) -> List[Dict[str,Any]]:
    """
    Simple approach to obtain multiple good candidates:
      - run multiple independent training runs (with different random seeds)
      - collect best candidate from each run
      - sort and deduplicate by parameter tuple
    """
    if seed is not None:
        random.seed(seed)

    found = []
    runs = max(1, num_candidates)
    tried_states = set()
    for r in range(runs):
        # vary seed to get variety
        s_seed = None if seed is None else (seed + r)
        best_state, best_params, best_score, Qtable = train_rl_wing(episodes=episodes, steps_per_episode=steps_per_episode,
                                                                     alpha=0.2, gamma=0.9, epsilon=0.25, seed=s_seed, verbose=False, weights=weights)
        if best_params is None:
            continue
        key = (best_params["m"], best_params["p"], best_params["t"], best_params["c_t"], best_params["sweep"])
        if key in tried_states:
            continue
        tried_states.add(key)
        cand = {
            "m": float(best_params["m"]),
            "p": float(best_params["p"]),
            "t": float(best_params["t"]),
            "c_t": float(best_params["c_t"]),
            "sweep": float(best_params["sweep"]),
            "score": float(best_score)
        }
        found.append(cand)
        if len(found) >= num_candidates:
            break

    # sort by score descending
    found.sort(key=lambda x: x["score"], reverse=True)
    # ensure top_k length
    return found[:num_candidates]

def map_candidate_to_output(cand: Dict[str,Any]) -> Dict[str,Any]:
    """
    Ensure candidate has consistent keys for UI: include readable floats and optional proxies.
    """
    out = dict(cand)
    # make sure numeric formatting is plain floats
    for k in ("m","p","t","c_t","sweep","score"):
        if k in out:
            out[k] = float(out[k])
    # Add optional derived proxies
    try:
        out.setdefault("lift_proxy", evaluate_wing_proxy(out["m"], out["p"], out["t"], C_R_DEFAULT, out["c_t"], S_DEFAULT, out["sweep"]))
    except Exception:
        pass
    return out

# ---------------------- Safe wing script updater ----------------------
def backup_file(path: str) -> str:
    bak = path + ".bak"
    shutil.copy2(path, bak)
    return bak

def safe_update_wing_script(m: float, p: float, t: float, c_t: float, sweep: float,
                            filename: str = DEFAULT_WING_SCRIPT) -> bool:
    """
    Safely update numeric parameter assignments in the target script.
    Replaces lines like `m = 7` with `m = <value>`. Creates backup.
    Returns True if file changed, False otherwise.
    """
    if not os.path.exists(filename):
        print(f"[safe_update] WARNING - wing script not found: {filename}")
        return False

    with open(filename, "r", encoding="utf-8") as f:
        code = f.read()

    bakpath = backup_file(filename)

    patterns = {
        r"(^\s*m\s*=\s*)([-+]?\d*\.?\d+)(\s*$)": r"\1" + f"{m:.6g}" + r"\3",
        r"(^\s*p\s*=\s*)([-+]?\d*\.?\d+)(\s*$)": r"\1" + f"{p:.6g}" + r"\3",
        r"(^\s*t\s*=\s*)([-+]?\d*\.?\d+)(\s*$)": r"\1" + f"{t:.6g}" + r"\3",
        r"(^\s*c_t\s*=\s*)([-+]?\d*\.?\d+)(\s*$)": r"\1" + f"{c_t:.6g}" + r"\3",
        r"(^\s*a_sweep\s*=\s*)([-+]?\d*\.?\d+)(\s*$)": r"\1" + f"{sweep:.6g}" + r"\3",
    }

    new_code = code
    replaced_any = False
    for patt, repl in patterns.items():
        new_code, n = re.subn(patt, repl, new_code, flags=re.MULTILINE)
        if n > 0:
            replaced_any = True

    # fallback: try literal replacements if regex failed (older script variants)
    if not replaced_any:
        fallback_map = {
            "m = 4": f"m = {m:.6g}",
            "p = 4": f"p = {p:.6g}",
            "t = 15": f"t = {t:.6g}",
            "c_t = 0.5": f"c_t = {c_t:.6g}",
            "a_sweep = 35.0": f"a_sweep = {sweep:.6g}",
        }
        for old, new in fallback_map.items():
            if old in new_code:
                new_code = new_code.replace(old, new)
                replaced_any = True

    if replaced_any:
        with open(filename, "w", encoding="utf-8") as f:
            f.write(new_code)
        print(f"[safe_update] Updated {filename} (backup at {bakpath})")
        print(f"  m={m:.6g}, p={p:.6g}, t={t:.6g}, c_t={c_t:.6g}, sweep={sweep:.6g}")
        return True

    print("[safe_update] No parameter patterns matched. Backup saved, file not changed.")
    return False

# ---------------------- Top-level run function for integration ----------------------
def run_rl_optimize(command_text: str = "optimize wing for endurance",
                    parsed_goal: Optional[Dict[str, Any]] = None,
                    shape: Optional[str] = None,
                    top_k: int = 1,
                    episodes: int = 600,
                    steps_per_episode: int = 20,
                    alpha: float = 0.2,
                    gamma: float = 0.9,
                    epsilon: float = 0.25,
                    seed: Optional[int] = None,
                    update_script: bool = False,
                    script_filename: str = DEFAULT_WING_SCRIPT,
                    run_catia: bool = False,
                    run_timeout: int = DEFAULT_RUN_TIMEOUT
                    ) -> Dict[str, Any]:
    """
    High-level entry used by main program.

    Returns:
      {
        "candidates": [ ... ],        # top_k candidate dicts (m,p,t,c_t,sweep,score)
        "updated_script": True/False,
        "script_filename": "...",
        "run_result": { stdout/stderr/error/saved } or None
      }
    """
    # Interpret goal -> weights
    weights = None
    cmd_lower = (command_text or "").lower()
    if parsed_goal and isinstance(parsed_goal, dict):
        obj = str(parsed_goal.get("objective", "") or parsed_goal.get("goal", "")).lower()
        if "low drag" in obj or "minimize drag" in obj or "low drag" in cmd_lower:
            # prioritize low drag (penalize weight more)
            weights = {"w_l": 0.85, "w_strength": 0.4, "w_weight_pen": 0.6}
        if "endurance" in obj or "efficiency" in obj or "endurance" in cmd_lower:
            weights = {"w_l": 1.2, "w_strength": 0.5, "w_weight_pen": 0.3}

    # Get top_k candidates via multiple short trainings (cheap)
    candidates_raw = collect_top_k_candidates(Q={}, num_candidates=top_k, seed=seed,
                                              episodes=episodes, steps_per_episode=steps_per_episode, weights=weights)
    candidates = [map_candidate_to_output(c) for c in candidates_raw]

    result = {
        "candidates": candidates,
        "top_k": top_k,
        "command_text": command_text,
    }

    if not candidates:
        return result

    # Optionally update the wing script with the best candidate
    updated = False
    if update_script:
        best = candidates[0]
        try:
            updated = safe_update_wing_script(best["m"], best["p"], best["t"], best["c_t"], best["sweep"], filename=script_filename)
        except Exception as e:
            result["update_error"] = str(e)
            updated = False
    result["updated_script"] = bool(updated)
    result["script_filename"] = script_filename if updated else None

    # Optionally run the wing script (external process). We capture stdout/stderr and look for saved files.
    run_result = None
    if run_catia and updated:
        try:
            start = time.time()
            p = subprocess.run([os.sys.executable, script_filename], capture_output=True, text=True, timeout=run_timeout)
            end = time.time()
            run_stdout = p.stdout or ""
            run_stderr = p.stderr or ""
            run_err = None if p.returncode == 0 else f"exit_{p.returncode}"

            saved = [ln.strip() for ln in run_stdout.splitlines() if ".catpart" in ln.lower() or ".catproduct" in ln.lower()]
            run_result = {
                "stdout": run_stdout,
                "stderr": run_stderr,
                "error": run_err,
                "saved": saved if saved else [str(os.path.abspath(os.path.dirname(script_filename)))]
            }
            run_result["runtime_sec"] = end - start
        except Exception as e:
            run_result = {"stdout": "", "stderr": str(e), "error": str(e), "saved": []}

    result["run_result"] = run_result
    return result

# ---------------------- CLI ----------------------
def _cli():
    parser = argparse.ArgumentParser(description="RL optimizer for NACA wing (tabular Q-learning, proxy reward).")
    parser.add_argument("--command", type=str, default="optimize wing for endurance", help="Natural-language goal")
    parser.add_argument("--top_k", type=int, default=1, help="How many top candidates to return")
    parser.add_argument("--episodes", type=int, default=600, help="Episodes per training run")
    parser.add_argument("--steps", type=int, default=20, help="Steps per episode")
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--update-script", action="store_true", dest="update_script", help="Write best params into wing script")
    parser.add_argument("--script-filename", type=str, default=DEFAULT_WING_SCRIPT)
    parser.add_argument("--run-catia", action="store_true", dest="run_catia", help="After updating, run wing script")
    parser.add_argument("--timeout", type=int, default=DEFAULT_RUN_TIMEOUT, help="Timeout for running wing script (seconds)")
    args = parser.parse_args()

    parsed_goal = {}
    out = run_rl_optimize(command_text=args.command,
                          parsed_goal=parsed_goal,
                          top_k=args.top_k,
                          episodes=args.episodes,
                          steps_per_episode=args.steps,
                          seed=args.seed,
                          update_script=args.update_script,
                          script_filename=args.script_filename,
                          run_catia=args.run_catia,
                          run_timeout=args.timeout)
    print(json.dumps(out, indent=2))

if __name__ == "__main__":
    _cli()
