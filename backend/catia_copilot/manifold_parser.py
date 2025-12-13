
import re

def norm(s: str) -> str:
    """Normalize text for stable matching."""
    return (
        s.lower()
         .replace(",", " ")
         .replace("mm", "")
         .replace("deg", "")
         .replace("°", "")
         .replace("=", " ")
         .replace(":", " ")
    )

def safe_float(x):
    try:
        return float(x)
    except:
        return None

def grab(text, keyword_list):
    """
    Universal number extractor.
    """
    for kw in keyword_list:
        # allow optional noise text between keyword and number
        patterns = [
            rf"{kw}\s+(-?\d+(?:\.\d+)?)",
            rf"{kw}\s*=\s*(-?\d+(?:\.\d+)?)",
            rf"{kw}\s*:\s*(-?\d+(?:\.\d+)?)",
            # NEW: detect "kw ... 34"
            rf"{kw}[^\d]+(-?\d+(?:\.\d+)?)",
        ]

        for p in patterns:
            m = re.search(p, text)
            if m:
                return safe_float(m.group(1))
    return None

def extract_all_manifold_params(command: str):
    s = norm(command)
    cfg = {}

    # ---------------------------
    # INLET / EXHAUST RADIUS
    # ---------------------------
    cfg["exhaust_rad"] = grab(s, [
        "inlet radius", "inlet rad",
        "inlet radius of", "inlet rad of",
        "exhaust radius", "exhaust rad",
        "inlet", "exhaust"
    ])

    # ---------------------------
    # MOUNT RADIUS
    # ---------------------------
    cfg["mnt_rad"] = grab(s, [
        "mount radius", "mnt radius",
        "mount rad", "mnt rad",
        "mounting radius", "mounting rad",
        "mounting"
    ])

    # ---------------------------
    # MOUNT ANGLE
    # ---------------------------
    cfg["mnt_angle_deg"] = grab(s, [
        "mount angle", "mnt angle",
        "mounting angle"
    ])

    # ---------------------------
    # MOUNT DISTANCE
    # ---------------------------
    cfg["mnt_dist"] = grab(s, [
        "mount distance", "mnt distance",
        "mount dist", "mnt dist",
        "mounting distance"
    ])

    # ---------------------------
    # DIAMOND SUPPORT
    # ---------------------------
    cfg["dmnd_DIST"] = grab(s, [
        "diamond dist", "dmnd dist big",
        "dmnd large", "diamond large"
    ])

    cfg["dmnd_dist"] = grab(s, [
        "diamond small", "dmnd dist small",
        "dmnd small", "diamond sm"
    ])

    # ---------------------------
    # PAD THICKNESS
    # ---------------------------
    cfg["pad_thickness_in"] = grab(s, [
        "inlet pad", "pad inlet thickness",
        "inlet pad thickness"
    ])

    cfg["pad_thickness_out"] = grab(s, [
        "outlet pad", "pad outlet thickness",
        "outlet pad thickness"
    ])

    # ---------------------------
    # PATTERN SPACING
    # ---------------------------
    cfg["pattern_spacing_Y"] = grab(s, [
        "pattern spacing", "pattern spacing near",
        "spacing", "spacing near",
        "pattern gap"
    ])

    # ---------------------------
    # OUTLET OFFSET
    # ---------------------------
    cfg["plane_outlet_offset"] = grab(s, [
        "outlet plane offset", "plane offset"
    ])

    # ---------------------------
    # OUTLET HEIGHT
    # ---------------------------
    cfg["outlet_h"] = grab(s, [
        "outlet height", "outlet height of",
        "height outlet", "outlet h"
    ])

    # ---------------------------
    # OUTLET MOUNT
    # ---------------------------
    cfg["mnt_out_dist"] = grab(s, [
        "outlet mount distance", "mount out distance"
    ])

    cfg["mnt_out_angle_deg"] = grab(s, [
        "outlet mount angle", "mount out angle"
    ])

    # ---------------------------
    # TRIANGLE DIST
    # ---------------------------
    cfg["triang_dist"] = grab(s, [
        "triangle distance", "triang distance"
    ])

    # ---------------------------
    # Z OFFSET
    # ---------------------------
    cfg["z_offset_inlet_top"] = grab(s, [
        "z offset inlet", "inlet top offset", "z inlet"
    ])

    # ---------------------------
    # MEET OFFSET
    # ---------------------------
    cfg["meet_offset_x"] = grab(s, [
        "meet offset", "meet x offset"
    ])

    # ---------------------------
    # TURN RADIUS
    # ---------------------------
    cfg["turn_rad"] = grab(s, [
        "turn radius", "turn rad",
        "bend radius"
    ])

    # ---------------------------
    # SWEEP RADIUS
    # ---------------------------
    cfg["sweep_exhaust_rad"] = grab(s, [
        "sweep radius", "sweep rad",
        "sweep exhaust radius"
    ])

    # ---------------------------
    # SHELL THICKNESS
    # ---------------------------
    cfg["shell_thickness"] = grab(s, [
        "shell thickness", "wall thickness",
        "thickness"
    ])

    # remove missing ones
    return {k: v for k, v in cfg.items() if v is not None}
