import type { ButtonHTMLAttributes, FC, ReactNode } from 'react';

type ButtonVariant = 'primary' | 'secondary' | 'ghost';

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  children: ReactNode;
}

const variantClasses: Record<ButtonVariant, string> = {
  primary:
    'bg-accent text-surface hover:bg-accent-hover font-semibold',
  secondary:
    'bg-chrome text-text border border-border hover:bg-page font-medium',
  ghost: 'text-muted hover:text-text bg-transparent',
};

/** Styled button following Archive Parchment design tokens. */
const Button: FC<ButtonProps> = ({
  variant = 'primary',
  className = '',
  children,
  ...props
}) => (
  <button
    type="button"
    className={`px-4 py-2 rounded-lg transition-colors disabled:opacity-50 ${variantClasses[variant]} ${className}`}
    {...props}
  >
    {children}
  </button>
);

export default Button;
