import type { FC } from 'react';
import type { StoryPart } from '../api/stories';
import ScoreBadge from './ScoreBadge';

interface StoryPathSpineProps {
  ancestors: StoryPart[];
  onSelect: (storyId: string) => void;
}

/** Path from root to the part before the current reading panel, with full text. */
const StoryPathSpine: FC<StoryPathSpineProps> = ({ ancestors, onSelect }) => {
  if (ancestors.length === 0) {
    return null;
  }

  return (
    <nav aria-label="Story so far" className="mb-6">
      <h2 className="mb-3 text-sm font-semibold tracking-wide text-muted uppercase">
        Story so far
      </h2>
      <ol className="m-0 list-none space-y-3 p-0">
        {ancestors.map((part, index) => (
          <li key={part.id}>
            <button
              type="button"
              onClick={() => onSelect(part.id)}
              className="w-full rounded-lg border border-border bg-chrome px-5 py-4 text-left transition-colors hover:border-accent hover:bg-accent-soft/40"
            >
              <div className="flex items-baseline justify-between gap-3">
                <h3 className="min-w-0 font-semibold text-text">
                  <span className="mr-2 text-muted tabular-nums">{index + 1}.</span>
                  {part.teaser}
                </h3>
                <ScoreBadge score={part.vote_score} className="shrink-0 text-xs" />
              </div>
              <p className="mt-1 text-sm text-muted">
                {part.author_username || 'Unknown'}
              </p>
              <p className="mt-3 font-serif text-base leading-relaxed whitespace-pre-wrap text-text">
                {part.content}
              </p>
            </button>
          </li>
        ))}
      </ol>
    </nav>
  );
};

export default StoryPathSpine;
