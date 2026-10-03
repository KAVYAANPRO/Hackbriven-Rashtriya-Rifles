import { cn } from '../../utils/classnames';

export function Card({ children, className, onClick, hoverable = false }) {
  return (
    <div
      className={cn('card', hoverable && 'card-hoverable', onClick && 'card-clickable', className)}
      onClick={onClick}
      role={onClick ? 'button' : undefined}
      tabIndex={onClick ? 0 : undefined}
    >
      {children}
    </div>
  );
}

export function CardHeader({ children, className }) {
  return <div className={cn('card-header', className)}>{children}</div>;
}

export function CardBody({ children, className }) {
  return <div className={cn('card-body', className)}>{children}</div>;
}

export function CardFooter({ children, className }) {
  return <div className={cn('card-footer', className)}>{children}</div>;
}
