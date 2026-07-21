import type { FC } from 'react';
import type { StoryPart } from '../api/stories';

interface StoryPathSpineProps {
  ancestors: StoryPart[];
  onSelect: (storyId: string) => void;
}

/** Compact path from root to the part before the current reading panel. */
const StoryPathSpine: FC<StoryPathSpineProps> = ({ ancestors, onSelect }) => {
  if (ancestors.length === 0) {
    return null;
  }

  return (
    <nav aria-label="Story so far" className="mb-6 space-y-2">
      <h2 className="text-sm font-semibold uppercase tracking-wide text-muted mb-3">
        Story so far
      </h2>
      <ol className="m-0 list-none space-y-2 p-0">
        {ancestors.map((part, index) => (
          <li key={part.id}>
            <button
              type="button"
              onClick={() => onSelect(part.id)}
              className="w-full text-left rounded-lg border border-border bg-chrome px-4 py-3 transition-colors hover:border-accent hover:bg-accent-soft/40"
            >
              <div className="flex items-baseline justify-between gap-3">
                <span className="min-w-0 truncate font-medium text-text">
                  <span className="mr-2 text-muted tabular-nums">{index + 1}.</span>
                  {part.teaser}
                </span>
                <span className="shrink-0 text-xs font-medium text-upvote tabular-nums">
                  ▲ {part.vote_score}
                </span>
              </div>
              <p className="mt-1 text-sm text-muted">
                {part.author_username || 'Unknown'}
              </p>
            </button>
          </li>
        ))}
      </ol>
    </nav>
  );
};

export default StoryPathSpine;
