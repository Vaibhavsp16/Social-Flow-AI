import React from 'react';
import { Outlet } from 'react-router-dom';
import { Toast } from '../components/Toast';

export const AuthLayout = () => {
  return (
    <div className="login">
      <section className="login-left">
        <div className="logo">
          BRIM<span>AI</span>
        </div>
        <h1>Create, manage and share your AI chatbot.</h1>
        <p>
          A simple workspace to build AI assistants from your business knowledge and share them with customers.
        </p>
        <div className="feature-row">
          <span className="pill">Create bots</span>
          <span className="pill">Upload knowledge</span>
          <span className="pill">View conversations</span>
          <span className="pill">Track analytics</span>
        </div>
      </section>
      <section className="login-right">
        <Outlet />
      </section>
      <Toast />
    </div>
  );
};
