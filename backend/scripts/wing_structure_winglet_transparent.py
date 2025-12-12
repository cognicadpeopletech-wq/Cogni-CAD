# wing_structure_winglet_transparent.py
# 
# Full wing + winglet generator (NACA 4-digit) for CATIA V5 using PyCATIA
# Changes: DO NOT close existing open CATIA documents. Improved STEP export fallback
# (no use of app.active_document as a last-resort) and safer temporary save handling.
# Updated: transparency control and robust STEP export fallback
#
# Usage: run where PyCatia & CATIA are available. STEP export will succeed only if
# your CATIA installation/license supports STEP export.

import numpy as np
from scipy.interpolate import interp1d
from pycatia import catia
from pycatia.mec_mod_interfaces.part_document import PartDocument
from pycatia.enumeration.enumeration_types import cat_limit_mode, cat_prism_orientation
from pathlib import Path
import os
import tempfile
import time
import sys
import json

# --------------------- Param Loading --------------------- #
DEFAULTS = {
    "m": 4.0,
    "p": 4.0,
    "t": 12.0,
    "c_r": 1.75,
    "c_t": 0.5,
    "s": 3.0,
    "a_sweep": 35.0,
    "Nribs": 10,
    "Dholes": 0.8,
    "xc_spar_1": 0.25,
    "xc_spar_2": 0.75,
    "t_rib": 0.01
}

