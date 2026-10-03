import { cn } from '../../utils/classnames';

export function Toggle({ checked, onChange, label, disabled = false, className }) {
  return (
    <label className={cn('toggle-wrapper', disabled && 'toggle-disabled', className)}>
      <input
        type="checkbox"
        className="toggle-input sr-only"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
        disabled={disabled}
        role="switch"
        aria-checked={checked}
      />
      <span className={cn('toggle-track', checked && 'toggle-track-active')}>
        <span className={cn('toggle-thumb', checked && 'toggle-thumb-active')} />
      </span>
      {label && <span className="toggle-label">{label}</span>}
    </label>
  );
}
