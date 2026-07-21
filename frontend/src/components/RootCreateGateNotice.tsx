import type { FC } from 'react';
import { Link } from 'react-router-dom';
import Panel from './ui/Panel';

interface RootCreateGateNoticeProps {
  /** User reputation is below the root-creation minimum. */
  belowMinReputation: boolean;
  minReputation: number;
  openRootTrees: number;
  maxConcurrentTrees: number;
}

/** Shown on Home when the user cannot start a new root story. */
const RootCreateGateNotice: FC<RootCreateGateNoticeProps> = ({
  belowMinReputation,
  minReputation,
  openRootTrees,
  maxConcurrentTrees,
}) => (
  <Panel className="p-6">
    <p className="font-medium text-text">Cannot start a new root story yet</p>
    {belowMinReputation ? (
      <p className="mt-2 text-sm leading-relaxed text-muted">
        Root stories need at least {minReputation} reputation (Apprentice). Continue
        existing stories and earn upvotes to unlock starting your own.
      </p>
    ) : (
      <p className="mt-2 text-sm leading-relaxed text-muted">
        You already have {openRootTrees} open root
        {openRootTrees === 1 ? '' : 's'} (limit {maxConcurrentTrees}). Continue those
        threads or wait until some leave the public shelves before opening another.
      </p>
    )}
    <Link
      to="/faq"
      className="mt-4 inline-block text-sm text-accent hover:text-accent-hover"
    >
      Learn about author tiers →
    </Link>
  </Panel>
);

export default RootCreateGateNotice;
