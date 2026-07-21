import type { FC, ReactNode } from 'react';

interface PanelProps {
  children: ReactNode;
  className?: string;
}

/** Flat bordered surface panel — no shadows. */
const Panel: FC<PanelProps> = ({ children, className = '' }) => (
  <div className={`bg-surface border border-border rounded-lg ${className}`}>
    {children}
  </div>
);

export default Panel;
