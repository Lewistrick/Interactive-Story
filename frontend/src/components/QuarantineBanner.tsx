import type { FC } from 'react';

interface QuarantineBannerProps {
  reason?: string | null;
}

/** Moderator-only notice that the current part is quarantined. */
const QuarantineBanner: FC<QuarantineBannerProps> = ({ reason }) => (
  <div
    role="status"
    className="mb-4 rounded-lg border border-downvote/40 bg-downvote-soft px-4 py-3 text-sm text-downvote"
  >
    <p className="font-semibold">Quarantined — hidden from the public</p>
    {reason ? <p className="mt-1 text-downvote/90">{reason}</p> : null}
  </div>
);

export default QuarantineBanner;
