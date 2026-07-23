import type { FC, KeyboardEvent } from 'react';
import type { StoryPart } from '../api/stories';
import AuthorLink from './AuthorLink';
import ScoreBadge from './ScoreBadge';

interface BranchCardProps {
  story: StoryPart;
  onClick: () => void;
}

/**
 * Continuation card for "Choose your path".
 *
 * Author link sits outside the main click target so nested interactive elements
 * do not fight React Router navigation (or appear to drop the session).
 */
const BranchCard: FC<BranchCardProps> = ({ story, onClick }) => {
  const onKeyDown = (e: KeyboardEvent<HTMLDivElement>) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      onClick();
    }
  };

  return (
    <div className="rounded-lg border border-border bg-surface transition-all hover:border-l-4 hover:border-l-accent">
      <div
        role="button"
        tabIndex={0}
        onClick={onClick}
        onKeyDown={onKeyDown}
        className="cursor-pointer p-4 text-left hover:pl-3"
      >
        <h3 className="mb-1 font-medium text-text">{story.teaser}</h3>
        <p className="line-clamp-2 font-serif text-sm text-muted">{story.content}</p>
        <div className="mt-2 flex items-center gap-3 text-xs text-muted">
          <ScoreBadge score={story.vote_score} className="text-xs" />
        </div>
      </div>
      <div className="border-t border-border px-4 py-2 text-xs text-muted">
        <AuthorLink userId={story.author_id} username={story.author_username} />
      </div>
    </div>
  );
};

export default BranchCard;
