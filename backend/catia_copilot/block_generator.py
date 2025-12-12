import json
import tempfile
import re
import os
from pathlib import Path
from typing import List, Tuple, Optional, Dict, Any

from catia_copilot.block_parser import (
    normalize, _normalize_short, extract_disk_diameter, extract_thickness,
    extract_global_square_side, extract_hole_positions, extract_global_hole_diameter,
    extract_integer_after_keywords, extract_value_for_keyword, extract_circle_diameter_or_radius,
    extract_cylinder_values, extract_plate_LWT, extract_hole_count_for_circular,
    extract_hole_diameter_for_circular, extract_block_holes,
    extract_L, extract_length, extract_square, extract_diameter, extract_circle_radius, extract_curve_points
)

# Constants (Must match main.py context if needed, or pass in)
# We assume BASE_DIR is available or passed. For now, we use os.getcwd() or similar if needed,
# but ideally pure logic here.

def _get_float_regex(text: str, patterns: List[str]) -> Optional[float]:
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            try: return float(m.group(1))
            except: pass
    return None

def build_square_flags_from_text(text: str) -> List[str]:
    flags: List[str] = []
    dia = extract_disk_diameter(text)
    if dia is not None: flags += ["--diameter", str(dia)]
    T = extract_thickness(text)
    if T is not None: flags += ["--T", str(T)]
    global_val = extract_global_square_side(text)
    holes = extract_hole_positions(text)
    for x, y, d in holes:
        d_val = d if d is not None else global_val
        if d_val is None:
            flags.append(f"--hole={x},{y},-1")
        else:
            flags.append(f"--hole={x},{y},{d_val}")
    flags += ["--cmd", normalize(text)]
    flags += ["--detected=square"]
    return flags

def build_square_flags_from_array(diameter: float, thickness: float, holes: List[Tuple[float, float, float]]) -> List[str]:
    flags: List[str] = []
    flags += ["--diameter", str(diameter)]
    flags += ["--T", str(thickness)]
    for x, y, side in holes:
        flags.append(f"--hole={x},{y},{side}")
    flags += ["--cmd", "json-input"]
    flags += ["--detected=square"]
    return flags

def build_disk_flags(text: str) -> List[str]:
    flags: List[str] = []
    dia = extract_disk_diameter(text)
    if dia is not None: flags += ["--diameter", str(dia)]
    T = extract_thickness(text)
    if T is not None: flags += ["--T", str(T)]
    
    holes = extract_hole_positions(text)
    # Filter out potential duplicates or invalid parse results if needed,
    # but block_parser's extract_hole_positions does a decent job.
    # We need to handle holes specified without diameter if a global hole diameter is present.
    global_dia = extract_global_hole_diameter(text)
    
    # NEW: Extract topology parameters (n, offset) for diagonal/perimeter scripts
    n = extract_integer_after_keywords(text, ["n", "holes", "count", "count:"])
    if n is not None: flags += ["--n", str(n)]
    
    offset = extract_value_for_keyword(text, ["offset", "inset", "inward"])
    if offset is not None: flags += ["--offset", str(offset)]
    
    if global_dia is not None: flags += ["--dia", str(global_dia)]

    for x, y, d in holes:
        d_val = d if d is not None else global_dia
        if d_val is  None:
             # Default fallback if absolutely no diameter found? 
             # Or maybe skip? Let's use 10.0 as a safe fallback or let script fail/warn.
             # Better to output what we have.
             d_val = 10.0 
        flags.append(f"--hole={x},{y},{d_val}")
        
    flags += ["--cmd", normalize(text)]
    return flags

