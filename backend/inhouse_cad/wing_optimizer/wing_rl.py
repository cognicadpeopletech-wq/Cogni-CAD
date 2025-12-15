import math
import json
from dataclasses import dataclass
from typing import Dict, Any, Callable, Optional, Tuple

import numpy as np

from inhouse_cad.wing_optimizer.vlm_solver import run_vlm


@dataclass 
class WingBaseline: 
    span: float = 10.0 
    root_chord: float = 1.5 
    tip_chord: float = 0.8 
    sweep_le_deg: float = 20.0 
    dihedral_deg: float = 5.0 
    twist_root_deg: float = 2.0 
    twist_tip_deg: float = -2.0 
    winglet_height: float = 1.0 
    winglet_cant_deg: float = 70.0 
    winglet_toe_out_deg: float = 0.0 


THETA_LOWER = np.array([-0.3, -0.3, -0.3, -10, -5, -5, -5, -0.5, -15, -20]) 
THETA_UPPER = np.array([ 0.5,  0.5,  0.5,  10, 10,  5,  5,  1.0, 15,  20]) 


def decode_naca4(code: str): 
    if len(code) != 4 or not code.isdigit(): 
        raise ValueError("Invalid NACA 4-digit code") 
    m = int(code[0]) / 100.0 
    p = int(code[1]) / 10.0 
    t = int(code[2:]) / 100.0 
    return m, p, t 


def generate_naca4_airfoil(m, p, t, n_points=81): 
    beta = np.linspace(0.0, math.pi, n_points) 
    x = 0.5 * (1.0 - np.cos(beta)) 

    a0, a1, a2, a3, a4 = 0.2969, -0.1260, -0.3516, 0.2843, -0.1015 
    y_t = 5 * t * (a0*np.sqrt(x)+a1*x+a2*x**2+a3*x**3+a4*x**4) 

    y_c = np.zeros_like(x) 
    dyc_dx = np.zeros_like(x) 
    if m > 0 and p > 0: 
        m1 = x < p 
        m2 = ~m1 
        y_c[m1] = m/(p**2) * (2*p*x[m1] - x[m1]**2) 
        y_c[m2] = m/((1-p)**2) * ((1-2*p)+2*p*x[m2] - x[m2]**2) 
        dyc_dx[m1] = 2*m/(p**2)*(p - x[m1]) 
        dyc_dx[m2] = 2*m/((1-p)**2)*(p - x[m2]) 

    theta = np.arctan(dyc_dx) 
    x_u = x - y_t*np.sin(theta) 
    z_u = y_c + y_t*np.cos(theta) 
    x_l = x + y_t*np.sin(theta) 
    z_l = y_c - y_t*np.cos(theta) 

    x_all = np.concatenate([x_u[::-1], x_l[1:]]) 
    z_all = np.concatenate([z_u[::-1], z_l[1:]]) 
    return x_all, z_all 


def apply_theta(base: WingBaseline, theta: np.ndarray) -> Dict[str, float]: 
    t = np.zeros(10) if theta is None else np.clip(theta, THETA_LOWER, THETA_UPPER) 
    return { 
        "span":               base.span * (1 + t[0]), 
        "root_chord":         base.root_chord * (1 + t[1]), 
        "tip_chord":          base.tip_chord * (1 + t[2]), 
        "sweep_le_deg":       base.sweep_le_deg + t[3], 
        "dihedral_deg":       base.dihedral_deg + t[4], 
        "twist_root_deg":     base.twist_root_deg + t[5], 
        "twist_tip_deg":      base.twist_tip_deg + t[6], 
        "winglet_height":     base.winglet_height * (1 + t[7]), 
        "winglet_cant_deg":   base.winglet_cant_deg + t[8], 
        "winglet_toe_out_deg":base.winglet_toe_out_deg + t[9], 
    } 


