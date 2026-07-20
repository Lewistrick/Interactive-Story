import type { FC } from 'react';

interface VotingButtonsProps {
  voteScore: number;
  userVote?: 'UP' | 'DOWN' | null;
  disabled?: boolean;
  onVote: (voteType: 'UP' | 'DOWN') => void;
}

const VotingButtons: FC<VotingButtonsProps> = ({
  voteScore,
  userVote,
  disabled = false,
  onVote,
}) => {
  return (
    <div className="flex items-center gap-4">
      <button
        type="button"
        onClick={() => onVote('UP')}
        disabled={disabled}
        className={`flex items-center gap-2 px-4 py-2 rounded-lg transition-colors disabled:opacity-50 ${
          userVote === 'UP'
            ? 'bg-green-600 text-white'
            : 'bg-green-100 text-green-800 hover:bg-green-200'
        }`}
        aria-pressed={userVote === 'UP'}
      >
        <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20" aria-hidden="true">
          <path d="M2 10.5a1.5 1.5 0 113 0v6a1.5 1.5 0 01-3 0v-6zM6 10.333v5.43a2 2 0 001.106 1.79l.05.025A4 4 0 008.943 18h5.416a2 2 0 001.962-1.608l1.2-6A2 2 0 0015.56 8H12V4a2 2 0 00-2-2 1 1 0 00-1 1v.667a4 4 0 01-.8 2.4L6.8 7.933a4 4 0 00-.8 2.4z" />
        </svg>
        Upvote
      </button>
      <span className="text-lg font-semibold text-gray-800 tabular-nums" aria-live="polite">
        {voteScore}
      </span>
      <button
        type="button"
        onClick={() => onVote('DOWN')}
        disabled={disabled}
        className={`flex items-center gap-2 px-4 py-2 rounded-lg transition-colors disabled:opacity-50 ${
          userVote === 'DOWN'
            ? 'bg-red-600 text-white'
            : 'bg-red-100 text-red-800 hover:bg-red-200'
        }`}
        aria-pressed={userVote === 'DOWN'}
      >
        <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20" aria-hidden="true">
          <path d="M18 9.5a1.5 1.5 0 11-3 0v-6a1.5 1.5 0 013 0v6zM14 9.667v-5.43a2 2 0 00-1.105-1.79l-.05-.025A4 4 0 0011.055 2H5.64a2 2 0 00-1.962 1.608l-1.2 6A2 2 0 004.44 12H8v4a2 2 0 002 2 1 1 0 001-1v-.667a4 4 0 01.8-2.4l1.4-1.866a4 4 0 00.8-2.4z" />
        </svg>
        Downvote
      </button>
    </div>
  );
};

export default VotingButtons;
