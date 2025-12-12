import React, { useEffect, useRef } from 'react';
import * as THREE from 'three';
import useUIStore from '../store/uiStore';

const OrientationCube = ({ onViewChange, onRotate, mainModel }) => {
    const { orientationCubeVisible } = useUIStore();
    const canvasRef = useRef(null);
    const sceneRef = useRef(null);
    const cameraRef = useRef(null);
    const rendererRef = useRef(null);
    const cubeRef = useRef(null);

    useEffect(() => {
        if (!canvasRef.current) return;

        // Setup scene
        const scene = new THREE.Scene();
        sceneRef.current = scene;

        // Setup camera
        const camera = new THREE.PerspectiveCamera(45, 1, 0.1, 1000);
        camera.position.set(2, 2, 2);
        camera.lookAt(0, 0, 0);
        cameraRef.current = camera;

        // Setup renderer
        const renderer = new THREE.WebGLRenderer({
            canvas: canvasRef.current,
            alpha: true,
            antialias: true
        });
        renderer.setSize(200, 200);
        rendererRef.current = renderer;

        // Create structured sphere-like cube (Sphere + 6 Circular Faces)
        const makeFaceTexture = (text) => {
            const canvas = document.createElement('canvas');
            canvas.width = 256;
            canvas.height = 256;
            const ctx = canvas.getContext('2d');

            // Clear alpha
            ctx.clearRect(0, 0, canvas.width, canvas.height);

            // Circular Background
            ctx.beginPath();
            ctx.arc(128, 128, 120, 0, Math.PI * 2);
            ctx.fillStyle = '#e0e0e0';
            ctx.fill();

            // Circular Border
            ctx.lineWidth = 15;
            ctx.strokeStyle = '#aaaaaa';
            ctx.stroke();

            // Inner Highlight
            ctx.beginPath();
            ctx.arc(128, 128, 80, 0, Math.PI * 2);
            ctx.fillStyle = 'rgba(255, 255, 255, 0.3)';
            ctx.fill();

            // Text
            ctx.fillStyle = '#444444';
            ctx.font = 'bold 60px Arial';
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.translate(128, 128);
            ctx.fillText(text, 0, 0);

            const texture = new THREE.CanvasTexture(canvas);
            texture.needsUpdate = true;
            return texture;
        };

        const materials = [
            new THREE.MeshStandardMaterial({ map: makeFaceTexture('Right'), emissive: 0x222222, roughness: 0.2 }),
            new THREE.MeshStandardMaterial({ map: makeFaceTexture('Left'), emissive: 0x222222, roughness: 0.2 }),
            new THREE.MeshStandardMaterial({ map: makeFaceTexture('Top'), emissive: 0x222222, roughness: 0.2 }),
            new THREE.MeshStandardMaterial({ map: makeFaceTexture('Bottom'), emissive: 0x222222, roughness: 0.2 }),
            new THREE.MeshStandardMaterial({ map: makeFaceTexture('Front'), emissive: 0x222222, roughness: 0.2 }),
            new THREE.MeshStandardMaterial({ map: makeFaceTexture('Back'), emissive: 0x222222, roughness: 0.2 }),
        ];

        // Container Group
        const cubeGroup = new THREE.Group();
        cubeRef.current = cubeGroup;
        scene.add(cubeGroup);

        // Central Sphere
        const sphereGeo = new THREE.SphereGeometry(0.48, 32, 32); // Slightly smaller than faces
        const sphereMat = new THREE.MeshStandardMaterial({ color: 0xcccccc, roughness: 0.4 });
        const sphere = new THREE.Mesh(sphereGeo, sphereMat);
        cubeGroup.add(sphere);

        // Adds a circular face mesh
        const addFace = (idx, pos, rot) => {
            const geo = new THREE.CircleGeometry(0.38, 32);
            const mesh = new THREE.Mesh(geo, materials[idx]);
            // Apply texture to both sides just in case, but really front is needed
            mesh.material.side = THREE.DoubleSide;

            mesh.position.set(...pos);
            mesh.rotation.set(...rot);
            mesh.userData = { faceIndex: idx }; // Store index for click handling
            cubeGroup.add(mesh);
        };

        // R=0, L=1, T=2, B=3, F=4, Back=5 (matching materials array)
        addFace(0, [0.51, 0, 0], [0, Math.PI / 2, 0]); // Right
        addFace(1, [-0.51, 0, 0], [0, -Math.PI / 2, 0]); // Left
        addFace(2, [0, 0.51, 0], [-Math.PI / 2, 0, 0]); // Top
        addFace(3, [0, -0.51, 0], [Math.PI / 2, 0, 0]); // Bottom
        addFace(4, [0, 0, 0.51], [0, 0, 0]); // Front
        addFace(5, [0, 0, -0.51], [0, Math.PI, 0]); // Back

        // Add lights
        scene.add(new THREE.AmbientLight(0xffffff, 0.8));
        const dirLight = new THREE.DirectionalLight(0xffffff, 0.8);
        dirLight.position.set(2, 4, 3);
        scene.add(dirLight);

        // Animation loop
        const animate = () => {
            requestAnimationFrame(animate);

            // Sync cube rotation with main model
            if (mainModel && cubeRef.current) {
                cubeRef.current.rotation.copy(mainModel.rotation);
            }

            renderer.render(scene, camera);
        };
        animate();

        // Drag interaction
        let isDragging = false;
        let lastX = 0, lastY = 0;

        const onPointerDown = (e) => {
            isDragging = true;
            const rect = canvasRef.current.getBoundingClientRect();
            lastX = e.clientX - rect.left;
            lastY = e.clientY - rect.top;
        };

        const onPointerMove = (e) => {
            if (!isDragging) return;
            const rect = canvasRef.current.getBoundingClientRect();
            const nx = e.clientX - rect.left;
            const ny = e.clientY - rect.top;
            const dx = nx - lastX;
            const dy = ny - lastY;
            lastX = nx;
            lastY = ny;

            cubeGroup.rotation.y += dx * 0.01;
            cubeGroup.rotation.x += dy * 0.01;

            // Notify parent to sync main model rotation
            if (onRotate) {
                onRotate({
                    x: cubeGroup.rotation.x,
                    y: cubeGroup.rotation.y,
                    z: cubeGroup.rotation.z
                });
            }
        };

        const onPointerUp = () => {
            isDragging = false;
        };

        const onClick = (e) => {
            const rect = canvasRef.current.getBoundingClientRect();
            const mouseX = ((e.clientX - rect.left) / rect.width) * 2 - 1;
            const mouseY = -((e.clientY - rect.top) / rect.height) * 2 + 1;

            const raycaster = new THREE.Raycaster();
            raycaster.setFromCamera(new THREE.Vector2(mouseX, mouseY), camera);

            // Intersect children of group (faces + sphere)
            const intersects = raycaster.intersectObjects(cubeGroup.children);

            if (intersects.length > 0) {
                // Check if we hit a face (userData.faceIndex exists)
                const hit = intersects.find(i => i.object.userData.faceIndex !== undefined);
                if (hit) {
                    const idx = hit.object.userData.faceIndex;
                    const faceMap = ['right', 'left', 'top', 'bottom', 'front', 'back'];
                    const view = faceMap[idx] || 'front';
                    if (onViewChange) onViewChange(view);
                }
            }
        };

        canvasRef.current.addEventListener('pointerdown', onPointerDown);
        window.addEventListener('pointermove', onPointerMove);
        window.addEventListener('pointerup', onPointerUp);
        canvasRef.current.addEventListener('click', onClick);

        return () => {
            canvasRef.current?.removeEventListener('pointerdown', onPointerDown);
            window.removeEventListener('pointermove', onPointerMove);
            window.removeEventListener('pointerup', onPointerUp);
            canvasRef.current?.removeEventListener('click', onClick);
        };
    }, [onViewChange, onRotate, mainModel]);

    return (
        <div className={`orientation-cube ${orientationCubeVisible ? 'active' : ''}`}>
            <canvas ref={canvasRef} width="200" height="200"></canvas>
        </div>
    );
};

export default OrientationCube;
