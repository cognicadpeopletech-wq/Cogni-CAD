import React, { Suspense, useEffect, useState, useRef } from 'react';
import { Canvas, useThree, useFrame } from '@react-three/fiber';
import { OrbitControls, Grid, Environment, useGLTF, Center, Bounds, ContactShadows, Html, TransformControls, Line } from '@react-three/drei';
import * as THREE from 'three';
import useUIStore from '../store/uiStore';
import ViewerToolbar from './ViewerToolbar';
import OrientationCube from './OrientationCube';

// --- HELPER: Snap to Feature (Vertex/Edge) ---
const snapToFeature = (intersect, cam) => {
  if (!intersect.face || !intersect.object) return intersect.point;

  const { face, object, point } = intersect;
  const positions = object.geometry.attributes.position;

  // Get vertices in World Space
  const getV = (idx) => {
    const v = new THREE.Vector3().fromBufferAttribute(positions, idx);
    return object.localToWorld(v);
  };

  const vA = getV(face.a);
  const vB = getV(face.b);
  const vC = getV(face.c);
  const vertices = [vA, vB, vC];

  let closestPoint = point; // Default to hit point
  let minMsgDist = Infinity;

  // threshold: 2% of camera distance for easier picking but allowing face selection
  const threshold = cam.position.distanceTo(point) * 0.02;

  // 1. Check Vertices
  vertices.forEach(v => {
    const d = v.distanceTo(point);
    if (d < minMsgDist) {
      minMsgDist = d;
      closestPoint = v;
    }
  });

  // 2. Check Edges (AB, BC, CA)
  const edges = [[vA, vB], [vB, vC], [vC, vA]];
  edges.forEach(([v1, v2]) => {
    const line = new THREE.Line3(v1, v2);
    const closestOnLine = new THREE.Vector3();
    line.closestPointToPoint(point, true, closestOnLine);
    const d = closestOnLine.distanceTo(point);

    // Prefer Vertex if distance is very similar (within 10%)
    if (d < minMsgDist * 0.9) {
      minMsgDist = d;
      closestPoint = closestOnLine;
    }
  });

  if (minMsgDist < threshold) {
    return closestPoint;
  }
  return point;
};

// --- COMPONENT: Fixed Size Marker ---
// --- COMPONENT: Fixed Size Marker (Scaled by Distance) ---
const FixedSizeMarker = ({ position, label }) => {
  const mesh = useRef();
  const { camera } = useThree();

  useFrame(() => {
    if (mesh.current) {
      // Scale based on distance to maintain constant screen size
      const dist = camera.position.distanceTo(new THREE.Vector3(...position));
      const scale = dist * 0.015; // Adjustment factor for size (approx small dot)
      mesh.current.scale.setScalar(scale);
      mesh.current.lookAt(camera.position);
    }
  });

  return (
    <group position={position}>
      <mesh ref={mesh}>
        <sphereGeometry args={[1, 16, 16]} />
        <meshBasicMaterial color="#00ff00" depthTest={false} transparent opacity={0.8} />
      </mesh>
      {label && (
        <Html position={[0, 0, 0]} center style={{ pointerEvents: 'none' }}>
        </Html>
      )}
    </group>
  );
};

// --- COMPONENT: FaceHighlight ---
const FaceHighlight = ({ vertices }) => {
  const geometry = React.useMemo(() => {
    if (!vertices) return null;
    const geo = new THREE.BufferGeometry();
    const positions = new Float32Array([
      vertices[0].x, vertices[0].y, vertices[0].z,
      vertices[1].x, vertices[1].y, vertices[1].z,
      vertices[2].x, vertices[2].y, vertices[2].z,
    ]);
    geo.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    geo.computeVertexNormals();
    return geo;
  }, [vertices]);

  if (!geometry) return null;

  return (
    <mesh geometry={geometry}>
      <meshBasicMaterial color="yellow" opacity={0.5} transparent side={THREE.DoubleSide} depthTest={false} />
    </mesh>
  );
};

