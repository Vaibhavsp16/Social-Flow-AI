import React from 'react';
import { Button } from './Button';

export const EmptyState = ({
  icon = '🤖',
  title = 'No data found',
  description = 'There are no items to display right now.',
  actionLabel,
  onAction,
}) => {
  return (
    <div className="empty">
      <div className="empty-icon">{icon}</div>
      <h3>{title}</h3>
      <p>{description}</p>
      {actionLabel && onAction && (
        <Button variant="primary" onClick={onAction}>
          {actionLabel}
        </Button>
      )}
    </div>
  );
};
