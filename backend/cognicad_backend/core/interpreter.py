import re
from .models import GeometryJSON, Material, Origin

def interpret_prompt(prompt: str) -> GeometryJSON:
    # Regex for "rectangle WxDxHmm color C"
    # Example: rectangle 100x200x40mm color red
    rect_match = re.search(r"rectangle\s+(\d+(?:\.\d+)?)x(\d+(?:\.\d+)?)x(\d+(?:\.\d+)?)", prompt, re.IGNORECASE)
    
    # Regex for "Create a Cylinder with diameter D mm and height H mm"
    cyl_match = re.search(r"cylinder.*diameter\s+(\d+(?:\.\d+)?).*height\s+(\d+(?:\.\d+)?)", prompt, re.IGNORECASE)
    
    # Regex for "Create a W x H x T L bracket with bend radius Rmm"
    l_match = re.search(r"(\d+(?:\.\d+)?)\s*x\s*(\d+(?:\.\d+)?)\s*x\s*(\d+(?:\.\d+)?)\s+L\s+bracket.*radius\s+(\d+(?:\.\d+)?)", prompt, re.IGNORECASE)

    color_match = re.search(r"color\s+(\w+|#[0-9a-fA-F]{6})", prompt, re.IGNORECASE)
    color = "gray"
    if color_match:
        color = color_match.group(1)

    if cyl_match:
        diameter = float(cyl_match.group(1))
        height = float(cyl_match.group(2))
        return GeometryJSON(
            type="cylinder",
            params={"diameter": diameter, "height": height},
            units="mm",
            material=Material(color=color),
            meta={"source": "regex-poc", "original_prompt": prompt}
        )

    if l_match:
        width = float(l_match.group(1))
        height = float(l_match.group(2))
        thickness = float(l_match.group(3))
        bend_radius = float(l_match.group(4))
        return GeometryJSON(
            type="l_bracket",
            params={
                "width": width,
                "height": height,
                "thickness": thickness,
                "bend_radius": bend_radius
            },
            units="mm",
            material=Material(color=color),
            meta={"source": "regex-poc", "original_prompt": prompt}
        )
    
    width = 100.0
    depth = 100.0
    height = 10.0
    
    if rect_match:
        width = float(rect_match.group(1))
        depth = float(rect_match.group(2))
        height = float(rect_match.group(3))
        
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
