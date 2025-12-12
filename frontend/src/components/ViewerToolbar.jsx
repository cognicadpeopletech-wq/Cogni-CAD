import React from 'react';
import useUIStore from '../store/uiStore';

const ViewerToolbar = ({ onZoomIn, onZoomOut, onResetView, onViewChange }) => {
    const { orientationCubeVisible, setOrientationCubeVisible } = useUIStore();
    const [showViews, setShowViews] = React.useState(false);

    const toggleOrientationCube = () => {
        setOrientationCubeVisible(!orientationCubeVisible);
    };

    const handleViewClick = (view) => {
        if (onViewChange) onViewChange(view);
        setShowViews(false);
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

            {/* Standard Views Menu */}
            <div style={{ position: 'relative' }}>
                <button
                    className={`vt-btn ${showViews ? 'active' : ''}`}
                    onClick={() => setShowViews(!showViews)}
                    title="Standard Views"
                >
                    <i className="fas fa-video vt-icon"></i>
                </button>
                {showViews && (
                    <div className="vt-dropdown-menu">
                        <div className="vt-menu-item" onClick={() => handleViewClick('top')}>Top</div>
                        <div className="vt-menu-item" onClick={() => handleViewClick('bottom')}>Bottom</div>
                        <div className="vt-menu-item" onClick={() => handleViewClick('front')}>Front</div>
                        <div className="vt-menu-item" onClick={() => handleViewClick('back')}>Back</div>
                        <div className="vt-menu-item" onClick={() => handleViewClick('left')}>Left</div>
                        <div className="vt-menu-item" onClick={() => handleViewClick('right')}>Right</div>
                    </div>
                )}
            </div>

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