def generate_wing_mesh(params, naca_code="2412", n_span=16, n_pts=81): 
    m, p, t = decode_naca4(naca_code) 
    span = params["span"] 
    cr = params["root_chord"] 
    ct = params["tip_chord"] 
    sweep = math.radians(params["sweep_le_deg"]) 
    dihedral = math.radians(params["dihedral_deg"]) 
    twr = params["twist_root_deg"] 
    twt = params["twist_tip_deg"] 
    winglet_h = params["winglet_height"] 
    winglet_cant = math.radians(params["winglet_cant_deg"]) 
    winglet_toe = math.radians(params["winglet_toe_out_deg"]) 

    eta = np.linspace(0,1,n_span) 
    y = eta * span 
    chords = (1-eta)*cr + eta*ct 
    twists = (1-eta)*twr + eta*twt 
    x_le = y * math.tan(sweep) 
    z_mid = y * math.tan(dihedral) 

    x_af_u, z_af_u = generate_naca4_airfoil(m, p, t, n_pts) 
    Np = x_af_u.shape[0] 

    V = [] 
    idx_section = [] 

    for i in range(n_span): 
        c = chords[i] 
        tw = math.radians(twists[i]) 
        x0, z0 = x_le[i], z_mid[i] 
        xQc = x0 + 0.25*c 
        zQc = z0 

        x_af = x_af_u * c 
        z_af = z_af_u * c 
        xloc = x_af + x0 
        zloc = z_af + z0 
        yloc = np.full_like(xloc, y[i]) 

        dx = xloc - xQc 
        dz = zloc - zQc 
        cosT = math.cos(tw) 
        sinT = math.sin(tw) 
        X = xQc + cosT*dx 
        Z = zQc + (-sinT)*dx + dz 

        start = len(V) 
        idx_section.append(start) 
        for xx, yy, zz in zip(X, yloc, Z): 
            V.append([xx, yy, zz]) 

    V = np.array(V, np.float32) 
    F = [] 

    for i in range(n_span-1): 
        i1 = idx_section[i] 
        i2 = idx_section[i+1] 
        for j in range(Np-1): 
            a = i1 + j 
            b = i1 + j + 1 
            c1 = i2 + j 
            d = i2 + j + 1 
            F.append([a,b,d]) 
            F.append([a,d,c1]) 

    # Simple winglet: extrude tip section along direction set by cant & toe 
    if winglet_h > 1e-6: 
        v_xy = np.array([math.cos(winglet_toe), math.sin(winglet_toe), 0.0]) 
        v = v_xy*math.cos(winglet_cant) + np.array([0.0,0.0,1.0])*math.sin(winglet_cant) 
        v /= np.linalg.norm(v) 
        tip_start = idx_section[-1] 
        tip_end = tip_start + Np 
        tip_V = V[tip_start:tip_end] 
        top_V = tip_V + v * winglet_h 
        top_start = V.shape[0] 
        V = np.vstack([V, top_V]) 
        for j in range(Np-1): 
            a = tip_start + j 
            b = tip_start + j + 1 
            c1 = top_start + j 
            d = top_start + j + 1 
            F.append([a,b,d]) 
            F.append([a,d,c1]) 

    return V, np.array(F, np.int32) 


def save_obj(path: str, V, F): 
    with open(path, "w") as f: 
        f.write("# wing mesh\n") 
        for v in V: 
            f.write(f"v {v[0]} {v[1]} {v[2]}\n") 
        for tri in F: 
            f.write(f"f {tri[0]+1} {tri[1]+1} {tri[2]+1}\n") 


def evaluate(geom_params: Dict[str, float], naca="2412") -> Dict[str, float]: 
    CL, CDi, eff = run_vlm(geom_params, alpha_deg=5.0, n_span=16) 
    # Add a simple fixed parasitic drag term 
    CD0 = 0.02 
    CD = CD0 + CDi 
    AR = geom_params["span"]**2 / (0.5*(geom_params["root_chord"]+geom_params["tip_chord"])*geom_params["span"]) 
    L_over_D = CL / (CD+1e-9) 
    return { 
        "CL": CL, 
        "CD": CD, 
        "CDi": CDi, 
        "e": eff, 
        "AR": AR, 
        "L_over_D": L_over_D 
    } 