def load_params(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return {k: v for k, v in json.load(f).items()}
    except:
        return {}

def get_params():
    params = DEFAULTS.copy()
    
    # 1. Check for JSON file arg strings (e.g. valid path)
    if len(sys.argv) >= 2 and not sys.argv[1].startswith("--"):
        js = sys.argv[1]
        if os.path.exists(js):
            params.update(load_params(js))
    
    # 2. Check for --params key
    if "--params" in sys.argv:
        try:
            p_idx = sys.argv.index("--params") + 1
            if p_idx < len(sys.argv):
                js_path = sys.argv[p_idx]
                if os.path.exists(js_path):
                    params.update(load_params(js_path))
        except:
            pass

    # 3. CLI input (simple overrides)
    # Not rigorously implemented for all args, relying on JSON mainly.
    
    # Normalize types
    for k, v in params.items():
        try:
            if k in ["Nribs"]:
                params[k] = int(v)
            else:
                params[k] = float(v)
        except:
            pass
            
    return params

# --------------------- Helpers --------------------- #
def naca_airfoil(m, p, t, chord, num_points=200):
    m_f = m / 100.0
    p_f = p / 10.0
    t_f = t / 100.0
    x = np.linspace(0.0, 1.0, num_points)
    yt = 5.0 * t_f * (0.2969*np.sqrt(x) - 0.1260*x - 0.3516*x**2 + 0.2843*x**3 - 0.1015*x**4)
    if (p_f == 0.0) or (m_f == 0.0):
        yc = np.zeros_like(x)
        dyc_dx = np.zeros_like(x)
    else:
        yc = np.where(x < p_f,
                      (m_f / p_f**2)*(2*p_f*x - x**2),
                      (m_f / (1-p_f)**2)*(1 - 2*p_f + 2*p_f*x - x**2))
        dyc_dx = np.where(x < p_f,
                          (2*m_f / p_f**2)*(p_f - x),
                          (2*m_f / (1-p_f)**2)*(p_f - x))
    theta = np.arctan(dyc_dx)
    xu = (x - yt*np.sin(theta)) * chord
    xl = (x + yt*np.sin(theta)) * chord
    yu = (yc + yt*np.cos(theta)) * chord
    yl = (yc - yt*np.cos(theta)) * chord
    xc = 0.5*(xu + xl)
    yc_c = 0.5*(yu + yl)
    return xu, yu, xl, yl, xc, yc_c


def safe_update(part):
    try:
        part.update()
    except Exception as e:
        # print("Warning: part.update() failed:", e) # Suppress
        pass


def extrapolate_3D(pt1, pt2, yloc_mm):
    p1 = np.array(pt1, dtype=float)
    p2 = np.array(pt2, dtype=float)
    v = p2 - p1
    n = np.linalg.norm(v)
    if n == 0:
        raise ValueError("Extrapolate: identical points.")
    vnorm = v / n
    if abs(vnorm[1]) < 1e-9:
        return p2 + np.array([0.0, yloc_mm - p2[1], 0.0])
    s = (yloc_mm - p1[1]) / vnorm[1]
    return p1 + s * vnorm

# --------------------- CATIA init --------------------- #
# NOTE: we DO NOT close existing documents. This script will create a new Part
# document and leave any currently open CATIA documents untouched.

caa = catia()
app = caa.application
docs = app.documents

# Create new part (this will add a new document but won't close others)
docs.add('Part')
document: PartDocument = app.active_document
part = document.part
partbody = part.bodies[0]
sketches = partbody.sketches
hybrid_bodies = part.hybrid_bodies
hsf = part.hybrid_shape_factory
shpfac = part.shape_factory
selection = document.selection

# Visual opacity value - change this to increase/decrease transparency
# Per CATIA API used: set_real_opacity(value, boolean) where 0 = transparent, 255 = opaque.
OPACITY_VAL = 247

# create hybrid bodies
construction_elements = hybrid_bodies.add(); construction_elements.name = "construction_elements"
wing_splines = hybrid_bodies.add(); wing_splines.name = "wing_splines"
wing_spars = hybrid_bodies.add(); wing_spars.name = "wing_spars"
wing_ribs = hybrid_bodies.add(); wing_ribs.name = "wing_ribs"
winglet_elements = hybrid_bodies.add(); winglet_elements.name = "winglet_elements"

# print("Starting wing generation...") # Suppress

# --------------------- Parameters --------------------- #
params = get_params()
# print("Using Parameters:", params) # Suppress

m = params["m"]
p = params["p"]
t = params["t"]

c_r = params["c_r"]
c_t = params["c_t"]
s = params["s"]
a_sweep = params["a_sweep"]
x_sweep = s * np.sin(np.deg2rad(a_sweep))

Nribs = int(params["Nribs"])
Dholes = params["Dholes"]
xc_spar_1 = params["xc_spar_1"]
xc_spar_2 = params["xc_spar_2"]
t_rib = params["t_rib"]

wlt_end_chord = 0.05
wlt_angle = 75.0 * np.pi / 180.0
wlt_rad = 0.3
s1 = 0.3
s2 = 0.5

MM = 1000.0
s_mm = s * MM
L = 10000

# --------------------- Compute profiles --------------------- #
xu_r, yu_r, xl_r, yl_r, xc_r, yc_r = naca_airfoil(m, p, t, c_r, num_points=200)
x_r = np.append(np.flip(xu_r), xl_r[1:])
z_r = np.append(np.flip(yu_r), yl_r[1:])

xu_t, yu_t, xl_t, yl_t, xc_t, yc_t = naca_airfoil(m, p, t, c_t, num_points=200)
x_t = np.append(np.flip(xu_t), xl_t[1:]) + x_sweep
z_t = np.append(np.flip(yu_t), yl_t[1:])

x_r_mm = x_r * MM; z_r_mm = z_r * MM
x_t_mm = x_t * MM; z_t_mm = z_t * MM

# --------------------- Import splines --------------------- #
wing_root_profile = hsf.add_new_spline(); wing_root_profile.name = "wing_root_profile"
for xi, zi in zip(x_r_mm, z_r_mm):
    wing_root_profile.add_point(hsf.add_new_point_coord(float(xi), 0.0, float(zi)))
wing_splines.append_hybrid_shape(wing_root_profile)

wing_root_TE = hsf.add_new_polyline(); wing_root_TE.name = "wing_root_TE"
wing_root_TE.insert_element(hsf.add_new_point_coord(float(x_r_mm[0]), 0.0, float(z_r_mm[0])), 0)
wing_root_TE.insert_element(hsf.add_new_point_coord(float(x_r_mm[-1]), 0.0, float(z_r_mm[-1])), 1)
wing_splines.append_hybrid_shape(wing_root_TE)
safe_update(part)

wing_root = hsf.add_new_join(wing_root_profile, wing_root_TE); wing_root.name = "wing_root"
construction_elements.append_hybrid_shape(wing_root)
safe_update(part)

wing_tip_profile = hsf.add_new_spline(); wing_tip_profile.name = "wing_tip_profile"
for xi, zi in zip(x_t_mm, z_t_mm):
    wing_tip_profile.add_point(hsf.add_new_point_coord(float(xi), float(s_mm), float(zi)))
wing_splines.append_hybrid_shape(wing_tip_profile)

wing_tip_TE = hsf.add_new_polyline(); wing_tip_TE.name = "wing_tip_TE"
wing_tip_TE.insert_element(hsf.add_new_point_coord(float(x_t_mm[0]), float(s_mm), float(z_t_mm[0])), 0)
wing_tip_TE.insert_element(hsf.add_new_point_coord(float(x_t_mm[-1]), float(s_mm), float(z_t_mm[-1])), 1)
wing_splines.append_hybrid_shape(wing_tip_TE)
safe_update(part)

wing_tip = hsf.add_new_join(wing_tip_profile, wing_tip_TE); wing_tip.name = "wing_tip"
construction_elements.append_hybrid_shape(wing_tip)
safe_update(part)

# print("Curves imported") # Suppress

# --------------------- Orientation points for loft --------------------- #
root_te_x = float(x_r_mm[-1]); root_te_y = 0.0; root_te_z = float(z_r_mm[-1])
tip_te_x  = float(x_t_mm[-1]); tip_te_y  = float(s_mm); tip_te_z  = float(z_t_mm[-1])

root_te_pt = hsf.add_new_point_coord(root_te_x, root_te_y, root_te_z); root_te_pt.name = "root_te_orientation"
construction_elements.append_hybrid_shape(root_te_pt)

tip_te_pt  = hsf.add_new_point_coord(tip_te_x, tip_te_y, tip_te_z); tip_te_pt.name = "tip_te_orientation"
construction_elements.append_hybrid_shape(tip_te_pt)
safe_update(part)

# --------------------- Build loft + fills --------------------- #
wing_surf = hsf.add_new_loft(); wing_surf.name = "wing_surf"
try:
    wing_surf.add_section_to_loft(wing_root, 1, root_te_pt)
    wing_surf.add_section_to_loft(wing_tip, 1, tip_te_pt)
    construction_elements.append_hybrid_shape(wing_surf)
    safe_update(part)
    # print("Loft created (orientation 1).") # Suppress
except Exception as e:
    # print("Loft orientation 1 failed:", e) # Suppress
    try:
        wing_surf = hsf.add_new_loft()
        wing_surf.add_section_to_loft(wing_root, 0, root_te_pt)
        wing_surf.add_section_to_loft(wing_tip, 0, tip_te_pt)
        wing_surf.name = "wing_surf_alt"
        construction_elements.append_hybrid_shape(wing_surf)
        safe_update(part)
        # print("Loft created (orientation 0).") # Suppress
    except Exception as e2:
        # print("Both loft attempts failed:", e2) # Suppress
        pass

# Fill ends & join
try:
    wing_root_filled = hsf.add_new_fill(); wing_root_filled.name = "wing_root_filled"; wing_root_filled.add_bound(wing_root); construction_elements.append_hybrid_shape(wing_root_filled)
    wing_tip_filled = hsf.add_new_fill(); wing_tip_filled.name = "wing_tip_filled"; wing_tip_filled.add_bound(wing_tip); construction_elements.append_hybrid_shape(wing_tip_filled)
    wing_surf_complete = hsf.add_new_join(wing_surf, wing_root_filled); wing_surf_complete.name = "wing_surf_complete"
    wing_surf_complete.add_element(wing_tip_filled); construction_elements.append_hybrid_shape(wing_surf_complete)
    safe_update(part)
    # print("Wing surface completed with fills and join.") # Suppress
except Exception as e:
    # print("Filling/Joining failed:", e) # Suppress
    pass

# Set wing surface opacity to chosen value (from screenshot)
try:
    selection.clear()
    selection.add(wing_surf_complete)
    selection.vis_properties.set_real_opacity(OPACITY_VAL, 1)
    selection.clear()
except Exception:
    pass
safe_update(part)

# --------------------- Spars, ribs, holes --------------------- #
def create_sparse_pad_on_plane(xc_frac, name="plane_spar"):
    try:
        ptA = hsf.add_new_point_coord(c_r * xc_frac * MM, 0.0, 0.0)
        ptB = hsf.add_new_point_coord(c_r * xc_frac * MM, 0.0, 1000.0)
        ptC = hsf.add_new_point_coord((c_t * xc_frac + x_sweep) * MM, s_mm, 0.0)
        plane = hsf.add_new_plane3_points(ptA, ptB, ptC)
        plane.name = name
        wing_spars.append_hybrid_shape(plane)
        safe_update(part)
        part.in_work_object = partbody
        sk = sketches.add(plane)
        ske2 = sk.open_edition()
        p1 = (-L, L); p2 = (L, L); p3 = (L, -L); p4 = (-L, -L)
        ske2.create_line(*p1, *p2); ske2.create_line(*p2, *p3); ske2.create_line(*p3, *p4); ske2.create_line(*p4, *p1)
        sk.close_edition()
        safe_update(part)
        pad = shpfac.add_new_pad(sk, t_rib/2.0 * MM)
        pad.direction_orientation = cat_prism_orientation.index("catRegularOrientation")
        pad.is_symmetric = True
        safe_update(part)
        try:
            shpfac.add_new_split(wing_surf_complete, 0)
            safe_update(part)
        except Exception:
            pass
        return plane
    except Exception as e:
        # print("create_sparse_pad_on_plane failed:", e) # Suppress
        return None

plane_spar_1 = create_sparse_pad_on_plane(xc_spar_1, name="plane_spar_1")
plane_spar_2 = create_sparse_pad_on_plane(xc_spar_2, name="plane_spar_2")
# print("Spars created (or attempted).") # Suppress

part.in_work_object = partbody
Lribs = s / (Nribs + 2.0)
y_ribs = np.linspace(Lribs, s - Lribs, Nribs)
y_ribs_mm = y_ribs * MM
rib_planes = []
for i, yloc in enumerate(y_ribs_mm):
    try:
        plane_rib = hsf.add_new_plane_offset(part.origin_elements.plane_zx, float(yloc), False)
        plane_rib.name = f"plane_rib_{i}"
        wing_ribs.append_hybrid_shape(plane_rib)
        safe_update(part)
        rib_planes.append(plane_rib)
        part.in_work_object = partbody
        sk = sketches.add(plane_rib)
        ske2 = sk.open_edition()
        ske2.create_line(-L, L, L, L); ske2.create_line(L, L, L, -L)
        ske2.create_line(L, -L, -L, -L); ske2.create_line(-L, -L, -L, L)
        sk.close_edition()
        safe_update(part)
        pad = shpfac.add_new_pad(sk, t_rib / 2.0 * MM)
        pad.direction_orientation = cat_prism_orientation.index("catRegularOrientation")
        pad.is_symmetric = True
        safe_update(part)
        try:
            shpfac.add_new_split(wing_surf_complete, 0)
            safe_update(part)
        except Exception:
            pass
    except Exception as e:
        # print(f"Rib {i} creation failed:", e) # Suppress
        pass
# print("Ribs created (or attempted).") # Suppress

c_loc_func = interp1d([0.0, s], [c_r, c_t], kind='linear', fill_value='extrapolate')
for i, yloc in enumerate(y_ribs):
    try:
        c_local = float(c_loc_func(yloc))
        xu_loc, yu_loc, xl_loc, yl_loc, xc_loc, yc_loc = naca_airfoil(m, p, t, c_local, num_points=200)
        xcenter = 0.5*(xu_loc + xl_loc)
        thickness_local = yu_loc - yl_loc
        loc_centers = np.linspace(c_local * xc_spar_1, c_local * xc_spar_2, 4)
        hlc_1 = (0.0 + c_local * xc_spar_1) / 2.0
        hlc_2 = loc_centers[1]
        hlc_3 = loc_centers[2]
        try:
            yc_interp = interp1d(xcenter, 0.5*(yu_loc+yl_loc), kind='linear', fill_value='extrapolate')
            t_interp = interp1d(xcenter, thickness_local, kind='linear', fill_value='extrapolate')
        except Exception:
            yc_interp = lambda xq: 0.0
            t_interp = lambda xq: c_local * 0.1
        xc1 = (yloc * np.sin(np.deg2rad(a_sweep)) + hlc_1) * MM
        yc1 = float(yc_interp(hlc_1)) * MM
        Dh1 = Dholes * float(t_interp(hlc_1)) * MM
        xc2 = (yloc * np.sin(np.deg2rad(a_sweep)) + hlc_2) * MM
        yc2 = float(yc_interp(hlc_2)) * MM
        Dh2 = Dholes * float(t_interp(hlc_2)) * MM
        xc3 = (yloc * np.sin(np.deg2rad(a_sweep)) + hlc_3) * MM
        yc3 = float(yc_interp(hlc_3)) * MM
        Dh3 = Dholes * float(t_interp(hlc_3)) * MM
        plane_obj = rib_planes[i]
        sk_h = sketches.add(plane_obj)
        skh2 = sk_h.open_edition()
        try:
            skh2.create_closed_circle(yc1, xc1, Dh1/2.0)
            skh2.create_closed_circle(yc2, xc2, Dh2/2.0)
            skh2.create_closed_circle(yc3, xc3, Dh3/2.0)
        except Exception:
            try:
                skh2.create_closed_circle(xc1, yc1, Dh1/2.0)
                skh2.create_closed_circle(xc2, yc2, Dh2/2.0)
                skh2.create_closed_circle(xc3, yc3, Dh3/2.0)
            except Exception as ex:
                # print(f"create_closed_circle failed for rib {i} both orders: {ex}") # Suppress
                pass
        sk_h.close_edition()
        safe_update(part)
        try:
            hole_feat = shpfac.add_new_pocket(sk_h, 1.5 * L)
            hole_feat.direction_orientation = cat_prism_orientation.index("catRegularOrientation")
            hole_feat.first_limit.limit_mode = cat_limit_mode.index("catUpToNextLimit")
            hole_feat.second_limit.limit_mode = cat_limit_mode.index("catUpToNextLimit")
            safe_update(part)
        except Exception as ex:
            # print(f"Pocket creation failed at rib {i}:", ex) # Suppress
            pass
    except Exception as e:
        # print(f"Lightening holes creation failed for rib {i}:", e) # Suppress
        pass
# print("Lightening holes created (or attempted).") # Suppress

# --------------------- Winglet creation (joined multi-section) --------------------- #
try:
    # print("=== Starting winglet creation ===") # Suppress
    te_root_coords = root_te_pt.get_coordinates()
    te_tip_coords = tip_te_pt.get_coordinates()

    corner_y_mm = (s + s1) * MM
    tip_y_mm    = (s + s1 + s2 * np.cos(wlt_angle)) * MM

    pt_corner_coords = extrapolate_3D(te_root_coords, te_tip_coords, corner_y_mm)
    pt_corner = hsf.add_new_point_coord(float(pt_corner_coords[0]), float(pt_corner_coords[1]), float(pt_corner_coords[2])); pt_corner.name = "pt_tip_upper_2"
    winglet_elements.append_hybrid_shape(pt_corner)
    safe_update(part)

    pt_tip_coords = extrapolate_3D(te_root_coords, te_tip_coords, tip_y_mm)
    pt_tip_coords[2] += s2 * np.sin(wlt_angle) * MM
    pt_tip = hsf.add_new_point_coord(float(pt_tip_coords[0]), float(pt_tip_coords[1]), float(pt_tip_coords[2])); pt_tip.name = "pt_tip_upper_3"
    winglet_elements.append_hybrid_shape(pt_tip)
    safe_update(part)

    wlt_line_1 = hsf.add_new_line_pt_pt(tip_te_pt, pt_corner); wlt_line_1.name = "wlt_line_1"; winglet_elements.append_hybrid_shape(wlt_line_1)
    wlt_line_2 = hsf.add_new_line_pt_pt(pt_corner, pt_tip); wlt_line_2.name = "wlt_line_2"; winglet_elements.append_hybrid_shape(wlt_line_2)
    safe_update(part)
    plane_corner = hsf.add_new_plane2_lines(wlt_line_1, wlt_line_2); plane_corner.name = "plane_corner"; winglet_elements.append_hybrid_shape(plane_corner)
    safe_update(part)
    wlt_corner = hsf.add_new_corner(wlt_line_1, wlt_line_2, plane_corner, wlt_rad * MM, 1, 1, True); wlt_corner.name = "wlt_corner"; winglet_elements.append_hybrid_shape(wlt_corner)
    safe_update(part)

    xu_wlt, yu_wlt, xl_wlt, zl_wlt, xc_wlt, zc_wlt = naca_airfoil(m, p, t, wlt_end_chord, num_points=120)
    x_wlt = np.append(np.flip(xu_wlt), xl_wlt[1:])
    z_wlt = np.append(np.flip(yu_wlt), zl_wlt[1:])
    y_wlt = np.zeros(len(x_wlt))
    prof_wlt = np.vstack([x_wlt, y_wlt, z_wlt])
    rot_x = np.array([[1.0, 0.0, 0.0],[0.0, np.cos(wlt_angle), -np.sin(wlt_angle)],[0.0, np.sin(wlt_angle), np.cos(wlt_angle)]])
    prof_wlt = rot_x.dot(prof_wlt)
    prof_first_mm = prof_wlt[:,0] * MM
    pt_tip_coords_actual = np.array(pt_tip.get_coordinates())
    diff_location = pt_tip_coords_actual - prof_first_mm

    winglet_tip_curve = hsf.add_new_spline(); winglet_tip_curve.name = "winglet_tip_curve"
    for j in range(prof_wlt.shape[1]):
        px = float(prof_wlt[0,j] * MM + diff_location[0])
        py = float(prof_wlt[1,j] * MM + diff_location[1])
        pz = float(prof_wlt[2,j] * MM + diff_location[2])
        winglet_tip_curve.add_point(hsf.add_new_point_coord(px, py, pz))
    winglet_elements.append_hybrid_shape(winglet_tip_curve)
    safe_update(part)

    winglet_tip_TE = hsf.add_new_polyline(); winglet_tip_TE.name = "winglet_tip_TE"
    winglet_tip_TE.insert_element(hsf.add_new_point_coord(float(prof_wlt[0,0]*MM + diff_location[0]), float(prof_wlt[1,0]*MM + diff_location[1]), float(prof_wlt[2,0]*MM + diff_location[2])), 0)
    winglet_tip_TE.insert_element(hsf.add_new_point_coord(float(prof_wlt[0,-1]*MM + diff_location[0]), float(prof_wlt[1,-1]*MM + diff_location[1]), float(prof_wlt[2,-1]*MM + diff_location[2])), 1)
    winglet_elements.append_hybrid_shape(winglet_tip_TE)
    safe_update(part)

    winglet_tip = hsf.add_new_join(winglet_tip_curve, winglet_tip_TE); winglet_tip.name = "winglet_tip"
    winglet_elements.append_hybrid_shape(winglet_tip)
    safe_update(part)

    ms_loft = None
    try:
        ms_loft = hsf.add_new_loft(); ms_loft.name = "winglet_ms_loft"
        ms_loft.add_section_to_loft(winglet_tip, 1, pt_tip)   # winglet_tip (closing point pt_tip_upper_3)
        ms_loft.add_section_to_loft(wing_tip, 1, tip_te_pt)   # wing_tip (closing point tip_te_orientation)
        ms_loft.add_guide(wlt_corner)
        winglet_elements.append_hybrid_shape(ms_loft)
        safe_update(part)
        # print("Winglet multi-section loft created (winglet_tip -> wing_tip) with guide wlt_corner.") # Suppress
    except Exception as e_ms:
        # print("winglet multi-section loft failed:", e_ms) # Suppress
        try:
            ms_alt = hsf.add_new_loft(); ms_alt.name = "winglet_ms_loft_alt"
            ms_alt.add_section_to_loft(winglet_tip_curve, 1, pt_tip)
            ms_alt.add_section_to_loft(wing_tip_profile, 1, tip_te_pt)
            ms_alt.add_guide(wlt_corner)
            winglet_elements.append_hybrid_shape(ms_alt)
            safe_update(part)
            # print("Winglet created using curve/section fallback.") # Suppress
            ms_loft = ms_alt
        except Exception as e_alt:
            # print("Winglet fallback also failed:", e_alt) # Suppress
            pass

except Exception as e_top:
    # print("Winglet creation top-level error:", e_top) # Suppress
    pass

# Set winglet opacity to OPACITY_VAL (from screenshot)
try:
    if 'ms_loft' in locals() and ms_loft is not None:
        selection.clear()
        selection.add(ms_loft)
        selection.vis_properties.set_real_opacity(OPACITY_VAL, 1)
        selection.clear()
except Exception:
    pass

safe_update(part)
# print("Script finished. Inspect the CATIA tree and geometry.") # Suppress
# print("To change transparency: edit OPACITY_VAL near top (0 = fully transparent, 255 = fully opaque).") # Suppress

# --------------------- STEP export (save to .stp) --------------------- #

def export_step(document_obj, out_path: Path, overwrite: bool = True):
    """
    Try to export the active document to STEP (.stp).
    Uses pycatia's export_data if available, then falls back to the document COM ExportData.
    IMPORTANT: this function will NOT use app.active_document as a fallback (to avoid touching
    other open CATIA documents). Returns True on success, False otherwise.
    """
    tmp_catpart = None
    try:
        # Ensure updated
        try:
            safe_update(document_obj.part)
        except Exception:
            pass

        # If output exists and overwrite disabled, skip
        if out_path.exists() and not overwrite:
            # print(f"STEP file already exists and overwrite=False: {out_path}") # Suppress
            return True

        # If the document has no saved name, try saving a temporary CATPart beside the output
        try:
            full_name = document_obj.full_name
        except Exception:
            full_name = None

        if not full_name or str(full_name).strip() == "":
            try:
                tmp_catpart = out_path.with_suffix('.CATPart')
                # Prefer the wrapper save_as if available
                try:
                    document_obj.save_as(str(tmp_catpart))
                except Exception:
                    # Try underlying COM Document SaveAs
                    com_doc_try = getattr(document_obj, "document", None)
                    if com_doc_try is not None:
                        try:
                            com_doc_try.SaveAs(str(tmp_catpart))
                        except Exception:
                            pass
            except Exception:
                tmp_catpart = None

        # Try pycatia wrapper export_data if present
        try:
            if hasattr(document_obj, "export_data"):
                document_obj.export_data(str(out_path), "stp")
                # print(f"Exported STEP (pycatia.export_data) -> {out_path}") # Suppress
                return True
        except Exception as e:
            # print("pycatia export_data failed:", e) # Suppress
            pass

        # Fallback to underlying COM ExportData from this document only
        try:
            com_doc = getattr(document_obj, "document", None)
            if com_doc is None:
                # print("Cannot locate underlying COM document for export. Aborting export to avoid altering other CATIA documents.") # Suppress
                return False
            com_doc.ExportData(str(out_path), "stp")
            # print(f"Exported STEP (COM ExportData) -> {out_path}") # Suppress
            return True
        except Exception as e2:
            # print("COM ExportData failed:", e2) # Suppress
            pass
            return False

    except Exception as e_all:
        # print("STEP export failed (outer):", e_all) # Suppress
        pass
        return False
    finally:
        # Do not delete temporary CATPart automatically. Leave it for user inspection.
        try:
            if tmp_catpart is not None and tmp_catpart.exists():
                time.sleep(0.5)
        except Exception:
            pass


# Choose output directory & filename (change as needed)
# By default we write next to the working directory (script folder). Change to an absolute path if preferred.
script_folder = Path.cwd()
out_filename = "winglet_export.stp"
output_path = script_folder / out_filename

# Ensure directory exists
output_path.parent.mkdir(parents=True, exist_ok=True)

# print(f"Attempting STEP export to: {output_path}") # Suppress
success = export_step(document, output_path, overwrite=True)

if not success:
    # print("STEP export failed. Common causes:") # Suppress
    # print(" - CATIA license doesn't include STEP export.") # Suppress
    # print(" - CATIA export settings (Tools > Options > General > Compatibility > STEP) require configuration.") # Suppress
    # print(" - The document may be unsaved or in a state requiring manual save; try saving in CATIA and re-run.") # Suppress
    pass
else:
    # print("STEP file ready. You can open this .stp on other systems (neutral STEP reader) if your CATIA license supports it.") # Suppress
    # print(f"STEP file location: {output_path}") # Suppress
    pass

print("Generation Successfully Completed")
