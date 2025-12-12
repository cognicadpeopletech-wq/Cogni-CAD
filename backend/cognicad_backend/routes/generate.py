from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from cognicad_backend.core.models import GeometryJSON
from cognicad_backend.core.shape_registry import get_shape_handler
# Register shapes
import cognicad_backend.shapes.rectangle_handler
import cognicad_backend.shapes.cylinder_handler
import cognicad_backend.shapes.l_bracket_handler
import io
import os
import tempfile

router = APIRouter()

@router.post("/generate")
async def generate(geometry: GeometryJSON, format: str = "glb"):
    try:
        handler = get_shape_handler(geometry.type)
        if not handler:
             raise HTTPException(status_code=400, detail=f"Unsupported shape: {geometry.type}")
        
        # Generate CadQuery Workplane
        result_wp = handler(geometry.params)
        
        # Export
        # CadQuery exports to file paths usually.
        # We need to use a temp file.
        
        suffix = ".glb"
        if format == "step" or format == "stp":
            suffix = ".step"
        elif format == "glb":
            suffix = ".glb"
        else:
             raise HTTPException(status_code=400, detail="Unsupported format")
             
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp_path = tmp.name
            
        # Export using CadQuery
        # format: 'STEP', 'STL', 'GLTF' (requires vtk?)
        # Standard CQ export:
        # assembly = cq.Assembly(result_wp)
        # assembly.save(tmp_path, exportType=...)
        
        # Simple export for Workplane
        if format == "step" or format == "stp":
            from cadquery import exporters
            exporters.export(result_wp, tmp_path, exporters.ExportTypes.STEP)
            media_type = "application/step"
            filename = "model.step"
        else:
            # GLTF export in CQ might be tricky without extra deps.
            # Fallback: Export STL and convert? 
            # Or use exporters.export(result_wp, tmp_path, exporters.ExportTypes.GLTF)?
            # Let's try direct GLTF if available, else STL.
            # Actually, for PoC, let's try TJS (ThreeJS) or STL if GLTF fails.
            # But frontend expects GLB.
            
            # If CQ doesn't support GLB natively in this version, we might need to use 
            # 'trimesh' to convert STL -> GLB.
            # Let's try to export STL from CQ, load in Trimesh, export GLB.
            
            from cadquery import exporters
            stl_path = tmp_path + ".stl"
            exporters.export(result_wp, stl_path, exporters.ExportTypes.STL)
            
            import trimesh
            mesh = trimesh.load(stl_path)
            
            # Export to GLB
            mesh.export(tmp_path, file_type="glb")
            
            # Cleanup STL
            if os.path.exists(stl_path):
                os.remove(stl_path)
                
            media_type = "model/gltf-binary"
            filename = "model.glb"
            
        # Read back
        with open(tmp_path, "rb") as f:
            content = f.read()
            
        # Cleanup
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
            
        return StreamingResponse(
            io.BytesIO(content),
            media_type=media_type,
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