// --- COMPONENT: MeasurementMarkers ---
const MeasurementMarkers = () => {
  const { measurePoints } = useUIStore();
  const [labels, setLabels] = useState([]);

  useEffect(() => {
    // Label calculation logic (kept separate from rendering Line for clarity)
    if (measurePoints.length < 2) {
      setLabels([]);
      return;
    }
    const newLabels = [];
    const p1 = measurePoints[0].point;
    const p2 = measurePoints[1].point;

    if (measurePoints.length === 2 && p1 && p2) {
      const dist = p1.distanceTo(p2);
      const mid = p1.clone().add(p2).multiplyScalar(0.5);

      let projStr = "";
      if (measurePoints[0].normal && measurePoints[1].normal) {
        const n1 = measurePoints[0].normal;
        const n2 = measurePoints[1].normal;
        if (Math.abs(n1.dot(n2)) > 0.8) {
          const vec = p2.clone().sub(p1);
          const pDist = Math.abs(vec.dot(n1));
          projStr = pDist.toFixed(2);
        }
      }

      newLabels.push({
        pos: mid,
        text: `${dist.toFixed(2)} mm`,
        subText: projStr ? `Face Dist: ${projStr} mm` : null
      });
    }

    if (measurePoints.length === 3) {
      const p3 = measurePoints[2].point;
      // Tri/Circle logic
      const a = p1.distanceTo(p2);
      const b = p2.distanceTo(p3);
      const c = p3.distanceTo(p1);
      const s = (a + b + c) / 2;
      const area = Math.sqrt(s * (s - a) * (s - b) * (s - c));
      if (area > 0.0001) {
        const R = (a * b * c) / (4 * area);
        const center = p1.clone().add(p2).add(p3).divideScalar(3);
        newLabels.push({
          pos: center,
          text: `⌀ ${(R * 2).toFixed(2)}`
        });
      }
    }
    setLabels(newLabels);
  }, [measurePoints]);

  if (!measurePoints || measurePoints.length === 0) return null;

  // Prepare points array for Line component
  // measurePoints contains { point: Vector3 }
  const linePoints = measurePoints.map(mp => [mp.point.x, mp.point.y, mp.point.z]);

  // Close the loop if 3 points (triangle)
  if (measurePoints.length === 3) {
    linePoints.push([measurePoints[0].point.x, measurePoints[0].point.y, measurePoints[0].point.z]);
  }

  return (
    <group>
      {measurePoints.map((mp, i) => (
        <FixedSizeMarker key={i} position={[mp.point.x, mp.point.y, mp.point.z]} />
      ))}

      {/* The visible green line asked by user */}
      {(measurePoints.length === 2 || measurePoints.length === 3) && (
        <Line
          points={linePoints}
          color="#ff0000"
          lineWidth={5}
          depthTest={true}
          renderOrder={1000}
          toneMapped={false}
        />
      )}

      {labels.map((lbl, i) => (
        <Html key={i} position={lbl.pos} center style={{ pointerEvents: 'none' }} zIndexRange={[1000, 0]}>
          <div style={{
            background: 'rgba(0,0,0,0.8)',
            color: '#00ff00',
            padding: '6px 10px',
            borderRadius: '4px',
            fontFamily: 'monospace',
            fontWeight: 'bold',
            border: '1px solid #00ff00',
            whiteSpace: 'nowrap',
            textAlign: 'center'
          }}>
            <div>{lbl.text}</div>
            {lbl.subText && <div style={{ fontSize: '0.8em', color: '#aaffaa' }}>{lbl.subText}</div>}
          </div>
        </Html>
      ))}
    </group>
  );
};


/**
 * ModelViewer
 * - Loads a GLB with useGLTF
 * - Fixes common CAD material issues (too transparent / too metallic)
 * - Uses legacy pivot centering logic (no forced scaling)
 */
