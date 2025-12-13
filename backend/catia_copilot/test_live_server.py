
import urllib.request
import json
import time

def test_command(cmd):
    url = "http://127.0.0.1:8000/run_command"
    headers = {'Content-Type': 'application/json'}
    data = json.dumps({"command": cmd}).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers)
    
    try:
        with urllib.request.urlopen(req) as response:
            res_body = response.read().decode('utf-8')
            print(f"\nCommand: {cmd}")
            try:
                j = json.loads(res_body)
                if "Warning" in j.get("output", "") or "Command not recognized" in j.get("output", "") or "ERROR" in j.get("output", "") or "Traceback" in j.get("output", "") or "error" in j.get("output", "").lower():
                     print(" -> FAILURE detected in output")
                     print(j.get("output", ""))
                else:
                     print(" -> SUCCESS")
                     print(j.get("output", "")[:200] + "...")
            except:
                pass
            return res_body
    except Exception as e:
        print(f"Error for '{cmd}': {e}")
        return str(e)

if __name__ == "__main__":
    # 1. Block Holes with 'd6' syntax
    test_command("Generate a block (300x150x20) and put two holes: d6 at (20,20) and d6 at (280,130)")
    
    # 2. Plate Topology with 'diagonals' (plural)
    test_command("Make a 1000x500x40 mm plate, 10 holes on the diagonals, offset 75 mm from every corner hole dia 20 mm")

    # 3. Unicode Error Check
    test_command("Create circular topology: 10 holes on a 70 mm diameter circle for a 400x300x40 mm block with hole dia 20 mm")

    # 4. RL Script Crash (RectRod)
    test_command("Design the lightest baseplate + rectangle rod assembly that can support a 10kg load.")

    # 5. Cylinder Robust Check (User Request)
    test_command("create cylinder radius 25 pad height 20 pocket depth 20 instances 100")
