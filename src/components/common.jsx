import { LABEL, isRun } from '../data.js';
import Icon from './Icon.jsx';

export function Pill({ status, large }) {
  const key = isRun(status) && status !== 'queued' ? 'running' : status;
  const live = key === 'running' || status === 'publishing' || status === 'queued';
  return (
    <span className={'pill' + (large ? ' pill--lg' : '')} data-s={key}>
      <i className={live ? 'live' : ''} />
      {LABEL[status] || status}
    </span>
  );
}

// Segmented control with a thumb that slides to the selected option.
export function Seg({ options, value, onChange, label, size }) {
  const idx = Math.max(0, options.findIndex((o) => o.v === value));
  return (
    <div className={'seg2' + (size ? ' seg2--' + size : '')} role="radiogroup" aria-label={label} style={{ '--n': options.length, '--i': idx }}>
      <i className="seg2-thumb" />
      {options.map((o) => (
        <button
          key={o.v}
          type="button"
          role="radio"
          aria-checked={o.v === value}
          className={o.v === value ? 'is-on' : ''}
          disabled={!!o.disabled}
          onClick={() => onChange(o.v)}
        >
          {o.label}
          {o.sub && <small>{o.sub}</small>}
          {o.note && <small className="seg2-note">{o.note}</small>}
        </button>
      ))}
    </div>
  );
}

export function Chips({ options, value, onChange }) {
  return options.map((o) => (
    <button key={o.v} type="button" className={'chip2' + (o.v === value ? ' is-on' : '')} onClick={() => onChange(o.v)}>
      {o.label}
    </button>
  ));
}

export function PageHeader({ title, sub, children }) {
  return (
    <header className="ph">
      <div className="ph-copy">
        <h1 className="ph-title">{title}</h1>
        {sub && <p className="ph-sub">{sub}</p>}
      </div>
      {children && <div className="ph-actions">{children}</div>}
    </header>
  );
}

// Visible failure state with a Retry action. Never leave a panel blank on a failed fetch.
export function ErrorState({ title = 'Something went wrong', message, onRetry, retryLabel = 'Retry', children, compact }) {
  return (
    <section className={'empty2 err2' + (compact ? ' err2--compact' : '')} role="alert">
      <span className="empty2-ic err2-ic"><Icon name="alert" size={compact ? 18 : 24} /></span>
      <h3>{title}</h3>
      {message && <p>{message}</p>}
      <div className="err2-actions">
        {onRetry && <button type="button" className="btn2 btn2--primary" onClick={onRetry}><Icon name="refresh" size={16} />{retryLabel}</button>}
        {children}
      </div>
    </section>
  );
}

// Shimmering placeholder block.
export function Skeleton({ h = 16, w = '100%', r = 6, style }) {
  return <i className="sk2" aria-hidden="true" style={{ height: h, width: w, borderRadius: r, ...style }} />;
}
