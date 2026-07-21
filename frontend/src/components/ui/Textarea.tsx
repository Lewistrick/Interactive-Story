import type { FC, TextareaHTMLAttributes } from 'react';

interface TextareaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {}

const textareaClassName =
  'w-full px-4 py-2 bg-surface border border-border rounded-lg text-text placeholder:text-muted focus:outline-none focus:ring-2 focus:ring-accent/40 focus:border-accent resize-y';

/** Textarea following Archive Parchment design tokens. */
const Textarea: FC<TextareaProps> = ({ className = '', ...props }) => (
  <textarea className={`${textareaClassName} ${className}`} {...props} />
);

export default Textarea;
