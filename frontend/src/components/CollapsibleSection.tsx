import type { FC, ReactNode } from 'react';

interface CollapsibleSectionProps {
  /** Section title shown in the header button. */
  title: string;
  /** Optional count badge (e.g. authored parts). */
  count?: number;
  /** Extra muted meta next to the title (e.g. vote up/down totals). */
  meta?: ReactNode;
  /** Whether the section body is visible. */
  open: boolean;
  /** Toggle open/closed. */
  onToggle: () => void;
  /** Optional controls rendered while open (sort, filters). */
  toolbar?: ReactNode;
  children: ReactNode;
}

/**
 * Expandable section for long moderator lists (Wireframe C).
 *
 * Keeps overview by collapsing body content while leaving title + count visible.
 */
const CollapsibleSection: FC<CollapsibleSectionProps> = ({
  title,
  count,
  meta,
  open,
  onToggle,
  toolbar,
  children,
}) => (
  <section className="rounded-lg border border-border bg-surface">
    <button
      type="button"
      onClick={onToggle}
      className="flex w-full items-center justify-between gap-3 px-4 py-3 text-left hover:bg-chrome/60 transition-colors rounded-lg"
      aria-expanded={open}
    >
      <span className="flex min-w-0 flex-wrap items-baseline gap-x-3 gap-y-1">
        <span className="font-semibold text-text">
          <span className="mr-2 inline-block w-4 text-muted" aria-hidden>
            {open ? '▼' : '▶'}
          </span>
          {title}
          {typeof count === 'number' ? (
            <span className="ml-2 font-normal text-muted tabular-nums">({count})</span>
          ) : null}
        </span>
        {meta ? <span className="text-sm text-muted">{meta}</span> : null}
      </span>
      <span className="shrink-0 text-xs text-muted">{open ? 'Hide' : 'Show'}</span>
    </button>
    {open ? (
      <div className="border-t border-border">
        {toolbar ? (
          <div className="flex flex-wrap items-center gap-3 border-b border-border bg-chrome/40 px-4 py-2">
            {toolbar}
          </div>
        ) : null}
        {children}
      </div>
    ) : null}
  </section>
);

export default CollapsibleSection;
