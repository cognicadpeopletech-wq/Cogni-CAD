
import re
from pathlib import Path

# Imports from sibling modules (assuming running as package or correct path setup)
from catia_copilot.block_parser import (
    normalize, _normalize_short, detect_topology_and_mode,
    contains_plate_context, extract_iso_class, extract_l_bracket_dims,
    extract_block_width, extract_thickness, extract_bend_radius, extract_block_holes,
    is_l_bracket_command, contains_disk_context, extract_block_length,
    extract_plate_LWT, extract_value_for_keyword
)
from catia_copilot.block_generator import (
    build_flags_for_rib_slot, build_flags_for_multipart, choose_script_and_tag,
    normalize_candidate_for_ui, build_square_flags_from_text, build_square_flags_from_array,
    build_topology_flags, build_coord_flags, build_cylinder_flags, build_flags_for_plate,
    build_block_flags, build_lbrac_flags, build_flags_for_circular, build_disk_flags,
    build_wheel_flags
)
from catia_copilot.cylinder_helpers import build_flags_for_fixed_robust, extract_param_simple

# Constants
COLOR_SCRIPT_NAME = "color.py"
MULTIPART_SCRIPT = "multipart_dynamic.py"
RIB_SLOT_SCRIPT = "rib_slot_dynamic.py"
LBRAC_SCRIPT_NAME = "L-Brac.py"
SCRIPT_CYLINDER = "create_cylinder_interactive.py"

# ... imports ...
# ... imports ...
import json
from catia_copilot.manifold_parser import extract_all_manifold_params

# Load intents (Global cache)
INTENTS_CACHE = None

def load_intents(base_dir: Path):
    global INTENTS_CACHE
    if INTENTS_CACHE is not None:
        # User requested reload check: Cache is persistent until server restart - Reload triggered (2)
        return INTENTS_CACHE
    
    intents_path = base_dir / "catia_copilot" / "intents.json"
    if not intents_path.exists():
        return {}
        
    try:
        with open(intents_path, "r", encoding="utf-8") as f:
            INTENTS_CACHE = json.load(f)
        return INTENTS_CACHE
    except Exception as e:
        print(f"Error loading intents.json: {e}")
        return {}

