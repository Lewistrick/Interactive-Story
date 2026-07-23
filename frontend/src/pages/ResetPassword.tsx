import { useState, type FC, type FormEvent } from 'react';
import { Navigate, useNavigate } from 'react-router-dom';
import { authApi } from '../api/auth';
import { useAuth } from '../contexts/useAuth';
import Button from '../components/ui/Button';
import Input from '../components/ui/Input';
import Label from '../components/ui/Label';
import Panel from '../components/ui/Panel';

/** Forced password change after compromise signals (velocity + IP/fingerprint). */
const ResetPassword: FC = () => {
  const navigate = useNavigate();
  const { user, refreshUser, logout, loading } = useAuth();
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  if (loading) {
    return (
      <div className="min-h-screen bg-page flex items-center justify-center px-4 text-muted">
        Loading…
      </div>
    );
  }

  if (!user) {
    return <Navigate to="/login" replace />;
  }

  if (!user.must_reset_password) {
    return <Navigate to="/" replace />;
  }

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError('');
    if (newPassword.length < 6) {
      setError('New password must be at least 6 characters');
      return;
    }
    if (newPassword !== confirmPassword) {
      setError('New passwords do not match');
      return;
    }
    setSubmitting(true);
    try {
      await authApi.changePassword({
        current_password: currentPassword,
        new_password: newPassword,
      });
      await refreshUser();
      navigate('/');
    } catch {
      setError('Could not change password. Check your current password and try again.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen bg-page flex items-center justify-center px-4">
      <Panel className="p-8 w-full max-w-md">
        <h1 className="text-2xl font-semibold text-text mb-2 text-center">Reset your password</h1>
        <p className="text-sm text-muted mb-6 text-center">
          Unusual activity was detected on your account. Choose a new password to continue.
        </p>

        {error && (
          <div className="bg-danger-soft border border-downvote/30 text-danger-text px-4 py-3 rounded-lg mb-4 text-sm">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <Label htmlFor="current">Current password</Label>
            <Input
              id="current"
              type="password"
              value={currentPassword}
              onChange={(e) => setCurrentPassword(e.target.value)}
              required
            />
          </div>
          <div>
            <Label htmlFor="new">New password</Label>
            <Input
              id="new"
              type="password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              required
              minLength={6}
            />
          </div>
          <div>
            <Label htmlFor="confirm">Confirm new password</Label>
            <Input
              id="confirm"
              type="password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              required
              minLength={6}
            />
          </div>
          <Button type="submit" variant="primary" disabled={submitting} className="w-full py-3">
            {submitting ? 'Saving…' : 'Save new password'}
          </Button>
        </form>

        <p className="text-center mt-6 text-muted text-sm">
          <button
            type="button"
            onClick={() => {
              logout();
              navigate('/login');
            }}
            className="text-accent hover:text-accent-hover font-semibold"
          >
            Sign out
          </button>
        </p>
      </Panel>
    </div>
  );
};

export default ResetPassword;
