import type { FC, ReactNode } from 'react';
import { Navigate } from 'react-router-dom';
import { useAuth } from '../contexts/useAuth';
import PageShell from './PageShell';

interface RequireModeratorProps {
  children: ReactNode;
}

/**
 * Wait for auth hydration from ``localStorage`` before gating moderator routes.
 *
 * Without this, a new tab (e.g. ctrl+click) sees ``user === null`` for one frame
 * and redirects to login even though a valid token is already stored.
 */
const RequireModerator: FC<RequireModeratorProps> = ({ children }) => {
  const { user, isAuthenticated, loading } = useAuth();

  if (loading) {
    return (
      <PageShell>
        <main className="mx-auto max-w-3xl px-4 py-16 text-center text-muted">
          Loading…
        </main>
      </PageShell>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  if (!user?.is_moderator) {
    return (
      <PageShell>
        <main className="mx-auto max-w-3xl px-4 py-16 text-center text-muted">
          Moderator access required.
        </main>
      </PageShell>
    );
  }

  return <>{children}</>;
};

export default RequireModerator;
