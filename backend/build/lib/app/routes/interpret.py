from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.core.interpreter import interpret_prompt
from app.core.models import GeometryJSON

router = APIRouter()

class InterpretRequest(BaseModel):
    prompt: str

@router.post("/interpret", response_model=GeometryJSON)
async def interpret(request: InterpretRequest):
    try:
        geometry = interpret_prompt(request.prompt)
        return geometry
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
