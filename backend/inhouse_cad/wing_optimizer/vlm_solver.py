import math
import numpy as np
from typing import Dict, Tuple

def run_vlm(geom_params: Dict[str, float], 
            alpha_deg: float = 5.0, 
            n_span: int = 16) -> Tuple[float, float, float]: 
    """ 
    Simple lifting-line / VLM-style solver. 
    Inputs: 
      geom_params: dict with at least 
         span, root_chord, tip_chord, sweep_le_deg, twist_root_deg, twist_tip_deg 
      alpha_deg: geometric angle of attack in degrees 
      n_span: number of spanwise panels 
    Returns: 
      CL (lift coefficient), 
      CDi (induced drag coefficient), 
      e   (span efficiency factor) 
    """ 
    span = geom_params["span"] 
    cr = geom_params["root_chord"] 
    ct = geom_params["tip_chord"] 
    sweep = math.radians(geom_params["sweep_le_deg"]) 
    twist_root = geom_params["twist_root_deg"] 
    twist_tip = geom_params["twist_tip_deg"] 

    b = span  # semi-span in our earlier notation, but we treat full span=b here 
    S = 0.5 * (cr + ct) * b 
    if S <= 0: 
        return 0.0, 0.0, 0.0 

    # Discretize half-span (lifting-line on half-wing, mirror for full) 
    N = n_span 
    # Classical lifting-line uses theta in (0, pi), map to y via cos(theta) 
    i = np.arange(1, N+1) 
    theta = i * math.pi / (2*N + 1)  # slightly away from wingtips 
    y = 0.5 * b * np.cos(theta)      # from near tip to near root on half-wing 

    # Local chord and twist 
    eta = (y - y.min()) / (y.max() - y.min() + 1e-9) 
    chords = (1.0 - eta) * cr + eta * ct 
    twists = (1.0 - eta) * twist_root + eta * twist_tip 

    alpha = math.radians(alpha_deg) 
    twist_rad = np.radians(twists) 
    alpha_eff = alpha - twist_rad  # local effective AoA [rad] 

    # Build system: Prandtl lifting-line (Fourier series form) 
    # Gamma(theta) = 2*b*U∞ * Σ A_n sin(n*theta) 
    # alpha_eff(theta_i) = Σ A_n * (sin(n*theta_i) * (1 + (n * c_i)/(2*b) / sin(theta_i))) 
    # We'll solve for A_n then compute CL, CDi. 

    n_modes = N 
    A = np.zeros((N, n_modes)) 
    rhs = alpha_eff  # local effective AoA at control points 

    for i_idx in range(N): 
        th = theta[i_idx] 
        ci = chords[i_idx] 
        for n in range(1, n_modes+1): 
            term = (2*b / (ci)) * math.sin(th) + n * math.sin(n*th)/math.sin(th) 
            A[i_idx, n-1] = term * math.sin(n*th) 

    # Solve for Fourier coefficients A_n 
    # A * a = rhs  =>  a = least-squares 
    coeffs, *_ = np.linalg.lstsq(A, rhs, rcond=None) 

    # Overall CL and CDi (see lifting-line theory) 
    CL = math.pi * (b / S) * 2 * coeffs[0]  # A1 dominates total lift 
    # Induced drag factor: 
    n = np.arange(1, n_modes+1) 
    CDi = math.pi * (b / S) * 4 * np.sum(n * coeffs**2) 

    AR = b**2 / S 
    e = CL**2 / (math.pi * AR * CDi + 1e-9) 

    return float(CL), float(CDi), float(e) 
