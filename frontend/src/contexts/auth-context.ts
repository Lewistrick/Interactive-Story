import { createContext } from 'react';
import type { User } from '../api/auth';

/** Shape of the auth context value. */
export interface AuthContextType {
  user: User | null;
  login: (username: string, password: string) => Promise<void>;
  register: (username: string, password: string) => Promise<void>;
  logout: () => void;
  /** Re-fetch `/auth/me` (e.g. after publishing a part). */
  refreshUser: () => Promise<void>;
  isAuthenticated: boolean;
  loading: boolean;
}

export const AuthContext = createContext<AuthContextType | undefined>(undefined);
