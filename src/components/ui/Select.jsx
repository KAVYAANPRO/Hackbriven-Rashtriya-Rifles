import { cn } from '../../utils/classnames';

export function Select({ label, options = [], error, hint, className, id, ...props }) {
  const selectId = id || label?.toLowerCase().replace(/\s+/g, '-');
  return (
    <div className="input-field">
      {label && <label htmlFor={selectId} className="input-label">{label}</label>}
      <select
        id={selectId}
        className={cn('input select', error && 'input-error', className)}
        aria-invalid={Boolean(error)}
        {...props}
      >
        {options.map((opt) => (
          <option key={opt.value} value={opt.value} disabled={opt.disabled}>
            {opt.label}
          </option>
        ))}
      </select>
      {error && <span className="input-error-text" role="alert">{error}</span>}
      {hint && !error && <span className="input-hint">{hint}</span>}
    </div>
  );
}
