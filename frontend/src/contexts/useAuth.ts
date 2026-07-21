import { useContext } from 'react';
import { AuthContext } from './auth-context';
import type { AuthContextType } from './auth-context';

/** Access the auth context; must be used under AuthProvider. */
export function useAuth(): AuthContextType {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