def build_topology_flags(text: str, topology_type: str, context: str = "disk") -> List[str]:
    # context can be "disk" or "plate"
    flags: List[str] = []
    norm = normalize(text)
    
    # Extract L/W/T for plate-based topologies
    if context == "plate" or "block" in norm or "plate" in norm:
        from catia_copilot.block_parser import extract_plate_LWT
        lwt = extract_plate_LWT(text)
        if lwt:
            flags += ["--L", str(lwt[0]), "--W", str(lwt[1]), "--T", str(lwt[2])]

    dia = extract_disk_diameter(text)
    if dia is not None: flags += ["--diameter", str(dia)]
    T = extract_thickness(text)
    # Avoid duplicate T if already set by LWT
    if T is not None and "--T" not in flags: flags += ["--T", str(T)]
    global_dia = extract_global_hole_diameter(text)
    n = extract_integer_after_keywords(text, ["n", "holes", "count", "count:"])
    if n is not None: flags += ["--n", str(n)]
    offset = extract_value_for_keyword(text, ["offset", "inset", "inward"])
    if offset is not None: flags += ["--offset", str(offset)]
    spacing = extract_value_for_keyword(text, ["spacing", "pitch"])
    if spacing is not None: flags += ["--spacing", str(spacing)]
    orientation = None
    if re.search(r"\balong\s+x\b|\balong\s+length\b|\balong\s+x-?axis\b|horizontal", norm): orientation = "x"
    if re.search(r"\balong\s+y\b|\balong\s+width\b|\balong\s+y-?axis\b|vertical", norm): orientation = "y"
    if orientation: flags += ["--orientation", orientation]
    if any(k in norm for k in ("midpoint", "center", "centre", "middle")): flags += ["--midpoint", "1"]
    circle_d = extract_value_for_keyword(text, ["circle diameter", "circle_dia", "hole circle"])
    if circle_d is not None: flags += ["--circle_dia", str(circle_d)]
    else:
        radius = extract_value_for_keyword(text, ["radius", "hole radius"])
        if radius is not None: flags += ["--radius", str(radius)]
    if global_dia is not None: flags += ["--dia", str(global_dia)]
    start_angle = extract_value_for_keyword(text, ["start_angle", "start angle", "start"])
    if start_angle is not None: flags += ["--start_angle", str(start_angle)]
    
    # Explicitly set mode flags based on topology_type requested by router
    if topology_type == "diagonal":
        flags += ["--diagonal", "1"]
    elif topology_type == "perimeter":
        flags += ["--perimeter", "1"]
        
    return flags

def build_coord_flags(text: str) -> List[str]:
    flags: List[str] = []
    dia = extract_disk_diameter(text)
    if dia is not None: flags += ["--diameter", str(dia)]
    T = extract_thickness(text)
    if T is not None: flags += ["--T", str(T)]
    global_dia = extract_global_hole_diameter(text)
    holes = extract_hole_positions(text)
    for x, y, d in holes:
        dval = d if d is not None else (global_dia if global_dia is not None else -1)
        flags += [f"--hole={x},{y},{dval}"]
    flags += ["--cmd", normalize(text)]
    return flags

def build_cylinder_flags(text: str) -> List[str]:
    flags: List[str] = []
    dia, h = extract_cylinder_values(text)
    if dia is not None: flags += ["--diameter", str(dia)]
    if h is not None: flags += ["--height", str(h)]
    flags += ["--cmd", normalize(text)]
    return flags

