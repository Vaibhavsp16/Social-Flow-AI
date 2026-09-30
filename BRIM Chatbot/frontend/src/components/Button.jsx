import React from 'react';

export const Button = ({
  children,
  variant = 'primary',
  full = false,
  loading = false,
  disabled = false,
  className = '',
  type = 'button',
  onClick,
  ...props
}) => {
  const variantClass = variant === 'secondary' ? 'secondary' : variant === 'danger' ? 'danger-btn' : 'primary';
  const fullClass = full ? 'full' : '';

  return (
    <button
      type={type}
      className={`btn ${variantClass} ${fullClass} ${className}`}
      disabled={disabled || loading}
      onClick={onClick}
      {...props}
    >
      {loading && <div className={`spinner ${variant === 'secondary' ? 'spinner-dark' : ''}`} />}
      {children}
    </button>
  );
};
