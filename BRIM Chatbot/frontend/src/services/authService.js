import api from './api';

export const authService = {
  async signup(name, email, password) {
    const response = await api.post('/auth/signup', { name, email, password });
    if (response.data.access_token) {
      localStorage.setItem('brim_auth_token', response.data.access_token);
      localStorage.setItem('brim_auth_user', JSON.stringify(response.data.user));
    }
    return response.data;
  },

  async login(email, password) {
    const response = await api.post('/auth/login', { email, password });
    if (response.data.access_token) {
      localStorage.setItem('brim_auth_token', response.data.access_token);
      localStorage.setItem('brim_auth_user', JSON.stringify(response.data.user));
    }
    return response.data;
  },

  // ── Google sign-in ────────────────────────────────────────────────────────
  // The browser gets an ID token from Google Identity Services; the API verifies it. No client
  // secret ever reaches the browser.
  async googleConfig() {
    const response = await api.get('/auth/google/config');
    return response.data;
  },

  async loginWithGoogle(credential) {
    const response = await api.post('/auth/google', { credential });
    if (response.data.access_token) {
      localStorage.setItem('brim_auth_token', response.data.access_token);
      localStorage.setItem('brim_auth_user', JSON.stringify(response.data.user));
    }
    return response.data;
  },

  async getCurrentUser() {
    const response = await api.get('/auth/me');
    localStorage.setItem('brim_auth_user', JSON.stringify(response.data));
    return response.data;
  },

  logout() {
    localStorage.removeItem('brim_auth_token');
    localStorage.removeItem('brim_auth_user');
  },

  getStoredToken() {
    return localStorage.getItem('brim_auth_token');
  },

  getStoredUser() {
    const userStr = localStorage.getItem('brim_auth_user');
    try {
      return userStr ? JSON.parse(userStr) : null;
    } catch {
      return null;
    }
  }
};
