import math
import os
import numpy as np
import cadquery as cq

def generate_wing_step(params, output_path, naca="2412"):
    """
    Generates a STEP file for the wing using CadQuery based on parameters.
    """
    try:
        # 1. Decode NACA 4-digit to points
        # reusing logic or re-implementing simple generator for CQ
        m = int(naca[0]) / 100.0
        p = int(naca[1]) / 10.0
        t = int(naca[2:]) / 100.0
        
        def naca4_points(n_points=100):
            beta = np.linspace(0.0, math.pi, n_points)
            x = 0.5 * (1.0 - np.cos(beta))
            a0, a1, a2, a3, a4 = 0.2969, -0.1260, -0.3516, 0.2843, -0.1015
            y_t = 5 * t * (a0*np.sqrt(x)+a1*x+a2*x**2+a3*x**3+a4*x**4)
            y_c = np.zeros_like(x)
            dyc_dx = np.zeros_like(x)
            if m > 0 and p > 0:
                m1 = x < p
                m2 = ~m1
                y_c[m1] = m/(p**2) * (2*p*x[m1] - x[m1]**2)
                y_c[m2] = m/((1-p)**2) * ((1-2*p)+2*p*x[m2] - x[m2]**2)
            
            theta = np.arctan(dyc_dx)
            x_u = x - y_t*np.sin(theta)
            z_u = y_c + y_t*np.cos(theta)
            x_l = x + y_t*np.sin(theta)
            z_l = y_c - y_t*np.cos(theta)
            
            # Combine into list of (x, y) tuples for CQ (sketch plane is XY usually)
            # We want (x, z) actually if we loft along Y
            upper = list(zip(x_u, z_u))
            lower = list(zip(x_l, z_l))
            return upper[::-1] + lower[1:]

        pts = naca4_points(40)
        
        # 2. Extract params
        span = params["span"]
        cr = params["root_chord"]
        ct = params["tip_chord"]
        sweep_deg = params["sweep_le_deg"]
        dihedral_deg = params["dihedral_deg"]
        twist_root = params["twist_root_deg"]
        twist_tip = params["twist_tip_deg"]
        # Basic winglet support (simplified as a separate loft or extension)
        # For robustness, we'll just do the main wing first.
        # If winglet exists, we can add a second segment.
        winglet_h = params.get("winglet_height", 0)
        
        # 3. Create Root Profile
        # Located at (0,0,0) usually. 
        # Airfoil coords are (0..1, 0). Scale by Chord.
        def make_wire(chord, twist_deg, translate_vec):
            # Scale
            scaled_pts = [(x*chord, z*chord) for x,z in pts]
            # Create CQ Workplane
            # We want the wing to grow along Y axis (Span).
            # So profiles are on XZ plane?
            # Let's place root at XZ plane.
            # Rotate by twist around LE? (0,0) is LE.
            
            # Helper to rotate 2D point
            rad = math.radians(-twist_deg) # Negative usually for wash-out
            c_ang = math.cos(rad)
            s_ang = math.sin(rad)
            
            final_pts = []
            for px, pz in scaled_pts:
                # Rotate
                rx = px * c_ang - pz * s_ang
                rz = px * s_ang + pz * c_ang
                # Translate (Sweep/Dihedral handled by workplane usually, but here manually)
                # translate_vec is (dx, dy, dz)
                final_pts.append((rx + translate_vec[0], rz + translate_vec[2])) # Y is span
            
            # Make wire on a plane at Y = translate_vec[1]
            return cq.Workplane("XZ").workplane(offset=translate_vec[1]).polyline(final_pts).close()

        # Root Section
        w_root_wp = make_wire(cr, twist_root, (0, 0, 0))
        root_wire = w_root_wp.val()
        
        # Tip Section
        tip_x = span * math.tan(math.radians(sweep_deg))
        tip_y = span
        tip_z = span * math.tan(math.radians(dihedral_deg))
        
        w_tip_wp = make_wire(ct, twist_tip, (tip_x, tip_y, tip_z))
        tip_wire = w_tip_wp.val()
        
        # Loft Main Wing
        # Use a fresh workplane to collect the wires and mark them pending
        wing = cq.Workplane("XY").newObject([root_wire, tip_wire]).toPending().loft()
        
        # Winglet (Simplified: Vertical extrusion from tip)
        if winglet_h > 0.1:
            # We just extrude the tip wire face? Or loft to detailed winglet.
            # Simplified: Loft from tip to tip+offset
            # Winglet params
            cant = params.get("winglet_cant_deg", 70)
            
            # Vector for winglet
            # Cant 90 = vertical (Z), Cant 0 = flat (Y)
            # This logic depends on definitions. Assuming Cant is angle from spanwise.
            wc_rad = math.radians(cant)
            
            # dy, dz components of length winglet_h
            wh_y = winglet_h * math.cos(wc_rad)
            wh_z = winglet_h * math.sin(wc_rad)
            
            # Tip chord scales down? Let's assume taper 0.6 for winglet
            w_chord = ct * 0.6
            
            wl_x = tip_x + (tip_x/span)*wh_y # Continue sweep ratio? simplified
            wl_y = tip_y + wh_y
            wl_z = tip_z + wh_z
            
            w_tip_winglet_wp = make_wire(w_chord, twist_tip, (wl_x, wl_y, wl_z))
            winglet_wire = w_tip_winglet_wp.val()
            
            # Loft for winglet (from tip_wire to winglet_wire)
            winglet = cq.Workplane("XY").newObject([tip_wire, winglet_wire]).toPending().loft()
            wing = wing.union(winglet)

        # Export
        # Explicitly specify STEP format to avoid extension ambiguity
        cq.exporters.export(wing, output_path, exportType="STEP")
        return True
    except Exception as e:
        import traceback
        err_msg = traceback.format_exc()
        print(f"STEP Gen Error: {e}")
        with open(os.path.join(os.path.dirname(output_path), "step_error.txt"), "w") as f:
            f.write(err_msg)
        return False
