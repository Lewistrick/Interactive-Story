import type { FC, ReactNode } from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from '../contexts/useAuth';

const ALLOWED_WHILE_RESET = new Set(['/reset-password', '/login', '/faq']);

/**
 * Redirect users who must change their password away from the rest of the app.
 */
const PasswordResetGate: FC<{ children: ReactNode }> = ({ children }) => {
  const { user, loading } = useAuth();
  const location = useLocation();

  if (loading) {
    return children;
  }

  if (user?.must_reset_password && !ALLOWED_WHILE_RESET.has(location.pathname)) {
    return <Navigate to="/reset-password" replace />;
  }

  return children;
};

export default PasswordResetGate;
