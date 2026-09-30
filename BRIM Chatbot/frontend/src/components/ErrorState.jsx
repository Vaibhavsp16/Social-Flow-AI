import React from 'react';
import { Button } from './Button';

export const ErrorState = ({
  title = 'Something went wrong',
  message = 'An error occurred while loading this section.',
  onRetry,
}) => {
  return (
    <div className="empty" style={{ borderColor: '#fca5a5', background: '#fffcfc' }}>
      <div className="empty-icon" style={{ background: '#fee2e2', color: '#e53e3e' }}>⚠️</div>
      <h3 style={{ color: '#991b1b' }}>{title}</h3>
      <p style={{ color: '#b91c1c' }}>{message}</p>
      {onRetry && (
        <Button variant="secondary" onClick={onRetry}>
          Try Again
        </Button>
      )}
    </div>
  );
};
