import type { FC, LabelHTMLAttributes, ReactNode } from 'react';

interface LabelProps extends LabelHTMLAttributes<HTMLLabelElement> {
  children: ReactNode;
}

/** Form label styled for Archive Parchment theme. */
const Label: FC<LabelProps> = ({ children, className = '', ...props }) => (
  <label
    className={`block text-sm font-medium text-text mb-2 ${className}`}
    {...props}
  >
    {children}
  </label>
);

export default Label;
