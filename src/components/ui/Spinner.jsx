import { cn } from '../../utils/classnames';

const sizes = {
  sm: 'spinner-sm',
  md: 'spinner-md',
  lg: 'spinner-lg',
};

export function Spinner({ size = 'md', className }) {
  return (
    <span
      className={cn('spinner', sizes[size], className)}
      role="status"
      aria-label="Loading"
    />
  );
}

export function FullPageSpinner({ message = 'Loading…' }) {
  return (
    <div className="full-page-spinner">
      <Spinner size="lg" />
      {message && <p className="spinner-message">{message}</p>}
    </div>
  );
}
