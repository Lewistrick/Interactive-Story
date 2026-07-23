import type { FC, ReactNode } from 'react';
import { useAuth } from '../contexts/useAuth';
import { useNavigate } from 'react-router-dom';
import Button from './ui/Button';
import ScoreBadge from './ScoreBadge';

interface HeaderProps {
  action?: ReactNode;
}

/** Top chrome bar with navigation and auth. */
const Header: FC<HeaderProps> = ({ action }) => {
  const { user, isAuthenticated, loading, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate('/');
  };

  return (
    <header className="bg-chrome border-b border-border">
      <div className="max-w-6xl mx-auto px-4 py-3 flex items-center justify-between gap-4">
        <button
          type="button"
          onClick={() => navigate('/')}
          className="text-xl font-semibold text-text hover:text-accent transition-colors"
        >
          Interactive Stories
        </button>

        <div className="flex items-center gap-3">
          <Button variant="ghost" onClick={() => navigate('/faq')}>
            FAQ
          </Button>
          {isAuthenticated && user?.is_moderator ? (
            <Button variant="ghost" onClick={() => navigate('/moderator')}>
              Moderation
            </Button>
          ) : null}
          {action}
          {loading ? (
            <span className="text-sm text-muted hidden sm:inline">…</span>
          ) : isAuthenticated ? (
            <>
              <button
                type="button"
                onClick={() => user?.id && navigate(`/users/${user.id}`)}
                className="text-sm text-muted hidden sm:inline hover:text-accent"
              >
                {user?.username}
                {user?.tier_name ? ` · ${user.tier_name}` : ''} ·{' '}
                <ScoreBadge score={user?.reputation_score ?? 0} label="Rep " />
              </button>
              <Button variant="secondary" onClick={handleLogout}>
                Logout
              </Button>
            </>
          ) : (
            <>
              <Button variant="ghost" onClick={() => navigate('/login')}>
                Login
              </Button>
              <Button variant="primary" onClick={() => navigate('/register')}>
                Register
              </Button>
            </>
          )}
        </div>
      </div>
    </header>
  );
};

export default Header;
