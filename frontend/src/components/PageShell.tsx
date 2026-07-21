import type { FC, ReactNode } from 'react';
import Header from './Header';
import UserWarningBanner from './UserWarningBanner';

interface PageShellProps {
  children: ReactNode;
  headerAction?: ReactNode;
}

/** Page layout with Archive Parchment chrome header. */
const PageShell: FC<PageShellProps> = ({ children, headerAction }) => (
  <div className="min-h-screen bg-page">
    <Header action={headerAction} />
    <UserWarningBanner />
    {children}
  </div>
);

export default PageShell;