function ModelViewer({ url, onModelReady }) {
  const { scene } = useGLTF(url);
  const clonedScene = React.useMemo(() => scene.clone(), [scene]);
  // --- FEATURE: Color Mode ---
  const { measureMode, addMeasurePoint, explodeMode, colorMode, transformMode, requestedColor } = useUIStore(); // Added requestedColor

  useEffect(() => {
    if (!isInitialized.current) return;

    clonedScene.traverse((child) => {
      if (child.isMesh) {
        if (colorMode) {
          if (requestedColor) {
            // Case A: Specific Color Request (e.g. "Apply red")
            // THREE.Color can parse names like 'red', 'blue', 'green'
            child.material.color.set(requestedColor);
          } else {
            // Case B: Generic "Apply Color" -> Unique/Random Colors
            // Use simple random generation for distinct colors per part
            const h = Math.random();
            const s = 0.85; // High saturation
            const l = 0.55; // Medium lightness
            child.material.color.setHSL(h, s, l);
          }
        } else {
          // Restore Original
          const orig = originalMaterials.current.get(child.uuid);
          if (orig && orig.color) {
            child.material.color.copy(orig.color);
          }
        }
        child.material.needsUpdate = true;
      }
    });
  }, [colorMode, clonedScene, requestedColor]);
  const { camera, scene: threeScene } = useThree();
  const raycaster = useRef(new THREE.Raycaster());

  // Refs for restoring original state (Explode/Color)
  const originalMaterials = useRef(new Map());
  const originalPositions = useRef(new Map());
  const explosionVectors = useRef(new Map()); // Store calculated directions
  const isInitialized = useRef(false);

  // Store model size for dynamic scaling
  const modelSize = useRef(0);
  const [selectedFaceVerts, setSelectedFaceVerts] = useState(null);

  useEffect(() => {
    if (!clonedScene) return;

    // 0. Ensure World Matrices are up to date
    clonedScene.updateMatrixWorld(true);

    // 1. Calculate Global Bounding Box & Center (World Space)
    const globalBox = new THREE.Box3().setFromObject(clonedScene);
    const globalCenter = new THREE.Vector3();
    globalBox.getCenter(globalCenter);

    // Calculate Size diagonal for dynamic explosion scaling
    const sizeVec = new THREE.Vector3();
    globalBox.getSize(sizeVec);
    modelSize.current = sizeVec.length();

    // 2. Traverse and Setup
    clonedScene.traverse((child) => {
      if (child.isMesh) {
        child.castShadow = false;
        child.receiveShadow = false;

        // Store Original Position
        if (!originalPositions.current.has(child.uuid)) {
          originalPositions.current.set(child.uuid, child.position.clone());
        }

        // 3. Calculate Explosion Vector (World Space -> Local Space)
        if (!explosionVectors.current.has(child.uuid)) {
          // A. Get Visual Center of this part in World Space
          const meshBox = new THREE.Box3().setFromObject(child);
          const meshCenter = new THREE.Vector3();
          meshBox.getCenter(meshCenter);

          // B. Calculate Direction in World Space
          let dirWorld = new THREE.Vector3().subVectors(meshCenter, globalCenter).normalize();

          // C. Handle perfectly centered parts (push Y up) or fallback
          if (dirWorld.lengthSq() < 0.0001) {
            dirWorld.set(0, 1, 0);
          }

          // D. Convert Direction to Parent's Local Space
          const dirLocal = dirWorld.clone();
          if (child.parent) {
            const parentQuat = new THREE.Quaternion();
            child.parent.getWorldQuaternion(parentQuat);
            dirLocal.applyQuaternion(parentQuat.invert());
          }

          explosionVectors.current.set(child.uuid, dirLocal.normalize());
        }

        if (child.material) {
          // Store Original Material
          if (!originalMaterials.current.has(child.uuid)) {
            originalMaterials.current.set(child.uuid, child.material.clone());
          }

          child.material = child.material.clone();
          child.material.side = THREE.DoubleSide;
          child.material.transparent = true;
          child.material.opacity = 0.9;
          child.material.depthWrite = true;
          child.material.depthTest = true;

          if (typeof child.material.metalness === 'number') {
            if (child.material.metalness > 0.9) child.material.metalness = 0.6;
          }
          if (typeof child.material.roughness === 'number') {
            if (child.material.roughness < 0.1) child.material.roughness = 0.3;
          }

          child.material.envMapIntensity = 1.2;

          if (
            !child.material.map &&
            child.material.color &&
            child.material.color.r > 0.92 &&
            child.material.color.g > 0.92 &&
            child.material.color.b > 0.92
          ) {
            child.material.color.setHex(0xc0c0c0);
          }

          if (child.geometry.attributes.color) {
            child.material.vertexColors = true;
          }

          child.material.needsUpdate = true;
        }
      }
    });

    isInitialized.current = true;
  }, [clonedScene, url]);


  // --- FEATURE: Explode Mode ---
  useFrame(() => {
    if (!isInitialized.current) return;

    // Expand by variable amount proportional to model size (50% of diagonal)
    // Minimal fallback of 200 if size is weirdly 0
    const baseScale = modelSize.current > 0 ? modelSize.current : 350;
    const expandDist = explodeMode ? baseScale * 0.5 : 0;

    clonedScene.traverse((child) => {
      if (child.isMesh) {
        const originalPos = originalPositions.current.get(child.uuid);
        const direction = explosionVectors.current.get(child.uuid);

        if (originalPos && direction) {
          const targetPos = originalPos.clone().add(direction.clone().multiplyScalar(expandDist));
          child.position.lerp(targetPos, 0.1);
        }
      }
    });
  });

  // --- FEATURE: Color Mode ---
  useEffect(() => {
    if (!isInitialized.current) return;

    console.log("Color Mode Active:", colorMode, "Requested Color:", requestedColor);

    clonedScene.traverse((child) => {
      if (child.isMesh) {
        if (colorMode) {
          if (requestedColor) {
            // Case A: Specific Color Request (e.g. "Apply red")
            child.material.color.set(requestedColor);
          } else {
            // Case B: Generic "Apply Color" -> Unique/Random Colors
            // Use simple random generation for distinct colors per part
            const h = Math.random();
            const s = 0.85;
            const l = 0.55;
            child.material.color.setHSL(h, s, l);
          }
        } else {
          // Restore
          const orig = originalMaterials.current.get(child.uuid);
          if (orig && orig.color) {
            child.material.color.copy(orig.color);
          }
        }
        child.material.needsUpdate = true;
      }
    });
  }, [colorMode, clonedScene, requestedColor]);

  // --- FEATURE: Measurement / Click Handling (User's Logic) ---
  const handleClick = (e) => {
    e.stopPropagation();
    if (e.button !== 0) return;

    let finalPoint = new THREE.Vector3(e.point.x, e.point.y, e.point.z);
    let finalNormal = null;

    // Handle Face Selection
    if (e.object && e.face) {
      const positions = e.object.geometry.attributes.position;
      const vA = new THREE.Vector3().fromBufferAttribute(positions, e.face.a);
      const vB = new THREE.Vector3().fromBufferAttribute(positions, e.face.b);
      const vC = new THREE.Vector3().fromBufferAttribute(positions, e.face.c);

      e.object.localToWorld(vA);
      e.object.localToWorld(vB);
      e.object.localToWorld(vC);

      setSelectedFaceVerts([vA, vB, vC]);
    }

    if (!measureMode) return;

    if (e.point) {
      finalPoint = snapToFeature(e, camera);

      if (e.face && e.object) {
        const normalMatrix = new THREE.Matrix3().getNormalMatrix(e.object.matrixWorld);
        finalNormal = e.face.normal.clone().applyMatrix3(normalMatrix).normalize();
      }

      addMeasurePoint({
        point: finalPoint, // Store needs 'point'
        normal: finalNormal
      });
    }
  };

  return (
    <Center
      onCentered={({ container, width, height, depth }) => {
        const maxDim = Math.max(width, height, depth);
        if (onModelReady) {
          onModelReady(container, maxDim);
        }
      }}
    >
      <primitive object={clonedScene} onPointerDown={handleClick} />
      {transformMode && (
        <TransformControls object={clonedScene} mode="translate" />
      )}
      {selectedFaceVerts && <FaceHighlight vertices={selectedFaceVerts} />}
    </Center>
  );
}