def route_explicit_command(command_raw: str, base_dir: Path):
    s = normalize(command_raw)
    def matches(pattern): return re.search(pattern, s) is not None
    
    script_to_run = None
    script_flags = []

    # --- 1. Specific Routing Overrides (Priority over Intents) ---

    # J) Diagonal Holes on Disk (Specific)
    if matches(r"diagonal") and matches(r"disk"):
        script_to_run = "diagonal_on_disk.py"
        flags = []
        
        # Diameter
        d_val = extract_value_for_keyword(command_raw, ["diameter", "dia", "d"])
        if d_val: flags.extend(["--diameter", str(d_val)])
            
        # Thickness
        t_val = extract_value_for_keyword(command_raw, ["thickness", "thick", "t"])
        if t_val: flags.extend(["--T", str(t_val)])
            
        # Count (N holes)
        n_match = re.search(r"(\d+)\s*(?:diagonal)?\s*holes?", command_raw, re.IGNORECASE)
        if n_match:
            flags.extend(["--n", n_match.group(1)])
            
        # Offset
        off_val = extract_value_for_keyword(command_raw, ["offset", "inset"])
        if off_val: flags.extend(["--offset", str(off_val)])
            
        # Hole Dia context check
        hd_context = re.search(r"offset\s*\d+(?:\.\d+)?\s*(?:dia(?:meter)?)?\s*(\d+(?:\.\d+)?)", command_raw, re.IGNORECASE)
        if hd_context:
            flags.extend(["--dia", hd_context.group(1)])
        else:
             # Fallback: check valid single "dia" that isn't the main disk dia
             pass

        script_flags = flags
        return script_to_run, script_flags

        script_flags = flags
        return script_to_run, script_flags

    # M) Circular Squared Disk (Specific)
    if matches(r"disk") and (matches(r"square.*holes?") or matches(r"squared.*holes?")):
        script_to_run = "circular_squared_disk.py"
        flags = []
        
        # Diameter
        d_val = extract_value_for_keyword(command_raw, ["diameter", "dia", "d"])
        if d_val: flags.extend(["--diameter", str(d_val)])
            
        # Thickness
        t_val = extract_value_for_keyword(command_raw, ["thickness", "thick", "t"])
        if t_val: flags.extend(["--T", str(t_val)])
            
        # Extract Square Holes: "squared holes 20 at (0,0) and 10 at (20,30)"
        sq_hole_pattern = r"(\d+(?:\.\d+)?)\s*(?:mm)?\s*(?:(?:square|squared)?\s*holes?)?\s*at\s*\((-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\)"
        matches_sq = re.findall(sq_hole_pattern, command_raw, re.IGNORECASE)
        
        for (side, x, y) in matches_sq:
            flags.append("--hole")
            flags.append(f"{x},{y},{side}")

        script_flags = flags
        return script_to_run, script_flags

    # H) Create Disk (Dynamic with Holes)
    # Ensure we don't capture specific topology requests (diagonal, perimeter, etc.) which should fall through
    elif (matches(r"^create\s+disk") or (matches(r"\bdisk\b") and matches(r"diameter") and matches(r"thickness"))) \
         and not matches(r"diagonal") and not matches(r"perimeter") and not matches(r"equidistant") and not matches(r"topology"):
        script_to_run = "circular_disk_dynamic.py"
        
        # Extract Diameter
        d_val = extract_value_for_keyword(command_raw, ["diameter", "dia", "d"])
        
        # Extract Thickness
        t_val = extract_value_for_keyword(command_raw, ["thickness", "thick", "t"])

        flags = []
        if d_val: flags.extend(["--diameter", str(d_val)])
        if t_val: flags.extend(["--T", str(t_val)])
        
        # Extract Holes: "16 diameter at (0,0)"
        hole_pattern = r"(\d+(?:\.\d+)?)\s*(?:mm)?\s*(?:dia(?:meter)?)?\s*(?:hole)?\s*at\s*\((-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\)"
        matches_holes = re.findall(hole_pattern, command_raw, re.IGNORECASE)
        
        for (dia, x, y) in matches_holes:
            flags.append("--hole")
            flags.append(f"{x},{y},{dia}")

        script_flags = flags
        return script_to_run, script_flags
    
    # 0. Check Intents (JSON-based)
    intents = load_intents(base_dir)
    for intent_name, data in intents.items():
        script = data.get("script")
        examples = data.get("examples", [])
        
        # Check against examples (case-insensitive substring or exact match logic)
        # For robustness, we check if the example is 'contained' in the command or vice versa?
        # User request implies specific phrases trigger specific scripts.
        # Let's check if any example phrase is essentially the user command.
        
        for ex in examples:
            # Normalize example
            ex_norm = normalize(ex)
            
            # Use regex with word boundaries to avoid partial matches (e.g. "hi" in "thickness")
            # The EXAMPLE is contained in the COMMAND as a phrase
            # OR if the COMMAND is contained in the EXAMPLE (for short commands)
            
            # Check if example is a 'phrase' in the user command
            if re.search(r"\b" + re.escape(ex_norm) + r"\b", s):
                 print(f"[DEBUG] Matched Intent: {intent_name} via example '{ex_norm}' for input '{s}'")
                 script_to_run = script
                 script_flags = ["--cmd", command_raw]
                 return script_to_run, script_flags
                 
            # Check if command is fully contained in example (e.g. user types "close files" and example is "close all files" -> maybe too loose?)
            # The previous logic allowed `s in ex_norm`.
            # If user types "link drawing", and example is "link drawing to part", `s` is in `ex`.
            # This is risky if `s` is "link". But lets keep it for consistency with "close all catia files" vs "close catia".
            if s in ex_norm and len(s) > 4: # generic length filter
                 # Ensure `s` is not just a random short word
                 print(f"[DEBUG] Matched Intent: {intent_name} via reverse match (command inside example) '{ex_norm}'")
                 script_to_run = script
                 script_flags = ["--cmd", command_raw]
                 return script_to_run, script_flags
    
    print(f"[DEBUG] No Intent matched for '{s}'. Proceeding to Regex checks.")

    # A) Color
    if matches(r"\b(color|paint|colour)\b"):
        script_to_run = COLOR_SCRIPT_NAME
        script_flags = ["--cmd", command_raw]
        
    # B) Load Latest / Persistent Workflow (High Priority)
    elif matches(r"load.*(?:current|existing|recent).*model"):
          script_to_run = "open_latest_file.py"
          script_flags = []
        
    # ... rest of existing logic ...
        
    # B) BOM
    elif matches(r"\b(bom|bill of materials)\b"):
        script_to_run = "bom_pycatia.py"
        script_flags = ["--cmd", command_raw]

    # Wing Optimization Result (Specific Check BEFORE generic optimizer)
    elif matches(r"generate.*optimized.*wing") or (matches(r"wing") and matches(r"m\s*=")):
        script_to_run = "wing_structure_winglet_transparent.py"
        # Extract params: m, p, t, ct, sweep
        m_val = re.search(r"m\s*=\s*(\d+(?:\.\d+)?)", s)
        p_val = re.search(r"p\s*=\s*(\d+(?:\.\d+)?)", s)
        t_val = re.search(r"t\s*=\s*(\d+(?:\.\d+)?)", s)
        ct_val = re.search(r"(?:ct|tipchord)\s*=\s*(\d+(?:\.\d+)?)", s)
        sw_val = re.search(r"sweep\s*=\s*(\d+(?:\.\d+)?)", s)
        
        flags = []
        if m_val: flags.extend(["--m", m_val.group(1)])
        if p_val: flags.extend(["--p", p_val.group(1)])
        if t_val: flags.extend(["--t", t_val.group(1)])
        if ct_val: flags.extend(["--ct", ct_val.group(1)])
        if sw_val: flags.extend(["--sweep", sw_val.group(1)])
        
        script_flags = flags

    # OPTIMIZATION
    elif matches(r"(lightest|best|optimal|optimize)") and (matches(r"design") or matches(r"assembly") or matches(r"shape") or matches(r"wing")):
         script_to_run = "run_optimizer_cli.py"
         script_flags = ["--goal", command_raw]
         if matches(r"among all shapes") or matches(r"all shapes") or matches(r"compare"):
              script_flags.append("--all-shapes")
    elif matches(r"among all shapes"):
         script_to_run = "run_optimizer_cli.py"
         script_flags = ["--goal", command_raw, "--all-shapes"]



    # C) Multipart (Plate + Cylinder)
    # Relaxed regex to catch "plate ... and add ... cylinder"
    elif matches(r"(?:plate|block).*with.*(?:cylinder|rod|tube|rect)") or \
         matches(r"(?:plate|block).*and.*(?:add|place|attach|include|position|put).*(?:cylinder|rod|tube|rect)") or \
         matches(r"(?:cylinder|rod).*on.*(?:plate|block)"):
        flags, params = build_flags_for_multipart(command_raw, base_dir)
        if flags and len(flags) >= 2 and flags[0] == "--params":
            json_path = flags[1]
            
            # Select specific script based on shape keywords
            if matches(r"baseplate"):
                 # Optimization result variants
                 if matches(r"rect.*tube") or matches(r"rectangular.*tube"):
                      script_to_run = "catia_create_parts_dynamic_rectrod_updated.py"
                 elif matches(r"rect.*rod") or matches(r"rectangular.*rod"):
                      script_to_run = "catia_create_parts_dynamic_rectrod.py"
                 elif matches(r"cylinder.*tube") or matches(r"tube"):
                      script_to_run = "catia_create_parts_dynamic_updated.py"
                 else:
                      # Default: Cylinder Rod (Solid)
                      script_to_run = "catia_create_parts_dynamic.py"
            
            elif matches(r"rect.*tube") or matches(r"rectangular.*tube"):
                 script_to_run = "catia_create_parts_dynamic_rectrod_updated.py"
            elif matches(r"rect.*rod") or matches(r"rectangular.*rod"):
                 script_to_run = "catia_create_parts_dynamic_rectrod.py"
            elif matches(r"cylinder.*tube") or matches(r"tube"):
                 script_to_run = "catia_create_parts_dynamic_updated.py"
            else:
                 # Default: Cylinder Rod (Solid) -> Use MULTIPART_SCRIPT with full flags
                 script_to_run = MULTIPART_SCRIPT
                 script_flags = flags
            
            # These specific scripts expect JSON file as first pos arg (if not --params)
            # Only override flags if we picked a legacy script
            if script_to_run != MULTIPART_SCRIPT:
                script_flags = [json_path]
        elif flags:
            if matches(r"baseplate"):
                 # Optimization result variants
                 if matches(r"rect.*tube") or matches(r"rectangular.*tube"):
                      script_to_run = "catia_create_parts_dynamic_rectrod_updated.py"
                 elif matches(r"rect.*rod") or matches(r"rectangular.*rod"):
                      script_to_run = "catia_create_parts_dynamic_rectrod.py"
                 elif matches(r"cylinder.*tube") or matches(r"tube"):
                      script_to_run = "catia_create_parts_dynamic_updated.py"
                 else:
                      # Default: Cylinder Rod (Solid)
                      script_to_run = "catia_create_parts_dynamic.py"
                 
                 script_flags = [flags[1]] if len(flags) > 1 else flags # Extract path from --params
            else:
                 script_to_run = MULTIPART_SCRIPT
                 script_flags = flags

    # D) Wheel
    elif matches(r"\b(wheel|rim)\b"):
        script_to_run = "car_wheel_rim_dynamic.py"
        script_flags = build_wheel_flags(command_raw)

    # E) Rib / Slot
    elif matches(r"(?:rib|slot)"):
        f, meta = build_flags_for_rib_slot({}, command_raw, base_dir)
        if f:
            script_to_run = RIB_SLOT_SCRIPT
            script_flags = f
            


    # F) L-Bracket
    elif is_l_bracket_command(command_raw):
         script_to_run = LBRAC_SCRIPT_NAME
         dims = extract_l_bracket_dims(command_raw)
         l1, l2 = dims if dims else (None, None)
         b_width = extract_value_for_keyword(command_raw, ["width", "w"]) or 20.0
         b_thick = extract_thickness(command_raw) or 5.0
         bend = extract_bend_radius(command_raw)
         holes = extract_block_holes(command_raw)
         
         script_flags = build_lbrac_flags(
             leg1=l1, leg2=l2, 
             extrude_len=b_width, 
             thick_top_offset=b_thick, 
             bend_radius=bend, 
             holes=holes
         )

    # G) Gear / Fixed Robust
    elif matches(r"\b(gear|instances)\b") and matches(r"\b(pocket|pad)\b"):
         script_to_run = "file_fixed_robust.py"
         
         # Inline Logic to extract parameters for file_fixed_robust.py 
         # (Replaces build_flags_for_fixed_robust to allow Modify/Use-Active)
         flags = []
         
         # Helper to extract value
         def get_val(text, patterns):
             for pat in patterns:
                 m = re.search(pat, text, re.IGNORECASE)
                 if m: return m.group(1)
             return None

         # Radius
         # Radius (Exclude "center hole/pocket" context)
         # Using negative lookbehind for 'center ' or 'hole ' is tricky with variable spacing.
         # Instead, we'll strip known 'center ...' phrases first or use a stricter regex.
         # Regex: Match radius/dia NOT preceded by "center " (approx)
         
         # Better approach: Extract specific features first (Center Hole), then check global?
         # But we iterate sequentially.
         # Let's use a regex that matches start of string or space, ignoring specific prefixes.
         
         # Filter out "center pocket diameter" from consideration for GLOBAL radius
         # We can simple check if the match is part of "center ...".
         # Or better: 
         def get_global_rad(text):
              # Remove "center" phrases temporarily
              tmp = re.sub(r"center\s*(?:pocket|hole)\s*(?:dia(?:meter)?|radius)\s*\d+(?:\.\d+)?", "", text, flags=re.IGNORECASE)
              tmp = re.sub(r"lug\s*(?:hole)?\s*(?:dia(?:meter)?|radius)\s*\d+(?:\.\d+)?", "", tmp, flags=re.IGNORECASE)
              return get_val(tmp, [r"radius\s*(\d+(\.\d+)?)", r"dia(?:meter)?\s*(\d+(\.\d+)?)"])

         rad = get_global_rad(command_raw)
         if rad:
             flags.append("--circle-radius")
             # If "diameter" keyword used in the MATCHED string part? 
             # get_val returns just the number. We need to know if it was diameter or radius.
             # Re-checking the temp string is safest.
             tmp_check = re.sub(r"center\s*(?:pocket|hole)\s*(?:dia(?:meter)?|radius)\s*\d+(?:\.\d+)?", "", command_raw, flags=re.IGNORECASE)
             is_diameter = re.search(r"dia(?:meter)?\s*" + re.escape(rad), tmp_check, re.IGNORECASE)
             
             val = float(rad)
             if is_diameter: val /= 2.0
             flags.append(str(val))

         # Pad Height
         ph = get_val(command_raw, [r"pad\s*height\s*(\d+(\.\d+)?)", r"height\s*(\d+(\.\d+)?)"])
         if ph:
             flags.append("--pad-height")
             flags.append(ph)

         # Pocket Depth
         pd = get_val(command_raw, [r"pocket\s*depth\s*(\d+(\.\d+)?)", r"depth\s*(\d+(\.\d+)?)"])
         if pd:
             flags.append("--pocket-depth")
             flags.append(pd)

         # Instances
         inst = get_val(command_raw, [r"instances\s*(\d+)", r"(\d+)\s*instances"])
         if inst:
             flags.append("--pattern-instances")
             flags.append(inst)

         # Center Hole
         ch = get_val(command_raw, [r"center\s*pocket\s*dia(?:meter)?\s*(\d+(\.\d+)?)", r"center\s*hole\s*dia(?:meter)?\s*(\d+(\.\d+)?)"])
         if ch:
             flags.append("--center-hole-dia")
             flags.append(ch)

         # Modify Mode
         if matches(r"\bmodify\b") or matches(r"\bupdate\b") or matches(r"\bchange\b"):
             flags.append("--use-active")

         script_flags = flags
         if not flags:
             # Fallback if inline extraction fails
             f, _ = build_flags_for_fixed_robust({}, command_raw)
             script_flags = f

    # X) Manifold Routing
    elif matches(r"\bmanifold\b"):
        script_to_run = "manifold_dynamic.py"
        # Extract params using the helper
        cfg = extract_all_manifold_params(command_raw)
        # Serialize to JSON for CLI
        import json
        json_params = json.dumps(cfg)
        script_flags = ["--params", json_params]

    # K) Unified Topology Routing (Priority: Plate > Disk)
    elif matches(r"\b(equidistant|diagonals?|perimeters?|circular topology|holes? on a \d+ mm diameter)\b") or matches(r"along\s+[xy]"):
        
        # 1. Plate Context (Stronger match if "plate"/"block" present)
        if contains_plate_context(command_raw):
             if matches(r"\bdiagonals?\b"):
                 script_to_run = "diagonal_topology_dynamic.py"
                 script_flags = build_topology_flags(command_raw, "diagonal", "plate")
             elif matches(r"\bperimeters?\b"):
                 script_to_run = "perimeter_topology_dynamic.py"
                 script_flags = build_topology_flags(command_raw, "perimeter", "plate")
             elif matches(r"\bcircular\b") or matches(r"\bdiameter circle\b"):
                 script_to_run = "circular_topology_dynamic.py"
                 script_flags = build_topology_flags(command_raw, "circular", "plate")
             else: # Default for plate + equidistant/linear
                 script_to_run = "equidistant_holes_dynamic.py"
                 script_flags = build_topology_flags(command_raw, "equidistant", "plate")

        # 2. Disk Context (Fallback if no Plate keywords, even if "dia" is present)
        elif contains_disk_context(command_raw):
             if matches(r"\bdiagonal\b"):
                 script_to_run = "diagonal_on_disk.py"
             elif matches(r"\bperimeter\b") or matches(r"around\s+perimeter"):
                 # Check for Squared Holes on Perimeter
                 if matches(r"square\s*holes?"):
                      script_to_run = "perimeter_SQURED_on_disk.py"
                 else:
                      script_to_run = "perimeter_on_disk.py"
             else:
                 script_to_run = "equidistant_on_disk.py"
             
             # Reuse disk flag builder since topologies on disk share similar flags
             script_flags = build_disk_flags(command_raw)

    # J) Optimization / RL Scripts
    elif matches(r"lightest\s+baseplate") and matches(r"cylinder|rectangle|rod|tube"):
         if matches(r"cylinder\s+rod"):
              script_to_run = "catia_create_parts_dynamic.py"
         elif matches(r"cylinder\s+tube"):
              script_to_run = "catia_create_parts_dynamic_updated.py"
         elif matches(r"rectangle\s+rod"):
              script_to_run = "catia_create_parts_dynamic_rectrod.py"
         elif matches(r"rectangle\s+tube"):
              script_to_run = "catia_create_parts_dynamic_rectrod_updated.py"
         script_flags = ["--cmd", command_raw]
    
    elif matches(r"wing\s+structure") or matches(r"optimize\s+wing"):
         script_to_run = "wing_structure_winglet_transparent.py"
         script_flags = ["--cmd", command_raw]

    elif matches(r"among\s+all\s+shapes") and matches(r"best\s+design"):
         # Default to base cylinder rod for now or a master script if one existed
         script_to_run = "catia_create_parts_dynamic.py" 
         script_flags = ["--cmd", command_raw]

    # K) Cylinder (Interactive / Robust)
    elif matches(r"^create\s+cylinder") or (matches(r"\bcylinder\b") and not matches(r"plate|block")):
         script_to_run = "file_fixed_robust.py"
         # Helper builds flags from text extraction if explicit dict is empty
         f, _ = build_flags_for_fixed_robust({}, command_raw)
         script_flags = f

    # L) Parametric Block
    elif contains_plate_context(command_raw) or matches(r"\d+x\d+x\d+"):
         # Extraction
         l_val = extract_block_length(command_raw)
         w_val = extract_block_width(command_raw)
         t_val = extract_thickness(command_raw)
         
         if l_val is None or w_val is None or t_val is None:
             lwt = extract_plate_LWT(command_raw)
             if isinstance(lwt, tuple) and len(lwt) == 3:
                 if l_val is None: l_val = lwt[0]
                 if w_val is None: w_val = lwt[1]
                 if t_val is None: t_val = lwt[2]

         holes = extract_block_holes(command_raw)
         
         if l_val and w_val and t_val:
             script_to_run = "Parametric_Block_Run.py"
             script_flags = build_block_flags(l_val, w_val, t_val, holes)

    return script_to_run, script_flags