def build_flags_for_plate(text: str, topology: str) -> List[str]:
    flags: List[str] = []
    s = normalize(text)
    plate_vals = extract_plate_LWT(text)
    if isinstance(plate_vals, tuple):
        L, W, T = plate_vals
        if L is not None: flags += ["--L", str(L)]
        if W is not None: flags += ["--W", str(W)]
        if T is not None: flags += ["--T", str(T)]
    n = extract_integer_after_keywords(text, ["n", "holes", "count", "count:"])
    if n is not None: flags += ["--n", str(n)]
    offset = extract_value_for_keyword(text, ["offset", "inset", "inward"])
    if offset is not None: flags += ["--offset", str(offset)]
    spacing = extract_value_for_keyword(text, ["spacing", "pitch"])
    if spacing is not None: flags += ["--spacing", str(spacing)]
    orientation = None
    if re.search(r"\balong\s+x\b|\balong\s+length\b|\balong\s+x-?axis\b|horizontal", s): orientation = "x"
    if re.search(r"\balong\s+y\b|\balong\s+width\b|\balong\s+y-?axis\b|vertical", s): orientation = "y"
    if orientation: flags += ["--orientation", orientation]
    if any(k in s for k in ("midpoint", "center", "centre", "middle")): flags += ["--midpoint", "1"]
    global_dia = extract_global_hole_diameter(text)
    if global_dia is not None:
        flags += ["--dia", str(global_dia)]
    
    # Try more robust extraction for circle diameter
    circle_d = extract_circle_diameter_or_radius(text)
    if circle_d is not None:
         flags += ["--diameter", str(circle_d)]
    else:
        # Fallback to keyword
        circle_d = extract_value_for_keyword(text, ["circle diameter", "circle_dia", "hole circle"])
        if circle_d is not None:
             flags += ["--circle_dia", str(circle_d)]
        else:
             radius = extract_value_for_keyword(text, ["radius", "hole radius"])
             if radius is not None:
                 flags += ["--radius", str(radius)]
    start_angle = extract_value_for_keyword(text, ["start_angle", "start angle", "start"])
    if start_angle is not None:
        flags += ["--start_angle", str(start_angle)]
    flags += ["--cmd", normalize(text)]
    return flags

def build_flags_for_circular(text: str):
    s = normalize(text)
    flags: List[str] = []
    plate = extract_plate_LWT(s)
    if isinstance(plate, tuple) and len(plate) == 3:
        L, W, T = plate
        if L is not None: flags += ["--L", str(L)]
        if W is not None: flags += ["--W", str(W)]
        if T is not None: flags += ["--T", str(T)]
    hole_dia = extract_hole_diameter_for_circular(s)
    if hole_dia is not None: flags += ["--dia", str(hole_dia)]
    circle_dia = extract_circle_diameter_or_radius(s)
    if circle_dia is not None: flags += ["--diameter", str(circle_dia)]
    n = extract_hole_count_for_circular(s)
    if n is not None: flags += ["--n", str(n)]
    flags += ["--cmd", s]
    return flags

def build_block_flags(length: float, width: float, thickness: float,
                      holes: List[Tuple[float, float, float]]) -> List[str]:
    flags: List[str] = []
    flags += ["--length", str(length)]
    flags += ["--width", str(width)]
    flags += ["--thickness", str(thickness)]
    flags += ["--num_holes", str(len(holes))]
    for i, (x, y, d) in enumerate(holes, start=1):
        flags += [f"--hole_{i}_x", str(x)]
        flags += [f"--hole_{i}_y", str(y)]
        flags += [f"--hole_{i}_d", str(d)]
    return flags

def build_lbrac_flags(leg1: float, leg2: float,
                      extrude_len: float,
                      thick_top_offset: float,
                      bend_radius: Optional[float],
                      holes: List[Tuple[float, float, float]]) -> List[str]:
    flags: List[str] = []
    flags += ["--point1", "0,0,0"]
    flags += ["--point2", f"0,{float(leg1) if leg1 is not None else 0},0"]
    flags += ["--point3", f"0,{float(leg1) if leg1 is not None else 0},{float(leg2) if leg2 is not None else 0}"]
    flags += ["--extrude_len", str(float(extrude_len))]
    flags += ["--thick_top_offset", str(float(thick_top_offset))]
    if bend_radius is not None:
        flags += ["--poly_radius_value", str(float(bend_radius))]

    if not holes:
        flags += ["--circle1", "0,0,-1"]
        flags += ["--circle2", "0,0,-1"]
    else:
        if len(holes) >= 1:
            x1, y1, d1 = holes[0]
            r1 = float(d1) / 2.0 if d1 is not None else 0.0
            flags += ["--circle1", f"{float(x1)},{float(y1)},{r1}"]
        else:
            flags += ["--circle1", "0,0,-1"]
        if len(holes) >= 2:
            x2, y2, d2 = holes[1]
            r2 = float(d2) / 2.0 if d2 is not None else 0.0
            flags += ["--circle2", f"{float(x2)},{float(y2)},{r2}"]
        else:
            flags += ["--circle2", "0,0,-1"]

    if holes:
        pocket_depth_value = float(thick_top_offset)
        flags += ["--pocket_depth", str(pocket_depth_value)]
        flags += ["--pocket_firstlimit", str(pocket_depth_value)]
    else:
        flags += ["--pocket_depth", "0"]
        flags += ["--pocket_firstlimit", "0"]

    return flags

