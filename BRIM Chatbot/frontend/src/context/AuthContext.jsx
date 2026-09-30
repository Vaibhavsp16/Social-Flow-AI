import React, { createContext, useContext, useState, useEffect } from 'react';
import { authService } from '../services/authService';

const AuthContext = createContext(null);

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(() => authService.getStoredUser());
  const [token, setToken] = useState(() => authService.getStoredToken());
  const [isLoading, setIsLoading] = useState(true);
  const [authError, setAuthError] = useState(null);

  useEffect(() => {
    const initializeAuth = async () => {
      const storedToken = authService.getStoredToken();
      if (storedToken) {
        try {
          const userData = await authService.getCurrentUser();
          setUser(userData);
          setToken(storedToken);
        } catch (err) {
          authService.logout();
          setUser(null);
          setToken(null);
        }
      }
      setIsLoading(false);
    };

    initializeAuth();
  }, []);

  const login = async (email, password) => {
    setIsLoading(true);
    setAuthError(null);
    try {
      const data = await authService.login(email, password);
      setUser(data.user);
      setToken(data.access_token);
      return data.user;
    } catch (err) {
      setAuthError(err.userMessage || 'Login failed');
      throw err;
    } finally {
      setIsLoading(false);
    }
  };

  const signup = async (name, email, password) => {
    setIsLoading(true);
    setAuthError(null);
    try {
      const data = await authService.signup(name, email, password);
      setUser(data.user);
      setToken(data.access_token);
      return data.user;
    } catch (err) {
      setAuthError(err.userMessage || 'Signup failed');
      throw err;
    } finally {
      setIsLoading(false);
    }
  };

  const logout = () => {
    authService.logout();
    setUser(null);
    setToken(null);
  };

  const refreshUser = async () => {
    try {
      const userData = await authService.getCurrentUser();
      setUser(userData);
      return userData;
    } catch {
      return null;
    }
  };

  const value = {
    user,
    token,
    isAuthenticated: !!token && !!user,
    isLoading,
    authError,
    login,
    signup,
    logout,
    refreshUser,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
