import type { FC, ReactNode } from 'react';
import { useAuth } from '../contexts/useAuth';
import { useNavigate } from 'react-router-dom';
import Button from './ui/Button';

interface HeaderProps {
  action?: ReactNode;
}

/** Top chrome bar with navigation and auth. */
const Header: FC<HeaderProps> = ({ action }) => {
  const { user, isAuthenticated, logout } = useAuth();
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
          {action}
          {isAuthenticated ? (
            <>
              <span className="text-sm text-muted hidden sm:inline">
                {user?.username}
                {user?.tier_name ? ` · ${user.tier_name}` : ''} · Rep{' '}
                {user?.reputation_score}
              </span>
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
