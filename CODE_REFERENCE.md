# Code Reference - GLB Upload & 3D Viewer Implementation

## Quick Code References

### Frontend - ChatPanel.jsx

#### Function 1: parseGLBCommand()
Detects if user wants to load/display a GLB model.

```jsx
const parseGLBCommand = (cmd) => {
  const lowerCmd = cmd.toLowerCase();
  const glbLoadKeywords = ['load', 'display', 'show', 'view', 'preview', 'render'];
  const glbTypeKeywords = ['glb', 'model', '3d', 'viewer'];
  
  const hasLoadAction = glbLoadKeywords.some(kw => lowerCmd.includes(kw));
  const hasGLBReference = glbTypeKeywords.some(kw => lowerCmd.includes(kw));
  
  return hasLoadAction && hasGLBReference;
};
```

**Usage:**
```jsx
if (isGLBCommand && uploadedFile) {
  // Display the model
  setLatestResult({ glb_url: uploadedFile });
}
```

---

#### Function 2: handleSend() - Updated
Now includes GLB command detection before sending to backend.

```jsx
const handleSend = async (manualCmd = null, hidden = false) => {
  const cmdToSend = (typeof manualCmd === 'string') ? manualCmd : input;
  if (!cmdToSend.trim()) return;

  // ✨ NEW: Check if user is trying to load a GLB model
  const isGLBCommand = parseGLBCommand(cmdToSend);
  if (isGLBCommand && uploadedFile) {
    if (!hidden) addMessage(cmdToSend, 'user');
    addMessage("🎨 Displaying your uploaded GLB model in the 3D viewer...", 'bot');
    setLatestResult({ glb_url: uploadedFile });
    if (!manualCmd) setInput('');
    return;  // ← Exit early, don't send to backend
  }

  // ... rest of handleSend logic
};
```

**Key Points:**
- Checks for GLB command BEFORE backend call
- Uses uploadedFile state to retrieve stored URL
- Calls setLatestResult() to trigger model display
- Returns early to skip unnecessary API call

---

#### Function 3: handleFileUpload() - Updated
Enhanced GLB file upload with automatic display.

```jsx
const handleFileUpload = async (e, type) => {
  const file = e.target.files?.[0];
  if (!file) return;

  addMessage(`Uploading ${type.toUpperCase()} file: ${file.name}...`, 'user');
  setLoading(true);

  const res = await uploadFile(file, type);
  setLoading(false);

  if (res.url) {
    addMessage(`✅ File uploaded successfully.`, 'bot');
    setUploadedFile(res.url);

    // ✨ NEW: Auto-display GLB files
    if (type === 'glb') {
      addMessage("🎨 Loading your GLB model in 3D viewer...", 'bot');
      setLatestResult({ glb_url: res.url });  // ← Triggers display
    }

    // Handle STEP conversion flow
    if (type === 'step') {
      const triggerConversion = async () => {
        // ... conversion logic
      };

      addMessage("Would you like to convert this STEP file to GLB for 3D preview?", 'bot', {
        label: "Convert to GLB",
        onClick: triggerConversion
      });
    }
  }

  e.target.value = null;
};
```

**Key Changes:**
- Direct GLB display: `setLatestResult({ glb_url: res.url })`
- Emoji feedback: `"🎨 Loading..."`
- Stores URL in `uploadedFile` for later command use

---

### Frontend - ThreeCanvas.jsx

#### Component: LoadingPlaceholder()
Displayed while GLB is loading from URL.

```jsx
function LoadingPlaceholder() {
  return (
    <mesh position={[0, 0, 0]}>
      <boxGeometry args={[1, 1, 1]} />
      <meshStandardMaterial color="#4f46e5" wireframe />
    </mesh>
  );
}
```

**Purpose:** Shows the user something is loading (wireframe blue cube)

---

#### Updated: useGLTF Hook Usage
```jsx
function ModelViewer({ url }) {
  const { scene } = useGLTF(url);
  return <primitive object={scene} />;
}
```

**Three.js Integration:**
- `useGLTF(url)` - Loads GLB/GLTF from URL
- Returns `scene` object containing 3D geometry
- `<primitive object={scene} />` - Renders in Three.js canvas

---

