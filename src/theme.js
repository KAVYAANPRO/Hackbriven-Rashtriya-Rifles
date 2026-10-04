import { useCallback, useEffect, useState } from 'react';

const KEY = 'ideafeed-theme';

function readStored() {
  try { return localStorage.getItem(KEY); } catch { return null; }
}

function apply(theme) {
  document.documentElement.setAttribute('data-theme', theme);
}

// Applied once, synchronously, before paint - avoids a flash of the wrong theme on load.
apply(readStored() === 'light' ? 'light' : 'dark');

export function useTheme() {
  const [theme, setTheme] = useState(() => (readStored() === 'light' ? 'light' : 'dark'));

  useEffect(() => { apply(theme); }, [theme]);

  const toggle = useCallback(() => {
    setTheme((t) => {
      const next = t === 'light' ? 'dark' : 'light';
      try { localStorage.setItem(KEY, next); } catch { /* ignore */ }
      return next;
    });
  }, []);

  return [theme, toggle];
}
