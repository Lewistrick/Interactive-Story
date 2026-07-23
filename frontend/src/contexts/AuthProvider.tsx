import type { FC, ReactNode } from 'react';
import { useState, useEffect } from 'react';
import axios from 'axios';
import { authApi } from '../api/auth';
import type { User } from '../api/auth';
import { AuthContext } from './auth-context';

/** True when the error is an authenticated-request rejection (clear the session). */
function isUnauthorized(error: unknown): boolean {
  return axios.isAxiosError(error) && error.response?.status === 401;
}

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
        } catch (error) {
          // Only drop the session on a real auth failure — network/5xx must not log the user out.
          if (isUnauthorized(error)) {
            localStorage.removeItem('token');
            setUser(null);
          }
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
    } catch (error) {
      if (isUnauthorized(error)) {
        localStorage.removeItem('token');
        setUser(null);
      }
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
