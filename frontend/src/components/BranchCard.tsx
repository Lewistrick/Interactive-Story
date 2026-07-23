import type { FC } from 'react';
import type { StoryPart } from '../api/stories';
import AuthorLink from './AuthorLink';
import ScoreBadge from './ScoreBadge';

interface BranchCardProps {
  story: StoryPart;
  onClick: () => void;
}

/** Continuation card for "Choose your path" section. */
const BranchCard: FC<BranchCardProps> = ({ story, onClick }) => (
  <button
    type="button"
    onClick={onClick}
    className="text-left p-4 bg-surface border border-border rounded-lg hover:border-l-4 hover:border-l-accent hover:pl-3 transition-all"
  >
    <h3 className="font-medium text-text mb-1">{story.teaser}</h3>
    <p className="text-sm text-muted line-clamp-2 font-serif">{story.content}</p>
    <div className="flex items-center gap-3 mt-2 text-xs text-muted">
      <AuthorLink userId={story.author_id} username={story.author_username} />
      <ScoreBadge score={story.vote_score} className="text-xs" />
    </div>
  </button>
);

export default BranchCard;
