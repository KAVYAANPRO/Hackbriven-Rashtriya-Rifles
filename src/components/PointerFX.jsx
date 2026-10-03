import { useEffect, useRef } from 'react';

// Cards, tiles and tabs that light up along their border where the pointer is.
export const GLOW_SELECTOR = [
  '.spot-card', '.cx-tier', '.cx-style', '.job-card', '.pack2', '.pack3', '.pl-card',
  '.st-nav-item', '.seg2 > button', '.chip2', '.pnode', '.dl-item', '.cx-drop', '.cx-thumb',
].join(',');

// Things the custom cursor treats as clickable (ring grows, dot shrinks).
const INTERACTIVE = 'a[href], button, [role="button"], [role="radio"], [role="tab"], [role="menuitem"], select, summary, label[for], input[type="checkbox"], input[type="radio"], video';
// Places where a text caret is more useful than any custom cursor.
const TEXT_FIELD = 'input:not([type="checkbox"]):not([type="radio"]):not([type="range"]):not([type="button"]):not([type="submit"]), textarea, [contenteditable="true"]';
const DISABLED = ':disabled, [aria-disabled="true"]';

const finePointer = () => typeof window !== 'undefined' && window.matchMedia && window.matchMedia('(hover: hover) and (pointer: fine)').matches;
const reducedMotion = () => typeof window !== 'undefined' && window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

// One pointer listener and one animation frame drive both effects:
//  * a minimal custom cursor (dot + trailing ring) on mouse/trackpad devices only;
//  * a border glow on whichever card/tab is under the pointer, positioned at the pointer.
export default function PointerFX() {
  const dotRef = useRef(null);
  const ringRef = useRef(null);

  useEffect(() => {
    const cursorOn = finePointer();
    const snap = reducedMotion();
    const root = document.documentElement;
    if (cursorOn) root.classList.add('fx-cursor-on');

    let x = -100, y = -100;          // pointer
    let rx = -100, ry = -100;        // ring (eases toward the pointer)
    let raf = 0;
    let glowEl = null;
    let lastTarget = null;
    let visible = false;

    const setGlow = (el) => {
      if (el === glowEl) return;
      if (glowEl) glowEl.classList.remove('is-glow');
      glowEl = el;
      if (glowEl) glowEl.classList.add('is-glow');
    };

    const frame = () => {
      raf = 0;
      // Glow: keep the light under the pointer, in the element's own coordinates.
      if (glowEl) {
        const r = glowEl.getBoundingClientRect();
        glowEl.style.setProperty('--gx', `${x - r.left}px`);
        glowEl.style.setProperty('--gy', `${y - r.top}px`);
      }
      if (!cursorOn) return;
      const k = snap ? 1 : 0.22;
      rx += (x - rx) * k;
      ry += (y - ry) * k;
      if (dotRef.current) dotRef.current.style.transform = `translate3d(${x}px, ${y}px, 0)`;
      if (ringRef.current) ringRef.current.style.transform = `translate3d(${rx}px, ${ry}px, 0)`;
      // Keep easing until the ring has caught up with the pointer.
      if (Math.abs(x - rx) > 0.3 || Math.abs(y - ry) > 0.3) raf = requestAnimationFrame(frame);
    };
    const kick = () => { if (!raf) raf = requestAnimationFrame(frame); };

    const onMove = (e) => {
      if (e.pointerType && e.pointerType !== 'mouse' && e.pointerType !== 'pen') return;
      x = e.clientX;
      y = e.clientY;
      const t = e.target instanceof Element ? e.target : null;
      if (t !== lastTarget) {
        lastTarget = t;
        const card = t && t.closest(GLOW_SELECTOR);
        setGlow(card && !card.matches(DISABLED) ? card : null);
        if (cursorOn) {
          const field = !!(t && t.closest(TEXT_FIELD));
          const clickable = t && t.closest(INTERACTIVE);
          root.classList.toggle('fx-cursor-text', field);
          root.classList.toggle('fx-cursor-hover', !!clickable && !clickable.matches(DISABLED) && !field);
          root.classList.toggle('fx-cursor-blocked', !!clickable && clickable.matches(DISABLED));
        }
      }
      if (cursorOn && !visible) {
        visible = true;
        rx = x; ry = y; // first appearance: start the ring on the pointer instead of flying in
        root.classList.add('fx-cursor-visible');
      }
      kick();
    };
    const onLeave = () => {
      visible = false;
      lastTarget = null;
      root.classList.remove('fx-cursor-visible');
      setGlow(null);
    };
    const onDown = () => root.classList.add('fx-cursor-down');
    const onUp = () => root.classList.remove('fx-cursor-down');
    const onScroll = () => { lastTarget = null; kick(); };

    window.addEventListener('pointermove', onMove, { passive: true });
    window.addEventListener('pointerdown', onDown, { passive: true });
    window.addEventListener('pointerup', onUp, { passive: true });
    window.addEventListener('scroll', onScroll, { passive: true, capture: true });
    document.addEventListener('mouseleave', onLeave);
    window.addEventListener('blur', onLeave);

    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener('pointermove', onMove);
      window.removeEventListener('pointerdown', onDown);
      window.removeEventListener('pointerup', onUp);
      window.removeEventListener('scroll', onScroll, { capture: true });
      document.removeEventListener('mouseleave', onLeave);
      window.removeEventListener('blur', onLeave);
      setGlow(null);
      root.classList.remove('fx-cursor-on', 'fx-cursor-visible', 'fx-cursor-hover', 'fx-cursor-text', 'fx-cursor-blocked', 'fx-cursor-down');
    };
  }, []);

  return (
    <div className="fx-cursor" aria-hidden="true">
      <i className="fx-ring" ref={ringRef} />
      <i className="fx-dot" ref={dotRef} />
    </div>
  );
}
