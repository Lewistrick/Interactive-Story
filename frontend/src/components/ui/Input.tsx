import type { FC, InputHTMLAttributes } from 'react';

type InputProps = InputHTMLAttributes<HTMLInputElement>;

const inputClassName =
  'w-full px-4 py-2 bg-surface border border-border rounded-lg text-text placeholder:text-muted focus:outline-none focus:ring-2 focus:ring-accent/40 focus:border-accent';

/** Text input following Archive Parchment design tokens. */
const Input: FC<InputProps> = ({ className = '', ...props }) => (
  <input className={`${inputClassName} ${className}`} {...props} />
);

export default Input;
