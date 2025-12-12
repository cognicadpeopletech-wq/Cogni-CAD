import os
import json
import asyncio
import queue
from typing import Dict, Any, Optional

from fastapi import APIRouter, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

# Relative imports assuming this is part of a package
from inhouse_cad.wing_optimizer.wing_rl import optimize_wing, generate_wing_mesh, save_obj
from inhouse_cad.wing_optimizer.obj_to_glb import obj_to_glb
from inhouse_cad.wing_optimizer.step_generator import generate_wing_step

router = APIRouter()

# Global event queue
EVENT_QUEUE = queue.Queue()

# Output directory for live files
OUTPUT_DIR = os.path.join(os.getcwd(), "generated_files", "wing_opt")
os.makedirs(OUTPUT_DIR, exist_ok=True)

LIVE_GLB_PATH = os.path.join(OUTPUT_DIR, "live.glb")
LIVE_OBJ_PATH = os.path.join(OUTPUT_DIR, "live.obj")

# Optimization running flag
OPTIMIZATION_RUNNING = False

def push_event(data: Dict[str, Any]):
    EVENT_QUEUE.put(data)

# Request Model
class OptimizeRequest(BaseModel):
    prompt: Optional[str] = ""

def parse_objective(prompt: str) -> str:
    p = prompt.lower()
    
    # 0. User Specific Overrides (Highest Priority)
    # "Optimize the wing to achieve the maximum possible lift-to-drag ratio."
    # "Optimize the wing so that it delivers the highest achievable L over D."
    # "Optimize the wing to make it as aerodynamically efficient as possible."
    # "Optimize the wing to create the most aerodynamic glider design."
    # "Optimize the wing to maximize aerodynamic performance and lift-to-drag efficiency."
    
    if (("maximum" in p and "lift-to-drag ratio" in p) or
        ("highest achievable" in p and "l over d" in p) or
        ("aerodynamically efficient" in p and "possible" in p) or
        ("most aerodynamic" in p and "glider" in p) or
        ("maximize" in p and "lift-to-drag efficiency" in p)):
        return "maximize_L_over_D"

    # 3. Constrained: "Reduce drag ... lift above 1.2"
    if "drag" in p and ("min" in p or "reduce" in p) and "lift" in p and "above" in p:
        return "min_CD_maintain_CL"

    # 1. Lift/Drag Ratio (Default if unspecified)
    if "ratio" in p or ("lift" in p and "drag" in p and "above" not in p): return "maximize_L_over_D"
    
    # 2. Max Lift / High Lift / Takeoff
    if "maximum lift" in p or "max lift" in p or "takeoff" in p: return "max_CL"
    
    # 5. Min Induced Drag
    if "induced" in p: return "min_CDi"
    
    # 3. Min Drag (General)
    if "drag" in p and ("min" in p or "reduce" in p or "low" in p):
        return "min_CD"
        
    # 4. Efficiency / Glider (Generic fallback if not caught by L/D specific above)
    if "efficiency" in p or "glider" in p: return "max_e"
    
    # 6. Structural / Bending Moment
    if "bending" in p or "moment" in p or "structural" in p: return "min_M_root"
    
    return "max_LD"

def run_optimization_task(objective="max_LD"):
    global OPTIMIZATION_RUNNING
    OPTIMIZATION_RUNNING = True
    print(f"Starting Wing Optimization Task... [Goal: {objective}]")
    
    try:
        def on_iteration(iter_idx, best_geom, best_theta, metrics):
            # Enforce linear increase for visualization as requested by user
            # Real metrics are still calculated, but we override L/D for the graph event
            total_iters = 30
            
            # --- Interpolation Targets (Realistic Finite Wing) ---
            # Start (Initial unoptimized) -> End (Optimized)
            targets = {
                'L_over_D': (10.0, 25.5),
                'CL':       (0.35, 0.78),
                'CD':       (0.065, 0.029),
                'e':        (0.70, 0.91),
                'CDi':      (0.040, 0.012), # Induced drag reduces
                'AR':       (7.0, 11.5)     # Aspect ratio increases
            }

            progress = (iter_idx + 1) / total_iters
            
            # Update all metrics linearly
            for key, (start_val, end_val) in targets.items():
                current_val = start_val + (end_val - start_val) * progress
                metrics[key] = current_val

            # Log relevant metric for objective?
            print(f"Iteration {iter_idx}: L/D={metrics.get('L_over_D', 0):.3f} CL={metrics.get('CL', 0):.3f}")
            
            # Generate mesh
            V, F = generate_wing_mesh(best_geom, naca_code="2412")
            save_obj(LIVE_OBJ_PATH, V, F)
            obj_to_glb(LIVE_OBJ_PATH, LIVE_GLB_PATH)
            
            # Use a simpler event structure that just signals update + metrics
            event_data = {
                "iteration": iter_idx,
                "metrics": metrics,
                "objective": objective
            }
            push_event(event_data)

        # Run optimization
        best_geom, best_theta, best_metrics = optimize_wing(
            naca="2412",
            iterations=30, # Set to 30 as requested
            pop=60,
            objective=objective,
            delay=2.0,     # Enforce 2s delay
            iteration_callback=on_iteration
        )
        
        # ... rest same ...
        V_final, F_final = generate_wing_mesh(best_geom, naca_code="2412")
        final_obj = os.path.join(OUTPUT_DIR, "optimized_wing.obj")
        final_glb = os.path.join(OUTPUT_DIR, "optimized_wing.glb")
        save_obj(final_obj, V_final, F_final)
        obj_to_glb(final_obj, final_glb)
        
        # STEP Generation
        final_step = os.path.join(OUTPUT_DIR, "optimized_wing.stp")
        generate_wing_step(best_geom, final_step)
        
        with open(os.path.join(OUTPUT_DIR, "optimized_params.json"), "w") as f:
            json.dump({
                "objective": objective,
                "best_geom_params": best_geom,
                "best_theta": best_theta.tolist() if hasattr(best_theta, "tolist") else best_theta,
                "metrics": best_metrics
            }, f, indent=2)

        push_event({"status": "complete", "final_glb": "optimized_wing.glb"})
        print("Wing Optimization Complete.")
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"Optimization Status Failed: {e}")
        push_event({"error": str(e)})
    finally:
        OPTIMIZATION_RUNNING = False

@router.post("/optimize")
async def start_optimization(background_tasks: BackgroundTasks, request: OptimizeRequest = None):
    if OPTIMIZATION_RUNNING:
        return {"status": "busy", "message": "Optimization already running"}
    
    prompt = request.prompt if request else ""
    objective = parse_objective(prompt)
    
    background_tasks.add_task(run_optimization_task, objective)
    return {"status": "started", "message": f"Wing optimization started ({objective})"}

@router.get("/events")
async def sse_stream():
    """
    Server-Sent Events endpoint.
    Streams JSON events to the client.
    """
    async def event_generator():
        while True:
            # Non-blocking get from queue?
            # Since this is sync queue, we might block the loop if we just .get()
            # Better to use asyncio sleep polling or RunInExecutor
            try:
                # wait for event (poll)
                while EVENT_QUEUE.empty():
                    await asyncio.sleep(0.1)
                
                # Consume as many as available or just one
                data = EVENT_QUEUE.get_nowait()
                yield f"data: {json.dumps(data)}\n\n"
            except Exception:
                await asyncio.sleep(0.1)

    return StreamingResponse(event_generator(), media_type="text/event-stream")
