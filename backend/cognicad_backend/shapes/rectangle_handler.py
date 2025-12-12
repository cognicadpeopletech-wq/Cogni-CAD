try:
    import cadquery as cq
except ImportError:
    cq = None
from cognicad_backend.core.shape_registry import register_shape
from typing import Dict, Any

@register_shape("box")
def create_rectangle(params: Dict[str, Any]) -> cq.Workplane:
    width = params.get("width", 100.0)
    depth = params.get("depth", 100.0)
    height = params.get("height", 10.0)
    
    # Create a box centered at origin
    return cq.Workplane("XY").box(width, depth, height)
