import type { FC, KeyboardEvent } from 'react';
import type { StoryList } from '../api/stories';
import AuthorLink from './AuthorLink';
import ScoreBadge from './ScoreBadge';

interface StoryListRowProps {
  story: StoryList;
  onClick: () => void;
}

/** Dense list row for the Home Discover page (Wireframe C). */
const StoryListRow: FC<StoryListRowProps> = ({ story, onClick }) => {
  const onKeyDown = (e: KeyboardEvent<HTMLDivElement>) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      onClick();
    }
  };

  return (
    <div className="flex items-center justify-between gap-4 border-b border-border bg-surface px-4 py-3 last:border-b-0 hover:bg-chrome/60">
      <div
        role="button"
        tabIndex={0}
        onClick={onClick}
        onKeyDown={onKeyDown}
        className="min-w-0 flex-1 cursor-pointer text-left"
      >
        <div className="truncate font-medium text-text">{story.teaser}</div>
        <div className="mt-0.5 text-sm text-muted">
          <AuthorLink userId={story.author_id} username={story.author_username} /> ·{' '}
          {story.children_count} branches
        </div>
      </div>
      <ScoreBadge score={story.vote_score} className="shrink-0 text-sm font-semibold" />
    </div>
  );
};

export default StoryListRow;
