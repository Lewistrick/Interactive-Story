import type { FC } from 'react';
import ScoreBadge from './ScoreBadge';

interface VotingButtonsProps {
  voteScore: number;
  userVote?: 'UP' | 'DOWN' | null;
  disabled?: boolean;
  canVote?: boolean;
  onVote: (voteType: 'UP' | 'DOWN') => void;
}

/** Upvote/downvote controls with Archive Parchment colors. */
const VotingButtons: FC<VotingButtonsProps> = ({
  voteScore,
  userVote,
  disabled = false,
  canVote = true,
  onVote,
}) => {
  const controlsDisabled = disabled || !canVote;

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={() => onVote('UP')}
          disabled={controlsDisabled}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors disabled:opacity-50 ${
            userVote === 'UP'
              ? 'bg-upvote text-surface'
              : 'bg-upvote-soft text-upvote hover:bg-upvote/20'
          }`}
          aria-pressed={userVote === 'UP'}
        >
          ▲ Upvote
        </button>
        <ScoreBadge score={voteScore} className="text-lg font-semibold" />
        <button
          type="button"
          onClick={() => onVote('DOWN')}
          disabled={controlsDisabled}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors disabled:opacity-50 ${
            userVote === 'DOWN'
              ? 'bg-downvote text-surface'
              : 'bg-downvote-soft text-downvote hover:bg-downvote/20'
          }`}
          aria-pressed={userVote === 'DOWN'}
        >
          ▼ Downvote
        </button>
      </div>
      {!canVote && (
        <p className="text-sm text-muted">Your account cannot vote right now.</p>
      )}
    </div>
  );
};

export default VotingButtons;