function CameraController({ onReady, autoRotate, enableDamping = true, modelMaxDim }) {
  const { camera } = useThree();
  const controlsRef = useRef();

  useEffect(() => {
    if (onReady && controlsRef.current) {
      onReady({ camera, controls: controlsRef.current });
    }
  }, [camera, onReady]);

  // Update controls based on model size (Legacy logic)
  useEffect(() => {
    if (modelMaxDim > 0 && controlsRef.current) {
      /*
        Legacy:
        controls.minDistance = maxDim / 10000;
        controls.maxDistance = maxDim * 100;
      */
      const controls = controlsRef.current;
      controls.minDistance = modelMaxDim / 10000;
      // Ensure minDistance isn't too small to be unstable
      if (controls.minDistance < 0.01) controls.minDistance = 0.01;

      controls.maxDistance = modelMaxDim * 100;
      controls.update();
    }
  }, [modelMaxDim]);

  return (
    <OrbitControls
      ref={controlsRef}
      makeDefault
      autoRotate={autoRotate}
      autoRotateSpeed={4.0}
      enableDamping={enableDamping}
      dampingFactor={0.1}
      zoomSpeed={0.8}
      rotateSpeed={1.5}
      minPolarAngle={0}
      maxPolarAngle={Math.PI}
    />
  );
}

