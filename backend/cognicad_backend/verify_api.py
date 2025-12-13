import requests
import json
import time

BASE_URL = "http://localhost:8000/api"

def test_interpret():
    print("Testing /interpret...")
    # Retry loop to wait for server
    for i in range(5):
        try:
            response = requests.post(f"{BASE_URL}/interpret", json={"prompt": "rectangle 100x200x40mm color red"})
            if response.status_code == 200:
                data = response.json()
                print("Success:", json.dumps(data, indent=2))
                assert data["type"] == "box"
                assert data["params"]["width"] == 100.0
                assert data["material"]["color"] == "red"
                return
        except Exception as e:
            print(f"Waiting for server... ({e})")
            time.sleep(2)
    print("Failed to connect to server")

def test_generate():
    print("Testing /generate...")
    geometry = {
        "type": "box",
        "params": {"width": 100, "height": 40, "depth": 200},
        "material": {"color": "red"},
        "units": "mm"
    }
    response = requests.post(f"{BASE_URL}/generate?format=glb", json=geometry)
    if response.status_code == 200:
        print(f"Success: Received {len(response.content)} bytes")
        with open("test_model.glb", "wb") as f:
            f.write(response.content)
    else:
        print("Failed:", response.text)

def test_cylinder():
    print("Testing /interpret (Cylinder)...")
    response = requests.post(f"{BASE_URL}/interpret", json={"prompt": "Create a Cylinder with diameter 20 mm and height 80 mm"})
    if response.status_code == 200:
        data = response.json()
        print("Success:", json.dumps(data, indent=2))
        assert data["type"] == "cylinder"
        assert data["params"]["diameter"] == 20.0
        assert data["params"]["height"] == 80.0
    else:
        print("Failed:", response.text)

def test_l_bracket():
    print("Testing /interpret (L-Bracket)...")
    response = requests.post(f"{BASE_URL}/interpret", json={"prompt": "Create a 50 x 50 x 10 L bracket with bend radius 10mm"})
    if response.status_code == 200:
        data = response.json()
        print("Success:", json.dumps(data, indent=2))
        assert data["type"] == "l_bracket"
        assert data["params"]["width"] == 50.0
        assert data["params"]["thickness"] == 10.0
    else:
        print("Failed:", response.text)

def test_step_export():
    print("Testing /generate (STEP)...")
    geometry = {
        "type": "box",
        "params": {"width": 100, "height": 40, "depth": 200},
        "material": {"color": "red"},
        "units": "mm"
    }
    response = requests.post(f"{BASE_URL}/generate?format=step", json=geometry)
    if response.status_code == 200:
        print(f"Success: Received {len(response.content)} bytes")
        with open("test_model.stp", "wb") as f:
            f.write(response.content)
    else:
        print("Failed:", response.text)

if __name__ == "__main__":
    try:
        test_interpret()
        test_cylinder()
        test_l_bracket()
        test_generate()
        test_step_export()
    except Exception as e:
        print("Error:", e)