def build_flags_for_rib_slot(explicit: dict, text: str, base_dir: Path):
    s = _normalize_short(text)
    preview = {}

    for k in ("L", "square_size", "circle_radius", "length"):
        if explicit.get(k) is not None:
            try: preview[k] = float(explicit[k])
            except: preview[k] = explicit[k]

    if explicit.get("curve_points"):
        preview["curve_points"] = [
            [float(p[0]), float(p[1]), float(p[2])]
            for p in explicit["curve_points"]
        ]

    preview.setdefault("L", extract_L(s))
    preview.setdefault("length", extract_length(s))
    preview.setdefault("square_size", extract_square(s))

    dia = extract_diameter(s)
    if dia:
        preview["circle_radius"] = float(dia) / 2.0
    preview.setdefault("circle_radius", extract_circle_radius(s))
    preview.setdefault("curve_points", extract_curve_points(s))

    required = ["square_size", "circle_radius", "curve_points"]
    missing = [k for k in required if preview.get(k) is None]
    
    # Check L or Length
    if preview.get("L") is None and preview.get("length") is None:
        missing.append("L (or length)")
        
    if missing:
        return None, {"error": f"Missing rib-slot parameters: {missing}"}

    tf = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, dir=str(base_dir))
    tf.write(json.dumps(preview))
    tf.close()
    return ["--params", tf.name], preview

