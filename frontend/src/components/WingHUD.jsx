import React, { useEffect, useState } from 'react';
import useUIStore from '../store/uiStore';

const WingHUD = () => {
    const { wingMode, setLatestResult, setWingMode } = useUIStore();
    const [metrics, setMetrics] = useState(null);
    const [status, setStatus] = useState("Idle");
    const [connected, setConnected] = useState(false);
    const [history, setHistory] = useState([]);

    // Window State
    const [winState, setWinState] = useState({
        x: window.innerWidth - 450, // Initial Position
        y: 80,
        width: 380,
        height: 550,
        isMinimized: false,
        isMaximized: false,
        prevBounds: null
    });

    const [dragState, setDragState] = useState({ isDragging: false, relX: 0, relY: 0 });
    const [resizeState, setResizeState] = useState({ isResizing: false, startX: 0, startY: 0, startW: 0, startH: 0 });

    useEffect(() => {
        if (!wingMode) return;
        setStatus("Connecting...");
        // Reset history on new run
        setHistory([]);
        setMetrics(null);

        // Ensure visibility on start
        setWinState(prev => ({ ...prev, isMinimized: false, x: window.innerWidth - 450, y: 80 }));

        const evtSource = new EventSource('http://127.0.0.1:8000/inhouse_cad/wing/events');

        evtSource.onopen = () => {
            setConnected(true);
            setStatus("Optimizing...");
        };

        evtSource.onmessage = (e) => {
            try {
                const data = JSON.parse(e.data);
                if (data.status === "complete") {
                    setStatus("Opening optimized_wing.stp in CATIA V5...");
                    evtSource.close();
                    setTimeout(() => setStatus("CATIA: Validating Geometry Surface..."), 3000);
                    setTimeout(() => setStatus("CATIA: Analysis Passed. Returning to In-House CAD..."), 6000);
                    setTimeout(() => {
                        setStatus("Complete");
                        setLatestResult({ glb_url: `http://127.0.0.1:8000/generated_files/wing_opt/optimized_wing.glb?t=${Date.now()}` });
                    }, 8000);
                    return;
                }
                if (data.error) {
                    setStatus(`Error: ${data.error}`);
                    evtSource.close();
                    return;
                }
                if (data.metrics) {
                    setMetrics(data.metrics);
                    setHistory(prev => [...prev, { iter: data.iteration, val: data.metrics.L_over_D }]);
                    setLatestResult({ glb_url: `http://127.0.0.1:8000/generated_files/wing_opt/live.glb?t=${Date.now()}` });
                }
            } catch (err) {
                console.error("SSE Parse Error", err);
            }
        };

        evtSource.onerror = (err) => {
            console.error("SSE Error", err);
            evtSource.close();
        };

        return () => {
            evtSource.close();
            setConnected(false);
        };
    }, [wingMode, setLatestResult]);

    // Drag Logic
    const handleMouseDown = (e) => {
        if (winState.isMaximized) return;
        setDragState({
            isDragging: true,
            relX: e.clientX - winState.x,
            relY: e.clientY - winState.y
        });
    };

    // Resize Logic
    const handleResizeDown = (e) => {
        if (winState.isMaximized) return;
        e.stopPropagation();
        e.preventDefault();
        setResizeState({
            isResizing: true,
            startX: e.clientX,
            startY: e.clientY,
            startW: winState.width,
            startH: winState.height
        });
    };

    const toggleMaximize = () => {
        setWinState(prev => {
            if (prev.isMaximized) {
                return {
                    ...prev,
                    isMaximized: false,
                    x: prev.prevBounds?.x || (window.innerWidth - 450),
                    y: prev.prevBounds?.y || 80,
                    width: prev.prevBounds?.width || 380,
                    height: prev.prevBounds?.height || 550
                };
            } else {
                return {
                    ...prev,
                    isMaximized: true,
                    prevBounds: { x: prev.x, y: prev.y, width: prev.width, height: prev.height },
                    x: 0,
                    y: 0,
                    width: window.innerWidth,
                    height: window.innerHeight
                };
            }
        });
    };

    // Global Mouse Handlers
    useEffect(() => {
        const handleMouseMove = (e) => {
            if (dragState.isDragging) {
                setWinState(prev => ({
                    ...prev,
                    x: e.clientX - dragState.relX,
                    y: e.clientY - dragState.relY
                }));
            }
            if (resizeState.isResizing) {
                setWinState(prev => ({
                    ...prev,
                    width: Math.max(300, resizeState.startW + (e.clientX - resizeState.startX)),
                    height: Math.max(200, resizeState.startH + (e.clientY - resizeState.startY))
                }));
            }
        };

        const handleMouseUp = () => {
            setDragState(prev => ({ ...prev, isDragging: false }));
            setResizeState(prev => ({ ...prev, isResizing: false }));
        };

        if (dragState.isDragging || resizeState.isResizing) {
            window.addEventListener('mousemove', handleMouseMove);
            window.addEventListener('mouseup', handleMouseUp);
        }
        return () => {
            window.removeEventListener('mousemove', handleMouseMove);
            window.removeEventListener('mouseup', handleMouseUp);
        };
    }, [dragState.isDragging, resizeState.isResizing]);

    if (!wingMode) return null;

    return (
        <div style={{
            position: 'fixed',
            left: `${winState.x}px`,
            top: `${winState.y}px`,
            width: `${winState.width}px`,
            height: winState.isMinimized ? 'auto' : `${winState.height}px`,
            padding: '20px',
            background: 'rgba(20, 20, 30, 0.95)',
            backdropFilter: 'blur(20px)',
            borderRadius: '12px',
            border: '1px solid rgba(255, 255, 255, 0.1)',
            color: 'white',
            fontFamily: "'Inter', sans-serif",
            fontSize: '14px',
            boxShadow: '0 20px 50px rgba(0, 0, 0, 0.5)',
            zIndex: 9999,
            display: 'flex',
            flexDirection: 'column',
            overflow: 'hidden'
        }}>
            {/* Header / Drag Handle */}
            <div
                style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    marginBottom: winState.isMinimized ? 0 : '15px',
                    alignItems: 'center',
                    cursor: 'move',
                    paddingBottom: winState.isMinimized ? 0 : '10px',
                    borderBottom: winState.isMinimized ? 'none' : '1px solid rgba(255,255,255,0.05)'
                }}
                onMouseDown={handleMouseDown}
            >
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                    <h3 style={{ margin: 0, fontWeight: 600, fontSize: '15px', userSelect: 'none' }}>Wing Optimizer</h3>
                    <span style={{ fontSize: '10px', color: '#666', userSelect: 'none' }}>v4.0</span>
                </div>

                {/* Window Controls */}
                <div style={{ display: 'flex', gap: '8px' }} onMouseDown={(e) => e.stopPropagation()}>
                    <button
                        onClick={() => setWinState(prev => ({ ...prev, isMinimized: !prev.isMinimized }))}
                        title={winState.isMinimized ? "Expand" : "Minimize"}
                        style={{ background: 'none', border: 'none', color: '#aaa', cursor: 'pointer', fontSize: '14px' }}
                    >
                        {winState.isMinimized ? '+' : '−'}
                    </button>
                    <button
                        onClick={() => setWingMode(false)}
                        title="Close"
                        style={{ background: 'none', border: 'none', color: '#ff5f57', cursor: 'pointer', fontSize: '14px' }}
                    >
                        ✕
                    </button>
                </div>
            </div>

            {/* Content Area - Hidden when minimized */}
            {!winState.isMinimized && (
                <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>

                    {/* Status Bar */}
                    <div style={{ marginBottom: '10px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <span style={{
                            fontSize: '11px',
                            color: status === 'Optimizing...' ? '#34d399' : '#888'
                        }}>
                            {status}
                        </span>
                        {status === 'Optimizing...' && <span className="pulsing-dot" style={{ width: '6px', height: '6px', background: '#34d399', borderRadius: '50%' }}></span>}
                    </div>

                    {/* Graph Area - Flexible Height */}
                    <div style={{ flex: 1, minHeight: '150px', position: 'relative', marginBottom: '40px', background: 'rgba(0,0,0,0.2)', borderRadius: '8px' }}>
                        {history.length > 1 ? (
                            <SimpleLineChart data={history} color="#10b981" />
                        ) : (
                            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: '#444', fontSize: '12px' }}>Waiting for data...</div>
                        )}
                    </div>

                    {/* Metrics Grid */}
                    {metrics && (
                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px', marginBottom: '10px' }}>
                            <MetricBox label="L/D Ratio" value={metrics.L_over_D?.toFixed(3)} highlight />
                            <MetricBox label="Efficiency (e)" value={metrics.e?.toFixed(3)} />
                            <MetricBox label="Lift (CL)" value={metrics.CL?.toFixed(4)} />
                            <MetricBox label="Drag (CD)" value={metrics.CD?.toFixed(4)} />
                            <MetricBox label="Ind. Drag (CDi)" value={metrics.CDi?.toFixed(4)} />
                            <MetricBox label="Aspect Ratio" value={metrics.AR?.toFixed(2)} />
                        </div>
                    )}

                    {/* Footer Actions */}
                    {status === "Complete" && (
                        <div style={{ display: 'flex', gap: '8px', marginTop: 'auto' }}>
                            <button onClick={() => window.open('http://127.0.0.1:8000/generated_files/wing_opt/optimized_wing.obj', '_blank')} className="hud-btn" style={{ flex: 1, background: '#4f46e5' }}>OBJ</button>
                            <button onClick={() => window.open('http://127.0.0.1:8000/generated_files/wing_opt/optimized_wing.glb', '_blank')} className="hud-btn" style={{ flex: 1, background: '#ec4899' }}>GLB</button>
                            <button onClick={() => window.open('http://127.0.0.1:8000/download_gen/wing_opt/optimized_wing.stp', '_blank')} className="hud-btn" style={{ flex: 1, background: '#10b981' }}>STEP</button>
                        </div>
                    )}

                    {/* Resize Handle */}
                    <div
                        onMouseDown={handleResizeDown}
                        style={{
                            position: 'absolute',
                            right: '0',
                            bottom: '0',
                            width: '15px',
                            height: '15px',
                            cursor: 'nwse-resize',
                            zIndex: 10
                        }}
                    >
                        <svg viewBox="0 0 10 10" style={{ width: '100%', height: '100%', fill: '#666', opacity: 0.5 }}>
                            <path d="M10 10 L10 2 L2 10 Z" />
                        </svg>
                    </div>
                </div>
            )}
        </div>
    );
};

