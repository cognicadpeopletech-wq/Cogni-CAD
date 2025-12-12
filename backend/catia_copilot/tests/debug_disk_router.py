
import sys
from pathlib import Path

# Add backend to sys.path
sys.path.append(str(Path.cwd() / "backend"))

from catia_copilot.prompt_router import route_explicit_command

prompt = "Create 6 diagonal holes on a diameter 100 disk thickness 5 offset 20 dia 5"
print(f"Testing Prompt: {prompt}")

script, flags = route_explicit_command(prompt, Path.cwd())
print(f"Script: {script}")
print(f"Flags: {flags}")
