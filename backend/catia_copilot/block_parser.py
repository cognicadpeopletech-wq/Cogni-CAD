import re
from typing import List, Tuple, Optional, Any

# ===========================
# Regex & Extraction Logic
# ===========================

number_re = r"(-?\d+(?:\.\d+)?)"

def normalize(text: str) -> str:
    if not text:
        return ""
    return text.replace("×", "x").replace("\u00D7", "x").replace("\u00A0", " ").lower().strip()

def _normalize_short(text: str) -> str:
    return normalize(text)

def extra_L(text: str):
    m = re.search(r"\b(?:l|length)\s*[:= ]\s*(-?\d+(\.\d+)?)", text)
    return float(m.group(1)) if m else None

def extract_L(text: str):
    return extra_L(text)

def extract_length(text: str):
    m = re.search(r"\b(?:length|len)\s*[:= ]\s*(-?\d+(\.\d+)?)", text)
    return float(m.group(1)) if m else None

def extract_square(text: str):
    m = re.search(r"square\s*[:= ]\s*(-?\d+(\.\d+)?)", text)
    return float(m.group(1)) if m else None

def extract_circle_radius(text: str):
    m = re.search(r"(?:radius|rad)\s*[:= ]\s*(-?\d+(\.\d+)?)", text)
    return float(m.group(1)) if m else None

def extract_diameter(text: str):
    m = re.search(r"(?:diameter|dia)\s*[:= ]\s*(-?\d+(\.\d+)?)", text)
    return float(m.group(1)) if m else None

