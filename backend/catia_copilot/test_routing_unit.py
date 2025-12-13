
import sys
import os
import unittest
from pathlib import Path

# Add current dir to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from main import route_explicit_command, BASE_DIR

class TestDetailedRouting(unittest.TestCase):
    
    def test_parametric_block(self):
        cmd = "Create a 200x200x50"
        script, flags = route_explicit_command(cmd, BASE_DIR)
        self.assertEqual(script, "Parametric_Block_Run.py")
        self.assertIn("--length", flags)
        self.assertIn("200.0", flags)

    def test_parametric_block_with_holes(self):
        cmd = "Create a 200x200x50 block with 2 holes at (50,50) dia 10"
        script, flags = route_explicit_command(cmd, BASE_DIR)
        self.assertEqual(script, "Parametric_Block_Run.py")
        self.assertIn("--hole_1_x", flags)
        self.assertIn("--hole_1_d", flags)

    def test_circular_topology(self):
        cmd = "Create circular topology: 10 holes on a 70 mm diameter circle for a 400x300x40 mm block"
        script, flags = route_explicit_command(cmd, BASE_DIR)
        self.assertEqual(script, "circular_topology_dynamic.py")
        self.assertTrue(any(x in flags for x in ["--L", "400.0", "400", "400.0"]))
        self.assertTrue(any(x in flags for x in ["--diameter", "--circle_dia", "70", "70.0"]))

    def test_cylinder(self):
        cmd = "create cylinder diameter 80 height 150"
        script, flags = route_explicit_command(cmd, BASE_DIR)
        # SCRIPT_CYLINDER is create_cylinder_interactive.py
        self.assertEqual(script, "create_cylinder_interactive.py")
        self.assertIn("--diameter", flags)
        self.assertIn("80.0", flags)

    def test_circular_disk(self):
        cmd = "Create disk diameter 220 thickness 15 WITH 3 HOLES 16 diameter at (0,0)"
        script, flags = route_explicit_command(cmd, BASE_DIR)
        self.assertEqual(script, "circular_disk_dynamic.py")
        self.assertIn("--diameter", flags)
        self.assertIn("220.0", flags)
        # Check for --hole=x,y,d format
        self.assertTrue(any(f.startswith("--hole=") for f in flags))

    def test_color(self):
        cmd = "Color the part"
        script, flags = route_explicit_command(cmd, BASE_DIR)
        self.assertEqual(script, "color.py")

    def test_l_bracket(self):
        cmd = "Create an 85x60 sheet metal L-bracket, thickness 10 mm, width 18 mm"
        script, flags = route_explicit_command(cmd, BASE_DIR)
        self.assertEqual(script, "L-Brac.py")
        # width maps to extrude_len in logic
        self.assertIn("--extrude_len", flags)
        # 18 mm
        self.assertTrue("18.0" in flags or "18" in flags) 

if __name__ == "__main__":
    unittest.main()