#### Component: ThreeCanvas - Full Updated Code
```jsx
const ThreeCanvas = ({ mode }) => {
  const { latestResult } = useUIStore();
  const [modelUrl, setModelUrl] = useState(null);
  const [loadError, setLoadError] = useState(false);  // ← Error handling

  useEffect(() => {
    if (latestResult?.glb_url) {
      setModelUrl(latestResult.glb_url);
      setLoadError(false);
    }
  }, [latestResult]);

  const handleModelError = () => {
    setLoadError(true);  // ← Fallback on error
  };

  return (
    <Canvas shadows camera={{ position: [4, 4, 4], fov: 50 }}>
      <color attach="background" args={['#050505']} />
      <Environment preset="city" />
      
      <Suspense fallback={<LoadingPlaceholder />}>
        <Stage intensity={0.5} environment="city" adjustCamera={true}>
          {modelUrl && !loadError ? (
            <ModelViewer url={modelUrl} />
          ) : modelUrl && loadError ? (
            <LoadingPlaceholder />  // ← Fallback if load fails
          ) : null}
        </Stage>
      </Suspense>

      <Grid 
        renderOrder={-1} 
        position={[0, -0.01, 0]} 
        infiniteGrid 
        cellSize={1} 
        sectionSize={5} 
        fadeDistance={25} 
        sectionColor="#4f46e5" 
        cellColor="#222" 
      />
      
      <OrbitControls makeDefault />
    </Canvas>
  );
};
```

**State Management:**
- `modelUrl` - Current GLB URL to display
- `loadError` - Tracks if GLB failed to load
- `useEffect` - Watches for latestResult changes
- Conditional rendering - Shows model or placeholder

---

### Frontend - State Flow

```
User Action
    ↓
ChatPanel Handler (handleFileUpload, handleSend)
    ↓
setUploadedFile(url)  ← Stores in component state
    ↓
setLatestResult({ glb_url: url })  ← Updates global store
    ↓
ThreeCanvas useEffect triggers
    ↓
setModelUrl(url)  ← Updates local state
    ↓
Canvas re-renders with <ModelViewer url={modelUrl} />
    ↓
Three.js loads and displays GLB
```

---

### Backend - main.py Endpoints

#### POST /upload
Already implemented. Usage from frontend:

```javascript
// api.js
export const uploadFile = async (file, type) => {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('type', type);  // 'glb', 'step', 'bom'

  const response = await api.post('/upload', formData);
  return response.data;
};
```

**Response Example:**
```json
{
  "url": "http://127.0.0.1:8000/static/uploads/550e8400-e29b-41d4-a716-446655440000.glb",
  "message": "File uploaded successfully",
  "filename": "550e8400-e29b-41d4-a716-446655440000.glb"
}
```

**Implementation (backend/main.py, line ~343):**
```python
@main_router.post("/upload")
async def upload_file(
    file: UploadFile = File(...), 
    type: str = Form(...),
    convert: str = Form(None)
):
    try:
        ext = os.path.splitext(file.filename)[1].lower()
        safe_name = f"{uuid.uuid4()}{ext}"
        upload_dir = STATIC_DIR / "uploads"
        upload_dir.mkdir(parents=True, exist_ok=True)
        file_path = upload_dir / safe_name
        
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        file_url = f"http://127.0.0.1:8000/static/uploads/{safe_name}"
        msg = f"Uploaded {file.filename} successfully."
        
        # Handle specific types
        if type.lower() == "glb":
            return JSONResponse({"url": file_url, "message": msg})
        
        return JSONResponse({"url": file_url, "message": msg, "filename": safe_name})
        
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)
```

---

#### POST /convert
Converts STEP to GLB. Already implemented:

```javascript
// api.js
export const convertFile = async (filename) => {
  const formData = new FormData();
  formData.append('filename', filename);

  const response = await api.post('/convert', formData);
  return response.data;
};
```

**Response Example:**
```json
{
  "glb_url": "http://127.0.0.1:8000/static/uploads/abc123.glb",
  "message": "Conversion completed. (via CadQuery)"
}
```

---

### Frontend - uiStore.js (No Changes Needed)

Already supports action messages:

```javascript
addMessage: (text, sender, action = null) => set((state) => ({ 
  messages: [...state.messages, { id: Date.now(), text, sender, action }] 
})),
```

**Message Object Structure:**
```javascript
{
  id: 1702200000000,
  text: "Model uploaded successfully",
  sender: 'bot',
  action: {
    type: 'downloads',      // or custom action
    items: { csv, xlsx, pdf }
    // or
    label: "Convert to GLB",
    onClick: functionRef
  }
}
```

