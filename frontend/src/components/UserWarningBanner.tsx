import type { FC } from 'react';
import { useAuth } from '../contexts/useAuth';

/** Banner for users under a temporary moderator warning / write quarantine. */
const UserWarningBanner: FC = () => {
  const { user } = useAuth();
  if (!user?.is_quarantined || user.is_blocked) {
    return null;
  }

  const until = user.quarantine_until
    ? new Date(user.quarantine_until).toLocaleString()
    : null;

  return (
    <div
      role="status"
      className="border-b border-downvote/30 bg-downvote-soft px-4 py-3 text-sm text-downvote"
    >
      <div className="mx-auto max-w-6xl">
        <p className="font-semibold">Account warning — posting and voting are paused</p>
        <p className="mt-1 text-downvote/90">
          {user.quarantine_reason || 'A moderator has placed a temporary restriction on your account.'}
          {until ? ` This lifts around ${until}.` : ''}
        </p>
      </div>
    </div>
  );
};

export default UserWarningBanner;
