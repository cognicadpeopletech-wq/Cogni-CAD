# main.py (Modularized)
import os
import sys
import json
import time
import logging
import traceback
from pathlib import Path
from fastapi import FastAPI, Request, Form, APIRouter, File, UploadFile
from fastapi.responses import JSONResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
import shutil
import uuid
import re


# --- New Module Imports ---
from nlp_engine import NLPEngine
from goal_parser import parse_goal
from rl_optimizer_v4 import run_rl_optimizer
from rl_optimize_wing import run_rl_optimize

# Block & Dispatcher modules
from block_parser import (
    normalize, _normalize_short, detect_topology_and_mode,
    contains_plate_context, extract_iso_class, extract_l_bracket_dims,
    extract_block_width, extract_thickness, extract_bend_radius, extract_block_holes,
    is_l_bracket_command, contains_disk_context, extract_block_length,
    extract_plate_LWT, extract_value_for_keyword
)
from block_generator import (
    build_flags_for_rib_slot, build_flags_for_multipart, choose_script_and_tag,
    normalize_candidate_for_ui, build_square_flags_from_text, build_square_flags_from_array,
    build_topology_flags, build_coord_flags, build_cylinder_flags, build_flags_for_plate,
    build_block_flags, build_lbrac_flags, build_flags_for_circular, build_disk_flags
)
from dispatcher import (
    run_script_with_timer, safe_run_script, run_rib_multipart, IS_WINDOWS
)

# --- Configuration ---
BASE_DIR = Path(__file__).resolve().parent
SCRIPTS_DIR = BASE_DIR / "scripts"
STATIC_DIR = BASE_DIR / "static_files"
LOG_DIR = BASE_DIR / "logs"
OUTPUTS_DIR = BASE_DIR / "outputs"
DOWNLOADS_DIR = BASE_DIR / "downloads"

# Pointing to frontend templates if backend needs to serve them (Fallback)
TEMPLATES_DIR = BASE_DIR.parent.parent / "frontend" / "templates"