---

## Data Flow Diagrams

### Flow 1: Upload GLB → Display
```
User selects file
  ↓ [File Input]
handleFileUpload(e, 'glb')
  ↓
uploadFile(file, 'glb')  [API call]
  ↓
Backend: /upload receives file
  ↓
Save to: static_files/uploads/[uuid].glb
  ↓
Return: { url: "http://127.0.0.1:8000/static/uploads/[uuid].glb" }
  ↓
setUploadedFile(res.url)
  ↓
setLatestResult({ glb_url: res.url })
  ↓ [Updates store]
ThreeCanvas receives latestResult
  ↓ [useEffect]
setModelUrl(glb_url)
  ↓ [Updates state]
Canvas re-renders
  ↓
useGLTF(modelUrl) loads GLB
  ↓
<primitive object={scene} /> renders
  ↓
3D model visible in viewer!
```

### Flow 2: Chat Command → Display
```
User types: "load the model"
  ↓
handleSend()
  ↓
parseGLBCommand("load the model")
  ↓ returns true
uploadedFile exists?
  ↓ yes
setLatestResult({ glb_url: uploadedFile })
  ↓
ThreeCanvas useEffect triggers
  ↓
setModelUrl(glb_url)
  ↓
Canvas re-renders
  ↓
GLB displays (already loaded, just showing)
```

### Flow 3: Upload STEP → Convert → Display
```
User selects STEP file
  ↓
handleFileUpload(e, 'step')
  ↓
uploadFile(file, 'step')  [API call]
  ↓
Backend: /upload receives STEP
  ↓
Save to: static_files/uploads/[uuid].stp
  ↓
Return: { url: "...", filename: "[uuid].stp" }
  ↓
addMessage("Convert to GLB?", 'bot', { onClick: triggerConversion })
  ↓ [User clicks button]
triggerConversion()
  ↓
convertFile(filename)  [API call]
  ↓
Backend: /convert receives filename
  ↓
CadQuery/OCP converts STEP → GLB
  ↓
Save to: static_files/uploads/[uuid2].glb
  ↓
Return: { glb_url: "...[uuid2].glb" }
  ↓
setLatestResult({ glb_url: ... })
  ↓
[Same as Flow 1 from here]
```

---

## Customization Points

### Change Loading Placeholder Color
**File:** `frontend/src/components/ThreeCanvas.jsx`

```jsx
// Change from:
<meshStandardMaterial color="#4f46e5" wireframe />

// To:
<meshStandardMaterial color="#ef4444" wireframe />  // Red
<meshStandardMaterial color="#22c55e" wireframe />  // Green
<meshStandardMaterial color="#f59e0b" wireframe />  // Amber
```

### Change Background Color
```jsx
// Change from:
<color attach="background" args={['#050505']} />

// To:
<color attach="background" args={['#1a1a2e']} />  // Dark blue
<color attach="background" args={['#0f0f0f']} />  // Darker
```

### Change Camera Position
```jsx
// Change from:
<Canvas camera={{ position: [4, 4, 4], fov: 50 }}>

// To:
<Canvas camera={{ position: [6, 6, 6], fov: 50 }}>  // Further away
<Canvas camera={{ position: [8, 4, 8], fov: 35 }}>  // Wide angle
```

### Change Grid Style
```jsx
// Modify Grid props:
<Grid 
  cellSize={0.5}           // Smaller cells
  sectionSize={10}         // Larger sections
  sectionColor="#ff0000"   // Red sections
  cellColor="#00ff00"      // Green cells
  fadeDistance={50}        // Fade sooner
/>
```

### Add More Keywords to GLB Command Parser
```jsx
// Add to glbLoadKeywords:
const glbLoadKeywords = ['load', 'display', 'show', 'view', 'preview', 'render', 'fetch', 'retrieve'];

// Add to glbTypeKeywords:
const glbTypeKeywords = ['glb', 'model', '3d', 'viewer', 'object', 'mesh', 'geometry'];
```

---

## Common Modifications

### Allow Multiple File Types in Upload
```jsx
// Change from:
<input type="file" accept=".glb,.gltf" />

// To:
<input type="file" accept=".glb,.gltf,.glb.gz" />
```

