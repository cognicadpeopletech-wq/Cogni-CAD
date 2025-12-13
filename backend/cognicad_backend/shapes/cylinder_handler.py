try:
    try:
    import cadquery as cq
except ImportError:
    cq = None
except ImportError:
    cq = None
from cognicad_backend.core.shape_registry import register_shape
from typing import Dict, Any

@register_shape("cylinder")
def create_cylinder(params: Dict[str, Any]) -> cq.Workplane:
    diameter = params.get("diameter", 20.0)
    height = params.get("height", 80.0)
    
    # Create cylinder centered at origin (Z-axis)
    return cq.Workplane("XY").cylinder(height, diameter/2.0)
