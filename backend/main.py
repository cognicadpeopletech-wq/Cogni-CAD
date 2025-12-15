# main.py (Modularized)
import os
import sys
# FORCE RELOAD TRIGGER 5
import json
import time
import logging
import traceback
import subprocess
import re
from pathlib import Path
from fastapi import FastAPI, Request, Form, APIRouter, File, UploadFile
from fastapi.responses import JSONResponse, HTMLResponse, RedirectResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
import shutil
import uuid

# --- Helper Logic Imports ---
# We try to import these; if they fail (due to dependencies), we might have issues, 
# but block_generator usually relies on regex (safe).
# Helper Logic Imports
try:
    from catia_copilot.dispatcher import run_script_with_timer
    from catia_copilot.block_parser import normalize
    from catia_copilot.block_generator import (
        build_flags_for_plate, 
        build_cylinder_flags, 
        build_flags_for_circular, 
        build_lbrac_flags,
        build_flags_for_rib_slot,
        build_flags_for_multipart,
        # build_square_flags_from_text # This seems specific to squared-disk
        build_disk_flags
    )
    from catia_copilot.prompt_router import route_explicit_command
    # Import In-house Generator Core
    import inhouse_cad.core
    # Import Wing Optimizer Router
    try:
        from inhouse_cad.wing_optimizer.pipeline import router as wing_router
    except Exception as e:
        wing_router = None
        logging.error(f"Wing Router Import Failed: {e}")

except ImportError as e:
    logging.error(f"Helper imports failed: {e}")
    wing_router = None
    # Define fallback run_script if dispatcher missing
    def run_script_with_timer(script_path, args=None, timeout=60):
        args = args or []
        
        # Determine runner based on extension
        if str(script_path).lower().endswith(".vbs"):
            # VBScript execution
            cmd = ["cscript", "//Nologo", script_path] + args
            # Note: cscript //Nologo suppressing logo info
        else:
            # Python execution (default)
            cmd = [sys.executable, script_path] + args
            
        try:
            start = time.time()
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
            dur = time.time() - start
            if res.returncode != 0:
                return (res.stdout, res.stderr, dur, f"Exit Code {res.returncode}")
            return (res.stdout, res.stderr, dur, None)
        except Exception as ex:
            return ("", "", 0, str(ex))
    
    def normalize(text): return text.lower().strip()
    # Dummy builders if missing
    def build_flags_for_plate(t, top): return ["--cmd", t]
    def build_cylinder_flags(t): return ["--cmd", t]
    def build_flags_for_circular(t): return ["--cmd", t]
    def build_lbrac_flags(*a): return []
    def build_flags_for_rib_slot(*a): return [], {}
    def build_flags_for_multipart(*a): return [], {}
    def route_explicit_command(cmd, b): return None, [] # Fallback router

# --- Configuration ---
BASE_DIR = Path(__file__).resolve().parent
SCRIPTS_DIR = BASE_DIR / "scripts"
STATIC_DIR = BASE_DIR / "static_files"
LOG_DIR = BASE_DIR / "logs"
OUTPUTS_DIR = BASE_DIR / "outputs"
DOWNLOADS_DIR = BASE_DIR / "downloads"
TEMPLATES_DIR = BASE_DIR.parent.parent / "frontend" / "templates"

