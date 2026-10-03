import { cn } from '../../utils/classnames';

const types = {
  default: 'badge-default',
  success: 'badge-success',
  warning: 'badge-warning',
  error: 'badge-error',
  info: 'badge-info',
  purple: 'badge-purple',
};

export function Badge({ children, type = 'default', className }) {
  return (
    <span className={cn('badge', types[type], className)}>
      {children}
    </span>
  );
}
