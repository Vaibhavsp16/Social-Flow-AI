import React from 'react';

export const LoadingState = ({ message = 'Loading...' }) => {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '60px 20px', gap: '14px' }}>
      <div className="spinner spinner-dark" style={{ width: '36px', height: '36px' }} />
      <p className="muted">{message}</p>
    </div>
  );
};
