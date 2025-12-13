# main.py (FastAPI version)
import os
import re
import subprocess
import traceback
import logging
import time
from fastapi import FastAPI, Request, Form
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from nlp_engine import NLPEngine
from pathlib import Path

# ------------------------------------------------------
# Initialization
# ------------------------------------------------------
app = FastAPI(title="CATIA Copilot FastAPI")

BASE_SCRIPT_DIR = r"..\copilot\scripts"
FILENAME_SAFE_RE = re.compile(r"^[A-Za-z0-9._-]+$")
nlp = NLPEngine()

# ------------------------------------------------------
# Static + Templates setup
# ------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
static_path = str(BASE_DIR / "static")
templates_path = str(BASE_DIR / "templates")

app.mount("/static", StaticFiles(directory=static_path), name="static")
templates = Jinja2Templates(directory=templates_path)

# ------------------------------------------------------
# Copilot Capabilities
# ------------------------------------------------------
COPILOT_CAPABILITIES = [
    {"name": "Close All Files", "desc": "Instantly close every open CATIA document to reset your workspace."},
    {"name": "Macro Link Replace", "desc": "Automatically update or replace macro links in drawings and part files."},
    {"name": "Toggle View Frames", "desc": "Turn view frames on or off in CATIA drawings with a single command."},
    {"name": "Swap Background / Foreground", "desc": "Switch between background and working view modes for easier drawing edits."},
    {"name": "Lock or Unlock Views", "desc": "Secure drawing views from accidental edits, or unlock them for modification."}
]

def get_capabilities_text():
    text = "I currently assist with several CATIA automation tasks:\n\n"
    for cap in COPILOT_CAPABILITIES:
        text += f"• {cap['name']} — {cap['desc']}\n"
    return text


# ------------------------------------------------------
# Utility Functions
# ------------------------------------------------------
def sanitize_filename(name: str) -> str:
    base = os.path.basename(name)
    if not base:
        raise ValueError("Empty filename after sanitization.")
    if not FILENAME_SAFE_RE.match(base):
        raise ValueError("Filename contains invalid characters. Allowed: letters, numbers, dot, dash, underscore.")
    return base


def ensure_placeholder_script(script_name):
    os.makedirs(BASE_SCRIPT_DIR, exist_ok=True)
    if script_name.lower().endswith((".vbs", ".py", ".catscript")):
        filename = script_name
    else:
        filename = script_name + ".vbs"

    script_path = os.path.join(BASE_SCRIPT_DIR, filename)
    created = False
    if not os.path.exists(script_path):
        with open(script_path, "w", encoding="utf-8") as f:
            if filename.lower().endswith(".vbs"):
                f.write(f'WScript.Echo "Placeholder script: {filename}"\n')
            else:
                f.write(f'# Placeholder script: {filename}\nprint("Placeholder script:", "{filename}")\n')
        created = True
    return script_path, created


# ------------------------------------------------------
# Universal Script Runner with Timer
# ------------------------------------------------------
def run_script_with_timer(script_path: str):
    """Run any script (.vbs, .py, .catscript) and return only actual output + execution time."""
    start = time.time()
    extension = os.path.splitext(script_path)[1].lower()
    output = ""
 
    try:
        if extension == ".vbs":
            result = subprocess.run(["cscript", "//nologo", script_path], capture_output=True, text=True)
            output = result.stdout.strip()
        elif extension == ".py":
            result = subprocess.run(["python", script_path], capture_output=True, text=True)
            output = result.stdout.strip()
        elif extension == ".catscript":
            result = subprocess.run(["cscript", "//nologo", script_path], capture_output=True, text=True)
            output = result.stdout.strip()
        else:
            output = f"❌ Unsupported script type: {extension}"
    except Exception as e:
        output = f"❌ Error running {os.path.basename(script_path)}: {e}"
 
    end = time.time()
    elapsed = round(end - start, 2)
 
    # ✅ Only show VBScript/Python output + execution time
    if not output:
        output = "✅ command executed successfully."
 
    return f"{output}\n\n⏱️ Execution Time: {elapsed} seconds"


