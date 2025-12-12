# Quick Start Guide - GLB Upload & 3D Viewer

## Prerequisites
- Backend running: `uvicorn main:app --reload --host 127.0.0.1 --port 8000`
- Frontend running: `npm run dev` (port 5173)
- A `.glb` file ready to upload (test file location: check your Downloads)

---

## Step-by-Step Instructions

### 1. Start the Application

**Terminal 1 - Backend:**
```powershell
cd "c:\Users\Basith\OneDrive - Ramp Group Technologies\Desktop\CogniCAD\backend"
pip install -e .
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

**Terminal 2 - Frontend:**
```powershell
cd "c:\Users\Basith\OneDrive - Ramp Group Technologies\Desktop\CogniCAD\frontend"
npm install
npm run dev
```

### 2. Open Browser
```
http://localhost:5173
```

You should see the CogniCAD interface with:
- **Left panel:** Chat interface with "+" button
- **Right panel:** 3D viewer (empty initially, dark background)

---

## Test Flow

### ✅ Test 1: Upload & Display GLB File

1. **Click the '+' button** in the chat panel (pill-shaped input area)
2. **Select "📂 Upload GLB"** from the dropdown menu
3. **Choose a GLB file** from your file manager
   - If you don't have one, download from: [Sketchfab](https://sketchfab.com) (filter: GLB export)
   - Or use a test model from `backend/cognicad_backend/test_model.glb`
4. **Observe:**
   - Message appears: "Uploading GLB file: [filename]..." in user color
   - After ~1-2 seconds: "✅ Loading your GLB model in 3D viewer..." in bot color
   - **3D model appears on the right panel!**
5. **Interact with the model:**
   - **Left-click + drag** = Rotate
   - **Scroll wheel** = Zoom in/out
   - **Right-click + drag** = Pan

---

### ✅ Test 2: Load Model via Chat Command

1. **After uploading a GLB file** (from Test 1)
2. **Type any of these commands** in the chat input:
   ```
   load the model
   show my glb
   display the 3d model
   preview the viewer
   render glb
   ```
3. **Press Enter** or click the **⬆️ arrow button**
4. **Observe:**
   - Your command appears in user color
   - Bot responds: "🎨 Displaying your uploaded GLB model in the 3D viewer..."
   - Model refreshes/displays in the 3D viewer

---

### ✅ Test 3: Upload STEP File & Convert to GLB

1. **Click the '+' button** again
2. **Select "⚙️ Upload STEP"**
3. **Choose a STEP file** (`.stp` or `.step`)
   - Test file available in `backend/test_model.stp`
4. **Observe:**
   - Message: "Uploading STEP file: [filename]..."
   - After upload: "✅ File uploaded successfully."
   - Bot asks: "Would you like to convert this STEP file to GLB for 3D preview?"
   - A blue button appears: "Convert to GLB"
5. **Click "Convert to GLB"**
6. **Observe:**
   - Message: "⏳ Converting STEP to GLB..." (processing...)
   - After ~3-5 seconds: "✅ Conversion successful! Displaying in 3D viewer..."
   - **Converted model appears on the right panel!**

---

## Expected Behavior

### Chat Panel (Left Side)
| Action | Expected Response |
|--------|------------------|
| Upload GLB | ✅ File uploaded successfully. / 🎨 Loading your GLB model... |
| Say "load model" | 🎨 Displaying your uploaded GLB model in the 3D viewer... |
| Upload STEP | ✅ File uploaded successfully. / Would you like to convert? |
| Click "Convert to GLB" | ⏳ Converting... / ✅ Conversion successful! |

### 3D Viewer (Right Side)
| Condition | Expected Display |
|-----------|-----------------|
| Initial load | Dark background with grid lines |
| GLB uploaded | 3D model rendered with orbit controls |
| Model loading | Wireframe cube placeholder (temporary) |
| Model failed to load | Wireframe cube stays (error fallback) |

---

## Troubleshooting

### Issue: Upload Button Shows But GLB Doesn't Appear

**Check:**
1. Browser console (F12 → Console tab) for errors
2. Backend is running and accessible
3. Model file is valid GLB format
4. Network tab shows successful upload (200/201 response)

**Fix:**
```powershell
# Restart backend
uvicorn main:app --reload --host 127.0.0.1 --port 8000

