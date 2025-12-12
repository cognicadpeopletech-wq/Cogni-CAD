"""
create_cylinder_fixed.py
Creates a cylinder in CATIA with fixed dimensions.
"""
 
from pycatia import catia
 
# -----------------------------------
# FIXED DIMENSIONS (EDIT IF NEEDED)
# -----------------------------------
DIAMETER = 80.0   # mm
HEIGHT = 150.0    # mm
 
 
def create_cylinder():
    c = catia()
    documents = c.documents
    part_doc = documents.add("Part")
    part = part_doc.part
 
    bodies = part.bodies
    body = bodies.item(1)       # Use MainBody (safe)
    sketches = body.sketches
 
    origin = part.origin_elements
    plane_xy = origin.plane_xy
 
    # -----------------------------
    # Create Sketch
    # -----------------------------
    sketch = sketches.add(plane_xy)
    sketch.open_edition()
 
    fac2d = sketch.factory_2d
    radius = DIAMETER / 2.0
 
    # Create circle
    fac2d.create_circle(0, 0, radius, 0, 6.283185307179586)
 
    sketch.close_edition()
    part.update()
 
    # -----------------------------
    # Pad the sketch (extrude)
    # -----------------------------
    shape_factory = part.shape_factory
    pad = shape_factory.add_new_pad(sketch, HEIGHT)
 
    part.update()
    print(f"SUCCESS: Cylinder created  Ø{DIAMETER} mm × {HEIGHT} mm")
 
 
if __name__ == "__main__":
    create_cylinder()