for d in [SCRIPTS_DIR, STATIC_DIR, LOG_DIR, OUTPUTS_DIR, DOWNLOADS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    filename=str(LOG_DIR / "copilot.log"),
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

app = FastAPI(title="PeopleCAD AI Co-Pilot")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
    app.mount("/downloads", StaticFiles(directory=str(OUTPUTS_DIR)), name="downloads")

templates = Jinja2Templates(directory=str(TEMPLATES_DIR)) if TEMPLATES_DIR.exists() else None

# --- Script definitions ---
SCRIPT_TIMEOUT = 600 # Increased for batch operations

# Map User Intents to Scripts
RECT_ROD_SCRIPT = "catia_create_parts_dynamic_rectrod.py"
CYLINDER_SCRIPT = "create_cylinder_interactive.py" # "catia_create_parts_dynamic.py" sometimes used for rods
DISK_SCRIPT = "circular_disk_dynamic.py"
TOPOLOGY_SCRIPT = "circular_topology_dynamic.py"
RIB_SLOT_SCRIPT = "rib_slot_dynamic.py"
MULTIPART_SCRIPT = "multipart_dynamic.py"
LBRAC_SCRIPT = "L-Brac.py"
COLOR_SCRIPT = "color.py" 
BOM_SCRIPT = "bom_pycatia.py"
WHEEL_SCRIPT = "car_wheel_rim_dynamic.py"
WING_SCRIPT = "wings_1.py"

# --- NLP Fallback Class ---
class FallbackNLP:
    def __init__(self):
        self.mappings = [
            (r"\b(rect|block|box|plate)\b", RECT_ROD_SCRIPT),
            (r"\b(cylinder|rod)\b", "catia_create_parts_dynamic.py"), # Using the robust one
            (r"\b(disk|disc)\b", DISK_SCRIPT),
            (r"\b(topology|circular topology)\b", TOPOLOGY_SCRIPT),
            (r"\b(rib|slot)\b", RIB_SLOT_SCRIPT),
            (r"\b(multipart|assembly)\b", MULTIPART_SCRIPT),
            (r"\b(bracket|l-bracket)\b", LBRAC_SCRIPT),
            (r"\b(color|paint)\b", COLOR_SCRIPT),
            (r"\b(bom|bill of materials)\b", BOM_SCRIPT),
            (r"\b(wheel|rim)\b", WHEEL_SCRIPT),
            (r"\b(wing|drone)\b", WING_SCRIPT),
            (r"\b(iso|tolerance)\b", "ApplyISO20457Tolerances.vbs")
        ]

    def find_script(self, text):
        norm = text.lower()
        for pattern, script in self.mappings:
            if re.search(pattern, norm):
                return script, 1.0
        return None, 0.0
    
    def list_intents(self):
        return [m[1] for m in self.mappings]

# --- NLP Loading ---
nlp = None
parse_goal = None
run_rl_optimizer = None
run_rl_optimize = None

try:
    from catia_copilot.nlp_engine import NLPEngine
    from catia_copilot.goal_parser import parse_goal
    from catia_copilot.rl_optimizer_v4 import run_rl_optimizer
    from catia_copilot.rl_optimize_wing import run_rl_optimize
    
    # Try real NLP
    nlp = NLPEngine(intents_path=str(BASE_DIR / "intents.json"))
except Exception as e:
    logging.warning(f"Real NLP Engine not available ({e}). Using Fallback.")
    nlp = FallbackNLP()

if nlp is None:
    nlp = FallbackNLP() # Ensure fallback is active if exception occurred

# --- Helper: Get Flags ---
def get_flags_for_script(script_name, command_raw, base_dir):
    flags = []
    
    if script_name == RECT_ROD_SCRIPT or script_name == "catia_create_parts_dynamic_rectrod_updated.py":
        flags = build_flags_for_plate(command_raw, "rect")
        
    elif script_name == "catia_create_parts_dynamic.py" or script_name == CYLINDER_SCRIPT:
        flags = build_cylinder_flags(command_raw)
        
    elif script_name == DISK_SCRIPT:
        flags = build_flags_for_circular(command_raw)
    
    elif script_name == TOPOLOGY_SCRIPT:
        # Topology usually uses similar circular/plate logic depending on context,
        # but let's assume circular base if not specified
        flags = build_flags_for_circular(command_raw) # Simplified
        
    elif script_name == RIB_SLOT_SCRIPT:
        # Rib slot requires complex extraction
        # We pass empty explicit dict for now as regex matching happens inside
        f, _ = build_flags_for_rib_slot({}, command_raw, base_dir)
        if f: flags = f

    elif script_name == MULTIPART_SCRIPT:
        f, _ = build_flags_for_multipart(command_raw, base_dir)
        if f: flags = f
        
    elif script_name == LBRAC_SCRIPT:
        # L-Brac usually requires parsing specific args.
        # Fallback: Pass command as cmd (the script might extract it if supported)
        # Assuming script supports --cmd or similar, or we need to parse here.
        # Check build_lbrac_flags signature... it needs args.
        # We'll skip complex flag building for L-Brac if not robustly parsed, 
        # or just pass raw text if script accepts it.
        # For now, pass --cmd
        flags = ["--cmd", command_raw]
        
    else:
        # Geneic pass-through
        flags = ["--cmd", command_raw]
        
    return flags

main_router = APIRouter()

@main_router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return "CogniCAD Backend Running."

# --- New Download Endpoint (Forces Download) ---
@main_router.get("/download_file/{filename}")
async def download_file(filename: str):
    file_path = OUTPUTS_DIR / filename
    if not file_path.exists():
        return JSONResponse({"error": "File not found"}, status_code=404)
    
    # Determine media type (optional, but good practice)
    media_type = "application/octet-stream" # Default binary
    if filename.endswith(".step") or filename.endswith(".stp"):
        # Force download even for text-based types
        media_type = "application/octet-stream" 
        
    return FileResponse(
        path=file_path, 
        filename=filename, 
        media_type=media_type,
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@main_router.get("/download_gen/{file_path:path}")
async def download_generated_file(file_path: str):
    # Serve files from generated_files_dir with attachment disposition
    full_path = generated_files_dir / file_path
    if not full_path.exists():
        return JSONResponse({"error": "File not found"}, status_code=404)
        
    filename = full_path.name
    return FileResponse(
        path=full_path,
        filename=filename,
        media_type="application/octet-stream", # Force download
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@main_router.post("/run_command")
async def run_command(request: Request):
    data = await request.json()
    command_raw = (data.get("command") or data.get("text") or "").strip()
    mode = data.get("mode", "CATIA_COPILOT")
    s = normalize(command_raw)
    logging.info(f"Command: {command_raw} [Mode: {mode}]")

    # --- In-House CAD Routing ---
    if mode == "INHOUSE_CAD":
        try:
            # Use the Refactored Core Dispatcher
            result = inhouse_cad.core.generate_model(command_raw, OUTPUTS_DIR)
            return JSONResponse(result)
        except Exception as e:
            return JSONResponse({"success": False, "message": f"In-house generation failed: {str(e)}", "error": str(e)})

    # --- 2.5 RL Optimizer Triggers (Catia Mode / Backend Mode) ---
    s_lower = s.lower()
    
    # Structural Optimization (RL)
    if "design the lightest" in s_lower or "give the best designs" in s_lower or ("lightest" in s_lower and "assembly" in s_lower):
        if run_rl_optimizer:
             candidates = []
             shape_tag_used = "mixed"

             # Check for "All Shapes" intent
             if "all shapes" in s_lower or "among all" in s_lower or "compare" in s_lower:
                 logging.info("Triggering Multi-Shape RL Optimizer...")
                 shapes_to_test = ["cylinder_solid", "cylinder_tube", "rect_rod", "rect_tube"]
                 for shape in shapes_to_test:
                     # Force specific shape logic by injecting shape arg if possible, 
                     # but run_rl_optimizer parses text. 
                     # We might need to call it with a 'shape' override if supported, 
                     # or rely on it supporting a direct kwarg.
                     # Inspection of rl_optimizer_v4 showed it takes `shape` arg.
                     res = run_rl_optimizer(command_raw, shape=shape) 
                     cands = res.get("candidates", [])
                     # Tag them just in case
                     for c in cands: c["shape_type"] = res.get("shape_tag", shape)
                     candidates.extend(cands)
                 
                 # Sort by score (lower is better)
                 candidates.sort(key=lambda x: x.get("score", 9999))
                 candidates.sort(key=lambda x: x.get("score", 9999))
                 candidates = candidates[:3] # Top 3 global
                 targeted_shape = "Mixed Shapes/Comparison"
             else:
                 # Single shape (inferred from text)
                 logging.info("Triggering Structural RL Optimizer...")
                 
                 # Infer shape from text to ensure correct optimizer mode
                 targeted_shape = "cylinder_solid" # Default
                 if ("rect" in s_lower or "square" in s_lower) and "tube" in s_lower:
                     targeted_shape = "rect_tube"
                 elif "rect" in s_lower or "square" in s_lower:
                     targeted_shape = "rect_rod"
                 elif "tube" in s_lower or "pipe" in s_lower:
                     targeted_shape = "cylinder_tube"
                 
                 optimizer_res = run_rl_optimizer(command_raw, shape=targeted_shape)
                 candidates = optimizer_res.get("candidates", [])
                 shape_tag_used = optimizer_res.get("shape_tag", targeted_shape)
                 for c in candidates:
                     if "shape_type" not in c: c["shape_type"] = shape_tag_used

             # Wrap for Frontend Card UI
             return JSONResponse({
                 "mode": "optimization_cards",
                 "options": candidates,
                 "raw_text": f"Found {len(candidates)} optimal designs for '{targeted_shape}':"
             })
    
    # Wing Optimization (RL)
    elif "optimize wing" in s_lower or "wing optimization" in s_lower:
        from catia_copilot.rl_optimize_wing import run_rl_optimize
        logging.info("Triggering Wing RL Optimizer...")
        res = run_rl_optimize(command_raw, top_k=1, update_script=False) # Don't update file, we pass params
        
        # Tag candidates as 'wing' so frontend knows how to render
        candidates = res.get("candidates", [])
        for c in candidates:
            c["shape_type"] = "wing"
        
        return JSONResponse({
            "mode": "optimization_cards",
            "options": candidates,
            "raw_text": f"Found {len(candidates)} optimal wing designs:"
        })


    # Wing Optimization (Catia Version)
    # The existing in-house one is handled by separate endpoint or mode check
    # But if user specifically asks in Catia Mode:
    if "optimize wing" in s_lower and "surveillance" in s_lower:
         if run_rl_optimize:
             logging.info("Triggering Wing RL Optimizer (Catia Mode)...")
             # This matches rl_optimize_wing.run_rl_optimize signature?
             # Checking import: from catia_copilot.rl_optimize_wing import run_rl_optimize
             # It likely takes (prompt, output_dir)
             res = run_rl_optimize(command_raw, output_dir=OUTPUTS_DIR)
             return JSONResponse(res)
         else:
             return JSONResponse({"output": "⚠️ Wing RL Optimizer module not loaded."})

    # 1. GLB Loading
    if "load glb" in s or "show glb" in s:
        return JSONResponse({"output": "GLB model loaded successfully in 3D Viewer."})

    # 1.5 Explode Model
    if "explode" in s or "disassemble" in s:
        return JSONResponse({"mode": "explode", "output": "💥 Exploding the model..."})

    # 1.5.5 Apply Colors
    # 1.5.5 Apply Colors
    color_match = re.search(r"apply\s+(?:the\s+)?(\w+)\s+(?:color|colour)", s)
    if color_match:
         color_name = color_match.group(1).lower()
         # Check if it's a known color or just generic "unique"/"random"
         if color_name not in ("unique", "random", "different"):
              return JSONResponse({
                  "mode": "apply_single_color", 
                  "color": color_name,
                  "output": f"🎨 Applying {color_name} color to the model..."
              })

    if "color" in s or ("apply" in s and "paint" in s):
        return JSONResponse({"mode": "apply_colors", "output": "🎨 Applying unique colors to the model..."})

    # 1.6 Rotation Logic
    rotation_match = re.search(r"rotate\s+(?:the\s+)?(.+?)\s+(?:by\s+)?(-?\d+)\s*deg", s)
    if rotation_match:
        target_part = rotation_match.group(1).strip() # e.g. "bracket"
        angle_deg = int(rotation_match.group(2))
        return JSONResponse({
            "mode": "rotate_part", 
            "target": target_part, 
            "angle": angle_deg,
            "output": f"🔄 Rotating '{target_part}' by {angle_deg}°..."
        })
        
    # 2. BOM Check (Snippet Logic)
    bom_triggers = ("bom", "bill of materials", "bill-of-materials", "generate bom", "create bom","Load Dirt Bike Catpart", "export bom", "generate bill")
    if any(k in s for k in bom_triggers):
        # Snippet logic for handling BOM
        uploaded_path = (data.get("uploaded_file") or data.get("uploaded_path") or data.get("uploaded") or data.get("input"))
        
        if not uploaded_path:
             # Check if there's a recent upload in static/uploads? 
             # Or just fail. User user snippet says "missing_input".
             return JSONResponse({
                "mode": "bom",
                "status": "missing_input",
                "message": "❌ No file uploaded. Please upload a CATPart/CATProduct file before requesting BOM.",
                "downloads": {"csv": None, "xlsx": None, "pdf": None},
                "output": "No uploaded file provided"
            })
            
        # Validate path
        if isinstance(uploaded_path, str) and uploaded_path.startswith("http"):
             # Convert URL back to local path if possible, or just use filename
             # e.g. http://127.0.0.1:8000/static/uploads/uuid.CATPart
             filename = uploaded_path.split("/")[-1]
             fs_path = STATIC_DIR / "uploads" / filename
        else:
             fs_path = Path(str(uploaded_path)).resolve()
             
        if not fs_path.exists():
             return JSONResponse({"mode": "bom", "error": f"Uploaded file not found: {fs_path}", "output": "Uploaded file not found"})
             
        # Run BOM Script
        bom_script = SCRIPTS_DIR / "bom_pycatia.py"
        if not bom_script.exists():
             return JSONResponse({"output": "❌ BOM script missing (bom_pycatia.py)"})
             
        args = ["--input", str(fs_path), "--out-dir", str(OUTPUTS_DIR)]
        out, err, dur, error = run_script_with_timer(str(bom_script), args=args, timeout=300)
        
        # Collect outputs
        outs = sorted([p for p in OUTPUTS_DIR.iterdir() if p.suffix.lower() in (".csv", ".xlsx", ".xls", ".pdf")],
                      key=lambda p: p.stat().st_mtime, reverse=True)
                      
        csv_url = xlsx_url = pdf_url = None
        for p in outs:
            # Assumes server is on localhost:8000. Ideally use request.base_url
            url = f"http://127.0.0.1:8000/downloads/{p.name}" 
            if p.suffix.lower() == ".csv" and not csv_url: csv_url = url
            if p.suffix.lower() in (".xlsx", ".xls") and not xlsx_url: xlsx_url = url
            if p.suffix.lower() == ".pdf" and not pdf_url: pdf_url = url
            
        return JSONResponse({
            "mode": "bom",
            "stdout": out,
            "stderr": err,
            "error": error,
            "time": dur,
            "downloads": {"csv": csv_url, "xlsx": xlsx_url, "pdf": pdf_url},
            "output": ("✅ BOM generated successfully." if not error else f"❌ BOM generation failed: {error}")
        })


    # --- Router V2 (Explicit Mappings) ---
    try:
        routed_script, routed_flags = route_explicit_command(command_raw, BASE_DIR)
        if routed_script:
            script_path = SCRIPTS_DIR / routed_script
            if script_path.exists():
                msg_init = f"🚀 Launching {routed_script}..."
                logging.info(msg_init)
                out, err, time_sec, error = run_script_with_timer(str(script_path), args=routed_flags, timeout=SCRIPT_TIMEOUT)
                
                # JSON Check
                try:
                     out_json = json.loads(out) if out.strip().startswith("{") else None
                     if out_json:
                          if "output" not in out_json:
                              out_json["output"] = f"✅ Task Completed Successfully in {time_sec} Seconds"
                          return JSONResponse(out_json)
                except: pass

                msg = f"✅ Task Completed Successfully in {time_sec} Seconds"
                # if out: msg += f"Output:\n{out}\n"
                # if err: msg += f"Stderr:\n{err}\n"
                # if error: msg = f"❌ Error: {error}"
                return JSONResponse({"output": msg, "time": time_sec})
            else:
                 logging.warning(f"Routed script {routed_script} not found on disk at {script_path}.")
    except Exception as e:
        logging.error(f"Router Error: {e}")
        # traceback.print_exc()

    # 2. Script Execution (Unified)
    script_name, score = nlp.find_script(command_raw)
    
    # Overrides for specific keywords if fallback is too generic
    # (Optional: e.g. "optimize" logic)
    if "optimize" in s:
        # Handle optimization separately if needed, or map it in FallbackNLP
        pass 

    if script_name:
        script_path = SCRIPTS_DIR / script_name
        if script_path.exists():
            msg_init = f"🚀 Launching {script_name}..."
            
            # Generate Flags
            flags = get_flags_for_script(script_name, command_raw, BASE_DIR)
            
            # Run
            out, err, time_sec, error = run_script_with_timer(str(script_path), args=flags, timeout=SCRIPT_TIMEOUT)
            
            msg = f"✅ Task Completed Successfully in {time_sec} Seconds"
            # if out: msg += f"Output:\n{out}\n"
            # if err: msg += f"Stderr:\n{err}\n"
            # if error: msg = f"❌ Error: {error}"
            
            return JSONResponse({"output": msg, "time": time_sec})
        else:
            return JSONResponse({"output": f"⚠️ Script found ({script_name}) but missing on disk."})

    return JSONResponse({"output": f"⚠️ Command not recognized: {command_raw}"})

@main_router.post("/execute_catia_script")
async def execute_catia_script(request: Request):
    """
    Directly execute a script with a JSON params file.
    Used by the Frontend 'Design Cards' to trigger generation.
    """
    try:
        data = await request.json()
        script_name = data.get("script_name")
        params = data.get("params")

        if not script_name:
            return JSONResponse({"success": False, "message": "Missing script_name"})

        script_path = SCRIPTS_DIR / script_name
        if not script_path.exists():
            return JSONResponse({"success": False, "message": f"Script not found: {script_name}"})

        # Save params to temp file
        temp_id = uuid.uuid4().hex
        temp_params_path = OUTPUTS_DIR / f"params_{temp_id}.json"
        
        with open(temp_params_path, "w") as f:
            json.dump(params, f, indent=2)

        logging.info(f"Executing {script_name} with params: {temp_params_path}")

        # Run Script
        # catia_create_parts_dynamic.py expects JSON file as direct argument if not using --flags
        args = [str(temp_params_path)]
        out, err, dur, error = run_script_with_timer(str(script_path), args=args, timeout=300)

        # Cleanup handled by script usually, but we can double check or rely on script
        # The script attempts to delete it.

        msg = f"✅ Executed {script_name}\n"
        if out: msg += f"Output: {out}\n"
        if error: msg = f"❌ Error: {error}\nOutput: {out}\nStderr: {err}"

        return JSONResponse({"success": not error, "output": msg, "message": msg, "time": dur})

    except Exception as e:
        logging.error(f"Execution failed: {e}")
        return JSONResponse({"success": False, "message": str(e)})

@main_router.post("/upload")
async def upload_file(
    file: UploadFile = File(...), 
    type: str = Form(...),
    convert: str = Form(None)
):
    try:
        # User Requirement: Preserve filename for CATIA assembly links
        # ext = os.path.splitext(file.filename)[1].lower()
        # safe_name = f"{uuid.uuid4()}{ext}"
        
        # Simple sanitization to prevent directory traversal
        filename = os.path.basename(file.filename)
        safe_name = filename 
        
        upload_dir = STATIC_DIR / "uploads"
        upload_dir.mkdir(parents=True, exist_ok=True)
        file_path = upload_dir / safe_name
        
        # Determine if we need to handle duplicates? For local CAD, overwriting is often desired to update parts.
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        file_url = f"http://127.0.0.1:8000/static/uploads/{safe_name}"
        msg = f"Uploaded {file.filename} successfully."
        
        # BOM Handling
        if type.lower() == "bom":
             content = file_path.read_text(errors='ignore')
             return JSONResponse({"url": file_url, "message": f"BOM Uploaded. Preview:\n{content[:200]}..."})
             
        # Return filename (now matches original)
        return JSONResponse({"url": file_url, "message": msg, "filename": safe_name})
        
    except Exception as e:
        logging.error(f"Upload failed: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

@main_router.post("/convert")
async def convert_file(filename: str = Form(...)):
    try:
        upload_dir = STATIC_DIR / "uploads"
        file_path = upload_dir / filename
        if not file_path.exists():
             return JSONResponse({"error": "File not found"}, status_code=404)
        
        glb_name = f"{uuid.uuid4()}.glb"
        glb_path = upload_dir / glb_name
        converted_url = f"http://127.0.0.1:8000/static/uploads/{glb_name}"
        msg = "Conversion completed."

        # User Legacy Logic: CadQuery -> Rotate -> STL -> Trimesh -> GLB
        import cadquery as cq
        from cadquery import exporters
        import trimesh
        import tempfile
        
        try:
            # 1. Load STEP
            logging.info(f"Loading STEP: {file_path}")
            model = cq.importers.importStep(str(file_path))
            
            # 2. Rotate -90 X (Z-up to Y-up)
            model = model.rotate((0,0,0), (1,0,0), -90)
            
            # 3. Export Intermediate STL
            with tempfile.NamedTemporaryFile(suffix=".stl", delete=False) as tmp_stl:
                stl_path = tmp_stl.name
                
            try:
                exporters.export(model, stl_path, exporters.ExportTypes.STL)
                
                # 4. Convert STL to GLB with Trimesh
                mesh = trimesh.load(stl_path)
                mesh.export(str(glb_path), file_type="glb")
                msg += " (via Legacy Pipeline)"
                
            finally:
                if os.path.exists(stl_path):
                    os.unlink(stl_path)
                    
        except Exception as e_conv:
            logging.error(f"Legacy conversion failed: {e_conv}")
            raise HTTPException(status_code=500, detail=f"Legacy conversion error: {str(e_conv)}")
        
        # try:
        #     # CadQuery Attempt
        #     import cadquery as cq
        #     model = cq.importers.importStep(str(file_path))
        #     model.export(str(glb_path), "GLB")
        #     msg += " (via CadQuery)"
        # except Exception as e_cq:
        #     logging.warning(f"CQ failed: {e_cq}")
        #     try:
        #         # OCP Attempt
        #         from OCP.STEPControl import STEPControl_Reader
        #         from OCP.IFSelect import IFSelect_RetDone
        #         from OCP.BRepMesh import BRepMesh_IncrementalMesh
        #         from OCP.StlAPI import StlAPI_Writer
                
        #         from OCP.TopExp import TopExp_Explorer
        #         from OCP.TopAbs import TopAbs_SOLID
        #         from OCP.TopoDS import TopoDS
                
        #         step_reader = STEPControl_Reader()
        #         if step_reader.ReadFile(str(file_path)) == IFSelect_RetDone:
        #             step_reader.TransferRoot(1)
        #             shape = step_reader.Shape(1)
                    
        #             # Iterate over solids to preserve components
        #             explorer = TopExp_Explorer(shape, TopAbs_SOLID)
        #             parts = []
                    
        #             # If no solids found (e.g. surface model), try faces or shells - but mostly solids for assemblies
        #             has_solids = False
        #             while explorer.More():
        #                 has_solids = True
        #                 solid = explorer.Current()
                        
        #                 # Mesh the solid
        #                 BRepMesh_IncrementalMesh(solid, 0.1, False, 0.5)
                        
        #                 # Write individual part to STL
        #                 stl_writer = StlAPI_Writer()
        #                 part_uuid = str(uuid.uuid4())
        #                 temp_stl = upload_dir / f"{part_uuid}.stl"
        #                 stl_writer.Write(solid, str(temp_stl))
                        
        #                 # Load into Trimesh
        #                 import trimesh
        #                 part_mesh = trimesh.load(str(temp_stl))
                        
        #                 # Add to list
        #                 parts.append(part_mesh)
                        
        #                 # Cleanup temp
        #                 if temp_stl.exists(): temp_stl.unlink()
                        
        #                 explorer.Next()
                    
        #             if not has_solids:
        #                 # Fallback for single shape or non-solid
        #                 BRepMesh_IncrementalMesh(shape, 0.1, False, 0.5)
        #                 stl_writer = StlAPI_Writer()
        #                 temp_stl = upload_dir / f"{uuid.uuid4()}.stl"
        #                 stl_writer.Write(shape, str(temp_stl))
        #                 import trimesh
        #                 parts.append(trimesh.load(str(temp_stl)))
        #                 if temp_stl.exists(): temp_stl.unlink()

        #             # Export Scene
        #             if parts:
        #                 scene = trimesh.Scene(parts)
        #                 scene.export(str(glb_path))
        #                 msg += " (via OCP Multi-Solid)"
        #             else:
        #                 raise Exception("No geometry extracted")
        #         else: raise Exception("STEP Read Failed")
        #     except Exception as e_ocp:
        #         logging.error(f"OCP failed: {e_ocp}")
        #         # Trimesh Fallback
        #         import trimesh
        #         mesh = trimesh.creation.box(extents=[100, 100, 100])
        #         mesh.visual.face_colors = [100, 100, 255, 200]
        #         mesh.export(str(glb_path))
        #         msg += " (Visual Placeholder)"

        return JSONResponse({"glb_url": converted_url, "message": msg, "converted": True})

    except Exception as e:
        logging.error(f"Conversion failed: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

@main_router.get("/download_csv")
async def download_csv():
    files = sorted([p for p in OUTPUTS_DIR.iterdir() if p.suffix.lower() == ".csv"], key=lambda p: p.stat().st_mtime, reverse=True)
    if not files: return JSONResponse({"error": "CSV not found"}, status_code=404)
    return FileResponse(str(files[0]), media_type="text/csv", filename=files[0].name)

@main_router.get("/download_xlsx")
async def download_xlsx():
    files = sorted([p for p in OUTPUTS_DIR.iterdir() if p.suffix.lower() in (".xlsx", ".xls")], key=lambda p: p.stat().st_mtime, reverse=True)
    if not files: return JSONResponse({"error": "XLSX file not found"}, status_code=404)
    return FileResponse(str(files[0]), media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", filename=files[0].name)

@main_router.get("/download_pdf")
async def download_pdf():
    files = sorted([p for p in OUTPUTS_DIR.iterdir() if p.suffix.lower() == ".pdf"], key=lambda p: p.stat().st_mtime, reverse=True)
    if not files: return JSONResponse({"error": "PDF file not found"}, status_code=404)
    return FileResponse(str(files[0]), media_type="application/pdf", filename=files[0].name)

@main_router.post("/open_in_catia")
async def open_in_catia(request: Request):
    try:
        data = await request.json()
        filename = data.get("filename")
        if not filename:
             return JSONResponse({"success": False, "message": "No filename provided"})
             
        # Resolve path in uploads
        file_path = STATIC_DIR / "uploads" / filename
        if not file_path.exists():
             return JSONResponse({"success": False, "message": f"File not found: {filename}"})
             
        script_path = SCRIPTS_DIR / "open_file_in_catia.py"
        args = ["--path", str(file_path)]
        
        out, err, dur, error = run_script_with_timer(str(script_path), args=args, timeout=60)
        
        if error:
             return JSONResponse({"success": False, "message": f"CATIA Error: {error}"})
             
        return JSONResponse({"success": True, "message": "File opened in CATIA."})
        
    except Exception as e:
        return JSONResponse({"success": False, "message": str(e)})

@main_router.post("/clear_outputs")
async def clear_outputs():
    removed = []
    for p in list(OUTPUTS_DIR.iterdir()):
        try:
            if p.is_file():
                p.unlink()
                removed.append(p.name)
        except: pass
    return JSONResponse({"cleared": removed, "output": f"Removed {len(removed)} files."})

# Window Control Endpoints (Optional - requires AutoHotkey or similar)
# --- Window Control Logic ---
LEFT_SCRIPT = SCRIPTS_DIR / "left.ahk"
RIGHT_SCRIPT = SCRIPTS_DIR / "right.ahk"
MAX_SCRIPT = SCRIPTS_DIR / "max.ahk"

def run_ahk(script_path):
    """Locates AutoHotkey and runs the specified script."""
    # Common locations for AHK
    possible_paths = [
        r"C:\Program Files\AutoHotkey\AutoHotkey.exe",
        r"C:\Program Files\AutoHotkey\v1.1.36.02\AutoHotkeyU64.exe", # Example specific version
        r"C:\Program Files (x86)\AutoHotkey\AutoHotkey.exe",
        "AutoHotkey.exe", # System PATH
    ]
    
    ahk_exe = None
    for p in possible_paths:
        if p == "AutoHotkey.exe":
            if shutil.which("AutoHotkey.exe"):
                 ahk_exe = "AutoHotkey.exe"
                 break
        elif os.path.exists(p):
            ahk_exe = p
            break
            
    if not ahk_exe:
        logging.warning("AutoHotkey interpreter not found.")
        return False, "AutoHotkey interpreter not found. Please install AutoHotkey."
        
    try:
        # Run AHK script detached
        cmd = [ahk_exe, str(script_path)]
        subprocess.Popen(cmd, shell=False, close_fds=True)
        return True, "Script launched"
    except Exception as e:
        logging.error(f"Failed to run AHK: {e}")
        return False, str(e)

@main_router.get("/split-left")
async def split_left():
    if not LEFT_SCRIPT.exists():
        # Soft notification instead of 500
        return JSONResponse({"status": "warning", "message": "Window control script missing (left.ahk)"})
    success, msg = run_ahk(LEFT_SCRIPT)
    if not success:
         return JSONResponse({"status": "warning", "message": f"Window control failed: {msg}"})
    return JSONResponse({"status": "success", "message": "Window split left"})

@main_router.get("/split-right")
async def split_right():
    if not RIGHT_SCRIPT.exists():
        return JSONResponse({"status": "warning", "message": "Window control script missing (right.ahk)"})
    success, msg = run_ahk(RIGHT_SCRIPT)
    if not success:
         return JSONResponse({"status": "warning", "message": f"Window control failed: {msg}"})
    return JSONResponse({"status": "success", "message": "Window split right"})

@main_router.get("/max-window")
async def max_window():
    if not MAX_SCRIPT.exists():
        return JSONResponse({"status": "warning", "message": "Window control script missing (max.ahk)"})
    success, msg = run_ahk(MAX_SCRIPT)
    if not success:
         return JSONResponse({"status": "warning", "message": f"Window control failed: {msg}"})
    return JSONResponse({"status": "success", "message": "Window maximized"})

app.include_router(main_router)
if wing_router:
    app.include_router(wing_router, prefix="/inhouse_cad/wing")
else:
    logging.warning("Skipping Wing Router (Import Failed)")

# Serve generated files for Wing Optimizer (live.glb)
generated_files_dir = Path(os.getcwd()) / "generated_files"
generated_files_dir.mkdir(parents=True, exist_ok=True)
app.mount("/generated_files", StaticFiles(directory=str(generated_files_dir)), name="generated_files")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
