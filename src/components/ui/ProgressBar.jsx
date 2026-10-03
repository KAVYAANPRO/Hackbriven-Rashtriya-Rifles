import { cn } from '../../utils/classnames';

export function ProgressBar({ value = 0, max = 100, label, color = 'primary', className }) {
  const pct = Math.round(Math.min(Math.max((value / max) * 100, 0), 100));

  return (
    <div className={cn('progress-wrapper', className)}>
      {label && <span className="progress-label">{label}</span>}
      <div
        className="progress-track"
        role="progressbar"
        aria-valuenow={value}
        aria-valuemin={0}
        aria-valuemax={max}
        aria-label={label}
      >
        <div
          className={cn('progress-fill', `progress-fill-${color}`)}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="progress-value">{pct}%</span>
    </div>
  );
}
