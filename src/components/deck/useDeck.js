import { useCallback, useEffect, useRef, useState } from 'react';

const LOCK_MS = 750; // matches the slide transition, so one gesture = one slide

// Full-screen deck with no page scroll: wheel, touch, keys and dots each jump straight to the
// next slide. `progress` is a smoothed float that eases toward the active index and is
// published as --p so parallax and the globe move continuously during a change.
export function useDeck(count) {
  const [active, setActive] = useState(0);
  const activeRef = useRef(0);
  const progress = useRef(0);
  const wrapRef = useRef(null);
  const lockUntil = useRef(0);

  const goTo = useCallback((i) => {
    const next = Math.max(0, Math.min(count - 1, i));
    const now = performance.now();
    if (next === activeRef.current || now < lockUntil.current) return;
    activeRef.current = next;
    lockUntil.current = now + LOCK_MS;
    setActive(next);
  }, [count]);

  const step = useCallback((d) => goTo(activeRef.current + d), [goTo]);

  useEffect(() => {
    const root = document.documentElement;
    root.classList.add('deck-lock');

    // ---- input ----
    let lastT = 0;
    let lastD = 0;
    const onWheel = (e) => {
      e.preventDefault();
      const d = e.deltaY || e.deltaX;
      const now = performance.now();
      const fresh = now - lastT > 120 || Math.abs(d) > Math.abs(lastD) * 1.3; // ignore trackpad inertia tails
      lastT = now;
      lastD = d;
      if (fresh && Math.abs(d) > 6) step(d > 0 ? 1 : -1);
    };
    const onKey = (e) => {
      if (/^(INPUT|TEXTAREA|SELECT)$/.test(e.target.tagName)) return;
      const k = e.key;
      if (k === 'ArrowDown' || k === 'PageDown' || (k === ' ' && !e.shiftKey)) step(1);
      else if (k === 'ArrowUp' || k === 'PageUp' || (k === ' ' && e.shiftKey)) step(-1);
      else if (k === 'Home') goTo(0);
      else if (k === 'End') goTo(count - 1);
      else return;
      e.preventDefault();
    };
    let y0 = null;
    const onTouchStart = (e) => { y0 = e.touches[0].clientY; };
    const onTouchMove = (e) => { e.preventDefault(); };
    const onTouchEnd = (e) => {
      if (y0 == null) return;
      const dy = y0 - e.changedTouches[0].clientY;
      y0 = null;
      if (Math.abs(dy) > 40) step(dy > 0 ? 1 : -1);
    };
    window.addEventListener('wheel', onWheel, { passive: false });
    window.addEventListener('keydown', onKey);
    window.addEventListener('touchstart', onTouchStart, { passive: true });
    window.addEventListener('touchmove', onTouchMove, { passive: false });
    window.addEventListener('touchend', onTouchEnd, { passive: true });

    // ---- smoothed progress ----
    let raf = 0;
    const tick = () => {
      const target = activeRef.current;
      const diff = target - progress.current;
      progress.current = Math.abs(diff) < 0.002 ? target : progress.current + diff * 0.11;
      wrapRef.current?.style.setProperty('--p', progress.current.toFixed(4));
      raf = Math.abs(target - progress.current) > 0 ? requestAnimationFrame(tick) : 0;
    };
    const kick = () => { if (!raf) raf = requestAnimationFrame(tick); };
    const poll = setInterval(kick, 100); // cheap: only starts a frame loop when the target moved

    return () => {
      root.classList.remove('deck-lock');
      window.removeEventListener('wheel', onWheel);
      window.removeEventListener('keydown', onKey);
      window.removeEventListener('touchstart', onTouchStart);
      window.removeEventListener('touchmove', onTouchMove);
      window.removeEventListener('touchend', onTouchEnd);
      clearInterval(poll);
      cancelAnimationFrame(raf);
    };
  }, [count, step, goTo]);

  return { active, progress, wrapRef, goTo };
}
