import cadquery as cq
import re

def create_rectangle(prompt: str):
    """
    Parses prompt for length, width, height and returns a CQ object and dims.
    """
    l, w, h = 100.0, 100.0, 10.0
    
    m_l = re.search(r'(?:length|l)\s*[:=]?\s*(\d+(?:\.\d+)?)', prompt)
    if m_l: l = float(m_l.group(1))
    
    m_w = re.search(r'(?:width|w)\s*[:=]?\s*(\d+(?:\.\d+)?)', prompt)
    if m_w: w = float(m_w.group(1))
    
    m_h = re.search(r'(?:height|h)\s*[:=]?\s*(\d+(?:\.\d+)?)', prompt)
    if m_h: h = float(m_h.group(1))
    
    # Create Box
    result = cq.Workplane("XY").box(l, w, h)
    
    return result, {"l": l, "w": w, "h": h}
