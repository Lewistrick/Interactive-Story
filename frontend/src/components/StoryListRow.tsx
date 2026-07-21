import type { FC } from 'react';
import type { StoryList } from '../api/stories';
import ScoreBadge from './ScoreBadge';

interface StoryListRowProps {
  story: StoryList;
  onClick: () => void;
}

/** Dense list row for the Home Discover page (Wireframe C). */
const StoryListRow: FC<StoryListRowProps> = ({ story, onClick }) => (
  <button
    type="button"
    onClick={onClick}
    className="w-full text-left px-4 py-3 bg-surface border-b border-border last:border-b-0 hover:bg-chrome/60 transition-colors flex items-center justify-between gap-4"
  >
    <div className="min-w-0">
      <div className="font-medium text-text truncate">{story.teaser}</div>
      <div className="text-sm text-muted mt-0.5">
        {story.author_username || 'Unknown'} · {story.children_count} branches
      </div>
    </div>
    <ScoreBadge score={story.vote_score} className="shrink-0 text-sm font-semibold" />
  </button>
);

export default StoryListRow;