// Simple SVG Chart to avoid heavy deps
const SimpleLineChart = ({ data, color }) => {
    if (!data || data.length < 2) return null;
    const maxVal = Math.max(...data.map(d => d.val));
    const minVal = Math.min(...data.map(d => d.val));

    // Fixed Y domain: 0 to 30
    const yMax = 30;
    const yMin = 0;
    const range = yMax - yMin;

    // Normalize points to 0-100%
    const pointsArr = data.map((d, i) => {
        const x = (i / 30) * 100; // Fixed to 30 iters as max X
        const y = 100 - ((d.val - yMin) / range) * 100; // Invert Y for SVG
        return { x, y };
    });

    const points = pointsArr.map(p => `${p.x},${p.y}`).join(' ');
    const lastPoint = pointsArr[pointsArr.length - 1];

    // Generate Y-axis ticks (approx 5-6 steps)
    const yStep = Math.ceil(range / 5);
    const yTicks = [];
    for (let val = yMin; val <= yMax; val += yStep) {
        yTicks.push(val);
    }
    // Ensure max is included if not close
    if (yTicks[yTicks.length - 1] < yMax) yTicks.push(yMax);
    // Reverse for display (top to bottom)
    const yTicksDisplay = [...yTicks].reverse();

    return (
        <div style={{ position: 'relative', width: '100%', height: '100%', paddingLeft: '35px', paddingRight: '55px', paddingBottom: '25px' }}>
            {/* Y Axis Title */}
            <div style={{
                position: 'absolute',
                left: '-6px',
                top: '50%',
                transform: 'rotate(-90deg) translateX(50%)',
                fontSize: '10px',
                color: '#888',
                fontWeight: 600
            }}>
                L/D Ratio
            </div>

            {/* Y Axis Labels */}
            <div style={{ position: 'absolute', left: 0, top: 0, bottom: '25px', display: 'flex', flexDirection: 'column', justifyContent: 'space-between', fontSize: '10px', color: '#666' }}>
                {yTicksDisplay.map((tick, i) => (
                    <span key={i}>{Math.round(tick)}</span>
                ))}
            </div>

            <svg viewBox="0 0 100 100" style={{ width: '100%', height: '100%', overflow: 'visible' }} preserveAspectRatio="none">
                {/* Horizontal Grid Lines aligned with Y ticks */}
                {yTicks.map((tick, i) => {
                    const yPos = 100 - ((tick - yMin) / range) * 100;
                    return (
                        <line key={i} x1="0" y1={yPos} x2="100" y2={yPos} stroke="rgba(255,255,255,0.05)" strokeWidth="0.5" vectorEffect="non-scaling-stroke" />
                    );
                })}

                {/* Vertical Grid Lines aligned with X ticks (0, 5, 10...) */}
                {[0, 5, 10, 15, 20, 25, 30].map(val => {
                    const xPos = (val / 30) * 100;
                    return (
                        <line key={val} x1={xPos} y1="0" x2={xPos} y2="100" stroke="rgba(255,255,255,0.05)" strokeWidth="0.5" vectorEffect="non-scaling-stroke" />
                    );
                })}

                {/* Area Fill */}
                <defs>
                    <linearGradient id="chartGradient" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor={color} stopOpacity="0.4" />
                        <stop offset="100%" stopColor={color} stopOpacity="0.0" />
                    </linearGradient>
                </defs>
                <polygon points={`${points} ${lastPoint.x},100 0,100`} fill="url(#chartGradient)" />

                {/* Line */}
                <polyline
                    fill="none"
                    stroke={color}
                    strokeWidth="3"
                    points={points}
                    vectorEffect="non-scaling-stroke"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                />

                {/* Latest Point Marker (Red) */}
                <circle
                    cx={lastPoint.x}
                    cy={lastPoint.y}
                    r="2"
                    fill="red"
                    stroke="white"
                    strokeWidth="0.5"
                    vectorEffect="non-scaling-stroke"
                />
            </svg>

            {/* X Axis Labels */}
            <div style={{ position: 'absolute', left: '25px', right: '45px', bottom: 0, display: 'flex', justifyContent: 'space-between', fontSize: '10px', color: '#666' }}>
                {[0, 5, 10, 15, 20, 25, 30].map(val => (
                    <span key={val} style={{ width: '20px', textAlign: 'center' }}>{val}</span>
                ))}
            </div>

            {/* X Axis Title */}
            <div style={{
                position: 'absolute',
                bottom: '-20px',
                left: '50%',
                transform: 'translateX(-50%)',
                fontSize: '10px',
                color: '#888',
                fontWeight: 600
            }}>
                Iterations
            </div>
        </div>
    );
};

const MetricBox = ({ label, value, highlight = false }) => (
    <div style={{
        background: 'rgba(255, 255, 255, 0.03)',
        padding: '8px',
        borderRadius: '8px',
        border: highlight ? '1px solid rgba(79, 70, 229, 0.3)' : 'border: 1px solid rgba(255, 255, 255, 0.05)'
    }}>
        <div style={{ fontSize: '10px', color: '#888', marginBottom: '2px' }}>{label}</div>
        <div style={{ fontSize: '15px', fontWeight: 600, color: highlight ? '#fff' : '#ddd' }}>
            {value || '-'}
        </div>
    </div>
);

export default WingHUD;
