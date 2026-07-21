import type { FC } from 'react';
import { Link } from 'react-router-dom';
import Panel from './ui/Panel';

interface DailyLimitNoticeProps {
  dailyPartLimit: number;
  /** Optional extra line (e.g. "You can still read and browse."). */
  hint?: string;
}

/** Shown instead of create forms when the user has used today's posting quota. */
const DailyLimitNotice: FC<DailyLimitNoticeProps> = ({
  dailyPartLimit,
  hint = 'You can still read stories and explore branches.',
}) => (
  <Panel className="p-6">
    <p className="text-text font-medium">Daily writing limit reached</p>
    <p className="mt-2 text-sm text-muted leading-relaxed">
      Your tier allows {dailyPartLimit} part{dailyPartLimit === 1 ? '' : 's'} per day.
      Come back tomorrow to write again — or grow your reputation to unlock a higher
      daily allowance.
    </p>
    <p className="mt-2 text-sm text-muted">{hint}</p>
    <Link
      to="/faq"
      className="inline-block mt-4 text-sm text-accent hover:text-accent-hover"
    >
      Learn about author tiers →
    </Link>
  </Panel>
);

export default DailyLimitNotice;
