import React, { useState } from 'react';
import ChatPanel from './components/ChatPanel';
import ThreeCanvas from './components/ThreeCanvas';
import WingHUD from './components/WingHUD';
import OptimizedValuesPanel from './components/OptimizedValuesPanel';
import useUIStore from './store/uiStore';
import './App.css';

function App() {
    const [mode, setMode] = useState('INHOUSE_CAD'); // 'CATIA_COPILOT' or 'INHOUSE_CAD'
    const [panelState, setPanelState] = useState('normal'); // 'normal' | 'left-maximized' | 'right-maximized'
    const { isDarkMode, toggleTheme } = useUIStore();

    const toggleLeftPanel = () => {
        setPanelState(prev => prev === 'left-maximized' ? 'normal' : 'left-maximized');
    };

    const toggleRightPanel = () => {
        setPanelState(prev => prev === 'right-maximized' ? 'normal' : 'right-maximized');
    };

    return (
        <div className={`app-container ${panelState} ${isDarkMode ? 'dark-mode' : ''}`}>
            <div className="main-layout">
                <ChatPanel
                    mode={mode}
                    setMode={setMode}
                    onTogglePanel={toggleLeftPanel}
                    panelState={panelState}
                    setPanelState={setPanelState}
                />
                <div className="canvas-area">
                    <button
                        className="right-expand-btn"
                        onClick={toggleRightPanel}
                        title="Maximize Workspace"
                    >
                        <i className="fas fa-expand"></i>
                    </button>

                    <ThreeCanvas mode={mode} />
                    <WingHUD />
                    <OptimizedValuesPanel />
                </div>
            </div>
        </div>
    );
}

export default App;