def build_flags_for_multipart(text: str, base_dir: Path):
    try:
        from catia_copilot.block_parser import extract_plate_LWT, extract_thickness, extract_cylinder_values, extract_combo
    except ImportError:
         print("WARNING: Could not import block_parser helpers. Using failover.")
         extract_plate_LWT = lambda x: None
         extract_thickness = lambda x: None
         extract_cylinder_values = lambda x: (None, None)
    
    # Need imports if using extract helpers not in block_parser
    # Assuming extract_plate etc are imported
    s = _normalize_short(text)
    
    width = None
    height = None
    pad = None
    
    # Try 3-dim LWT first
    lwt = extract_plate_LWT(s)
    if lwt:
        width, height, pad = lwt
    else:
        # Try 2-dim (WxH) + explicit thickness/pad
        # Using extract_combo from block_parser or local regex
        # We need to find "300x200"
        import re
        m = re.search(r"(\d+(?:\.\d+)?)\s*(?:x|×|by)\s*(\d+(?:\.\d+)?)", s)
        if m:
            width = float(m.group(1))
            height = float(m.group(2))
    
    # Override/Failback pad
    if not pad:
        pad = extract_thickness(s)
        if not pad:
            import re
            m_pad = re.search(r"(?:pad|thickness|thick|height|depth)\s*[:=]?\s*(\d+(?:\.\d+)?)", s)
            if m_pad:
                 pad = float(m_pad.group(1))

    cyl_r, cyl_h = extract_cylinder_values(s)
    if cyl_r:
        cyl_r = float(cyl_r)/2.0 # extract_cylinder_values usually returns diameter if keyword is diameter?
        # Wait, extract_cylinder_values checks "diameter X height Y".
        # Prompt: "cylinder radius 40" -> 40 IS radius.
        # extract_cylinder_values logic: captures radius if text says radius?
        # Let's check block_parser logic later. Assuming it works or we need manual.
        pass
    
    # Manual extraction for "cylinder radius 40" if helper failed
    if not cyl_r:
        m_rad = re.search(r"radius\s*(\d+(?:\.\d+)?)", s)
        if m_rad: cyl_r = float(m_rad.group(1))
        
    # Manual extraction for "diameter 60" (needed for optimization prompt: cylinder diameter 60)
    if not cyl_r:
        m_dia = re.search(r"diameter\s*(\d+(?:\.\d+)?)", s)
        if m_dia: cyl_r = float(m_dia.group(1)) / 2.0

    if not cyl_h:
        m_h = re.search(r"height\s*(\d+(?:\.\d+)?)", s)
        if m_h: cyl_h = float(m_h.group(1))

    # Fallback for "length 192 width 90" if extract_plate_LWT failed
    if width is None or height is None:
        m_len = re.search(r"(?:length|l)\s*[:=]?\s*(\d+(?:\.\d+)?)", s)
        if m_len: height = float(m_len.group(1)) # length usually mapped to Y/Height or X? 
        # In catia_create_parts_dynamic: WIDTH->X, HEIGHT->Y. 
        # Prompt: "length 192 width 90". Usually Length=X, Width=Y. 
        # But here variable names are width/height.
        # Let's map Length->Height variable (Y), Width->Width variable (X) to match block_parser conventions if that's what LWT does.
        # block_parser: L, W, T.
        # build_flags: width, height, pad = lwt ie. width=L, height=W (wait, check unpacking)
        # block_parser extract_plate_LWT returns (L, W, T).
        # build_flags line 318: width, height, pad = lwt
        # So width=L, height=W.
        # So Length matches Width variable?
        # Let's assume Length -> Width variable (L), Width -> Height variable (W).
        pass
         
    if width is None:
        m_l = re.search(r"(?:length|l)\s*[:=]?\s*(\d+(?:\.\d+)?)", s)
        if m_l: width = float(m_l.group(1))
        
    if height is None:
         m_w = re.search(r"(?:width|w)\s*[:=]?\s*(\d+(?:\.\d+)?)", s)
         if m_w: height = float(m_w.group(1))

    # Rectangular extraction
    rod_w = _get_float_regex(s, [r"(?:rect.*width|rod.*width|tube.*width)\s*[:=]?\s*(\d+(?:\.\d+)?)"])
    rod_d = _get_float_regex(s, [r"(?:rect.*depth|rod.*depth|tube.*depth)\s*[:=]?\s*(\d+(?:\.\d+)?)"])
    rod_h = _get_float_regex(s, [r"(?:rect.*height|rod.*height|tube.*height)\s*[:=]?\s*(\d+(?:\.\d+)?)"])
    wall  = _get_float_regex(s, [r"(?:wall|thickness.*wall)\s*[:=]?\s*(\d+(?:\.\d+)?)"])
    
    # If rod_h missing, maybe use cyl_h logic or generic height if not yet taken
    if not rod_h and not cyl_h:
         m_h = re.search(r"height\s*(\d+)", s)
         if m_h: rod_h = float(m_h.group(1))

    # simplified extraction for example
    pos_x, pos_y = (0.0, 0.0)
    # Check "at 50 30" or "at (50, 30)"
    m_pos = re.search(r"at\s*(?:\()?\s*(-?\d+(?:\.\d+)?)\s*[, ]\s*(-?\d+(?:\.\d+)?)\s*(?:\))?", s)
    if m_pos:
        pos_x = float(m_pos.group(1))
        pos_y = float(m_pos.group(2))

    missing = []
    if not width: missing.append("plate width/height")
    if not pad: missing.append("pad thickness")
    
    # Check for either cylinder OR rectangular params
    has_cyl = (cyl_r is not None)
    has_rect = (rod_w is not None and rod_d is not None) # height might be optional or defaulted? Let's strict check if needed
    
    # If explicitly asked for rect, we demand rect params
    is_rect_intent = ("rect" in s)
    
    if is_rect_intent:
        if not rod_w: missing.append("rod/tube width")
        if not rod_d: missing.append("rod/tube depth")
        # height often defaulted to 100 in script, but better to check
    elif not has_cyl:
         # If not rect intent, implies cylinder default
         if not cyl_r: missing.append("cylinder radius")

    if missing:
        return None, {"error": f"Missing parameters: {missing}"}

    params = {
        "plate_width": width,
        "plate_height": height,
        "pad_thickness": pad,
        "corner_offset": 15.0,
        "hole_diameter": 10.0,
        "cyl_radius": cyl_r,
        "cyl_height": cyl_h,
        "rod_width": rod_w,
        "rod_depth": rod_d,
        "rod_height": rod_h or 100.0,
        "rod_wall_thickness": wall or 2.0,
        "hollow_height": 60.0, # default for rect tube script
        "pos_x": pos_x,
        "pos_y": pos_y,
        # keys for catia_create_parts_dynamic.py compatibility
        "WIDTH": width,
        "HEIGHT": height,
        "PAD_THICKNESS": pad,
        "CYL_RADIUS": cyl_r,
        "CYL_HEIGHT": cyl_h,
        # keys for other dynamic scripts
        "ROD_WIDTH": rod_w or 50.0,
        "ROD_DEPTH": rod_d or 40.0,
        "ROD_HEIGHT": rod_h or 100.0,
        "WALL_THICKNESS": wall or 2.0,       # For Cylinder Tube
        "ROD_WALL_THICKNESS": wall or 2.0,   # For Rect Tube
        "HOLLOW_HEIGHT": 60.0
    }

    tf = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, dir=str(base_dir))
    tf.write(json.dumps(params))
    tf.close()
    return ["--params", tf.name], params

