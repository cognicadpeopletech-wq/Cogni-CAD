
import unittest
import sys
import os
import json
from pathlib import Path

# Setup path to import backend modules
current = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(current, "..", "..")) # backend
sys.path.append(os.path.join(current, "..")) # catia_copilot

try:
    from catia_copilot.prompt_router import route_explicit_command, MULTIPART_SCRIPT
    from catia_copilot.block_generator import build_flags_for_multipart
except ImportError:
    pass

class TestOptVariants(unittest.TestCase):
    def setUp(self):
        self.base_dir = Path("./tmp_test_opt")
        self.base_dir.mkdir(exist_ok=True)

    def tearDown(self):
        # cleanup
        pass

    def test_cyl_tube(self):
        # Prompt from ChatPanel: "Create baseplate length 200 width 150 thickness 20 with cylinder tube diameter 50 height 120 wall 2"
        cmd = "Create baseplate length 200 width 150 thickness 20 with cylinder tube diameter 50 height 120 wall 2"
        script, flags = route_explicit_command(cmd, self.base_dir)
        
        self.assertEqual(script, "catia_create_parts_dynamic_updated.py")
        self.assertTrue(len(flags) >= 1)
        
        # Check json content
        with open(flags[0], 'r') as f:
            params = json.load(f)
            
        self.assertEqual(params.get("WIDTH"), 200.0)
        self.assertEqual(params.get("WALL_THICKNESS"), 2.0)
        self.assertEqual(params.get("CYL_RADIUS"), 25.0) # diameter 50 -> radius 25

    def test_rect_rod(self):
        cmd = "Create baseplate length 200 width 150 thickness 20 with rectangular rod width 60 depth 40 height 100"
        script, flags = route_explicit_command(cmd, self.base_dir)
        
        self.assertEqual(script, "catia_create_parts_dynamic_rectrod.py")
        
        with open(flags[0], 'r') as f:
            params = json.load(f)
            
        self.assertEqual(params.get("ROD_WIDTH"), 60.0)
        self.assertEqual(params.get("ROD_DEPTH"), 40.0)
        self.assertEqual(params.get("ROD_HEIGHT"), 100.0)

    def test_rect_tube(self):
        cmd = "Create baseplate length 200 width 150 thickness 20 with rectangular tube width 60 depth 40 height 100 wall 3"
        script, flags = route_explicit_command(cmd, self.base_dir)
        
        self.assertEqual(script, "catia_create_parts_dynamic_rectrod_updated.py")
        
        with open(flags[0], 'r') as f:
            params = json.load(f)
            
        self.assertEqual(params.get("ROD_WIDTH"), 60.0)
        self.assertEqual(params.get("ROD_WALL_THICKNESS"), 3.0)

if __name__ == '__main__':
    unittest.main()
