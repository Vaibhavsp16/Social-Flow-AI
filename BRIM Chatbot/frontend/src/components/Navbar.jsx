import React from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

export const Navbar = ({ onToggleSidebar }) => {
  const { user } = useAuth();
  const navigate = useNavigate();

  const initial = user?.name ? user.name.charAt(0).toUpperCase() : 'U';

  return (
    <header className="topbar">
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
        <button
          className="btn secondary mobile-menu"
          onClick={onToggleSidebar}
          aria-label="Toggle Navigation Menu"
        >
          ☰
        </button>
        <Link to="/dashboard" style={{ textDecoration: 'none' }}>
          <div className="logo">
            BRIM<span>AI</span>
          </div>
        </Link>
      </div>
      <div className="top-actions">
        <button className="btn secondary" onClick={() => navigate('/pricing')}>
          Upgrade
        </button>
        <div className="avatar" title={user?.name || user?.email}>
          {initial}
        </div>
      </div>
    </header>
  );
};
