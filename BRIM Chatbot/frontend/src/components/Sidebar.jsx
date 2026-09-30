import React from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { useToast } from '../context/ToastContext';

export const Sidebar = ({ isOpen, onClose }) => {
  const { logout } = useAuth();
  const { showToast } = useToast();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    showToast('Logged out successfully');
    navigate('/login');
  };

  const navItems = [
    { to: '/dashboard', label: '⌂  Dashboard' },
    { to: '/bots', label: '◈  My Bots' },
    { to: '/history', label: '◷  Chat History' },
    { to: '/analytics', label: '▥  Analytics' },
    { to: '/pricing', label: '◇  Pricing' },
  ];

  return (
    <aside className={`sidebar ${isOpen ? 'mobile-open' : ''}`}>
      <div className="nav-title">Workspace</div>
      <div className="nav">
        {navItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            onClick={onClose}
            className={({ isActive }) => (isActive ? 'active' : '')}
          >
            {item.label}
          </NavLink>
        ))}
      </div>

      <div className="nav-title" style={{ marginTop: 'auto', paddingTop: '20px' }}>
        Account
      </div>
      <div className="nav">
        <button onClick={() => showToast('Settings screen ready for implementation')}>
          ⚙  Settings
        </button>
        <button onClick={handleLogout}>
          ↪  Log out
        </button>
      </div>
    </aside>
  );
};