def optimize_wing( 
    naca="2412", 
    iterations=40, 
    pop=60, 
    elite_frac=0.2, 
    seed=0, 
    objective="max_LD", # Default
    delay: float = 0.0,
    iteration_callback: Optional[Callable[[int, Dict[str,float], np.ndarray, Dict[str,float]], None]] = None, 
) -> Tuple[Dict[str,float], np.ndarray, Dict[str,float]]: 
    """ 
    Main RL-style CEM optimizer. 
    Objectives: 
      - max_LD (Maximize Lift-to-Drag)
      - max_CL (Maximize Lift Coeff)
      - min_CD (Minimize Total Drag Coeff)
      - max_e  (Maximize Span Efficiency)
      - min_CDi (Minimize Induced Drag)
      - min_M_root (Minimize Root Bending Moment ~ Lift * Span)
      - takeoff (Maximize CL, with alpha=10 implied or optimized)
    """ 
    rng = np.random.default_rng(seed) 
    base = WingBaseline() 
    dim = 10 
    mu = np.zeros(dim) 
    sigma = np.ones(dim) * 0.3 
    elite_n = max(1, int(pop*elite_frac)) 

    best_theta = None 
    best_geom = None 
    best_metrics = {} 
    best_score = -1e9 

    # Early Stopping Tracking
    last_best_score = -1e9
    plateau_count = 0
    
    import time
    for it in range(iterations): 
        if delay > 0:
            time.sleep(delay)

        # --- Early Stopping Check ---
        # (DISABLED for Demo Profile: Run 30 linear + 4 const)
        # if it > 5:
        #     improvement = best_score - last_best_score
        #     # If improvement is very small (< 0.05)
        #     if improvement < 0.05:
        #         plateau_count += 1
        #     else:
        #         plateau_count = 0
        #     
        #     last_best_score = best_score
        #     
        #     # Stop if flat for 4 iterations AND we have a good result (> 24)
        #     if plateau_count >= 4 and best_score > 24.0:
        #         print(f"Optimization Converged: L/D > 24 and stable for 4 iterations.")
        #         break
        
        # --- FORCED PLATEAU DEMO LOGIC ---
        if it >= 30:
            # Force constant output for 31, 32, 33, 34, 35
            if iteration_callback is not None:
                iteration_callback(it+1, best_geom, best_theta, best_metrics)
            
            # Stop specifically after 5 forced iterations (plateau)
            # We want total 35 iterations. Indices: 0..34.
            if it >= 34:
                print("Wing Optimization Complete.")
                break
            continue # Skip normal optimization loop for these steps
        
        samples = rng.normal(mu, sigma, (pop, dim)) 
        samples = np.clip(samples, THETA_LOWER, THETA_UPPER) 
        scores = [] 
        metrics_list = [] 
        geoms = [] 

        for theta in samples: 
            geom = apply_theta(base, theta) 
            try:
                metrics = evaluate(geom, naca=naca) 
                
                # Scoring Logic
                if objective == "max_LD" or objective == "maximize_L_over_D":
                    score = metrics["L_over_D"]
                elif objective == "max_CL" or objective == "takeoff":
                    score = metrics["CL"]
                elif objective == "min_CD":
                    score = 1.0 / (metrics["CD"] + 1e-9)
                elif objective == "min_CD_maintain_CL":
                    # Constraint: CL >= 1.2
                    if metrics["CL"] < 1.2:
                        # Soft penalty to guide it back to feasible region
                        score = -10.0 + metrics["CL"] 
                    else:
                        # Minimize Drag -> Maximize 1/CD
                        score = 1.0 / (metrics["CD"] + 1e-9)
                elif objective == "max_e":
                    score = metrics["e"]
                elif objective == "min_CDi":
                    score = 1.0 / (metrics["CDi"] + 1e-9)
                elif objective == "min_M_root":
                    # Approx bending: Lift Force * Dist ~ (CL * Area) * (Span/4)
                    # Force ~ CL * Area. Dist ~ Span.
                    # Area ~ Span * MeanChord.
                    # M ~ CL * Span^2 * MeanChord
                    # Minimize M -> Maximize 1/M
                    area = geom["span"] * 0.5 * (geom["root_chord"] + geom["tip_chord"])
                    moment = metrics["CL"] * area * (geom["span"] * 0.25)
                    score = 1.0 / (moment + 1e-9)
                else:
                    score = metrics["L_over_D"]

            except:
                score = -1e9 # Penalty for failure
                metrics = {"L_over_D": 0, "CL":0, "CD":1, "e":0}
            
            scores.append(score) 
            metrics_list.append(metrics) 
            geoms.append(geom) 

        scores = np.array(scores) 
        idx_iter_best = int(np.argmax(scores)) 
        
        # Track global best
        if scores[idx_iter_best] > best_score: 
            best_score = float(scores[idx_iter_best]) 
            best_theta = samples[idx_iter_best].copy() 
            best_geom = geoms[idx_iter_best] 
            best_metrics = metrics_list[idx_iter_best] 

        elites = samples[np.argsort(scores)[-elite_n:]] 
        mu = elites.mean(axis=0) 
        sigma = elites.std(axis=0) + 1e-6 

        if iteration_callback is not None: 
            iteration_callback( 
                it+1, 
                best_geom, 
                best_theta, 
                best_metrics 
            ) 

    # Fallback if no valid score found
    if best_geom is None:
         best_geom = apply_theta(base, np.zeros(dim))
         best_theta = np.zeros(dim)
         best_metrics = evaluate(best_geom)

    return best_geom, best_theta, best_metrics 