def normalize_candidate_for_ui(candidate: dict, shape_tag: str):
    c = {k.lower(): v for k, v in (candidate or {}).items()} if isinstance(candidate, dict) else {}
    out = {}
    def _get_float(keys, default):
        for k in keys:
            if k in c and c[k] is not None:
                try: return float(c[k])
                except: pass
        return float(default)

    out['length_mm'] = _get_float(['length_mm', 'base_length_mm', 'length', 'l'], 200.0)
    out['width_mm']  = _get_float(['width_mm', 'base_width_mm', 'width', 'w'], 150.0)
    out['thickness_mm'] = _get_float(['thickness_mm', 'pad_thickness', 'pad_thickness_mm', 'thickness', 't'], 20.0)

    if any(k in shape_tag for k in ('cylinder','cyl','rod','tube')):
        out['cyl_diameter'] = _get_float(['cyl_diameter','cylinder_diameter_mm','diameter','d','rect_w','rod_w_mm'], 50.0)
        out['cyl_height']   = _get_float(['cyl_height','cylinder_height_mm','cyl_h','height','rect_h','rod_h_mm'], 120.0)
        out['wall_mm'] = _get_float(['wall_mm','wall','thickness_wall','wall_thickness'], c.get('wall_mm') or 2.0)

    if 'rect' in shape_tag:
        out['rect_w'] = _get_float(['rect_w','rect_width','rod_w_mm','width','w'], out['width_mm'])
        out['rect_h'] = _get_float(['rect_h','rect_height','rod_h_mm','height','h','length'], out['length_mm'])

    if 'wing' in shape_tag:
        out['m'] = _get_float(['m','M','m_val'], 4.0)
        out['p'] = _get_float(['p','P','p_val'], 4.0)
        out['t'] = _get_float(['t','T','thickness'], 15.0)
        out['c_t'] = _get_float(['c_t','ct','c_t_val'], 0.5)
        out['sweep'] = _get_float(['sweep','a_sweep','sweep_deg'], 35.0)
        out['score'] = _get_float(['score','fitness'], 0.0)
        if 'lift_proxy' in c: out['lift_proxy'] = float(c.get('lift_proxy'))

    if 'weight_kg' in c: out['weight_kg'] = float(c.get('weight_kg'))
    if 'capacity_proxy' in c: out['capacity_proxy'] = float(c.get('capacity_proxy'))
    if 'score' in c and 'score' not in out: out['score'] = float(c.get('score'))

    out['shape_tag'] = shape_tag
    out['raw_candidate'] = candidate
    return out

