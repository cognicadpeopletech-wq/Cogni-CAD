
import sys
import os
import unittest
import shutil
from pathlib import Path

# Setup path so we can import from backend/catia_copilot
sys.path.append(os.path.join(os.getcwd(), 'backend'))

try:
    from catia_copilot.prompt_router import route_explicit_command, MULTIPART_SCRIPT
    from catia_copilot.block_generator import build_flags_for_multipart
except ImportError:
    # If running from root of repo
    sys.path.append(os.path.join(os.getcwd(), 'backend', 'catia_copilot'))
    from catia_copilot.prompt_router import route_explicit_command, MULTIPART_SCRIPT
    from catia_copilot.block_generator import build_flags_for_multipart

BASE_DIR = Path(os.getcwd())

class TestRoutingFix(unittest.TestCase):
    
    def test_multipart_routing_add_connector(self):
        # The prompt that currently fails
        cmd = "Create an assembly plate of size 300x200, pad thickness 25, and add a cylinder of radius 40 and height 150 positioned at (50, 30)."
        
        script, flags = route_explicit_command(cmd, BASE_DIR)
        
        print(f"DEBUG: Script routed to: {script}")
        print(f"DEBUG: Flags: {flags}")
        
        self.assertEqual(script, MULTIPART_SCRIPT, "Should route to multipart_dynamic.py")
        
    def test_multipart_routing_place_connector(self):
        cmd = "Generate an assembly plate of size 120x240 with pad 15, and place a cylinder of radius 35 and height 100 at coordinates (-20, 40)."
        script, flags = route_explicit_command(cmd, BASE_DIR)
        self.assertEqual(script, MULTIPART_SCRIPT, "Should route to multipart_dynamic.py")

    def test_multipart_params_extraction(self):
        # We also want to verify that build_flags_for_multipart extracts the correct coordinates
        # specifically the (50, 30) format
        cmd = "Create an assembly plate of size 300x200, pad thickness 25, and add a cylinder of radius 40 and height 150 positioned at (50, 30)."
        
        flags, params = build_flags_for_multipart(cmd, BASE_DIR)
        
        self.assertIsNotNone(params, "Params should not be None")
        if params:
            self.assertEqual(params.get("pos_x"), 50.0)
            self.assertEqual(params.get("pos_y"), 30.0)
            self.assertEqual(params.get("plate_width"), 300.0)
            self.assertEqual(params.get("plate_height"), 200.0)
            self.assertEqual(params.get("cyl_radius"), 40.0)

if __name__ == '__main__':
    unittest.main()
