
import re
import math
import json
from typing import List, Tuple, Optional, Dict, Any

number_re = r"(-?\d+(?:\.\d+)?)"

def safe_float(v):
    try:
        return float(v)
    except Exception:
        return None

def safe_int(v):
    try:
        return int(float(v))
    except Exception:
        return None

def extract_param_simple(text: str, name_variants: List[str]) -> Optional[float]:
    s = (text or "").lower()
    for v in name_variants:
        m = re.search(rf"{re.escape(v)}\s*[:=]?\s*{number_re}", s)
        if m:
            return safe_float(m.group(1))
        m2 = re.search(rf"{number_re}\s*(?:mm)?\s*{re.escape(v)}", s)
        if m2:
            return safe_float(m2.group(1))
    return None

def extract_triangle_points(text: str) -> Optional[List[List[float]]]:
    m = re.search(r"\[\s*\[[^\]]+\]\s*,\s*\[[^\]]+\]\s*,\s*\[[^\]]+\]\s*\]", text or "")
    if m:
        try:
            arr = json.loads(m.group(0))
            if isinstance(arr, list) and len(arr) == 3:
                return [[safe_float(p[0]), safe_float(p[1])] for p in arr]
        except Exception:
            pass
    return None

def build_flags_for_fixed_robust(explicit: dict, command_text: str) -> Tuple[List[str], dict]:
    """
    Build flags for file_fixed_robust.py
    """
    flags: List[str] = []
    preview = {}

    mappings = {
        'circle_radius': '--circle-radius',
        'pad_height': '--pad-height',
        'second_sketch_z': '--second-sketch-z',
        'pocket_depth': '--pocket-depth',
        'pattern_instances': '--pattern-instances',
        'pattern_spacing': '--pattern-spacing',
        'center_hole_dia': '--center-hole-dia',
    }

    for k, flag in mappings.items():
        val = explicit.get(k, None)
        if val is None:
            continue
        if k == 'pattern_instances':
            ival = safe_int(val)
            if ival is None: continue
            preview[k] = ival
            flags += [flag, str(int(ival))]
            continue

        if k == 'pattern_spacing':
            fval = safe_float(val)
            if fval is None: continue
            preview[k] = float(fval)
            flags += [flag, str(float(fval))]
            continue

        fval = safe_float(val)
        if fval is None: continue
        preview[k] = float(fval)
        flags += [flag, str(float(fval))]

    if explicit.get('debug'):
        flags.append('--debug')
        preview['debug'] = True

    if explicit.get('triangle_points'):
        preview['triangle_points'] = explicit['triangle_points']
        flags += ['--triangle-points', json.dumps(explicit['triangle_points'])]

    s = (command_text or "").lower()
    if s:
        if 'circle_radius' not in preview:
            r = extract_param_simple(s, ['circle radius', 'circle-radius', 'radius', 'radius mm'])
            if r is not None:
                preview['circle_radius'] = r
                flags += ['--circle-radius', str(r)]
            else:
                d = extract_param_simple(s, ['diameter'])
                if d is not None:
                    preview['circle_radius'] = float(d) / 2.0
                    flags += ['--circle-radius', str(preview['circle_radius'])]

        if 'pad_height' not in preview:
            h = extract_param_simple(s, ['pad height', 'pad-height', 'height'])
            if h is not None:
                preview['pad_height'] = h; flags += ['--pad-height', str(h)]

        if 'pocket_depth' not in preview:
            pd = extract_param_simple(s, ['pocket depth', 'pocket-depth', 'pocket'])
            if pd is not None:
                preview['pocket_depth'] = pd; flags += ['--pocket-depth', str(pd)]

        if 'pattern_instances' not in preview:
            inst = extract_param_simple(s, ['instances', 'pattern instances', 'n'])
            if inst is not None:
                ival = safe_int(inst)
                if ival is not None:
                    preview['pattern_instances'] = ival
                    flags += ['--pattern-instances', str(int(ival))]

        if 'pattern_spacing' not in preview:
            sp = extract_param_simple(s, ['pattern spacing', 'spacing'])
            if sp is not None:
                preview['pattern_spacing'] = sp; flags += ['--pattern-spacing', str(sp)]

        if '--triangle-points' not in " ".join(flags):
            tri = extract_triangle_points(s)
            if tri is not None:
                preview['triangle_points'] = tri; flags += ['--triangle-points', json.dumps(tri)]

        if 'center_hole_dia' not in preview:
            # Look for "center pocket with diameter X" or "center hole diameter X"
            # simpler regex strategy: look for "center pocket" or "center hole" and then a number associated?
            # Or just usage of extract_param_simple with specific phrases
            chd = extract_param_simple(s, ['center pocket with diameter', 'center pocket diameter', 'center hole diameter', 'center hole', 'center pocket'])
            if chd is not None:
                preview['center_hole_dia'] = chd; flags += ['--center-hole-dia', str(chd)]

    instances = preview.get('pattern_instances')
    spacing_present = ('pattern_spacing' in preview) or any(a.startswith('--pattern-spacing') for a in flags)
    if instances and not spacing_present:
        try:
            spacing_calc = 360.0 / float(instances)
            preview['pattern_spacing'] = spacing_calc
            flags += ['--pattern-spacing', str(spacing_calc)]
        except Exception:
            pass

    # Deduplicate flags
    seen = set(); deduped = []; i = 0
    while i < len(flags):
        f = flags[i]
        if f.startswith("--"):
            key = f; val = None
            if i+1 < len(flags) and not flags[i+1].startswith("--"):
                val = flags[i+1]; pair=(key,val)
                if pair not in seen:
                    deduped.extend([key,val]); seen.add(pair)
                i += 2; continue
            else:
                if (key, None) not in seen:
                    deduped.append(key); seen.add((key,None))
                i += 1; continue
        else:
            i += 1
    return deduped, preview

def generate_cylinder_summary(preview: dict) -> str:
    radius = preview.get('circle_radius')
    if radius is None:
        return "Insufficient parameters to generate cylinder summary."
    try:
        diameter = float(radius) * 2.0
    except Exception:
        return "Insufficient parameters."
    pocket_depth = preview.get('pocket_depth')
    hole_text = f"{float(pocket_depth):g} mm" if pocket_depth else "unknown depth"
    instances = preview.get('pattern_instances')
    spacing = preview.get('pattern_spacing')
    return f"Created {diameter:g} mm Cylinder, {hole_text} holes ({instances or '?'}) at {spacing or '?'} deg."
