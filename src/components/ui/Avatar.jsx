import { cn } from '../../utils/classnames';

function getInitials(name) {
  if (!name) return '?';
  return name.split(' ').map((n) => n[0]).slice(0, 2).join('').toUpperCase();
}

export function Avatar({ src, name, size = 'md', className }) {
  const sizes = { sm: 'avatar-sm', md: 'avatar-md', lg: 'avatar-lg', xl: 'avatar-xl' };
  return (
    <span className={cn('avatar', sizes[size], className)} aria-label={name}>
      {src ? (
        <img src={src} alt={name} className="avatar-img" />
      ) : (
        <span className="avatar-initials">{getInitials(name)}</span>
      )}
    </span>
  );
}
