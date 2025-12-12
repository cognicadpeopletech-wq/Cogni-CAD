import React from 'react';

const ModeSwitcher = ({ mode, setMode }) => {
  return (
    <div style={{
      display: 'flex', 
      background: '#2d3748', 
      borderRadius: '8px', 
      padding: '4px',
      marginBottom: '1rem'
    }}>
      <button 
        onClick={() => setMode('CAD')}
        style={{
          flex: 1,
          background: mode === 'CAD' ? '#4f46e5' : 'transparent',
          color: 'white',
          border: 'none',
          padding: '8px',
          borderRadius: '6px',
          cursor: 'pointer',
          fontWeight: '500',
          transition: 'all 0.2s'
        }}
      >
        AI CAD
      </button>
      <button 
        onClick={() => setMode('CATIA')}
        style={{
          flex: 1,
          background: mode === 'CATIA' ? '#4f46e5' : 'transparent',
          color: 'white',
          border: 'none',
          padding: '8px',
          borderRadius: '6px',
          cursor: 'pointer',
          fontWeight: '500',
          transition: 'all 0.2s'
        }}
      >
        CATIA Script
      </button>
    </div>
  );
};

export default ModeSwitcher;