const ThreeCanvas = ({ mode }) => {
  const { latestResult, orientationCubeVisible, measurePoints, setExplodeMode, setColorMode, setMeasureMode } = useUIStore();
  const [modelUrl, setModelUrl] = useState('/models/V3_DIRT_BIKE_3.compressed.glb');
  const [cameraControls, setCameraControls] = useState(null);
  const [mainModel, setMainModel] = useState(null);
  const [modelMaxDim, setModelMaxDim] = useState(0);

  // Stability Controls
  const [autoRotate, setAutoRotate] = useState(false);
  const [enableDamping, setEnableDamping] = useState(true);
  const initialCameraSet = useRef(false); // Guard against reset

  useEffect(() => {
    if (latestResult && latestResult.glb_url !== undefined) {
      setModelUrl(latestResult.glb_url);

      // Reset View Modes on new model load
      setExplodeMode(false);
      setColorMode(false);
      setMeasureMode(false);
    }
  }, [latestResult, setExplodeMode, setColorMode, setMeasureMode]);

  const handleModelReady = (model, maxDim) => {
    setMainModel(model);
    setModelMaxDim(maxDim);

    // Initial Camera Fit (Legacy logic: dist = (size / 2) / tan(fov/2) * 1.5)
    if (cameraControls && maxDim > 0 && !initialCameraSet.current) {
      const { camera, controls } = cameraControls;
      const fov = camera.fov * (Math.PI / 180);
      let cameraZ = (maxDim / 2) / Math.tan(fov / 2);
      let paddingMultiplier = 1.5;
      // if (modelUrl && modelUrl.includes('V3_DIRT_BIKE_3')) {
      //   paddingMultiplier = 1.5 * 0.75; // 5% closer zoom for default bike
      // }
      cameraZ *= paddingMultiplier;

      camera.position.set(0, 0, cameraZ);
      camera.updateProjectionMatrix();

      controls.target.set(0, 0, 0); // Always target 0,0,0 (pivot)
      controls.update();
      initialCameraSet.current = true;
    }
  };

  const handleZoomIn = () => {
    if (cameraControls?.camera && cameraControls?.controls) {
      const { camera, controls } = cameraControls;
      const target = controls.target.clone();
      const direction = camera.position.clone().sub(target);
      direction.multiplyScalar(0.7);
      camera.position.copy(target.clone().add(direction));
      controls.update();
    }
  };

  const handleZoomOut = () => {
    if (cameraControls?.camera && cameraControls?.controls) {
      const { camera, controls } = cameraControls;
      const target = controls.target.clone();
      const direction = camera.position.clone().sub(target);
      direction.multiplyScalar(1.4);
      camera.position.copy(target.clone().add(direction));
      controls.update();
    }
  };

  const handleResetView = () => {
    if (cameraControls?.camera && cameraControls?.controls) {
      const { camera, controls } = cameraControls;
      if (modelMaxDim > 0) {
        const fov = camera.fov * (Math.PI / 180);
        let cameraZ = (modelMaxDim / 2) / Math.tan(fov / 2);
        cameraZ *= 1.5;
        camera.position.set(0, 0, cameraZ);
      } else {
        camera.position.set(10, 5, 10); // Fallback
      }
      controls.target.set(0, 0, 0);
      controls.update();
    }
  };

  const handleViewChange = React.useCallback((view) => {
    if (!cameraControls?.camera || !cameraControls?.controls) return;

    // 1. Force Stability
    setEnableDamping(false);
    setAutoRotate(false);
    if (cameraControls.controls) {
      cameraControls.controls.enableDamping = false;
      cameraControls.controls.autoRotate = false;
    }

    const { camera, controls } = cameraControls;
    const target = controls.target.clone();

    // 2. Relative Logic - Align with Model's Rotation
    const modelQuat = mainModel ? mainModel.quaternion.clone() : new THREE.Quaternion();
    let offset = new THREE.Vector3();
    let up = new THREE.Vector3(0, 1, 0);

    if (view === 'front') offset.set(0, 0, 1);
    if (view === 'back') offset.set(0, 0, -1);
    if (view === 'left') offset.set(-1, 0, 0);
    if (view === 'right') offset.set(1, 0, 0);
    if (view === 'top') { offset.set(0, 1, 0.0001); up.set(0, 0, -1); }
    if (view === 'bottom') { offset.set(0, -1, 0.0001); up.set(0, 0, 1); }

    // Apply Model's Rotation to offset and up vector
    offset.applyQuaternion(modelQuat);
    up.applyQuaternion(modelQuat);

    // 3. Snap Position (Match Initial Load Zoom)
    const size = modelMaxDim > 0 ? modelMaxDim : 10;
    const fov = camera.fov * (Math.PI / 180);
    // Calculate distance to fit the object perfectly given the FOV
    let dist = (size / 2) / Math.tan(fov / 2);

    // Apply the same padding multiplier as the initial load (1.5x)
    // This ensures consistent zoom levels between initial load and view switches
    dist *= 1.5;

    camera.position.copy(target.clone().add(offset.multiplyScalar(dist)));
    camera.up.copy(up);
    camera.lookAt(target);
    controls.update();

  }, [cameraControls, modelMaxDim, mainModel]);

  /* Existing handleCubeRotate logic matches OrientationCube updates */
  const handleCubeRotate = (rotation) => {
    if (mainModel) {
      mainModel.rotation.x = rotation.x;
      mainModel.rotation.y = rotation.y;
      mainModel.rotation.z = rotation.z;
    }
  };

  // Sync Text-Based Rotation from Store
  const { modelRotation, requestedView, setRequestedView } = useUIStore();

  // Effect: Auto-Rotate specific model + Reset Guard
  useEffect(() => {
    if (modelUrl === '/models/V3_DIRT_BIKE_3.compressed.glb') {
      setAutoRotate(true);
    } else {
      setAutoRotate(false);
    }
    initialCameraSet.current = false; // Reset guard logic
  }, [modelUrl]);

  // Effect: Re-enable damping on manual interaction
  useEffect(() => {
    if (cameraControls?.controls) {
      const onStart = () => {
        setEnableDamping(true);
        setAutoRotate(false); // Stop autorotate on user interact
      };
      cameraControls.controls.addEventListener('start', onStart);
      return () => cameraControls.controls.removeEventListener('start', onStart);
    }
  }, [cameraControls]);

  useEffect(() => {
    if (mainModel) {
      mainModel.rotation.y = modelRotation.y;
    }
  }, [mainModel, modelRotation]);

  // Sync Natural Language View Control
  useEffect(() => {
    if (requestedView) {
      handleViewChange(requestedView);
      setRequestedView(null);
    }
  }, [requestedView, setRequestedView, handleViewChange]);

  return (
    <div className="viewer-container">
      <ViewerToolbar
        onZoomIn={handleZoomIn}
        onZoomOut={handleZoomOut}
        onResetView={handleResetView}
        onViewChange={handleViewChange}
      />
      {/* Branding Overlay for Full Screen Mode */}
      <div className="maximize-branding-overlay">
        <div style={{ display: 'flex', alignItems: 'center', gap: '0px' }}>
          <div className="brand-title">PeopleCAD</div>
          <img src="image (2).png" alt="PeopleCAD" className="brand-logo-img" style={{ height: '45px' }} />
          {/* Optional: Add logo img if needed, user only showed text in request but previous had logo.
                  User said "my title shuould have to come in top left with the below dialouge".
                  Image shows just text. keeping just text for now to match "font style" request.
              */}
        </div>
        <div className="brand-tagline">Design Smarter. Build Faster</div>
      </div>
      {orientationCubeVisible && (
        <OrientationCube
          onViewChange={handleViewChange}
          onRotate={handleCubeRotate}
          mainModel={mainModel}
        />
      )}

      <Canvas
        shadows={false}
        camera={{ position: [0, 0, 500], fov: 50, near: 0.01, far: 1000000 }}
        dpr={[1, 1.5]}
        gl={{
          alpha: true,
          maintainAspectRatio: true,
          powerPreference: "high-performance",
          antialias: false
        }}
        onCreated={({ gl }) => {
          gl.setClearColor(0x000000, 0);
          gl.toneMapping = THREE.ACESFilmicToneMapping;
          gl.toneMappingExposure = 1.2;
        }}
      >
        <ambientLight intensity={1.5} />
        <directionalLight position={[5, 12, 8]} intensity={2.0} />
        <directionalLight position={[-5, 6, 5]} intensity={1.0} />
        <Environment preset="city" blur={0.8} />

        <Suspense fallback={null}>
          {modelUrl && (
            <group>
              <ModelViewer
                key={modelUrl}
                url={modelUrl}
                onModelReady={handleModelReady}
              />
            </group>
          )}
        </Suspense>

        <MeasurementMarkers />

        <CameraController
          onReady={setCameraControls}
          autoRotate={autoRotate}
          enableDamping={enableDamping}
          modelMaxDim={modelMaxDim}
        />
      </Canvas>
    </div >
  );
};

export default ThreeCanvas;