def extract_curve_points(text: str):
    t = text.lower()
    t = t.replace("\n", " ").replace("\t", " ")
    t = t.replace("→", " ").replace("|", " ")
    t = t.replace(";", " ").replace(",", " ")
    t = t.replace("(", " ").replace(")", " ")
    t = re.sub(r"(curve|points|point|path|via|pt|pts)\s*[:=]?", " ", t)

    m = re.search(r"curve\s*=\s*\[([^\]]+)\]", text.lower())
    if m:
        raw = m.group(1)
        nums = re.findall(r"-?\d+(?:\.\d+)?", raw)
        if len(nums) % 3 != 0:
            nums = nums[: (len(nums) // 3) * 3]
        return [
            [float(nums[i]), float(nums[i+1]), float(nums[i+2])]
            for i in range(0, len(nums), 3)
        ]

    nums = re.findall(r"-?\d+(?:\.\d+)?", t)
    if len(nums) < 3:
        return None

    junk = {str(int(v)) for v in re.findall(r"(?:l|square|radius|diameter|length)\s*=\s*(\d+)", t)}
    nums = [n for n in nums if n not in junk]

    if len(nums) < 3:
        return None
    if len(nums) % 3 != 0:
        nums = nums[: (len(nums) // 3) * 3]

    return [[float(nums[i]), float(nums[i+1]), float(nums[i+2])]
            for i in range(0, len(nums), 3)]

def extract_plate(text: str):
    m = re.search(r"(?:plate|base\s+plate).*?(\d+)\s*x\s*(\d+)", text)
    return (float(m.group(1)), float(m.group(2))) if m else (None, None)

def extract_pad_thickness(text: str):
    m = re.search(r"pad(?:\s*(?:thickness|height))?(?:\s*of)?\s*=?\s*(\d+)", text)
    return float(m.group(1)) if m else None

def extract_cylinder(text: str):
    m = re.search(
        r"(?:cylinder|cylindrical\s+boss).*?"
        r"(?:radius|r)\s*=?\s*(\d+).*?"
        r"(?:height|h)\s*=?\s*(\d+)", text)
    return (float(m.group(1)), float(m.group(2))) if m else (None, None)

def extract_cylinder_position(text: str):
    m = re.search(r"(?:at|positioned\s+at|location)\s*(-?\d+)\s+(-?\d+)", text)
    return (float(m.group(1)), float(m.group(2))) if m else (0.0, 0.0)

def extract_disk_diameter(text: str) -> Optional[float]:
    s = normalize(text)
    m = re.search(rf"diameter\s*[:=]?\s*{number_re}", s)
    if m: return float(m.group(1))
    m = re.search(rf"{number_re}\s*(?:mm)?\s*diameter", s)
    if m: return float(m.group(1))
    m = re.search(rf"radius\s*[:=]?\s*{number_re}", s)
    if m: return float(m.group(1)) * 2
    m = re.search(rf"{number_re}\s*(?:mm)?\s*(?:disk|plate|circle|circular|disc)\b", s)
    if m: return float(m.group(1))
    m = re.search(rf"(?:disk|plate|circle|disc)\s*(?:of\s*)?{number_re}", s)
    if m: return float(m.group(1))
    m = re.search(rf"{number_re}\s*(?:mm)?\s*dia\b", s)
    if m: return float(m.group(1))
    m = re.search(rf"dia\s*[:=]?\s*{number_re}", s)
    if m: return float(m.group(1))
    return None

def extract_thickness(text: str) -> Optional[float]:
    s = normalize(text)
    m = re.search(rf"(?:thickness|t\b|height|depth)\s*[:=]?\s*{number_re}", s)
    if m: return float(m.group(1))
    m = re.search(rf"{number_re}\s*(?:mm)?\s*(?:thick|thickness|thk)\b", s)
    if m: return float(m.group(1))
    return None

def extract_global_square_side(text: str) -> Optional[float]:
    s = normalize(text)
    m = re.search(rf"side\s*[:=]?\s*{number_re}", s)
    if m: return float(m.group(1))
    m = re.search(rf"(?:square|squared|sq|sqr|sq\w{{0,6}}).{{0,20}}?{number_re}", s)
    if m: return float(m.group(1))
    m2 = re.search(rf"{number_re}\s*(?:mm)?\s*(?:square|squared|sq|sqr|side)\b", s)
    if m2: return float(m2.group(1))
    m3 = re.search(rf"(?:square|squared|sq|sqr|sq\w{{0,6}})\s*(?:holes?|side|of)?\s*(?:[:=]?\s*)?{number_re}", s)
    if m3: return float(m3.group(1))
    return None

def extract_hole_positions(text: str) -> List[Tuple[float, float, Optional[float]]]:
    s = normalize(text)
    holes: List[Tuple[float, float, Optional[float]]] = []
    triple = re.compile(r"\(\s*" + number_re + r"\s*,\s*" + number_re + r"\s*,\s*" + number_re + r"\s*\)")
    for m in triple.finditer(s):
        holes.append((float(m.group(1)), float(m.group(2)), float(m.group(3))))
    pair = re.compile(r"\(\s*" + number_re + r"\s*,\s*" + number_re + r"\s*\)")
    for m in pair.finditer(s):
        x, y = float(m.group(1)), float(m.group(2))
        if not any(abs(hx - x) < 1e-6 and abs(hy - y) < 1e-6 for hx, hy, _ in holes):
            holes.append((x, y, None))
    # patterns like "10 diameter at (x,y)"
    pat1 = re.compile(
        rf"(?P<d>{number_re})\s*(?:mm)?\s*(?:diameter|diamter|damter|dia|side)\s*(?:at\s*)?"
        rf"\(\s*(?P<x>{number_re})\s*,\s*(?P<y>{number_re})\s*\)"
    )
    for m in pat1.finditer(s):
        holes.append((float(m.group("x")), float(m.group("y")), float(m.group("d"))))
    pat2 = re.compile(
        rf"\(\s*(?P<x>{number_re})\s*,\s*(?P<y>{number_re})\s*\)\s*(?:,)?\s*(?P<d>{number_re})\s*(?:mm)?\s*(?:dia|diameter|side)?"
    )
    for m in pat2.finditer(s):
        holes.append((float(m.group("x")), float(m.group("y")), float(m.group("d"))))
    # raw XY pairs
    raw_xy = re.findall(rf"{number_re}\s*,\s*{number_re}", s)
    for xy in raw_xy:
        if isinstance(xy, tuple):
            x_str, y_str = xy[0], xy[1]
        else:
            parts = str(xy).split(",")
            if len(parts) != 2:
                continue
            x_str, y_str = parts[0].strip(), parts[1].strip()
        try:
            x, y = float(x_str), float(y_str)
        except Exception:
            continue
        if not any(abs(hx - x) < 1e-6 and abs(hy - y) < 1e-6 for hx, hy, _ in holes):
            holes.append((x, y, None))
    # de-duplicate and merge diameters if found separately
    final: List[Tuple[float, float, Optional[float]]] = []
    for x, y, d in holes:
        exists = False
        for i, (fx, fy, fd) in enumerate(final):
            if abs(fx - x) < 1e-6 and abs(fy - y) < 1e-6:
                if fd is None and d is not None:
                    final[i] = (fx, fy, d)
                exists = True
                break
        if not exists:
            final.append((x, y, d))
    return final

def extract_integer_after_keywords(text: str, keys: List[str]) -> Optional[int]:
    s = normalize(text)
    m = re.search(r"(\d+)\s*holes?\b", s)
    if m:
        return int(m.group(1))
    for k in keys:
        m = re.search(rf"{k}\s*[:=]?\s*(\d+)\b", s)
        if m:
            return int(m.group(1))
    m2 = re.search(r"\b(\d{1,3})\b", s)
    if m2:
        return int(m2.group(1))
    return None

def extract_value_for_keyword(text: str, keywords: List[str]) -> Optional[float]:
    s = normalize(text)
    for kw in keywords:
        m = re.search(rf"{kw}\s*[:=]?\s*{number_re}", s)
        if m:
            try:
                return float(m.group(1))
            except:
                pass
    for kw in keywords:
        m = re.search(rf"{number_re}\s*(?:mm)?\s*{kw}", s)
        if m:
            try:
                return float(m.group(1))
            except:
                pass
    return None

def extract_global_hole_diameter(text: str) -> Optional[float]:
    s = normalize(text)
    m = re.search(rf"hole(?:s)?(?:\s|_)?(?:dia|diameter)?\s*[:=]?\s*{number_re}", s)
    if m: return float(m.group(1))
    m = re.search(rf"(?:dia|ø)\s*[:=]?\s*{number_re}", s)
    if m: return float(m.group(1))
    return None

def extract_cylinder_values(text: str) -> Tuple[Optional[float], Optional[float]]:
    s = normalize(text)
    m_combo = re.search(rf"(\d+(?:\.\d+)?)\s*(?:x|×|by)\s*(\d+(?:\.\d+)?)", s)
    if m_combo:
        try:
            return float(m_combo.group(1)), float(m_combo.group(2))
        except:
            pass
    dia = None; h = None
    m1 = re.search(rf"(?:diameter|dia|d)\s*[:=]?\s*{number_re}", s)
    if m1: dia = float(m1.group(1))
    m2 = re.search(rf"(?:height|h)\s*[:=]?\s*{number_re}", s)
    if m2: h = float(m2.group(1))
    if dia is None:
        m3 = re.search(rf"{number_re}\s*mm\s*(?:diameter|dia|d)", s)
        if m3: dia = float(m3.group(1))
    if h is None:
        m4 = re.search(rf"{number_re}\s*mm\s*(?:height|h)", s)
        if m4: h = float(m4.group(1))
    return dia, h

def extract_plate_LWT(text: str):
    s = normalize(text)
    # 1. Triple format: 300x200x50, 300 x 200 x 50, (300x200x50)
    # Using number_re throughout for consistency
    pat_triple = rf"(?:^|\s|\(|\[)({number_re})\s*(?:x|×|by)\s*({number_re})\s*(?:x|×|by)\s*({number_re})(?:\s*mm)?(?:$|\s|\)|\])"
    m = re.search(pat_triple, s)
    if m:
        # group 1, 3, 5 corresponds to the 3 numbers because number_re has one capturing group inside
        # Actually number_re = (-?\d+(?:\.\d+)?) -> ONE capturing group.
        # So ({number_re}) is a nested group.
        # Outer group is 1, inner is 2. Next number outer is 3, inner 4. etc.
        # Let's simplify and use findall or specific groups. 
        # Easier: Just use simple \d patterns allowing floats if we control the regex here.
        pass
    
    # Simplify regex to avoid group hell
    # (\d+(?:\.\d+)?) is what we want.
    npattern = r"(\d+(?:\.\d+)?)"
    m2 = re.search(rf"{npattern}\s*(?:x|×|by)\s*{npattern}\s*(?:x|×|by)\s*{npattern}", s)
    if m2:
         try: return float(m2.group(1)), float(m2.group(2)), float(m2.group(3))
         except: pass
    L = W = T = None
    mL = re.search(rf"(?:length|l)\s*[:=]?\s*{number_re}", s)
    mW = re.search(rf"(?:width|w|breadth|b)\s*[:=]?\s*{number_re}", s)
    mT = re.search(rf"(?:thickness|t|height|depth)\s*[:=]?\s*{number_re}", s)
    if mL: L = float(mL.group(1))
    if mW: W = float(mW.group(1))
    if mT: T = float(mT.group(1))
    if L is not None and W is not None and T is not None: return L, W, T
    return (L, W, T)

def extract_hole_count_for_circular(text: str):
    s = normalize(text)
    m = re.search(rf"(\d+)\s*holes?", s)
    if m: return int(m.group(1))
    return None

def extract_hole_diameter_for_circular(text: str):
    s = normalize(text)
    m = re.search(rf"hole(?:\s|_)?(?:dia|diameter)?\s*[:=]?\s*{number_re}\s*(?:mm)?", s)
    if m:
        try: return float(m.group(1))
        except: pass
    return None

def extract_circle_diameter_or_radius(text: str):
    s = normalize(text)
    m = re.search(rf"{number_re}\s*(?:mm)?\s*diameter\s*(?:circle)?", s)
    if m:
        try: return float(m.group(1))
        except: pass
    m2 = re.search(rf"diameter\s*[:=]?\s*{number_re}\s*(?:mm)?", s)
    if m2:
        try: return float(m2.group(1))
        except: pass
    m3 = re.search(rf"{number_re}\s*(?:mm)?\s*radius\s*(?:circle)?", s)
    if m3:
        try: return float(m3.group(1)) * 2.0
        except: pass
    m4 = re.search(rf"radius\s*[:=]?\s*{number_re}\s*(?:mm)?", s)
    if m4:
        try: return float(m4.group(1)) * 2.0
        except: pass
    return None

def extract_block_length(text: str) -> Optional[float]:
    s = normalize(text)
    m = re.search(rf"length\s*[:=]?\s*{number_re}", s)
    if m:
        return float(m.group(1))
    m2 = re.search(rf"{number_re}\s*(?:mm)?\s*length", s)
    if m2:
        return float(m2.group(1))
    m3 = re.search(rf"{number_re}\s*x\s*{number_re}", s)
    if m3:
        return float(m3.group(1))
    m4 = re.search(rf"(?:rectangle|block)\s*{number_re}\s*(?:by|x)\s*{number_re}", s)
    if m4:
        return float(m4.group(1))
    return None

def extract_block_width(text: str) -> Optional[float]:
    s = normalize(text)
    m = re.search(rf"width\s*[:=]?\s*{number_re}", s)
    if m:
        return float(m.group(1))
    m2 = re.search(rf"{number_re}\s*(?:mm)?\s*width", s)
    if m2:
        return float(m2.group(1))
    m3 = re.search(rf"{number_re}\s*x\s*{number_re}", s)
    if m3:
        return float(m3.group(2))
    m4 = re.search(rf"(?:rectangle|block)\s*{number_re}\s*(?:by|x)\s*{number_re}", s)
    if m4:
        return float(m4.group(2))
    return None

def extract_block_holes(text: str) -> List[Tuple[float, float, float]]:
    s = normalize(text)
    holes: List[Tuple[float, float, float]] = []
    p1 = re.findall(rf"\(\s*{number_re}\s*,\s*{number_re}\s*\)\s*(?:dia|diameter)\s*{number_re}", s)
    for x, y, d in p1:
        try:
            holes.append((float(x), float(y), float(d)))
        except Exception:
            continue
    p2 = re.findall(rf"x\s*[:=]\s*{number_re}.*?y\s*[:=]\s*{number_re}.*?(?:d|dia|diameter)\s*[:=]?\s*{number_re}", s)
    for x, y, d in p2:
        try:
            holes.append((float(x), float(y), float(d)))
        except Exception:
            continue
    p3 = re.findall(rf"hole\s*\d*\s*at\s*{number_re}\s*[, ]\s*{number_re}.*?(?:dia|d|diameter)\s*{number_re}", s)
    for x, y, d in p3:
        try:
            holes.append((float(x), float(y), float(d)))
        except Exception:
            continue
            
    # New pattern: "5 mm at (25,25)" or "— 5 mm at (25,25)"
    # number_re has internal capturing, so findall returns too many groups. Use finditer.
    # Pattern: [dash?] D mm at (X,Y)
    # New pattern: "5 mm at (25,25)", "d6 at (20,20)", "d=6 at (25,25)"
    # number_re is (-?\d+(?:\.\d+)?)
    
    # 1. d6 at (x,y) or d=6 at (x,y)
    # This specifically looks for 'd' immediately followed by number, OR 'd' space number, OR 'd=' number
    pat_d = re.compile(rf"(?:d|dia|diameter)\s*[:=]?\s*(?P<d>{number_re})\s*(?:mm)?\s*at\s*\(\s*(?P<x>{number_re})\s*,\s*(?P<y>{number_re})\s*\)")
    for m in pat_d.finditer(s):
        try:
             holes.append((float(m.group("x")), float(m.group("y")), float(m.group("d"))))
        except: continue

    # 2. "5 mm at (25,25)" (previous pattern, refined)
    pat4 = re.compile(rf"(?:—|-)?\s*(?P<d>{number_re})\s*mm\s*at\s*\(\s*(?P<x>{number_re})\s*,\s*(?P<y>{number_re})\s*\)")
    for m in pat4.finditer(s):
        try:
            # group("d") might return the outer capturing group of number_re depending on engine, 
            # but usually named group captures content.
            # number_re is (-?\d...), so group(1) inside P<d>.
            # Let's trust full match string for float conversion or just group()
            # Actually, because number_re is (-?\d..), P<d> wraps it. valid.
            d_val = float(m.group("d"))
            x_val = float(m.group("x"))
            y_val = float(m.group("y"))
            holes.append((x_val, y_val, d_val))
        except Exception:
            continue
            
    return holes

def extract_l_bracket_dims(text: str) -> Optional[Tuple[float, float]]:
    s = normalize(text)
    m = re.search(rf"{number_re}\s*x\s*{number_re}", s)
    if m:
        return float(m.group(1)), float(m.group(2))
    m2 = re.search(rf"{number_re}\s*(?:by)\s*{number_re}", s)
    if m2:
        return float(m2.group(1)), float(m2.group(2))
    m3 = re.search(rf"leg(?:s| length)?s?\s*[:=]?\s*{number_re}\s*(?:and|,)\s*{number_re}", s)
    if m3:
        return float(m3.group(1)), float(m3.group(2))
    return None

def extract_bend_radius(text: str) -> Optional[float]:
    s = normalize(text)
    m = re.search(rf"bend\s*radius\s*[:=]?\s*{number_re}", s)
    if m:
        return float(m.group(1))
    m2 = re.search(rf"radius\s*[:=]?\s*{number_re}", s)
    if m2 and "hole" not in s and "circle" not in s:
        return float(m2.group(1))
    return None

def extract_iso_class(text: str) -> Optional[str]:
    s = normalize(text)
    m = re.search(r"\bclass\s*(?:=|:)?\s*([fmcv])\b", s)
    if m:
        return m.group(1).lower()
    if "fine" in s and "class" in s: return "f"
    if "medium" in s and "class" in s: return "m"
    if "coarse" in s and "class" in s: return "c"
    if "very" in s and "class" in s: return "v"
    if "iso 2768 f" in s or "iso2768 f" in s: return "f"
    if "iso 2768 m" in s or "iso2768 m" in s: return "m"
    if "iso 2768 c" in s or "iso2768 c" in s: return "c"
    if "iso 2768 v" in s or "iso2768 v" in s: return "v"
    return None

def is_l_bracket_command(text: str) -> bool:
    s = normalize(text)
    return any(k in s for k in (
        "l-bracket", "l bracket", "lbracket", "l shaped bracket", "l-shaped bracket",
        "l shape bracket", "l shape", "create an l-bracket", "create l-bracket",
        "generate the l-bracket", "generate l-bracket", "make an l-bracket",
        "generate an l-bracket", "create l bracket", "generate an l bracket"
    ))

def contains_disk_context(s: str) -> bool:
    s = normalize(s)
    return any(k in s for k in ("disk", "circle", "circular", "disc", "diameter", "dia"))

def contains_plate_context(s: str) -> bool:
    s = normalize(s)
    return any(k in s for k in ("plate", "block", "rectangle", "rectangular", "baseplate", "bracket"))

def detect_topology_and_mode(text: str) -> Tuple[str, str]:
    s = normalize(text)
    disk_ctx = contains_disk_context(s)
    plate_ctx = contains_plate_context(s)

    has_square = any(k in s for k in ("square", "squared", "sq", "square holes", "squares"))
    has_explicit_coords = bool(re.search(r"\(\s*-?\d+(?:\.\d+)?\s*,\s*-?\d+(?:\.\d+)?\s*\)", s))

    has_diag = any(k in s for k in ("diagonal", "diagonals", "along diagonal", "along diagon"))
    has_equi = any(k in s for k in ("equidistant", "equally spaced", "along x", "along y", "linear", "equi"))
    has_peri = any(k in s for k in ("perimeter", "around perimeter", "around edge", "circumferential", "around circle"))
    has_circ = any(k in s for k in ("circular topology", "circular pattern", "on circle", "hole circle", "circular"))
    has_cyl = "cylinder" in s or "cyl" in s or "create cylinder" in s

    if has_cyl:
        return "cylinder", "cylinder"

    if has_square and (disk_ctx or plate_ctx):
        return "default", "square"
    elif has_explicit_coords and (disk_ctx or plate_ctx):
        return "default", "coords"

    if plate_ctx:
        if has_diag: return "diagonal", "topology"
        if has_equi: return "equidistant", "topology"
        if has_peri: return "perimeter", "topology"
        if has_circ: return "circular", "topology"
        return "diagonal", "topology"

    if disk_ctx:
        if has_diag: return "diagonal", "topology"
        if has_equi: return "equidistant", "topology"
        if has_peri: return "perimeter", "topology"
        if has_circ: return "circular", "topology"

    if has_square: return "default", "square"
    if has_diag: return "diagonal", "topology"
    if has_equi: return "equidistant", "topology"
    if has_peri: return "perimeter", "topology"
    if has_circ: return "circular", "topology"

    return "circular", "topology"
