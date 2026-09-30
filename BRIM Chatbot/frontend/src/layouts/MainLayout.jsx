import React, { useState } from 'react';
import { Outlet } from 'react-router-dom';
import { Navbar } from '../components/Navbar';
import { Sidebar } from '../components/Sidebar';
import { Toast } from '../components/Toast';

export const MainLayout = () => {
  const [sidebarOpen, setSidebarOpen] = useState(false);

  return (
    <div className="app">
      <Navbar onToggleSidebar={() => setSidebarOpen((prev) => !prev)} />
      <div className="layout">
        <Sidebar isOpen={sidebarOpen} onClose={() => setSidebarOpen(false)} />
        <main className="main">
          <Outlet />
        </main>
      </div>
      <Toast />
    </div>
  );
};
