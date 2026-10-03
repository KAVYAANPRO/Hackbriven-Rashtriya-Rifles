import { Fragment, useEffect, useLayoutEffect, useRef, useState } from 'react';

// Splits text into words that blur/slide in, staggered, once the slide is active.
export function Words({ text, start = 0 }) {
  return text.split(' ').map((w, i) => (
    <Fragment key={i}>
      <span className="w"><span style={{ '--i': i + start }}>{w}</span></span>{' '}
    </Fragment>
  ));
}

// Counts from 0 to `to` while `on` is true; resets when it turns off.
export function CountUp({ to, on = true, duration = 800, whenVisible = false }) {
  const ref = useRef(null);
  const [v, setV] = useState(0);
  const [seen, setSeen] = useState(!whenVisible);

  useEffect(() => {
    if (!whenVisible) return undefined;
    const io = new IntersectionObserver(([e]) => {
      if (e.isIntersecting) { setSeen(true); io.disconnect(); }
    }, { threshold: 0.4 });
    io.observe(ref.current);
    return () => io.disconnect();
  }, [whenVisible]);

  const go = on && seen;
  useEffect(() => {
    if (!go) { setV(0); return undefined; }
    let raf;
    const t0 = performance.now();
    const step = (t) => {
      const k = Math.min(1, (t - t0 - 220) / duration);
      const e = 1 - Math.pow(1 - Math.max(0, k), 3);
      setV(Math.round(to * e));
      if (k < 1) raf = requestAnimationFrame(step);
    };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [go, to, duration]);
  return <span ref={ref}>{v}</span>;
}

const CURVE = 'M0 196 C 90 188, 120 128, 215 126 S 330 120 385 78 S 470 18 520 12';
const AREA = CURVE + ' L520 220 L0 220 Z';
// Callout positions along the curve, spread from low (cheapest tier) to high (dearest tier).
const pointAt = (i, n) => (n <= 1 ? 0.98 : 0.4 + (0.58 * i) / (n - 1));

// Credits-by-tier curve: draws itself in, then the callouts fade up.
// `tiers` = [{ v, label, cost }] cheapest first, from GET /plans; cost is null while pricing loads.
export function TierChart({ on, tiers = [] }) {
  const path = useRef(null);
  const [len, setLen] = useState(900);
  const [pts, setPts] = useState([]);
  const n = tiers.length;

  useLayoutEffect(() => {
    const p = path.current;
    const L = p.getTotalLength();
    setLen(L);
    setPts(Array.from({ length: n }, (_, i) => {
      const { x, y } = p.getPointAtLength(L * pointAt(i, n));
      return { x, y };
    }));
  }, [n]);

  return (
    <div className={'chart' + (on ? ' is-on' : '')}>
      <svg viewBox="0 0 520 220" preserveAspectRatio="none" aria-hidden="true">
        <defs>
          <linearGradient id="curve-g" x1="0" x2="1">
            <stop offset="0" stopColor="#005066" />
            <stop offset="0.55" stopColor="#7fd1a8" />
            <stop offset="1" stopColor="#b4e768" />
          </linearGradient>
          <linearGradient id="area-g" x1="0" x2="0" y1="0" y2="1">
            <stop offset="0" stopColor="#005066" stopOpacity="0.55" />
            <stop offset="1" stopColor="#005066" stopOpacity="0" />
          </linearGradient>
        </defs>
        <path className="chart-area" d={AREA} fill="url(#area-g)" />
        <path
          ref={path}
          className="chart-line"
          d={CURVE}
          fill="none"
          stroke="url(#curve-g)"
          strokeWidth="2.2"
          vectorEffect="non-scaling-stroke"
          style={{ strokeDasharray: len, strokeDashoffset: on ? 0 : len }}
        />
      </svg>
      {pts.map((q, i) => {
        const t = tiers[i];
        if (!t) return null;
        const quiet = n > 2 && i > 0 && i < n - 1;
        return (
          <div
            key={t.v}
            className={'callout' + (quiet ? ' callout--quiet' : '')}
            style={{ left: `${(q.x / 520) * 100}%`, top: `${(q.y / 220) * 100}%`, '--k': i }}
          >
            <div className="callout-top">
              <b>{t.cost == null ? <span className="callout-wait">–</span> : <CountUp to={t.cost} on={on} duration={700} />}</b>
              <span>credits</span>
              <i />
            </div>
            <em className="callout-dot" />
            <span className="callout-name">{t.label}</span>
          </div>
        );
      })}
    </div>
  );
}
