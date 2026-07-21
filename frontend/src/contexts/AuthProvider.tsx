import type { FC, ReactNode } from 'react';
import { useState, useEffect } from 'react';
import { authApi } from '../api/auth';
import type { User } from '../api/auth';
import { AuthContext } from './auth-context';

/** Provides auth state and actions to the React tree. */
export const AuthProvider: FC<{ children: ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const checkAuth = async () => {
      const token = localStorage.getItem('token');
      if (token) {
        try {
          const userData = await authApi.getCurrentUser();
          setUser(userData);
        } catch {
          localStorage.removeItem('token');
        }
      }
      setLoading(false);
    };

    void checkAuth();
  }, []);

  const refreshUser = async () => {
    const token = localStorage.getItem('token');
    if (!token) {
      setUser(null);
      return;
    }
    try {
      const userData = await authApi.getCurrentUser();
      setUser(userData);
    } catch {
      localStorage.removeItem('token');
      setUser(null);
    }
  };

  const login = async (username: string, password: string) => {
    await authApi.login({ username, password });
    const userData = await authApi.getCurrentUser();
    setUser(userData);
  };

  const register = async (username: string, password: string) => {
    await authApi.register({ username, password });
    await login(username, password);
  };

  const logout = () => {
    authApi.logout();
    setUser(null);
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        login,
        register,
        logout,
        refreshUser,
        isAuthenticated: !!user,
        loading,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};
