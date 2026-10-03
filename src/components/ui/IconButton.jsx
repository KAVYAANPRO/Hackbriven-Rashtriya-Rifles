import { cn } from '../../utils/classnames';

export function IconButton({ icon, onClick, label, variant = 'ghost', size = 'md', disabled, className }) {
  const sizes = { sm: 'icon-btn-sm', md: 'icon-btn-md', lg: 'icon-btn-lg' };
  return (
    <button
      type="button"
      className={cn('icon-btn', `icon-btn-${variant}`, sizes[size], className)}
      onClick={onClick}
      disabled={disabled}
      aria-label={label}
      title={label}
    >
      {icon}
    </button>
  );
}
