import React from 'react';
import useUIStore from '../store/uiStore';

const ViewerToolbar = ({ onZoomIn, onZoomOut, onResetView, onViewChange }) => {
    const { orientationCubeVisible, setOrientationCubeVisible } = useUIStore();

    const toggleOrientationCube = () => {
        setOrientationCubeVisible(!orientationCubeVisible);
    };

    return (
        <div className="viewer-horizontal-toolbar">
            <button
                className={`vt-btn dice-btn ${orientationCubeVisible ? 'active' : ''}`}
                onClick={toggleOrientationCube}
                title="Toggle Orientation Cube"
            >
                <i className="fas fa-cube vt-icon"></i>
            </button>

            <button className="vt-btn" onClick={onResetView} title="Reset view">
                <i className="fas fa-home vt-icon"></i>
            </button>
            <button className="vt-btn" onClick={onZoomIn} title="Zoom in">
                <i className="fas fa-plus vt-icon"></i>
            </button>
            <button className="vt-btn" onClick={onZoomOut} title="Zoom out">
                <i className="fas fa-minus vt-icon"></i>
            </button>
        </div>
    );
};

export default ViewerToolbar;