# ------------------------------------------------------
# Rectangle Parser
# ------------------------------------------------------
def parse_rectangular_command(command: str):
    """
    Robustly extracts Length, Breadth, Thickness from varied human inputs.
    Supports:
      - Compact: 200x100x50, 200 X 100 X 50, 300*150*75, 250 by 120 by 60
      - With/without units (mm), anywhere in the string
      - Named dims in any order with synonyms and punctuation
      - Fallback: first three numbers map to L, B, T
    """
    text = command.lower()
    # Normalize common noise
    text = (
        text.replace("millimeters", " mm")
            .replace("millimeter", " mm")
            .replace("centimeters", " cm")
            .replace("centimeter", " cm")
            .replace("cms", " cm")
            .replace("mm.", " mm")
    )
    # Map synonym tokens to canonical names to help named matching
    synonyms = {
        "length": ["length", "long", "len", "l"],
        "breadth": ["breadth", "width", "wide", "w"],
        "thickness": ["thickness", "thick", "height", "depth", "t", "h"]
    }
    # Build regex for compact patterns like 200x100x50, 200 by 100 by 50, 300*150*75
    compact = re.search(
        r"(\d+(?:\.\d+)?)\s*(?:x|X|\*|by)\s*(\d+(?:\.\d+)?)\s*(?:x|X|\*|by)\s*(\d+(?:\.\d+)?)",
        text
    )
    if compact:
        l, b, t = map(float, compact.groups())
        # If obvious unit scale like cm present overall, convert to mm
        if re.search(r"\bcm\b", text):
            l, b, t = l * 10, b * 10, t * 10
        return {"Length": l, "Breadth": b, "Thickness": t}

    # Named dimensions in any order
    def grab(name_list):
        # Allow optional punctuation and unit after number
        pat = rf"(?:{'|'.join(map(re.escape, name_list))})\s*[:=]?\s*(\d+(?:\.\d+)?)\s*(mm|cm)?\b"
        return re.search(pat, text)

    out = {}
    m_len = grab(synonyms["length"])
    m_brd = grab(synonyms["breadth"])
    m_thk = grab(synonyms["thickness"])

    def to_mm(match):
        val = float(match.group(1))
        unit = match.group(2)
        if unit == "cm":
            return val * 10.0
        return val

    if m_len:
        out["Length"] = to_mm(m_len)
    if m_brd:
        out["Breadth"] = to_mm(m_brd)
    if m_thk:
        out["Thickness"] = to_mm(m_thk)

    if len(out) == 3:
        return out

    # If only some named dims found, fill remaining by scanning numbers in order
    nums = [float(n) for n in re.findall(r"(\d+(?:\.\d+)?)\s*(?:mm|cm)?", text)]
    # If 'cm' appears globally and no explicit units tagged numbers, assume cm -> mm
    if re.search(r"\bcm\b", text) and not re.search(r"\d+(?:\.\d+)?\s*mm", text):
        nums = [n * 10.0 for n in nums]

    ordered_keys = ["Length", "Breadth", "Thickness"]
    for key in ordered_keys:
        if key not in out and nums:
            out[key] = nums.pop(0)

    if len(out) == 3:
        # Basic sanity checks
        if any(v <= 0 for v in out.values()):
            return None
        return out

    # Final fallback: strictly first three numbers map to L, B, T
    if len(nums) >= 3:
        l, b, t = nums[0], nums[1], nums[2]
        if min(l, b, t) <= 0:
            return None
        return {"Length": l, "Breadth": b, "Thickness": t}

    return None


# ------------------------------------------------------
# 3D Rectangle Script Runner
# ------------------------------------------------------
def run_rectangular_baseplate(params):
    """Generate a parametric VBScript from template and execute it."""
    template_path = os.path.join(BASE_SCRIPT_DIR, "Rectangular3D_Baseplate.vbs")
    if not os.path.exists(template_path):
        return "❌ Template Rectangular3D_Baseplate.vbs not found."

    with open(template_path, "r", encoding="utf-8") as f:
        content = f.read()

    content = (
        content.replace("<LENGTH>", str(params["Length"]))
               .replace("<BREADTH>", str(params["Breadth"]))
               .replace("<THICKNESS>", str(params["Thickness"]))
    )

    gen_path = os.path.join(BASE_SCRIPT_DIR, "Rectangular3D_Run.vbs")
    with open(gen_path, "w", encoding="utf-8") as f:
        f.write(content)

    return run_script_with_timer(gen_path)


