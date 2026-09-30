import React from 'react';

export const Input = ({
  label,
  error,
  required = false,
  className = '',
  id,
  ...props
}) => {
  const inputId = id || (label ? label.toLowerCase().replace(/\s+/g, '-') : undefined);

  return (
    <div className={`field ${className}`}>
      {label && (
        <label htmlFor={inputId}>
          {label} {required && '*'}
        </label>
      )}
      <input id={inputId} {...props} />
      {error && <div className="field-error">{error}</div>}
    </div>
  );
};
