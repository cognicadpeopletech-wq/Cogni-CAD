from pydantic import BaseModel, Field
from typing import Optional, Dict, Any

class GeometryParams(BaseModel):
    width: float
    height: float
    depth: float

class CylinderParams(BaseModel):
    diameter: float
    height: float

class LBracketParams(BaseModel):
    width: float
    height: float
    thickness: float
    bend_radius: float

class Material(BaseModel):
    color: str

class Origin(BaseModel):
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0

class GeometryJSON(BaseModel):
    type: str
    params: Dict[str, Any] # Can be GeometryParams, CylinderParams, or LBracketParams
    units: str = "mm"
    material: Material
    origin: Origin = Field(default_factory=Origin)
    meta: Optional[Dict[str, Any]] = None
