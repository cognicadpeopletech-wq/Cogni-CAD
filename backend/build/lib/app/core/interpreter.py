import re
from .models import GeometryJSON, Material, Origin

def interpret_prompt(prompt: str) -> GeometryJSON:
    # Regex for "rectangle WxDxHmm color C"
    # Example: rectangle 100x200x40mm color red
    
    # Simple regex for dimensions
    # Matches 100x200x40 or 100.5x200.5x40.5
    dim_match = re.search(r"(\d+(?:\.\d+)?)x(\d+(?:\.\d+)?)x(\d+(?:\.\d+)?)", prompt)
    color_match = re.search(r"color\s+(\w+|#[0-9a-fA-F]{6})", prompt)
    
    width = 100.0
    depth = 100.0
    height = 10.0
    color = "gray"
    
    if dim_match:
        width = float(dim_match.group(1))
        depth = float(dim_match.group(2))
        height = float(dim_match.group(3))
        
    if color_match:
        color = color_match.group(1)
        
    return GeometryJSON(
        type="box",
        params={
            "width": width,
            "depth": depth,
            "height": height
        },
        units="mm", # Defaulting to mm for now
        material=Material(color=color),
        meta={"source": "regex-poc", "original_prompt": prompt}
    )
