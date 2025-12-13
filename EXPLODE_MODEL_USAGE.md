# Explode Model Function Usage

The `explodeModel(factor)` function in `ThreeCanvas.jsx` creates an animated explosion effect that separates model parts from their assembly center.

## How It Works

1. **Loads the GLB model** and extracts all meshes into a `meshMap`
2. **Computes the assembly center** using `Box3` for all meshes
3. **For each mesh**:
   - Calculates the direction from assembly center to mesh center
   - Computes target position: `originalPosition + (direction × factor)`
4. **Animates smoothly** using `requestAnimationFrame` over 800ms
5. **Stores exploded positions** in `mesh.userData.explodedPosition`

## API

### Expose the ref in App.jsx

```jsx
import ThreeCanvas from './components/ThreeCanvas';
import { useRef } from 'react';

function App() {
  const canvasRef = useRef(null);

  return (
    <div className="app">
      <ThreeCanvas ref={canvasRef} mode={mode} />
      <button onClick={() => canvasRef.current?.explodeModel(2)}>
        Explode Model
      </button>
    </div>
  );
}
```

### Function Signature

```jsx
explodeModel(factor = 1)
```

**Parameters:**
- `factor` (number, default: 1): Multiplier for explosion distance
  - `0`: All parts at assembly center
  - `1`: Parts move 1 unit along their direction vector
  - `2`: Parts move 2 units (double distance)
  - `0.5`: Parts move 0.5 units (half distance)

## Example Usage

```jsx
// Explode with factor of 2
canvasRef.current?.explodeModel(2);

// Explode with factor of 1.5
canvasRef.current?.explodeModel(1.5);

// Reset to original positions (factor 0)
canvasRef.current?.explodeModel(0);
```

## Implementation Details

### State Management
- `meshMapRef`: Stores all mesh objects from the loaded GLB
- `modelGroupRef`: Stores the scene/group containing all meshes
- `animationIdRef`: Tracks the current animation frame ID

### Animation
- **Duration**: 800ms (configurable)
- **Easing**: Linear interpolation using `lerpVectors`
- **Cancellation**: Previous animations are cancelled if `explodeModel` is called again

### Data Storage
Each mesh stores:
- `userData.originalPosition`: Initial position before explosion
- `userData.explodedPosition`: Final position after explosion animation

## Technical Notes

1. The function automatically cancels ongoing animations before starting a new one
2. Original positions are captured on first load and never change
3. Uses `Box3.expandByObject()` for accurate mesh bounds
4. Direction vectors are normalized for consistent explosion distances
5. Animation is smooth and performant using native `requestAnimationFrame`

## Error Handling

The function logs a warning if:
- Model hasn't finished loading yet
- No meshes were found in the scene

```jsx
console.warn('Model not loaded or no meshes found');
```

## Performance Considerations

- Suitable for models with up to 100+ meshes
- Animation runs at 60fps using `requestAnimationFrame`
- Each frame updates mesh positions via `lerpVectors`
- Automatic cleanup on new model load
