import React from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { AuthLayout } from '../layouts/AuthLayout';
import { MainLayout } from '../layouts/MainLayout';
import { ProtectedRoute } from './ProtectedRoute';

// Pages
import { Login } from '../pages/Login';
import { Signup } from '../pages/Signup';
import { Dashboard } from '../pages/Dashboard';
import { MyBots } from '../pages/MyBots';
import { CreateBot } from '../pages/CreateBot';
import { BotOverview } from '../pages/BotOverview';
import { ChatHistory } from '../pages/ChatHistory';
import { Analytics } from '../pages/Analytics';
import { Pricing } from '../pages/Pricing';
import { ChatPreview } from '../pages/ChatPreview';
import { ChatInterface } from '../pages/ChatInterface';

export const AppRoutes = () => {
  return (
    <Routes>
      {/* Public Auth Routes */}
      <Route element={<AuthLayout />}>
        <Route path="/login" element={<Login />} />
        <Route path="/signup" element={<Signup />} />
      </Route>

      {/* Standalone Chat & Preview Routes */}
      <Route path="/preview" element={<ChatPreview />} />
      <Route path="/preview/:id" element={<ChatInterface />} />
      <Route path="/chat/:id" element={<ChatInterface />} />
      <Route path="/bots/:id/chat" element={<ChatInterface />} />

      {/* Protected Application Routes */}
      <Route element={<ProtectedRoute />}>
        <Route element={<MainLayout />}>
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/bots" element={<MyBots />} />
          <Route path="/bots/create" element={<CreateBot />} />
          <Route path="/bots/:id" element={<BotOverview />} />
          <Route path="/history" element={<ChatHistory />} />
          <Route path="/analytics" element={<Analytics />} />
          <Route path="/pricing" element={<Pricing />} />
        </Route>
      </Route>

      {/* Catch-all fallback */}
      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  );
};
