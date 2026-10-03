import { useEffect, useRef } from 'react';

// Rough continent outlines as [lon, lat]. Dots are sampled inside them, so the map is
// generated in code rather than shipped as an image.
const LAND = [
  [[-168, 66], [-162, 70], [-140, 70], [-125, 70], [-95, 72], [-82, 68], [-80, 62], [-93, 58], [-88, 52], [-80, 52], [-78, 58], [-68, 60], [-62, 56], [-56, 52], [-66, 45], [-70, 42], [-76, 38], [-76, 35], [-81, 31], [-80, 26], [-83, 29], [-90, 30], [-97, 27], [-97, 22], [-92, 18], [-87, 21], [-88, 16], [-83, 10], [-79, 9], [-82, 8], [-86, 12], [-92, 15], [-98, 17], [-105, 20], [-106, 23], [-112, 29], [-115, 31], [-117, 33], [-121, 35], [-124, 40], [-124, 47], [-128, 51], [-135, 58], [-145, 60], [-152, 59], [-158, 57], [-165, 55], [-160, 59], [-166, 62]],
  [[-73, 78], [-60, 82], [-35, 83], [-20, 80], [-20, 70], [-30, 67], [-42, 60], [-50, 64], [-55, 70], [-68, 76]],
  [[-80, 9], [-72, 12], [-62, 10], [-52, 5], [-50, 0], [-44, -2], [-35, -6], [-39, -14], [-41, -22], [-48, -26], [-53, -34], [-58, -38], [-65, -41], [-66, -47], [-69, -52], [-72, -54], [-75, -48], [-73, -38], [-71, -30], [-70, -18], [-76, -14], [-81, -6], [-80, -1], [-78, 3]],
  [[-10, 36], [-9, 43], [-2, 44], [-4, 48], [2, 51], [8, 54], [10, 57], [12, 55], [20, 55], [22, 60], [28, 60], [30, 70], [40, 68], [60, 70], [75, 73], [100, 77], [115, 74], [140, 72], [160, 70], [180, 68], [180, 65], [170, 60], [160, 58], [155, 52], [143, 52], [140, 46], [130, 42], [127, 36], [122, 40], [121, 31], [119, 24], [110, 20], [108, 15], [106, 10], [100, 13], [100, 5], [104, 1], [98, 8], [98, 16], [92, 22], [88, 22], [80, 15], [78, 8], [73, 17], [72, 22], [66, 25], [58, 25], [56, 27], [50, 30], [48, 29], [50, 26], [56, 24], [59, 22], [52, 16], [43, 13], [39, 21], [35, 28], [34, 31], [36, 36], [30, 36], [27, 37], [26, 40], [23, 38], [18, 40], [12, 44], [16, 40], [15, 38], [12, 42], [8, 44], [3, 43], [-1, 37], [-6, 36]],
  [[-17, 21], [-10, 30], [-6, 36], [10, 37], [11, 33], [20, 31], [32, 31], [34, 28], [39, 20], [43, 12], [51, 12], [48, 5], [40, -3], [39, -10], [41, -16], [35, -24], [33, -28], [27, -34], [20, -35], [17, -30], [12, -17], [13, -9], [9, -1], [9, 4], [4, 6], [-8, 4], [-13, 8], [-17, 14]],
  [[114, -22], [122, -18], [130, -12], [137, -12], [142, -11], [146, -19], [153, -26], [150, -37], [141, -38], [135, -35], [130, -32], [116, -35], [114, -26]],
  [[95, 5], [98, 4], [106, -4], [105, -6], [100, -2]],
  [[109, 2], [117, 7], [119, 1], [116, -4], [110, -3]],
  [[105, -6], [114, -7], [114, -8.5], [106, -7.5]],
  [[119, 1], [125, 1], [122, -5], [119, -4]],
  [[131, -1], [141, -3], [150, -10], [141, -9], [135, -4]],
  [[130, 33], [135, 35], [140, 41], [142, 40], [141, 35], [137, 34]],
  [[-5, 50], [1, 51], [2, 53], [-2, 57], [-5, 58], [-6, 55], [-3, 54]],
  [[44, -25], [47, -25], [50, -15], [49, -12], [44, -17]],
  [[172, -35], [178, -38], [175, -41], [172, -41]],
  [[-24, 64], [-14, 64], [-15, 66], [-22, 66]],
  [[120, 18], [122, 18], [126, 9], [122, 7], [120, 14]],
];

const inside = (lon, lat, poly) => {
  let c = false;
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const [xi, yi] = poly[i];
    const [xj, yj] = poly[j];
    if (yi > lat !== yj > lat && lon < ((xj - xi) * (lat - yi)) / (yj - yi) + xi) c = !c;
  }
  return c;
};

// Evenly spaced sphere sample (rows narrow toward the poles), kept only where there is land.
function buildDots() {
  const dots = [];
  const d = 2.3;
  let row = 0;
  for (let lat = -78; lat <= 84; lat += d, row++) {
    const step = d / Math.max(0.2, Math.cos((lat * Math.PI) / 180));
    for (let lon = -180 + (row % 2) * step * 0.5; lon < 180; lon += step) {
      if (LAND.some((p) => inside(lon, lat, p))) {
        const la = (lat * Math.PI) / 180;
        const lo = (lon * Math.PI) / 180;
        dots.push([la, lo]);
      }
    }
  }
  return dots;
}

