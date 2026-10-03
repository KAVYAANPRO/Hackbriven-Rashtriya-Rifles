import { cn } from '../../utils/classnames';

export function Divider({ label, vertical = false, className }) {
  if (vertical) {
    return <div className={cn('divider-vertical', className)} />;
  }
  if (label) {
    return (
      <div className={cn('divider-labeled', className)}>
        <span className="divider-line" />
        <span className="divider-text">{label}</span>
        <span className="divider-line" />
      </div>
    );
  }
  return <hr className={cn('divider', className)} />;
}
