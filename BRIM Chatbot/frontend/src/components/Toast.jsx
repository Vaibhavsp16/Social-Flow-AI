import React from 'react';
import { useToast } from '../context/ToastContext';

export const Toast = () => {
  const { toast } = useToast();

  if (!toast.visible) return null;

  return (
    <div className="toast-container">
      <div className="toast">
        <span>{toast.message}</span>
      </div>
    </div>
  );
};
