import cadquery as cq
import trimesh
import os
import uuid
import re
from pathlib import Path

# Import Shape Handlers
from .shapes import rectangle

def generate_model(prompt: str, output_dir: Path):
    """
    Dispatcher: Parses prompt, calls appropriate shape handler, exports files.
    """
    prompt = prompt.lower()
    shape_type = "unknown"
    result = None
    params = {}

    # --- Routing Logic ---
    if "rectangle" in prompt or "box" in prompt:
        shape_type = "rectangle"
        result, params = rectangle.create_rectangle(prompt)
    else:
        return {
            "success": False,
            "message": "Unsupported shape. Currently supporting: Rectangle/Box."
        }
        
    # --- Export Logic ---
    run_id = str(uuid.uuid4())[:8]
    base_name = f"inhouse_{shape_type}_{run_id}"
    
    step_filename = f"{base_name}.step"
    glb_filename = f"{base_name}.glb"
    stl_filename = f"{base_name}.stl" # Intermediate
    
    step_path = output_dir / step_filename
    glb_path = output_dir / glb_filename
    stl_path = output_dir / stl_filename
    
    # Export STEP
    try:
        cq.exporters.export(result, str(step_path))
    except Exception as e:
        return {"success": False, "message": f"STEP export failed: {e}"}

    # Export GLB (CQ -> STL -> Trimesh -> GLB)
    try:
        cq.exporters.export(result, str(stl_path))
        mesh = trimesh.load(str(stl_path))
        if isinstance(mesh, trimesh.Scene):
             if len(mesh.geometry) > 0:
                 mesh = list(mesh.geometry.values())[0]
        mesh.export(str(glb_path))
        if os.path.exists(str(stl_path)):
             os.remove(str(stl_path))
    except Exception as e:
        return {"success": False, "message": f"GLB export failed: {e}"}

    # Formatted Info String
    info_str = f"Generated {shape_type} (" + ", ".join([f"{k.upper()}={v}" for k,v in params.items()]) + ")"

    # Return Result with DOWNLOAD URLS (to be serviced by main.py dedicated endpoint)
    # We will use /download_file/{filename} convention.
    return {
        "success": True,
        "step_url": f"/download_file/{step_filename}",
        "glb_url": f"/download_file/{glb_filename}",
        "message": info_str
    }
