
import sys
import os
import unittest
from pathlib import Path

# Setup path
# When running via python -m ... from root, typical path is just root
# But prompt_router imports "from catia_copilot...", suggesting catia_copilot is a package in path
# OR backend is in path.

current = os.path.dirname(os.path.abspath(__file__))
# tests is in backend/catia_copilot/tests
# we want valid imports
sys.path.append(os.path.join(current, "..", "..")) # backend
sys.path.append(os.path.join(current, "..")) # catia_copilot

try:
    from catia_copilot.prompt_router import route_explicit_command, MULTIPART_SCRIPT
    from catia_copilot.block_generator import build_flags_for_multipart
except ImportError:
    # If standard import fails, try relative or adjust path
    pass

BASE_DIR = Path(os.getcwd())

class TestOptimizationPrompt(unittest.TestCase):
    
    def test_optimization_result_prompt(self):
        # The prompt from the user screenshot
        cmd = "Create baseplate length 192 width 90 thickness 20 with cylinder diameter 58 height 52"
        
        script, flags = route_explicit_command(cmd, BASE_DIR)
        print(f"DEBUG: Script: {script}")
        print(f"DEBUG: Flags: {flags}")
        
        # User says this should run 'catia_create_parts_dynamic.py'
        # Currently, my previous change might make it 'multipart_dynamic.py'
        # But if it returns None, that explains "Command not recognized"
        
        self.assertIsNotNone(script, "Script should not be None (Command not recognized)")
        # Ideally:
        expected_script = "catia_create_parts_dynamic.py"
        self.assertEqual(script, expected_script)

    def test_extraction_values(self):
        cmd = "Create baseplate length 192 width 90 thickness 20 with cylinder diameter 58 height 52"
        flags, params = build_flags_for_multipart(cmd, BASE_DIR)
        
        self.assertIsNotNone(params)
        print(f"DEBUG: Params: {params}")
        if params:
            self.assertEqual(params.get("plate_width"), 90.0) # width
            self.assertEqual(params.get("plate_height"), 192.0) # length mapped to height/length? Need to check logic
            self.assertEqual(params.get("pad_thickness"), 20.0)
            self.assertEqual(params.get("cyl_radius"), 29.0) # 58/2
            self.assertEqual(params.get("cyl_height"), 52.0)

if __name__ == '__main__':
    unittest.main()
