import os
import logging

# Aggressive logging suppression
# Force root logger and specific loggers to critical/error only
for name in logging.root.manager.loggerDict:
    logging.getLogger(name).setLevel(logging.CRITICAL)

logging.getLogger("pycatia").setLevel(logging.CRITICAL)
logging.getLogger("documents").setLevel(logging.CRITICAL) # "INFO in documents"
logging.basicConfig(level=logging.CRITICAL, force=True)


try:
    from pycatia import catia
    from pycatia.mec_mod_interfaces.part_document import PartDocument
except ImportError:
    pass # Handle potential import errors silently or minimal


# ----- Path
# --------------------------------------------------------------------------- #
PATH = os.path.dirname(os.path.abspath(__file__)) + '\\'
PATH_prev = os.path.dirname(PATH) + '\\'

#
# =========================================================================== #
# ----- CATIA variables
# =========================================================================== #
#
caa = catia()
application = caa.application
documents = application.documents
if documents.count > 0:
    for document in documents:
        document.close()
        
# Load Part
documents.open(PATH + "solid_combine.CATPart")

# Get references to document, parts and tools to create geometries
document: PartDocument = application.active_document        # Get active document
part = document.part                                        # Get Part
partbody = part.bodies[0]                                   # Get default PartBody by index
# partbody = part.bodies.item("PartBody")                     # Get default PartBody by name
sketches = partbody.sketches                                # Get sketches on PartBody 
hybrid_bodies = part.hybrid_bodies                          # Get Hybrid Bodies 
hsf = part.hybrid_shape_factory                             # Get Hybrid Shape Factory 
shpfac = part.shape_factory                                 # Get Shape Factory 
selection = document.selection                              # Get document selection

# Get references to main planes
plane_XY = part.origin_elements.plane_xy
plane_YZ = part.origin_elements.plane_yz
plane_ZX = part.origin_elements.plane_zx

# Hide main planes
selection.clear();
selection.add(plane_XY)
selection.add(plane_YZ)
selection.add(plane_ZX)
selection.vis_properties.set_show(1) # 0: Show / 1: Hide
selection.clear()

# Update the document
document.part.update()

# Set PartBody as a working object
part.in_work_object = partbody

# %% ------------------------------------------------------------------------ #
# ----- Get reference to elements
# # --------------------------------------------------------------------------- #
# print("")
# print("Sketches names in PartBody")
# print(partbody.sketches.get_item_names())
# print("")
# print("Operations in PartBody")
# print(partbody.shapes.get_item_names())
# print("")

# Reference to sketch 2
sketch2 = partbody.sketches.get_item("Sketch.2")

# Reference to fillet operation
fillet1 = partbody.shapes.get_item_by_name("EdgeFillet.1")

# %% ------------------------------------------------------------------------ #
# ----- Get reference to fillet operation parameters
# --------------------------------------------------------------------------- #

# All part parameters
part_parameters = part.parameters.get_item_names()
# for idx in range(len(part_parameters)):
#     print(idx,":",part_parameters[idx])

# %% Get and print "EdgeFillet.1" parameters
fillet_parameters = [item for item in part_parameters if "EdgeFillet.1" in item]
# for idx in range(len(fillet_parameters)):
#     print(idx,":",fillet_parameters[idx])

# %% Modify fillet radius
fillet_radius = part.parameters.item(fillet_parameters[0])
fillet_radius.value = 2

# Update the document
document.part.update()

# %% ------------------------------------------------------------------------ #
# ----- Get reference to sketch constraint and modify hole radius
# --------------------------------------------------------------------------- #

# Get sketch 3 reference
sketch3 = partbody.sketches.get_item("Sketch.3")

# Get the geometrical elements of the sketch
sketch3_geo_elem = sketch3.geometric_elements.get_item_names()

# Print index and names
# for idx in range(len(sketch3_geo_elem)):
#     print(idx,":",sketch3_geo_elem[idx])

# %% Get the constraints of the sketch
sketch3_constraints = sketch3.constraints.get_item_names()

# for idx in range(len(sketch3_constraints)):
#     print(idx,":",sketch3_constraints[idx])

# %% Print radius constraints and their values
radius_constraints = [item for item in sketch3_constraints if "Radius" in item]   
 
for idx in range(len(radius_constraints)):    
    const = sketch3.constraints.item(radius_constraints[idx])
    rad_val = const.dimension.value
    # print(idx,":",radius_constraints[idx],", Value :",rad_val)  

# %% Modify hole radius

# Get reference to radius constraint
hole_radius = sketch3.constraints.item(radius_constraints[1]).dimension

# Open sketch
ske2D = sketch3.open_edition()

# Change constraint value
hole_radius.value = 6

# sketch close edition 
sketch3.close_edition()

# Update the document
document.part.update()

# %% ------------------------------------------------------------------------ #
# ----- Loop to generate CAD files
# --------------------------------------------------------------------------- #
# ----- Loop to generate CAD files
# --------------------------------------------------------------------------- #

# Create the directory to store the files
SAVE_PATH = os.path.join(PATH, "step_files")

if not os.path.exists(SAVE_PATH):
    os.makedirs(SAVE_PATH)

# print("STEP files will be saved in:", SAVE_PATH)
# print("")

# Define parameters
fillet2study = [1,2,3]
radius2study = [1,2,3,4,5,6,7,8,9]

# print("# --------------------------- #")
# print("# ----- Generating designs:")
# print("# --------------------------- #")
# print("")

for fill in fillet2study:
    for rad in radius2study:
        try:
            # Update fillet radius
            fillet_radius.value = fill
            
            # Update hole diameter
            ske2D = sketch3.open_edition()
            hole_radius.value = rad
            sketch3.close_edition()

            # Update model
            document.part.update()
            
            # Prepare file name & path
            filename = f"fill_{fill}_rad_{rad}.stp"
            full_path = os.path.join(SAVE_PATH, filename)

            # Save the file
            document.export_data(full_path, "stp", overwrite=True)
            print(f"Generated: {filename}")
        except Exception as e:
            print(f"Failed for Fill={fill}, Rad={rad}: {e}")

        # Print file info
        # print(f"Fillet Radius: {fill} mm, Hole Radius: {rad} mm --> Saved: {full_path}")
