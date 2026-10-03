import { cn } from '../../utils/classnames';

export function Skeleton({ width, height, rounded = false, className }) {
  return (
    <span
      className={cn('skeleton', rounded && 'skeleton-rounded', className)}
      style={{ width, height }}
      aria-hidden="true"
    />
  );
}

export function SkeletonText({ lines = 3, className }) {
  return (
    <div className={cn('skeleton-text', className)}>
      {Array.from({ length: lines }).map((_, i) => (
        <Skeleton
          key={i}
          height="1em"
          width={i === lines - 1 ? '70%' : '100%'}
          className="skeleton-line"
        />
      ))}
    </div>
  );
}
