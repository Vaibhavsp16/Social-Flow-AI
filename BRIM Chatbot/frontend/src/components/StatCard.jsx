import React from 'react';

export const StatCard = ({ label, value, delta, className = '' }) => {
  return (
    <div className={`stat ${className}`}>
      <div className="label">{label}</div>
      <div className="value">{value}</div>
      {delta && <div className="delta">{delta}</div>}
    </div>
  );
};
