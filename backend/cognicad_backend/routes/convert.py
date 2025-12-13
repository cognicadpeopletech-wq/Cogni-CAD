# from fastapi import APIRouter, UploadFile, File, HTTPException
# from fastapi.responses import StreamingResponse
# import io
# import tempfile
# import os
# import cadquery as cq
# import trimesh

# router = APIRouter()

# @router.post("/convert")
# async def convert(file: UploadFile = File(...), target_format: str = "step"):
#     if target_format not in ["step", "glb"]:
#         raise HTTPException(status_code=400, detail="Only STEP and GLB supported")

#     # Save uploaded file to temp
#     suffix = ".stp" if file.filename.lower().endswith(('.stp', '.step')) else ""
#     with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_input:
#         tmp_input.write(await file.read())
#         tmp_input_path = tmp_input.name

#     try:
#         if target_format == "glb":
#             # 1. Load STEP with CadQuery
#             try:
#                 model = cq.importers.importStep(tmp_input_path)
#             except Exception as e:
#                 raise HTTPException(status_code=400, detail=f"Failed to load STEP file: {str(e)}")

#             # 2. Export to intermediate STL
#             with tempfile.NamedTemporaryFile(delete=False, suffix=".stl") as tmp_stl:
#                 tmp_stl_path = tmp_stl.name
            
#             cq.exporters.export(model, tmp_stl_path)

#             # 3. Load STL with Trimesh and export to GLB
#             try:
#                 mesh = trimesh.load(tmp_stl_path)
#                 glb_data = mesh.export(file_type='glb')
                
#                 # Clean up STL
#                 os.unlink(tmp_stl_path)

#                 return StreamingResponse(
#                     io.BytesIO(glb_data),
#                     media_type="model/gltf-binary",
#                     headers={"Content-Disposition": "attachment; filename=converted_model.glb"}
#                 )
#             except Exception as e:
#                 if os.path.exists(tmp_stl_path):
#                     os.unlink(tmp_stl_path)
#                 raise HTTPException(status_code=500, detail=f"Conversion to GLB failed: {str(e)}")

#         else: # target_format == "step"
#             # Just echo back for now as per previous logic, or handle other conversions
#             # Since we just saved it, we can read it back if needed, but for "convert" 
#             # usually implies changing format. 
#             # If the user wants to download the generated geometry as STEP, that's a different flow (generate endpoint).
#             # Here we assume this endpoint is for file-to-file conversion.
            
#             # For now, let's just return the same file content to satisfy the interface if they ask for STEP->STEP
#             with open(tmp_input_path, "rb") as f:
#                 content = f.read()
            
#             return StreamingResponse(
#                 io.BytesIO(content),
#                 media_type="application/step",
#                 headers={"Content-Disposition": f"attachment; filename={file.filename}"}
#             )

#     finally:
#         # Clean up input file
#         if os.path.exists(tmp_input_path):
#             os.unlink(tmp_input_path)
from fastapi import APIRouter, Form, HTTPException
from fastapi.responses import JSONResponse
import os
import cadquery as cq
from cadquery import exporters
import trimesh
import tempfile
import logging

router = APIRouter()

# Directory settings - Adjusting to match probable upload location
UPLOAD_DIR = "static_files/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.post("/convert")
async def convert(filename: str = Form(...)):
    """
    Converts a previously uploaded STEP file to GLB using user's specific logic.
    Expects 'filename' to be the name of a file in 'static_files/uploads/'.
    Returns JSON with 'glb_url' to the converted file.
    """
    
    input_path = os.path.join(UPLOAD_DIR, filename)
    if not os.path.exists(input_path):
        raise HTTPException(status_code=404, detail="Input file not found")

    # Generate output filename
    base_name = os.path.splitext(filename)[0]
    output_filename = f"{base_name}.glb"
    output_path = os.path.join(UPLOAD_DIR, output_filename)
    
    # Run the user's legacy conversion logic
    success = convert_step_to_glb_logic(input_path, output_path)
    
    if success:
        # Return URL for frontend to load/download
        return {"glb_url": f"/static/uploads/{output_filename}"}
    else:
        raise HTTPException(status_code=500, detail="Conversion failed internally")

def convert_step_to_glb_logic(step_file_path: str, output_glb_path: str) -> bool:
    """
    Converts a STEP file to a GLB file using CadQuery and Trimesh.
    Logic ported directly from user request.
    """
    try:
        logging.info(f"Starting conversion: {step_file_path} -> {output_glb_path}")
        
        # 1. IMPORT: Load the STEP file
        model = cq.importers.importStep(step_file_path)
        
        # Orient Z-up (CAD) to Y-up (GLB)
        # Rotate -90 degrees around X-axis
        # User Code: model = model.rotate((0,0,0), (1,0,0), -90)
        model = model.rotate((0,0,0), (1,0,0), -90)

        # 2. INTERMEDIATE: Export to STL
        # Using temp file for STL as per legacy logic
        with tempfile.NamedTemporaryFile(suffix=".stl", delete=False) as tmp:
            stl_path = tmp.name
            
        try:
            # Export from CadQuery to temporary STL
            # User Code: exporters.export(model, stl_path, exporters.ExportTypes.STL)
            exporters.export(model, stl_path, exporters.ExportTypes.STL)
            
            # 3. CONVERT: STL -> GLB
            # User Code: mesh = trimesh.load(stl_path); mesh.export(...)
            mesh = trimesh.load(stl_path)
            mesh.export(output_glb_path, file_type="glb")
            
            logging.info(f"Conversion successful: {output_glb_path}")
            return True
            
        finally:
            # Clean up temp STL
            if os.path.exists(stl_path):
                os.remove(stl_path)
                
    except Exception as e:
        logging.exception(f"STEP conversion failed: {e}")
        print(f"Error during conversion: {e}")
        return False