# Create dirs if missing
for d in [SCRIPTS_DIR, STATIC_DIR, LOG_DIR, OUTPUTS_DIR, DOWNLOADS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    filename=str(LOG_DIR / "copilot.log"),
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

app = FastAPI(title="CogniCAD AI Co-Pilot")

# CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

templates = Jinja2Templates(directory=str(TEMPLATES_DIR)) if TEMPLATES_DIR.exists() else None

# --- Constants & Script Names ---
SCRIPT_TIMEOUT = 60
RIB_MULTIPART_TIMEOUT = 120

# Script filenames (Assumed to be in scripts/)
CYLINDER_ROD_SCRIPT = "catia_create_parts_dynamic.py"
CYLINDER_TUBE_SCRIPT = "catia_create_parts_dynamic_updated.py"
RECT_ROD_SCRIPT = "catia_create_parts_dynamic_rectrod.py"
RECT_TUBE_SCRIPT = "catia_create_parts_dynamic_rectrod_updated.py"
DYNAMIC_SCRIPT = CYLINDER_ROD_SCRIPT
WING_SCRIPT_NAME = "wings_1.py" # User listed this
LBRAC_SCRIPT_NAME = "L-Brac.py" 
COLOR_SCRIPT_NAME = "color.py"
ISO_20457_SCRIPT_NAME = "ApplyISO20457Tolerances.vbs"
ISO_2768_SCRIPT_NAME = "apply_general_tolerances_ISO2768.vbs"
MULTIPART_SCRIPT = "multipart_dynamic.py"
RIB_SLOT_SCRIPT = "rib_slot_dynamic.py"
SCRIPT_SQUARED = "circular_squared_disk.py"
SCRIPT_DISK = "circular_disk_dynamic.py" # Placeholder
SCRIPT_CYLINDER = "create_cylinder_interactive.py" 
SCRIPT_CIRCULAR = "circular_topology_dynamic.py"

# --- NLP Engine ---
nlp = None
try:
    nlp = NLPEngine(intents_path=str(BASE_DIR / "intents.json"))
except Exception as e:
    logging.error(f"Failed to init NLP engine: {e}")

main_router = APIRouter()

@main_router.get("/", response_class=HTMLResponse)
async def index(request: Request, new_cap: str = None):
    if templates and (TEMPLATES_DIR / "index.html").exists():
        caps = nlp.list_intents() if nlp else []
        return templates.TemplateResponse("index.html", {"request": request, "capabilities": caps, "new_cap": new_cap})
    return "CogniCAD Backend Running. Use Frontend to interact."

@main_router.post("/run_command")
async def run_command(request: Request):
    data = await request.json()
    command_raw = (data.get("command") or data.get("text") or "").strip()
    s = normalize(command_raw)
    logging.info(f"Command: {command_raw}")

    # 1. GLB Loading
    if "load glb" in s or "show glb" in s:
        return JSONResponse({"output": "GLB model loaded successfully in 3D Viewer."})
        
# --- PROMPT ROUTER (Explicit Mappings) ---
def route_explicit_command(command_raw: str, base_dir: Path):
    s = normalize(command_raw)
    def matches(pattern): return re.search(pattern, s) is not None
    
    script_to_run = None
    script_flags = []
    
    # A) Color
    if matches(r"\b(color|paint|colour)\b"):
        script_to_run = COLOR_SCRIPT_NAME
        script_flags = ["--cmd", command_raw]
        
    # B) Load Latest / Persistent Workflow (High Priority)
    elif matches(r"load.*(?:current|existing|recent).*model"):
          script_to_run = "open_latest_file.py"
          script_flags = []
          
    # C) BOM
    elif matches(r"\b(bom|bill of materials)\b"):
        script_to_run = "bom_pycatia.py"
        script_flags = ["--cmd", command_raw]

    # C) Multipart (Plate + Cylinder)
    elif matches(r"(?:plate|block).*with.*(?:cylinder|rod)") or matches(r"(?:cylinder|rod).*on.*(?:plate|block)"):
        flags, params = build_flags_for_multipart(command_raw, base_dir)
        if flags:
            script_to_run = MULTIPART_SCRIPT
            script_flags = flags

    # D) Wheel
    elif matches(r"\b(wheel|rim)\b"):
        script_to_run = "car_wheel_rim_dynamic.py"
        script_flags = ["--cmd", command_raw]

    # E) Rib / Slot
    elif matches(r"\b(rib|slot)\b"):
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
         
         # Logic to extract parameters for file_fixed_robust.py since it expects flags, not natural language
         flags = []
         
         # Helper to extract value
         def get_val(text, patterns):
             for pat in patterns:
                 m = re.search(pat, text, re.IGNORECASE)
                 if m: return m.group(1)
             return None

         # Radius
         rad = get_val(command_raw, [r"radius\s*(\d+(\.\d+)?)", r"dia(?:meter)?\s*(\d+(\.\d+)?)"])
         if rad:
             # if detected diameter, divide by 2? Regex above captures number.
             # If "diameter 50" -> 50. If user meant radius, usually says radius.
             # Logic ambiguity: "diameter 16" implies diameter. 
             # file_fixed_robust expects --circle-radius.
             if re.search(r"dia(?:meter)?", command_raw, re.IGNORECASE) and not re.search(r"hole", command_raw, re.IGNORECASE): 
                  # heuristic: if "diameter" is used for the main body (not center hole), default logic might preserve it? 
                  # For robust script, --circle-radius is RADIUS.
                  # Let's assume explicit values:
                 pass
             flags.append("--circle-radius")
             flags.append(str(float(rad)) if "radius" in command_raw else str(float(rad)/2))

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
             # Fallback if extraction fails, though script might fail without params
             script_flags = ["--cmd", command_raw] # Keep original fallback just in case modified script uses it (it doesn't, but safety)



    # H) Circular Disk (Explicit Holes)
    elif (contains_disk_context(command_raw) and 
          (matches(r"at\s*\(\s*-?\d") or matches(r"holes?\s*at") or matches(r"\(\s*0\s*,\s*0\s*(?:,\s*\d+)?\s*\)")) and 
          not matches(r"\b(equidistant|diagonal|perimeter)\b") and
          not contains_plate_context(command_raw)): 
          
          if matches(r"square\s*holes?"):
              if matches(r"center.*circular.*hole") or matches(r"circular.*hole.*center"):
                  script_to_run = "perimeter_SQURED_on_disk.py"
              else:
                  script_to_run = "circular_squared_disk.py"
              script_flags = build_square_flags_from_text(command_raw)
          else:
              script_to_run = "circular_disk_dynamic.py"
              script_flags = build_disk_flags(command_raw)

    # I) Disk Topologies
    elif contains_disk_context(command_raw) and (matches(r"\b(equidistant|diagonal|perimeter)\b") or matches(r"along\s+x")):
         if matches(r"\bdiagonal\b"):
             script_to_run = "diagonal_on_disk.py"
         elif matches(r"\bperimeter\b") or matches(r"around\s+perimeter"):
             script_to_run = "perimeter_on_disk.py"
         else:
             script_to_run = "equidistant_on_disk.py"
         script_flags = build_flags_for_circular(command_raw)

    # J) Rectangle / Block Topologies
    elif contains_plate_context(command_raw) and matches(r"\b(diagonal|equidistant|perimeter|circular topology|10 holes on a \d+ mm diameter circle)\b"):
         if matches(r"\bdiagonal\b"):
             script_to_run = "diagonal_topology_dynamic.py"
         elif matches(r"\bperimeter\b"):
             script_to_run = "perimeter_topology_dynamic.py"
         elif matches(r"\bcircular\b") or matches(r"\bdiameter circle\b"):
             script_to_run = "circular_topology_dynamic.py"
         else:
              script_to_run = "equidistant_holes_dynamic.py"
         
         script_flags = build_flags_for_plate(command_raw, "topology")

    # K) Cylinder (Interactive)
    elif matches(r"^create\s+cylinder") or (matches(r"\bcylinder\b") and not matches(r"plate|block")):
         script_to_run = SCRIPT_CYLINDER
         script_flags = build_cylinder_flags(command_raw)

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

@main_router.post("/run_command")
async def run_command(request: Request):
    data = await request.json()
    command_raw = (data.get("command") or data.get("text") or "").strip()
    s = normalize(command_raw)
    logging.info(f"Command: {command_raw}")
    print(f"DEBUG: Received command: '{command_raw}'") # Debug print

    # 1. GLB Loading
    if "load glb" in s or "show glb" in s:
        return JSONResponse({"output": "GLB model loaded successfully in 3D Viewer."})
        
    # --- PROMPT ROUTER (Explicit Mappings) ---
    logging.info(f"Routing command: {command_raw}")
    try:
        script_to_run, script_flags = route_explicit_command(command_raw, BASE_DIR)
        logging.info(f"Router Result -> Script: {script_to_run}, Flags: {script_flags}")
    except Exception as e:
        logging.error(f"Router Exception: {e}")
        traceback.print_exc()
        script_to_run = None
    
    # Execute Routed Script
    if script_to_run:
        script_path = SCRIPTS_DIR / script_to_run
        logging.info(f"Checking script path: {script_path} (Exists: {script_path.exists()})")
        if script_path.exists():
            msg_init = f"🚀 Launching {script_to_run}..."
            logging.info(msg_init)
            out, err, time_sec, error = run_script_with_timer(str(script_path), args=script_flags, timeout=SCRIPT_TIMEOUT)
            
            # Special handling for JSON output (e.g. rib slot)
            try:
                 out_json = json.loads(out) if out.strip().startswith("{") else None
                 if out_json:
                      return JSONResponse(out_json)
            except: pass

            msg = f"✅ Executed Command Successfully\n"
            if out: msg += f"Output:\n{out}\n"
            if err: msg += f"Stderr:\n{err}\n"
            if error: msg = f"❌ Error: {error}"
            return JSONResponse({"output": msg, "time": time_sec})
        else:
            logging.warning(f"Routed script {script_to_run} not found.")

    # 2. NLP Script Lookup (High Priority)
    # ...

    return JSONResponse({
        "output": f"⚠️ Command not recognized: {command_raw}",
        "debug_router_script": str(script_to_run),
        "debug_router_flags": str(script_flags),
        "debug_script_exists": str((SCRIPTS_DIR / script_to_run).exists()) if script_to_run else "N/A",
        "debug_scripts_dir": str(SCRIPTS_DIR)
    })

    # 2. NLP Script Lookup (High Priority)


    # 2. NLP Script Lookup (High Priority)
    if nlp:
        script_name, score = nlp.find_script(command_raw)
        if script_name and score > 0.6: # Configurable threshold
            script_path = SCRIPTS_DIR / script_name
            if script_path.exists():
                # Notify User of CATIA Execution
                msg_init = f"🚀 Launching {script_name} in CATIA Application..."
                logging.info(msg_init)
                
                out, err, time_sec, error = run_script_with_timer(str(script_path), timeout=SCRIPT_TIMEOUT)
                msg = f"✅ Executed {script_name} in CATIA (Score: {score:.2f})\n"
                if out: msg += f"Output:\n{out}\n"
                if err: msg += f"Stderr:\n{err}\n"
                if error: msg = f"❌ Error: {error}"
                return JSONResponse({"output": msg, "time": time_sec})

    # 3. Optimization / Batch
    if "optimize" in s or "design" in s or "lightest" in s:

        # Check for wing optimization
        if "wing" in s:
            res = run_rl_optimize(command_text=command_raw, update_script=True, run_catia=False) # Frontend handles display
            return JSONResponse(res)
        
        # General RL optimization
        parsed = parse_goal(command_raw)
        shape_tag = "cylinder_solid" # Simplification for now, or detect
        res = run_rl_optimizer(command_raw, parsed_goal=parsed)
        return JSONResponse(res)

    # 4. Explicit Shapes (Cylinder, Square, etc via Flags)
    # Checking for specific keywords handled by block_generator
    chosen_script = None
    flags = []
    mode = "default"

    if "rib" in s or "slot" in s:
         # Simplified rib logic
         f, meta = build_flags_for_rib_slot({}, command_raw, BASE_DIR)
         if f:
             chosen_script = RIB_SLOT_SCRIPT
             flags = f
             mode = "rib_slot"

    # Fallback to topology detection
    if not chosen_script:
        topology, det_mode = detect_topology_and_mode(command_raw)
        mode = det_mode
        if mode == "cylinder":
            chosen_script = SCRIPT_CYLINDER
            flags = build_cylinder_flags(command_raw)
        elif mode == "square":
            chosen_script = SCRIPT_SQUARED
            flags = build_square_flags_from_text(command_raw)

    if chosen_script:
        script_path = SCRIPTS_DIR / chosen_script
        if not script_path.exists():
             pass
        else:
            out, err, time_sec, error = run_script_with_timer(str(script_path), args=flags, timeout=SCRIPT_TIMEOUT)
            result = f"Executed {chosen_script}\nTime: {time_sec}s"
            if error: result = f"Error: {error}"
            return JSONResponse({"output": result, "stdout": out, "stderr": err})

    return JSONResponse({"output": f"⚠️ Command not recognized: {command_raw}"})

@main_router.post("/upload")
async def upload_file(file: UploadFile = File(...), type: str = Form(...)):
    try:
        # Create a safe filename
        ext = os.path.splitext(file.filename)[1]
        safe_name = f"{uuid.uuid4()}{ext}"
        file_path = STATIC_DIR / "uploads" / safe_name
        
        # Ensure uploads dir exists
        (STATIC_DIR / "uploads").mkdir(parents=True, exist_ok=True)
        
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        file_url = f"http://127.0.0.1:8000/static/uploads/{safe_name}"
        
        if type.lower() == "step":
            # Placeholder for conversion logic
            # In a real scenario, we'd call a CLI tool here:
            # subprocess.run(["CADExchanger", "-i", str(file_path), "-o", str(file_path.with_suffix(".glb"))])
            # For now, we return a mock conversion message or simply the file if it's GLB
            return JSONResponse({
                "url": file_url, 
                "message": f"Uploaded STEP file: {file.filename}. Conversion to GLB started (Mock).",
                "converted": False
            })
            
        elif type.lower() == "bom":
             # Read content for BOM
             content = (STATIC_DIR / "uploads" / safe_name).read_text(errors='ignore')
             return JSONResponse({
                 "url": file_url,
                 "message": f"BOM Uploaded. First 100 chars: {content[:100]}..."
             })

        # Default (GLB or others)
        return JSONResponse({"url": file_url, "message": f"Uploaded {file.filename} successfully."})
        
    except Exception as e:
        logging.error(f"Upload failed: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


app.include_router(main_router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
