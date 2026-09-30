import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 15000,
});

// Request interceptor to attach JWT token
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('brim_auth_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Response interceptor to format errors
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // Clear token on 401 if unauthorized
      const currentPath = window.location.pathname;
      if (!currentPath.includes('/login') && !currentPath.includes('/signup')) {
        localStorage.removeItem('brim_auth_token');
        localStorage.removeItem('brim_auth_user');
        window.location.href = '/login';
      }
    }
    
    // Normalize error message
    let message = 'An unexpected error occurred. Please try again.';
    if (error.response?.data?.detail) {
      if (typeof error.response.data.detail === 'string') {
        message = error.response.data.detail;
      } else if (Array.isArray(error.response.data.detail)) {
        message = error.response.data.detail.map((d) => d.msg || d.message || JSON.stringify(d)).join(', ');
      }
    } else if (error.message) {
      message = error.message;
    }
    
    error.userMessage = message;
    return Promise.reject(error);
  }
);

export default api;
