from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse
import io

router = APIRouter()

@router.post("/convert")
async def convert(file: UploadFile = File(...), target_format: str = "step"):
    # PoC: Just return a dummy file or echo back for now if we don't have pythonOCC
    
    if target_format != "step":
        raise HTTPException(status_code=400, detail="Only STEP supported")
        
    # Placeholder content for STEP
    content = b"ISO-10303-21;\nHEADER;\nENDSEC;\nDATA;\nENDSEC;\nEND-ISO-10303-21;\n"
    
    return StreamingResponse(
        io.BytesIO(content),
        media_type="application/step",
        headers={"Content-Disposition": "attachment; filename=model.stp"}
    )