def choose_script_and_tag(text: str, dynamic_script: str, cylinder_rod: str, cylinder_tube: str, rect_rod: str, rect_tube: str):
    # logic to choose script
    t = normalize(text)
    def word_in(txt, w): return re.search(rf"\b{re.escape(w)}\b", txt) is not None

    if re.search(r"\bcylinder\b.*\btube\b|\btube\b.*\bcylinder\b", t): return cylinder_tube, "cylinder_tube"
    if re.search(r"\bcylinder\b.*\brod\b|\brod\b.*\bcylinder\b", t): return cylinder_rod, "cylinder_solid"
    if re.search(r"\b(rect)\b.*\btube\b", t): return rect_tube, "rect_tube"
    if re.search(r"\b(rect)\b.*\brod\b", t): return rect_rod, "rect_rod"

    if "wing" in t: return "wing_script_placeholder", "wing"
    return dynamic_script, "default_dynamic"

def build_wheel_flags(text: str) -> List[str]:
    flags: List[str] = []
    s = normalize(text)

    def extract(patterns):
        return _get_float_regex(s, patterns)
        
    # Rim Dimensions
    outer = extract([r"outer\s*radius\s*[:=]?\s*(\d+(?:\.\d+)?)", r"radius\s*(\d+(?:\.\d+)?)"])
    inner = extract([r"inner\s*radius\s*[:=]?\s*(\d+(?:\.\d+)?)"])
    width = extract([r"rim\s*width\s*[:=]?\s*(\d+(?:\.\d+)?)", r"width\s*(\d+(?:\.\d+)?)"])
    thick = extract([r"rim\s*thickness\s*[:=]?\s*(\d+(?:\.\d+)?)", r"thickness\s*(\d+(?:\.\d+)?)"])
    
    if outer: flags += ["--outer-radius", str(outer)]
    if inner: flags += ["--inner-radius", str(inner)]
    if width: flags += ["--rim-width", str(width)]
    if thick: flags += ["--rim-thickness", str(thick)]
    
    # Center Hole
    center_r = extract([r"center\s*hole\s*radius\s*[:=]?\s*(\d+(?:\.\d+)?)", r"center\s*of\s*radius\s*(\d+(?:\.\d+)?)"])
    if center_r: flags += ["--center-hole-radius", str(center_r)]
    
    # Lug Holes
    lug_r = extract([r"lug\s*hole[s]?\s*of\s*radius\s*[:=]?\s*(\d+(?:\.\d+)?)", r"lug\s*radius\s*[:=]?\s*(\d+(?:\.\d+)?)"])
    lug_count = extract([r"(\d+)\s*lug\s*hole[s]?", r"lug\s*hole[s]?\s*count\s*[:=]?\s*(\d+)"])
    offset = extract([r"bolt\s*circle\s*offset\s*[:=]?\s*(\d+(?:\.\d+)?)", r"offset\s*(\d+(?:\.\d+)?)"])
    
    if lug_r: flags += ["--lug-hole-radius", str(lug_r)]
    if lug_count: flags += ["--lug-hole-count", str(int(lug_count))]
    if offset: flags += ["--lug-hole-offset", str(offset)]
    
    # Fillet
    fillet = extract([r"fillets?\s*of\s*(\d+(?:\.\d+)?)", r"fillet\s*radius\s*[:=]?\s*(\d+(?:\.\d+)?)"])
    if fillet: flags += ["--fillet-radius", str(fillet)]
    
    flags += ["--cmd", s]
    return flags
