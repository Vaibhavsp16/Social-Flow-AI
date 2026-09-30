import React from 'react';
import { Button } from './Button';

export const Modal = ({
  isOpen,
  onClose,
  title,
  children,
  maxWidth = '520px'
}) => {
  if (!isOpen) return null;

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        backgroundColor: 'rgba(23, 21, 42, 0.45)',
        backdropFilter: 'blur(4px)',
        zIndex: 100,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '20px',
      }}
      onClick={onClose}
    >
      <div
        className="card"
        style={{
          width: '100%',
          maxWidth,
          backgroundColor: '#fff',
          padding: '28px',
          borderRadius: '18px',
          boxShadow: '0 20px 50px rgba(0,0,0,0.2)',
          maxHeight: '90vh',
          overflowY: 'auto',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '18px' }}>
          <h2 style={{ fontSize: '20px', fontWeight: '700' }}>{title}</h2>
          <button
            onClick={onClose}
            style={{
              background: 'transparent',
              border: 0,
              fontSize: '20px',
              color: '#8a8e9a',
              padding: '4px 8px',
            }}
          >
            ✕
          </button>
        </div>
        <div>{children}</div>
      </div>
    </div>
  );
};
