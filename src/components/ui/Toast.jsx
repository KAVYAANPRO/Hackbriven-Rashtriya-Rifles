import { useEffect } from 'react';
import { cn } from '../../utils/classnames';

const icons = {
  success: '✓',
  error: '✕',
  warning: '⚠',
  info: 'ℹ',
};

export function Toast({ id, message, type = 'info', onDismiss }) {
  return (
    <div className={cn('toast', `toast-${type}`)}>
      <span className="toast-icon" aria-hidden="true">{icons[type]}</span>
      <span className="toast-message">{message}</span>
      <button className="toast-close" onClick={() => onDismiss(id)} aria-label="Dismiss">✕</button>
    </div>
  );
}

export function ToastContainer({ notifications, onDismiss }) {
  if (!notifications?.length) return null;
  return (
    <div className="toast-container" aria-live="polite">
      {notifications.map((n) => (
        <Toast key={n.id} {...n} onDismiss={onDismiss} />
      ))}
    </div>
  );
}