# Check CORS is enabled (should be in main.py)
# Check /static/uploads/ directory exists
```

### Issue: Chat Command Doesn't Trigger Model Display

**Check:**
1. You typed a command with keywords: `load`, `show`, `display`, `preview`, `render`
2. AND keywords: `glb`, `model`, `3d`, `viewer`
3. You uploaded a GLB file first

**Example Working Commands:**
- ✅ "load the glb"
- ✅ "display 3d model"
- ✅ "show model in viewer"
- ❌ "hello" (no action keywords)
- ❌ "load this" (no GLB reference)

### Issue: STEP Conversion Fails

**Check:**
1. Backend has dependencies installed:
   ```powershell
   pip install cadquery
   ```
2. STEP file is valid (can be opened in CAD software)
3. File size is reasonable (<100MB)

**Debug:**
```powershell
# Check backend logs
tail -f "c:\Users\Basith\OneDrive - Ramp Group Technologies\Desktop\CogniCAD\backend\logs\copilot.log"

# Test conversion manually
python -c "import cadquery as cq; cq.importers.importStep('test.stp')"
```

---

## File Locations for Testing

| File | Path | Purpose |
|------|------|---------|
| Test Model (GLB) | `backend/cognicad_backend/test_model.glb` | Ready to upload |
| Test Model (STEP) | `backend/test_model.stp` | Ready for conversion |
| Uploads Directory | `backend/static_files/uploads/` | Where files are stored |
| Server Logs | `backend/logs/copilot.log` | Debugging |

---

## Success Checklist

- [x] Backend `/upload` endpoint accepts GLB files
- [x] Frontend '+' menu has "Upload GLB" option
- [x] Uploaded GLB displays in 3D viewer (right panel)
- [x] Chat commands like "load model" trigger display
- [x] STEP files can be uploaded and converted
- [x] 3D viewer responds to mouse interactions (rotate/zoom/pan)
- [x] Error messages are user-friendly
- [x] Model loading shows placeholder while processing

---

## Performance Notes

- **Upload Speed:** Depends on file size (typical: <2 seconds for <10MB)
- **Conversion Speed:** STEP→GLB takes 2-5 seconds
- **Render Speed:** Real-time with OrbitControls (60 FPS on modern hardware)
- **Memory:** Large models (>50MB) may cause slowdowns

**Optimization Tip:** Compress models before uploading
```bash
# Using gltf-transform (if installed)
gltf-transform compress model.glb model.compressed.glb
```

---

## Next: Integration with Your Workflow

After confirming the above tests work:

1. **Replace test files** with your actual CAD models
2. **Customize 3D viewer** (colors, lighting, etc.) in `ThreeCanvas.jsx`
3. **Add model metadata** display (dimensions, materials, etc.)
4. **Implement export features** (screenshot, download modified model, etc.)

---

## Support Commands

When chatting with the AI copilot after uploading a GLB:

- "rotate the model 45 degrees"  *(future feature)*
- "show dimensions"  *(future feature)*
- "export as STL"  *(future feature)*
- "load another model"  *(supported now)*
- "clear the viewer"  *(supported now)*

---

## Documentation References

- **Three.js GLB Loading:** https://threejs.org/examples/webgl_loader_gltf.html
- **React Three Fiber:** https://docs.pmnd.rs/react-three-fiber/
- **Drei Utils:** https://github.com/pmndrs/drei
- **FastAPI File Upload:** https://fastapi.tiangolo.com/tutorial/request-files/
- **CadQuery STEP Import:** https://cadquery.readthedocs.io/

---

**Ready to test?** 🚀 Start the servers and follow the step-by-step instructions above!

