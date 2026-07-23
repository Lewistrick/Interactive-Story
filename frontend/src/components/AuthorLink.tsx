import type { FC, MouseEvent } from 'react';
import { Link } from 'react-router-dom';

interface AuthorLinkProps {
  userId: string | null | undefined;
  username: string | null | undefined;
  className?: string;
}

/** Link to a public user profile; falls back to plain text when id is missing. */
const AuthorLink: FC<AuthorLinkProps> = ({ userId, username, className }) => {
  const label = username || 'Unknown';
  if (!userId) {
    return <span className={className}>{label}</span>;
  }
  const handleClick = (e: MouseEvent) => {
    e.stopPropagation();
  };
  return (
    <Link
      to={`/users/${userId}`}
      onClick={handleClick}
      className={className ?? 'text-accent hover:text-accent-hover'}
    >
      {label}
    </Link>
  );
};

export default AuthorLink;
