import { useScrollTop } from '../../hooks/useScrollTop';
import { cn } from '../../utils/classnames';

export function ScrollToTop({ className }) {
  const { scrolled, scrollToTop } = useScrollTop();

  if (!scrolled) return null;

  return (
    <button
      className={cn('scroll-to-top', className)}
      onClick={scrollToTop}
      aria-label="Scroll to top"
    >
      ↑
    </button>
  );
}
