import React from 'react';

export const Select = ({
  label,
  options = [],
  error,
  required = false,
  className = '',
  id,
  value,
  onChange,
  placeholder,
  ...props
}) => {
  const selectId = id || (label ? label.toLowerCase().replace(/\s+/g, '-') : undefined);

  return (
    <div className={`field ${className}`}>
      {label && (
        <label htmlFor={selectId}>
          {label} {required && '*'}
        </label>
      )}
      <select id={selectId} value={value} onChange={onChange} {...props}>
        {placeholder && <option value="">{placeholder}</option>}
        {options.map((opt) => {
          const val = typeof opt === 'object' ? opt.value : opt;
          const lbl = typeof opt === 'object' ? opt.label : opt;
          return (
            <option key={val} value={val}>
              {lbl}
            </option>
          );
        })}
      </select>
      {error && <div className="field-error">{error}</div>}
    </div>
  );
};
