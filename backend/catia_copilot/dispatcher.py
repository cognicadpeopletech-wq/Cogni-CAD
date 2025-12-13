import sys
import subprocess
import time
import os
import logging
from pathlib import Path
from typing import List, Optional, Tuple

IS_WINDOWS = os.name == "nt"

def run_script_with_timer(script_path: str, args: Optional[List[str]] = None, timeout: int = 60):
    start = time.time()
    ext = os.path.splitext(script_path)[1].lower()
    if args is None: args = []
    try:
        if ext in (".vbs", ".catscript"):
            if not IS_WINDOWS:
                return "", "", 0.0, "❌ VBScript/CATScript requires Windows."
            cmd = ["cscript", "//nologo", script_path] + args
        elif ext == ".py":
            cmd = [sys.executable, script_path] + args
        else:
            return "", "", 0.0, f"❌ Unsupported script type: {ext}"
        
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        elapsed = round(time.time() - start, 3)
        stdout, stderr = proc.stdout.strip(), proc.stderr.strip()
        return stdout, stderr, elapsed, None
    except subprocess.TimeoutExpired:
        return "", "", round(time.time() - start, 3), f"❌ Timeout after {timeout}s"
    except Exception as e:
        logging.exception("Script error")
        return "", "", round(time.time() - start, 3), f"❌ Error: {e}"

def safe_run_script(script_path: Path, param_json_path: str = None, timeout: int = 60):
    try:
        cmd = [sys.executable, str(script_path)]
        if param_json_path:
            cmd.append(str(param_json_path))
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        stdout = p.stdout or ""
        stderr = p.stderr or ""
        return stdout.strip(), stderr.strip(), None if p.returncode == 0 else f"exit_{p.returncode}"
    except Exception as e:
        return "", str(e), str(e)

def run_rib_multipart(script_name: str, flags: List[str], base_script_dir: Path, timeout: int = 120):
    cand = base_script_dir / script_name
    if not cand.exists():
        cand = Path(script_name)
    if not cand.exists():
        return "", f"❌ Script not found: {script_name}", 0.0, f"Script not found: {script_name}"
    return run_script_with_timer(str(cand), args=flags, timeout=timeout)
