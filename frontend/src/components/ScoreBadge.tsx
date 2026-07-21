import type { FC } from 'react';

interface ScoreBadgeProps {
  score: number;
  /** Extra classes (e.g. size). */
  className?: string;
  /** Prefix before the arrow, e.g. "Rep ". */
  label?: string;
}

/**
 * Display a net score: green ▲ for non-negative, red ▼ with absolute value when negative.
 */
const ScoreBadge: FC<ScoreBadgeProps> = ({ score, className = '', label = '' }) => {
  const negative = score < 0;
  const abs = Math.abs(score);
  const color = negative ? 'text-downvote' : 'text-upvote';
  const arrow = negative ? '▼' : '▲';

  return (
    <span className={`font-medium tabular-nums ${color} ${className}`.trim()}>
      {label}
      {arrow} {abs}
    </span>
  );
};

export default ScoreBadge;
