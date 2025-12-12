import cadquery as cq
import trimesh
import re
import os
import uuid
from pathlib import Path

def generate_model(prompt: str, output_dir: Path):
    """
    Parses the prompt and generates a 3D model using CadQuery.
    Returns a dictionary with paths to the generated files (GLB, STEP).
    """
    prompt = prompt.lower()
    
    # Defaults
    l, w, h = 100.0, 100.0, 10.0
    shape_type = "unknown"
    
    # 1. Rectangle / Box Logic
    if "rectangle" in prompt or "box" in prompt:
        shape_type = "rectangle"
        
        # Parse dimensions
        m_l = re.search(r'(?:length|l)\s*[:=]?\s*(\d+(?:\.\d+)?)', prompt)
        if m_l: l = float(m_l.group(1))
        
        m_w = re.search(r'(?:width|w)\s*[:=]?\s*(\d+(?:\.\d+)?)', prompt)
        if m_w: w = float(m_w.group(1))
        
        m_h = re.search(r'(?:height|h)\s*[:=]?\s*(\d+(?:\.\d+)?)', prompt)
        if m_h: h = float(m_h.group(1))
        
        # CadQuery creation
        result = cq.Workplane("XY").box(l, w, h)
        
    else:
        # Fallback or error
        return {
            "success": False,
            "message": "Unsupported shape. Currently supporting: Rectangle/Box."
        }
        
    # Generate unique filenames
    run_id = str(uuid.uuid4())[:8]
    base_name = f"inhouse_{shape_type}_{run_id}"
    
    step_filename = f"{base_name}.step"
    glb_filename = f"{base_name}.glb"
    stl_filename = f"{base_name}.stl" # Intermediate
    
    step_path = output_dir / step_filename
    glb_path = output_dir / glb_filename
    stl_path = output_dir / stl_filename
    
    # Export STEP using CadQuery
    try:
        cq.exporters.export(result, str(step_path))
    except Exception as e:
        return {"success": False, "message": f"STEP export failed: {e}"}

    # Export GLB (CQ -> STL -> Trimesh -> GLB)
    try:
        cq.exporters.export(result, str(stl_path))
        
        # Convert STL to GLB using Trimesh
        mesh = trimesh.load(str(stl_path))
        # Ensure it's a Trimesh object
        if isinstance(mesh, trimesh.Scene):
             # If it loaded as a scene, merge or take geometry (usually stl is one mesh)
             if len(mesh.geometry) > 0:
                 mesh = list(mesh.geometry.values())[0]
        
        mesh.export(str(glb_path))
        
        # Cleanup STL if desired, but keeping it is fine/useful
        if os.path.exists(str(stl_path)):
             os.remove(str(stl_path))
             
    except Exception as e:
        return {"success": False, "message": f"GLB export failed: {e}"}
        
    return {
        "success": True,
        "step_url": f"/downloads/{step_filename}",
        "glb_url": f"/downloads/{glb_filename}",
        "message": f"Generated {shape_type} (L={l}, W={w}, H={h})"
    }
