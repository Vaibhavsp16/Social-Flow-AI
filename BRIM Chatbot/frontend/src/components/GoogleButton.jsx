import React, { useEffect, useRef, useState } from 'react';
import { authService } from '../services/authService';

const GIS_SRC = 'https://accounts.google.com/gsi/client';
const SCRIPT_ID = 'google-identity-services';

function loadGis() {
  if (window.google?.accounts?.id) return Promise.resolve();
  const existing = document.getElementById(SCRIPT_ID);
  if (existing) {
    return new Promise((resolve, reject) => {
      existing.addEventListener('load', resolve, { once: true });
      existing.addEventListener('error', () => reject(new Error('Google script failed')), { once: true });
    });
  }
  return new Promise((resolve, reject) => {
    const script = document.createElement('script');
    script.id = SCRIPT_ID;
    script.src = GIS_SRC;
    script.async = true;
    script.defer = true;
    script.onload = resolve;
    script.onerror = () => reject(new Error('Google script failed'));
    document.head.appendChild(script);
  });
}

/**
 * "Continue with Google".
 *
 * Renders Google's own button when the deployment is configured, and an explanation when it is not
 * — a button that silently does nothing is worse than a clear message naming the missing setting.
 */
export const GoogleButton = ({
  onCredential,
  onError,
  disabled = false,
  label = 'Continue with Google',
}) => {
  const holder = useRef(null);
  const handlerRef = useRef(onCredential);
  const [state, setState] = useState('loading'); // loading | ready | unconfigured | failed
  const [detail, setDetail] = useState('');

  // Kept in a ref so a re-render never has to re-initialise Google's client.
  handlerRef.current = onCredential;

  useEffect(() => {
    let cancelled = false;

    (async () => {
      try {
        const config = await authService.googleConfig();
        if (cancelled) return;
        if (!config.enabled || !config.client_id) {
          setState('unconfigured');
          return;
        }
        await loadGis();
        if (cancelled || !holder.current) return;

        window.google.accounts.id.initialize({
          client_id: config.client_id,
          callback: async (response) => {
            try {
              await handlerRef.current?.(response.credential);
            } catch (err) {
              onError?.(err.userMessage || 'Google sign-in failed. Please try again.');
            }
          },
          auto_select: false,
          cancel_on_tap_outside: true,
        });

        window.google.accounts.id.renderButton(holder.current, {
          type: 'standard',
          theme: 'outline',
          size: 'large',
          text: 'continue_with',
          shape: 'rectangular',
          logo_alignment: 'left',
          width: 320,
        });
        setState('ready');
      } catch (err) {
        if (cancelled) return;
        setState('failed');
        setDetail(err.userMessage || err.message || 'Could not load Google sign-in.');
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [onError]);

  if (state === 'unconfigured') {
    return (
      <div
        style={{
          border: '1px dashed var(--line, #e7e4f3)',
          borderRadius: '10px',
          padding: '10px 14px',
          fontSize: '12.5px',
          color: '#6f7184',
          textAlign: 'center',
        }}
      >
        <b style={{ color: '#4b5563' }}>{label}</b> — not configured yet.
        <div style={{ marginTop: '4px' }}>
          Add <code>GOOGLE_CLIENT_ID</code> to the API and <code>VITE_GOOGLE_CLIENT_ID</code> to the
          web app, then authorise this origin in Google Cloud Console.
        </div>
      </div>
    );
  }

  if (state === 'failed') {
    return (
      <div style={{ fontSize: '12.5px', color: '#b91c1c', textAlign: 'center' }}>
        Google sign-in could not load. {detail}
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', justifyContent: 'center', minHeight: '44px' }}>
      {state === 'loading' && (
        <div style={{ fontSize: '12.5px', color: '#9ca3af', alignSelf: 'center' }}>
          Loading Google sign-in…
        </div>
      )}
      <div
        ref={holder}
        style={{ opacity: disabled ? 0.5 : 1, pointerEvents: disabled ? 'none' : 'auto' }}
      />
    </div>
  );
};

export default GoogleButton;