### Add File Size Validation
```javascript
const MAX_FILE_SIZE = 50 * 1024 * 1024; // 50MB

if (file.size > MAX_FILE_SIZE) {
  addMessage(`❌ File too large. Max ${MAX_FILE_SIZE / (1024*1024)}MB`, 'bot');
  return;
}
```

### Add File Type Validation
```javascript
const validGLBTypes = ['model/gltf-binary', 'model/gltf+json', 'application/octet-stream'];

if (!validGLBTypes.includes(file.type)) {
  addMessage(`❌ Invalid file type. Please upload a GLB file.`, 'bot');
  return;
}
```

### Change Upload API Endpoint
```javascript
// In ChatPanel.jsx, change:
const res = await uploadFile(file, 'glb');

// To custom endpoint:
const formData = new FormData();
formData.append('file', file);
const res = await fetch('http://custom-server/upload', {
  method: 'POST',
  body: formData
});
```

---

## Testing Code Snippets

### Manual Test 1: Check if parseGLBCommand Works
```javascript
// Open browser console and paste:
function parseGLBCommand(cmd) {
  const lowerCmd = cmd.toLowerCase();
  const glbLoadKeywords = ['load', 'display', 'show', 'view', 'preview', 'render'];
  const glbTypeKeywords = ['glb', 'model', '3d', 'viewer'];
  const hasLoadAction = glbLoadKeywords.some(kw => lowerCmd.includes(kw));
  const hasGLBReference = glbTypeKeywords.some(kw => lowerCmd.includes(kw));
  return hasLoadAction && hasGLBReference;
}

// Test cases:
console.log(parseGLBCommand("load the model"));  // true
console.log(parseGLBCommand("show glb"));        // true
console.log(parseGLBCommand("hello world"));     // false
```

### Manual Test 2: Check Store State
```javascript
// In browser console:
import useUIStore from '../store/uiStore';

const store = useUIStore();
console.log(store.latestResult);  // Should have glb_url
console.log(store.messages);      // Should show upload messages
```

### Manual Test 3: Check API Response
```javascript
// In browser console:
const uploadTest = async () => {
  const file = new File(['test'], 'test.glb');
  const form = new FormData();
  form.append('file', file);
  form.append('type', 'glb');
  
  const res = await fetch('http://127.0.0.1:8000/upload', {
    method: 'POST',
    body: form
  });
  
  console.log(await res.json());
};

uploadTest();
```

---

## Debugging Tips

### Enable Verbose Logging
Add to ChatPanel.jsx:
```jsx
const handleFileUpload = async (e, type) => {
  console.log('[DEBUG] Upload started for type:', type);
  console.log('[DEBUG] File:', e.target.files?.[0]);
  
  const res = await uploadFile(file, type);
  console.log('[DEBUG] Upload response:', res);
  
  if (res.url) {
    console.log('[DEBUG] Setting modelUrl to:', res.url);
    setLatestResult({ glb_url: res.url });
  }
};
```

### Check Three.js Errors
```jsx
<Suspense fallback={
  <div style={{ color: 'white' }}>Loading model...</div>
}>
  {modelUrl && (
    <ErrorBoundary onError={(err) => {
      console.error('[Three.js Error]', err);
      setLoadError(true);
    }}>
      <ModelViewer url={modelUrl} />
    </ErrorBoundary>
  )}
</Suspense>
```

### Monitor Network Requests
Use Firefox/Chrome DevTools:
1. Open DevTools (F12)
2. Go to Network tab
3. Upload file
4. Check:
   - POST /upload → 200 response
   - File download starts from /static/uploads/
   - GLB file size and type

---

## Summary

| Component | File | Key Function |
|-----------|------|--------------|
| Command Parser | ChatPanel.jsx | `parseGLBCommand()` |
| Upload Handler | ChatPanel.jsx | `handleFileUpload()` |
| Send Handler | ChatPanel.jsx | `handleSend()` |
| Model Viewer | ThreeCanvas.jsx | `<ModelViewer />` |
| Loading UI | ThreeCanvas.jsx | `<LoadingPlaceholder />` |
| Backend Upload | main.py | `/upload` endpoint |
| Backend Convert | main.py | `/convert` endpoint |
| Global State | uiStore.js | `setLatestResult()` |

All components work together to provide a seamless GLB upload and viewing experience! 🚀

