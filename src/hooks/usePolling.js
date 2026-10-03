import { useEffect, useRef, useCallback } from 'react';

export function usePolling(fn, interval = 5000, enabled = true) {
  const timerRef = useRef(null);
  const fnRef = useRef(fn);

  fnRef.current = fn;

  const stop = useCallback(() => {
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  const start = useCallback(() => {
    stop();
    timerRef.current = setInterval(() => fnRef.current(), interval);
  }, [interval, stop]);

  useEffect(() => {
    if (!enabled) return stop();
    start();
    return stop;
  }, [enabled, start, stop]);

  return { start, stop };
}
