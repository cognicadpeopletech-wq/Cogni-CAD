import React, { useState, useEffect } from 'react';
import useUIStore from '../store/uiStore';

const OptimizedValuesPanel = () => {
    const { optimizedValues, setOptimizedValues } = useUIStore();

    // Window State
    const [winState, setWinState] = useState({
        x: window.innerWidth / 2 + 100, // Offset from center
        y: window.innerHeight / 2 - 250,
        width: 380,
        height: 500,
        isMinimized: false,
        isMaximized: false,
        prevBounds: null
    });

    const [dragState, setDragState] = useState({ isDragging: false, relX: 0, relY: 0 });
    const [resizeState, setResizeState] = useState({ isResizing: false, startX: 0, startY: 0, startW: 0, startH: 0 });

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
                    x: prev.prevBounds?.x || (window.innerWidth / 2 + 100),
                    y: prev.prevBounds?.y || (window.innerHeight / 2 - 250),
                    width: prev.prevBounds?.width || 380,
                    height: prev.prevBounds?.height || 500
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

    if (!optimizedValues) return null;

    const formatVal = (val, fixed = 2) => val !== undefined && val !== null ? val.toFixed(fixed) : '-';

    return (
        <div style={{
            position: 'fixed',
            left: `${winState.x}px`,
            top: `${winState.y}px`,
            width: `${winState.width}px`,
            height: winState.isMinimized ? 'auto' : `${winState.height}px`,
            background: 'rgba(20, 20, 30, 0.95)',
            backdropFilter: 'blur(20px)',
            borderRadius: '12px',
            border: '1px solid rgba(79, 70, 229, 0.3)',
            color: 'white',
            fontFamily: "'Inter', sans-serif",
            fontSize: '14px',
            boxShadow: '0 25px 60px rgba(0, 0, 0, 0.6)',
            zIndex: 10000,
            display: 'flex',
            flexDirection: 'column',
            overflow: 'hidden'
        }}>
            {/* Header */}
            <div
                style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    padding: '15px 20px',
                    alignItems: 'center',
                    cursor: winState.isMaximized ? 'default' : 'move',
                    borderBottom: winState.isMinimized ? 'none' : '1px solid rgba(255,255,255,0.05)',
                    background: 'rgba(255,255,255,0.02)'
                }}
                onMouseDown={handleMouseDown}
                onDoubleClick={toggleMaximize}
            >
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                    <h3 style={{ margin: 0, fontWeight: 700, fontSize: '16px', textShadow: '0 2px 10px rgba(79,70,229,0.5)', userSelect: 'none' }}>Optimized Values</h3>
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
                        onClick={toggleMaximize}
                        title={winState.isMaximized ? "Restore" : "Maximize"}
                        style={{ background: 'none', border: 'none', color: '#aaa', cursor: 'pointer', fontSize: '10px' }}
                    >
                        {winState.isMaximized ? '❐' : '□'}
                    </button>
                    <button
                        onClick={() => setOptimizedValues(null)}
                        title="Close"
                        style={{ background: 'none', border: 'none', color: '#ff5f57', cursor: 'pointer', fontSize: '16px' }}
                    >
                        ✕
                    </button>
                </div>
            </div>

            {/* Content - Hidden when minimized */}
            {!winState.isMinimized && (
                <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden', position: 'relative' }}>
                    <div style={{ padding: '20px', display: 'flex', flexDirection: 'column', gap: '12px', overflowY: 'auto' }}>

                        <ItemGroup title="Wing Geometry">
                            <Item label="Wing Span" value={`${formatVal(optimizedValues.span)} m`} />
                        </ItemGroup>

                        <ItemGroup title="Chord Distribution">
                            <Item label="Root Chord" value={`${formatVal(optimizedValues.root_chord)} m`} />
                            <Item label="Tip Chord" value={`${formatVal(optimizedValues.tip_chord)} m`} />
                            <Item label="Taper Ratio" value={formatVal(optimizedValues.tip_chord / optimizedValues.root_chord, 3)} />
                        </ItemGroup>

                        <ItemGroup title="Aerodynamic Setup">
                            <Item label="Sweep (LE)" value={`${formatVal(optimizedValues.sweep_le_deg)}°`} />
                            <Item label="Dihedral" value={`${formatVal(optimizedValues.dihedral_deg)}°`} />
                        </ItemGroup>

                        <ItemGroup title="Twist Distribution">
                            <Item label="Root Twist" value={`${formatVal(optimizedValues.twist_root_deg)}°`} />
                            <Item label="Tip Twist" value={`${formatVal(optimizedValues.twist_tip_deg)}°`} />
                        </ItemGroup>

                        {optimizedValues.winglet_height > 0.05 && (
                            <ItemGroup title="Winglet Geometry">
                                <Item label="Height" value={`${formatVal(optimizedValues.winglet_height)} m`} />
                                <Item label="Cant Angle" value={`${formatVal(optimizedValues.winglet_cant_deg)}°`} />
                                <Item label="Toe Out" value={`${formatVal(optimizedValues.winglet_toe_out_deg)}°`} />
                            </ItemGroup>
                        )}
                    </div>

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

const ItemGroup = ({ title, children }) => (
    <div style={{ paddingBottom: '10px', borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
        <div style={{ fontSize: '11px', textTransform: 'uppercase', color: '#ffffffff', marginBottom: '8px', letterSpacing: '0.5px' }}>{title}</div>
        <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1fr) minmax(0, 1fr)', gap: '8px' }}>
            {children}
        </div>
    </div>
);

const Item = ({ label, value }) => (
    <div style={{ background: 'rgba(0,0,0,0.2)', padding: '8px', borderRadius: '6px' }}>
        <div style={{ fontSize: '11px', color: '#aaa', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{label}</div>
        <div style={{ fontSize: '14px', fontWeight: 600, color: '#eef', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{value}</div>
    </div>
);

export default OptimizedValuesPanel;
