import { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { local, STORAGE_KEYS } from '../utils/storage';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => local.get(STORAGE_KEYS.USER));
  const [token, setToken] = useState(() => local.get(STORAGE_KEYS.AUTH_TOKEN));
  const [loading, setLoading] = useState(false);

  const isAuthenticated = Boolean(token && user);

  const login = useCallback((userData, authToken) => {
    setUser(userData);
    setToken(authToken);
    local.set(STORAGE_KEYS.USER, userData);
    local.set(STORAGE_KEYS.AUTH_TOKEN, authToken);
  }, []);

  const logout = useCallback(() => {
    setUser(null);
    setToken(null);
    local.remove(STORAGE_KEYS.USER);
    local.remove(STORAGE_KEYS.AUTH_TOKEN);
  }, []);

  const updateUser = useCallback((updates) => {
    setUser((prev) => {
      const updated = { ...prev, ...updates };
      local.set(STORAGE_KEYS.USER, updated);
      return updated;
    });
  }, []);

  return (
    <AuthContext.Provider value={{ user, token, isAuthenticated, loading, login, logout, updateUser }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
