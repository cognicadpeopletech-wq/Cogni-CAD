from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from app.core.models import GeometryJSON
import trimesh
import io

router = APIRouter()

@router.post("/generate")
async def generate(geometry: GeometryJSON, format: str = "glb"):
    if geometry.type != "box":
        raise HTTPException(status_code=400, detail="Only box supported for now")
    
    # Create trimesh box
    # Trimesh box takes extents (width, height, depth)
    # We map params to extents.
    try:
        mesh = trimesh.creation.box(extents=[
            geometry.params["width"],
            geometry.params["depth"],
            geometry.params["height"]
        ])
        
        # Simple color assignment if possible
        # mesh.visual.face_colors = ...
        
        if format == "glb":
            file_obj = io.BytesIO()
            mesh.export(file_obj, file_type="glb")
            file_obj.seek(0)
            return StreamingResponse(
                file_obj,
                media_type="model/gltf-binary",
                headers={"Content-Disposition": "attachment; filename=model.glb"}
            )
        else:
            raise HTTPException(status_code=400, detail="Unsupported format")
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
