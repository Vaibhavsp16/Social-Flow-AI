import React from 'react';

export const BotCard = ({ bot, onClick }) => {
  const statusClass = bot.status === 'Live' ? 'status' : 'status draft';

  return (
    <div className="bot-card" onClick={onClick}>
      <div className="bot-head">
        <div className="bot-icon">AI</div>
        <div>
          <h3>{bot.name}</h3>
          <p>{bot.industry || bot.project?.industry || 'General'}</p>
        </div>
        <span className={statusClass} style={{ marginLeft: 'auto' }}>
          <span className="dot"></span>
          {bot.status || 'Live'}
        </span>
      </div>
      <p style={{ marginTop: '14px', flex: 1 }}>{bot.description || 'AI assistant for business enquiry and customer interactions.'}</p>
      <div className="bot-meta">
        <span>◉ {bot.language || 'English'}</span>
        <span>◌ {bot.personality || 'Friendly'}</span>
      </div>
    </div>
  );
};
