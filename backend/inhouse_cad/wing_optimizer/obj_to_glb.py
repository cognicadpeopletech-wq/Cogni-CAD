import numpy as np
import trimesh
from pygltflib import GLTF2, Scene, Node, Mesh, Buffer, BufferView, Accessor, Asset, Primitive

def obj_to_glb(obj_path, glb_path):
    # Use trimesh to load OBJ
    mesh = trimesh.load(obj_path, force='mesh')
    
    # Extract vertices and faces
    vertices = mesh.vertices.astype(np.float32)
    
    # Rotate -90 degrees around X-axis (Swap Y and Z, negate new Z)
    # x' = x
    # y' = z
    # z' = -y
    # VLM: y=span, z=lift. Three: y=up.
    # Map VLM z(lift) -> Three y(up). VLM y(span) -> Three z(depth).
    # New V = [x, z, -y]
    
    x = vertices[:, 0]
    y = vertices[:, 1]
    z = vertices[:, 2]
    
    # Stack new coordinates
    vertices = np.column_stack((x, z, -y))
    
    faces = mesh.faces.astype(np.uint32)
    indices = faces.flatten()

    glb = GLTF2()
    v_bytes = vertices.tobytes()
    i_bytes = indices.tobytes()
    blob = v_bytes + i_bytes
    
    # Single buffer
    glb.buffers.append(Buffer(byteLength=len(blob)))
    glb.set_binary_blob(blob)

    # Buffer Views
    # 0 = vertices (Vec3 float)
    gl_target_array_buffer = 34962
    gl_target_element_array_buffer = 34963
    
    glb.bufferViews.append(BufferView(buffer=0, byteOffset=0, 
                                      byteLength=len(v_bytes), target=gl_target_array_buffer))
    glb.bufferViews.append(BufferView(buffer=0, byteOffset=len(v_bytes), 
                                      byteLength=len(i_bytes), target=gl_target_element_array_buffer))

    # Accessors
    # Vertices
    gl_float = 5126
    glb.accessors.append(Accessor(
        bufferView=0, byteOffset=0,
        componentType=gl_float, count=len(vertices),
        type="VEC3",
        min=vertices.min(0).tolist(),
        max=vertices.max(0).tolist()
    ))

    # Indices
    gl_uint = 5125 # Trimesh uses uint32 usually, but WebGL 1.0 prefers uint16. GLTFLib/pygltflib handles this usually.
                   # Let's stick to uint32 (5125) if supported, or ensure < 65535 and use uint16.
                   # For this demo, let's assume standard support.
    glb.accessors.append(Accessor(
        bufferView=1, byteOffset=0,
        componentType=gl_uint, count=len(indices),
        type="SCALAR",
        min=[int(indices.min())],
        max=[int(indices.max())],
    ))

    # Mesh & primitive
    prim = Primitive(attributes={"POSITION": 0}, indices=1)
    glb.meshes.append(Mesh(primitives=[prim]))
    
    # Node & Scene
    glb.nodes.append(Node(mesh=0))
    glb.scenes.append(Scene(nodes=[0]))
    glb.scene = 0
    
    glb.asset = Asset(version="2.0")
    
    glb.save(glb_path)
