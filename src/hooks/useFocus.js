import { useRef, useCallback } from 'react';

export function useFocus() {
  const ref = useRef(null);
  const focus = useCallback(() => ref.current?.focus(), []);
  const blur = useCallback(() => ref.current?.blur(), []);
  return { ref, focus, blur };
}

export function useFocusTrap(containerRef) {
  const focusableSelectors = [
    'a[href]', 'button:not([disabled])', 'input:not([disabled])',
    'select:not([disabled])', 'textarea:not([disabled])', '[tabindex]:not([tabindex="-1"])',
  ].join(', ');

  const trap = useCallback((e) => {
    if (e.key !== 'Tab' || !containerRef.current) return;
    const focusable = [...containerRef.current.querySelectorAll(focusableSelectors)];
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (e.shiftKey ? document.activeElement === first : document.activeElement === last) {
      e.preventDefault();
      (e.shiftKey ? last : first)?.focus();
    }
  }, [containerRef]);

  return trap;
}
