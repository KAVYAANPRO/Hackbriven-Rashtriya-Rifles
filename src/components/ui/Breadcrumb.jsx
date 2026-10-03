import { cn } from '../../utils/classnames';

export function Breadcrumb({ items, separator = '/', className }) {
  return (
    <nav className={cn('breadcrumb', className)} aria-label="breadcrumb">
      <ol className="breadcrumb-list">
        {items.map((item, i) => {
          const isLast = i === items.length - 1;
          return (
            <li key={i} className="breadcrumb-item" aria-current={isLast ? 'page' : undefined}>
              {item.href && !isLast ? (
                <a href={item.href} className="breadcrumb-link">{item.label}</a>
              ) : (
                <span className={cn('breadcrumb-text', isLast && 'breadcrumb-current')}>
                  {item.label}
                </span>
              )}
              {!isLast && <span className="breadcrumb-sep" aria-hidden="true">{separator}</span>}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
