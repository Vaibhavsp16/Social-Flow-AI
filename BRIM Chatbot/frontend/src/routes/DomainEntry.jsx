import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../services/api';

const APP_HOSTS = ['localhost', '127.0.0.1'];

function isAppHost(hostname) {
  return APP_HOSTS.includes(hostname) || hostname.endsWith('.vercel.app');
}

/**
 * Entry point for a hostname that is not the app's own.
 *
 * A customer's domain points at this deployment, so the first thing the browser asks for is "/".
 * This resolves the hostname to a bot and sends the visitor straight into that chat. On the app's
 * own host it behaves exactly as before and goes to the dashboard.
 */
export const DomainEntry = () => {
  const navigate = useNavigate();
  const [message, setMessage] = useState('');

  useEffect(() => {
    const hostname = window.location.hostname;
    if (isAppHost(hostname)) {
      navigate('/dashboard', { replace: true });
      return;
    }

    let cancelled = false;
    setMessage('Looking up this chatbot…');
    api
      .get('/public/resolve', { params: { host: hostname } })
      .then((response) => {
        if (cancelled) return;
        navigate(`/p/${response.data.slug}`, { replace: true });
      })
      .catch((error) => {
        if (cancelled) return;
        const detail = error?.response?.data?.detail;
        setMessage(
          typeof detail === 'string'
            ? detail
            : 'No chatbot is published on this domain yet.'
        );
        // Give the message a moment, then behave like the normal app.
        setTimeout(() => navigate('/dashboard', { replace: true }), 2200);
      });

    return () => {
      cancelled = true;
    };
  }, [navigate]);

  return (
    <div
      style={{
        minHeight: '100dvh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        flexDirection: 'column',
        gap: '10px',
        color: '#6b7280',
        fontSize: '13.5px',
        background: '#f7f8fc',
      }}
    >
      {message || 'Loading…'}
    </div>
  );
};

export default DomainEntry;
