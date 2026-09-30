import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { useToast } from '../context/ToastContext';
import { Button } from '../components/Button';
import { Input } from '../components/Input';

export const Signup = () => {
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const { signup } = useAuth();
  const { showToast } = useToast();
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!name.trim() || !email.trim() || !password) {
      setError('Please fill in all required fields.');
      return;
    }

    if (password.length < 6) {
      setError('Password must be at least 6 characters.');
      return;
    }

    setLoading(true);
    setError('');

    try {
      await signup(name.trim(), email.trim(), password);
      showToast('Account created successfully! Welcome to BRIM AI.');
      navigate('/dashboard', { replace: true });
    } catch (err) {
      setError(err.userMessage || 'Failed to create account.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-card">
      <h2>Create account</h2>
      <p className="muted">Start building your AI chatbots in minutes.</p>

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
          label="Full Name"
          type="text"
          required
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="e.g. Vaibhav Patel"
        />

        <Input
          label="Work Email"
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
          placeholder="Minimum 6 characters"
          autoComplete="new-password"
        />

        <Button type="submit" variant="primary" full loading={loading}>
          Create Account
        </Button>
      </form>

      <p style={{ textAlign: 'center', fontSize: '13px', marginTop: '22px' }}>
        Already have an account?{' '}
        <Link to="/login" style={{ color: 'var(--brand)', fontWeight: '700' }}>
          Sign in
        </Link>
      </p>
    </div>
  );
};
