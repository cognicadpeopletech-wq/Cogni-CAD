from typing import Callable, Dict, Any, Optional
try:
    import cadquery as cq
except ImportError:
    cq = None
    print("Warning: CadQuery could not be imported.")

# Registry maps shape type (str) -> handler function
# Handler function signature: (params: Dict[str, Any]) -> cq.Workplane

if cq:
    _registry: Dict[str, Callable[[Dict[str, Any]], cq.Workplane]] = {}
else:
    _registry: Dict[str, Callable[[Dict[str, Any]], Any]] = {}

def register_shape(shape_type: str):
    def decorator(func):
        _registry[shape_type] = func
        return func
    return decorator

def get_shape_handler(shape_type: str) -> Optional[Callable[[Dict[str, Any]], cq.Workplane]]:
    return _registry.get(shape_type)