const DOTS = buildDots();
const STARS = Array.from({ length: 70 }, (_, i) => ({
  x: (Math.sin(i * 12.9898) * 43758.5453) % 1,
  y: (Math.sin(i * 78.233) * 12543.1234) % 1,
  r: 0.4 + ((i * 37) % 10) / 12,
  s: (i % 7) / 3,
}));
const frac = (n) => Math.abs(n - Math.floor(n));

// Pre-renders the parts that never change (stars, sphere body, rim glow) once per resize, so
// each frame only has to blit them and plot the land dots.
function makeLayer(w, h, dpr, paint) {
  const c = document.createElement('canvas');
  c.width = w * dpr; c.height = h * dpr;
  const x = c.getContext('2d');
  x.setTransform(dpr, 0, 0, dpr, 0, 0);
  paint(x);
  return c;
}

export default function Globe({ active, progress }) {
  const ref = useRef(null);

  useEffect(() => {
    const canvas = ref.current;
    const ctx = canvas.getContext('2d');
    let w = 0;
    let h = 0;
    let dpr = 1;
    let raf = 0;
    let t0 = performance.now();
    let back = null;
    let rimLayer = null;
    const buckets = [[], [], []];
    const COLORS = ['#7fcfae', '#bfe8a6', '#e6f6bd'];

    const resize = () => {
      const r = canvas.parentElement.getBoundingClientRect();
      dpr = Math.min(1.5, window.devicePixelRatio || 1);
      w = r.width; h = r.height;
      canvas.width = w * dpr; canvas.height = h * dpr;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      const R = Math.min(w * 0.557, h * 0.93);
      const cx = w / 2;
      const cy = -h * 0.11;

      back = makeLayer(w, h, dpr, (x) => {
        STARS.forEach((s) => {
          x.globalAlpha = 0.25 + 0.4 * (s.s / 2.4);
          x.fillStyle = '#e8f3c8';
          x.beginPath(); x.arc(frac(s.x) * w, frac(s.y) * h, s.r, 0, 6.283); x.fill();
        });
        x.globalAlpha = 1;
        const body = x.createRadialGradient(cx, cy, R * 0.6, cx, cy, R);
        body.addColorStop(0, 'rgba(3,12,14,0.96)');
        body.addColorStop(0.82, 'rgba(0,44,56,0.55)');
        body.addColorStop(1, 'rgba(0,90,110,0.7)');
        x.fillStyle = body;
        x.beginPath(); x.arc(cx, cy, R, 0, 6.283); x.fill();
      });

      rimLayer = makeLayer(w, h, dpr, (x) => {
        const rim = x.createLinearGradient(0, 0, w, 0);
        rim.addColorStop(0, '#2aa6a0');
        rim.addColorStop(0.5, '#b4e768');
        rim.addColorStop(1, '#2aa6a0');
        x.strokeStyle = rim;
        x.globalAlpha = 0.35; x.lineWidth = 22; x.shadowColor = '#b4e768'; x.shadowBlur = 40;
        x.beginPath(); x.arc(cx, cy, R, 0, 6.283); x.stroke();
        x.globalAlpha = 1; x.lineWidth = 3; x.shadowBlur = 18;
        x.beginPath(); x.arc(cx, cy, R, 0, 6.283); x.stroke();
      });
    };

    const draw = (now) => {
      const spin = ((now - t0) / 1000) * 8; // degrees per second
      const lon0 = ((-72 + spin + (progress.current - 4) * 14) * Math.PI) / 180;
      const tilt = (14 * Math.PI) / 180;
      const sinT = Math.sin(tilt);
      const cosT = Math.cos(tilt);
      const R = Math.min(w * 0.557, h * 0.93);
      const cx = w / 2;
      const cy = -h * 0.11;

      ctx.clearRect(0, 0, w, h);
      ctx.drawImage(back, 0, 0, w, h);

      buckets[0].length = 0; buckets[1].length = 0; buckets[2].length = 0;
      for (let i = 0; i < DOTS.length; i++) {
        const la = DOTS[i][0];
        const dl = DOTS[i][1] - lon0;
        const cl = Math.cos(la);
        const cd = Math.cos(dl);
        const z = sinT * Math.sin(la) + cosT * cl * cd;
        if (z <= 0.04) continue;
        const x = cx + R * cl * Math.sin(dl);
        const y = cy - R * (cosT * Math.sin(la) - sinT * cl * cd);
        if (y < -4 || y > h + 4 || x < -4 || x > w + 4) continue;
        buckets[z > 0.62 ? 2 : z > 0.3 ? 1 : 0].push(x, y);
      }
      const unit = Math.max(1, w / 760);
      for (let b = 0; b < 3; b++) {
        const pts = buckets[b];
        const sz = (1.1 + b * 0.55) * unit;
        ctx.globalAlpha = 0.45 + b * 0.27;
        ctx.fillStyle = COLORS[b];
        for (let i = 0; i < pts.length; i += 2) ctx.fillRect(pts[i] - sz / 2, pts[i + 1] - sz / 2, sz, sz);
      }
      ctx.globalAlpha = 1;
      ctx.drawImage(rimLayer, 0, 0, w, h);
    };

    const loop = (now) => { draw(now); raf = requestAnimationFrame(loop); };

    resize();
    draw(performance.now());
    const ro = new ResizeObserver(() => { resize(); draw(performance.now()); });
    ro.observe(canvas.parentElement);
    if (active) { t0 = performance.now(); raf = requestAnimationFrame(loop); }
    return () => { cancelAnimationFrame(raf); ro.disconnect(); };
  }, [active, progress]);

  return <canvas ref={ref} className="globe" aria-hidden="true" />;
}
