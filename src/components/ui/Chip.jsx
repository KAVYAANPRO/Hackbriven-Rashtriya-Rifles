import { cn } from '../../utils/classnames';

export function Chip({ children, onRemove, selected = false, onClick, className }) {
  return (
    <span
      className={cn('chip', selected && 'chip-selected', onClick && 'chip-clickable', className)}
      onClick={onClick}
      role={onClick ? 'button' : undefined}
      tabIndex={onClick ? 0 : undefined}
    >
      {children}
      {onRemove && (
        <button
          className="chip-remove"
          onClick={(e) => { e.stopPropagation(); onRemove(); }}
          aria-label="Remove"
        >
          ×
        </button>
      )}
    </span>
  );
}
