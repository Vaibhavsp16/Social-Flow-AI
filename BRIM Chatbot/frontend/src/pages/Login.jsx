import React, { useState } from 'react';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { useToast } from '../context/ToastContext';
import { Button } from '../components/Button';
import { Input } from '../components/Input';

export const Login = () => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const { login } = useAuth();
  const { showToast } = useToast();
  const navigate = useNavigate();
  const location = useLocation();

  const from = location.state?.from?.pathname || '/dashboard';

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!email.trim() || !password) {
      setError('Please fill in all fields.');
      return;
    }

    setLoading(true);
    setError('');

    try {
      await login(email.trim(), password);
      showToast('Welcome back to BRIM AI!');
      navigate(from, { replace: true });
    } catch (err) {
      setError(err.userMessage || 'Invalid email or password.');
    } finally {
      setLoading(false);
    }
  };

  const handleDemoLogin = () => {
    setEmail('vaibhav@example.com');
    setPassword('password123');
  };

  return (
    <div className="auth-card">
      <h2>Welcome back</h2>
      <p className="muted">Sign in to continue to your workspace.</p>

      {error && (
        <div
          style={{
            background: '#fee2e2',
            border: '1px solid #fca5a5',
            color: '#b91c1c',
            padding: '10px 14px',
            borderRadius: '8px',
            fontSize: '13px',
            marginTop: '16px',
          }}
        >
          {error}
        </div>
      )}

      <form onSubmit={handleSubmit}>
        <Input
          label="Email"
          type="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="name@company.com"
          autoComplete="email"
        />

        <Input
          label="Password"
          type="password"
          required
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="••••••••"
          autoComplete="current-password"
        />

        <Button type="submit" variant="primary" full loading={loading}>
          Log in
        </Button>
      </form>

      <div style={{ textAlign: 'center', margin: '18px 0', color: '#a0a3ae', fontSize: '12px' }}>
        OR
      </div>

      <Button
        type="button"
        variant="secondary"
        full
        onClick={() => {
          showToast('Social login will be connected soon');
        }}
      >
        Continue with Google
      </Button>

      <div style={{ marginTop: '16px', textAlign: 'center' }}>
        <button
          type="button"
          onClick={handleDemoLogin}
          style={{
            background: 'none',
            border: 'none',
            color: 'var(--muted)',
            fontSize: '12px',
            cursor: 'pointer',
            textDecoration: 'underline'
          }}
        >
          Fill demo credentials
        </button>
      </div>

      <p style={{ textAlign: 'center', fontSize: '13px', marginTop: '22px' }}>
        Don't have an account?{' '}
        <Link to="/signup" style={{ color: 'var(--brand)', fontWeight: '700' }}>
          Sign up
        </Link>
      </p>
    </div>
  );
};