# ------------------------------------------------------
# Routes
# ------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request, "capabilities": COPILOT_CAPABILITIES})


@app.get("/add_task", response_class=HTMLResponse)
async def add_task_form(request: Request):
    return templates.TemplateResponse("add_task.html", {"request": request})


@app.post("/add_task", response_class=HTMLResponse)
async def add_task(
    request: Request,
    intent_name: str = Form(""),
    description: str = Form(""),
    script_name: str = Form(""),
    examples: str = Form(""),
    script_content: str = Form(""),
    allow_overwrite: bool = Form(False),
    trigger: str = Form(""),
    script: str = Form("")
):
    try:
        if intent_name or examples or script_name:
            examples_list = [e.strip() for e in examples.splitlines() if e.strip()]
            if intent_name and intent_name not in examples_list:
                examples_list.insert(0, intent_name)

            if not intent_name or not script_name or not examples_list:
                return templates.TemplateResponse("add_task.html", {
                    "request": request,
                    "error": "⚠️ Please provide intent name, script filename and at least one example phrase."
                })

            script_name = sanitize_filename(script_name)
            if not script_name.lower().endswith((".vbs", ".py", ".catscript")):
                script_name += ".vbs"

            script_path = os.path.join(BASE_SCRIPT_DIR, script_name)
            os.makedirs(BASE_SCRIPT_DIR, exist_ok=True)

            if script_content:
                with open(script_path, "w", encoding="utf-8") as f:
                    f.write(script_content)
            else:
                script_path, _ = ensure_placeholder_script(script_name)

            nlp.add_intent(intent_name, script_name, examples_list, description)
            msg = f"✅ Added intent '{intent_name}' mapped to '{script_name}'"
            return templates.TemplateResponse("add_task.html", {"request": request, "success": msg})

        return templates.TemplateResponse("add_task.html", {"request": request, "error": "⚠️ Please fill in all fields."})

    except Exception as e:
        tb = traceback.format_exc()
        return templates.TemplateResponse("add_task.html", {"request": request, "error": f"Failed to add task: {e}\n{tb}"})


@app.post("/run_command")
async def run_command(request: Request):
    data = await request.json()
    user_input = data.get("command", "").strip()

    if not user_input:
        return JSONResponse({"output": "⚠️ Please enter a valid command."})

    # Capabilities
    if any(word in user_input.lower() for word in ["capabilities", "help", "features"]):
        return JSONResponse({"output": get_capabilities_text()})

    # ✅ Detect 3D Rectangle Command
    keywords = [
    "rectangle","rectangular","block","baseplate","solid","plate","cuboid","brick",
    "reactnagle","blok"]
    if any(k in user_input.lower() for k in keywords):
        params = parse_rectangular_command(user_input)
        if params:
            output = run_rectangular_baseplate(params)
            return JSONResponse({
                "matched_script": "Rectangular3D_Baseplate.vbs",
                "parameters": params,
                "output": output
            })
        else:
            return JSONResponse({"output": "⚠️ Could not parse dimensions. Use 'length 200 width 100 thickness 50' format."})

    # 🧠 NLP fallback (other features)
    script_name, score = nlp.find_script(user_input)
    base_script_dir = BASE_SCRIPT_DIR

    if script_name:
        script_path = os.path.join(base_script_dir, script_name)
        if os.path.exists(script_path):
            output = run_script_with_timer(script_path)
        else:
            output = f"❌ Script file not found: {script_path}"
    else:
        output = f"⚠️ Unknown or unsupported command: '{user_input}'."

    return JSONResponse({
        "matched_script": script_name,
        "similarity": round(score, 2) if score else None,
        "output": output
    })
