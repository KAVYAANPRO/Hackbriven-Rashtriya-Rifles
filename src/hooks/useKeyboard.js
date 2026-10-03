import { useEffect, useCallback } from 'react';

export function useKeyboard(keyMap) {
  const handleKeyDown = useCallback((event) => {
    const key = event.key;
    const ctrl = event.ctrlKey || event.metaKey;
    const shift = event.shiftKey;
    const alt = event.altKey;

    for (const [combo, handler] of Object.entries(keyMap)) {
      const parts = combo.toLowerCase().split('+');
      const expectedKey = parts[parts.length - 1];
      const expectedCtrl = parts.includes('ctrl') || parts.includes('cmd');
      const expectedShift = parts.includes('shift');
      const expectedAlt = parts.includes('alt');

      if (
        key.toLowerCase() === expectedKey &&
        ctrl === expectedCtrl &&
        shift === expectedShift &&
        alt === expectedAlt
      ) {
        event.preventDefault();
        handler(event);
        break;
      }
    }
  }, [keyMap]);

  useEffect(() => {
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [handleKeyDown]);
}
