
import sys
import os
from pathlib import Path

# Add backend to sys.path
sys.path.append(str(Path.cwd() / "backend"))

from catia_copilot.prompt_router import route_explicit_command

prompt = "Make a 1000x500x40 mm plate, 4 holes on the diagonals, offset 75 mm from every corner hole dia 20 mm"
print(f"Testing Prompt: {prompt}")

script, flags = route_explicit_command(prompt, Path.cwd())
print(f"Script: {script}")
print(f"Flags: {flags}")
