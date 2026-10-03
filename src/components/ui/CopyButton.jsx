import { useClipboard } from '../../hooks/useClipboard';
import { cn } from '../../utils/classnames';

export function CopyButton({ text, label = 'Copy', className }) {
  const { copy, copied } = useClipboard();
  return (
    <button
      type="button"
      className={cn('copy-btn', copied && 'copy-btn-done', className)}
      onClick={() => copy(text)}
      aria-label={copied ? 'Copied!' : label}
    >
      {copied ? '✓ Copied' : label}
    </button>
  );
}
