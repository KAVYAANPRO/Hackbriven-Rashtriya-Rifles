import { useId } from 'react';

// Small vector illustrations for the style picker, one per style id - a preview of the look,
// like Canva's style thumbnails. Drawn at 160x80 and scaled to fill the card.
// `uid` keeps gradient/filter ids unique when several thumbnails are on the page.

function Auto({ uid }) {
  return (
    <>
      <defs>
        <linearGradient id={`${uid}bg`} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#14302c" />
          <stop offset="1" stopColor="#2f5a3a" />
        </linearGradient>
      </defs>
      <rect width="160" height="80" fill={`url(#${uid}bg)`} />
      <rect x="44" y="50" width="62" height="7" rx="3.5" transform="rotate(-32 75 53)" fill="#e9eedf" />
      <rect x="92" y="28" width="16" height="7" rx="3" transform="rotate(-32 100 31)" fill="#b4e768" />
      <path d="M118 14l3 8 8 3-8 3-3 8-3-8-8-3 8-3z" fill="#b4e768" />
      <path d="M134 34l2 5 5 2-5 2-2 5-2-5-5-2 5-2z" fill="#f4f7ee" />
      <path d="M104 46l1.6 4 4 1.6-4 1.6-1.6 4-1.6-4-4-1.6 4-1.6z" fill="#d7f59a" />
      <circle cx="26" cy="20" r="1.6" fill="#d7f59a" />
      <circle cx="140" cy="62" r="1.4" fill="#e9eedf" />
    </>
  );
}

function Cinematic({ uid }) {
  return (
    <>
      <defs>
        <linearGradient id={`${uid}sky`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#2a1a4a" />
          <stop offset=".55" stopColor="#d9653b" />
          <stop offset="1" stopColor="#f6b25a" />
        </linearGradient>
      </defs>
      <rect width="160" height="80" fill={`url(#${uid}sky)`} />
      <circle cx="104" cy="50" r="14" fill="#ffd27a" opacity=".95" />
      <path d="M0 62 C30 50 52 58 74 52 S118 46 160 58 V80 H0z" fill="#1d1222" />
      <path d="M58 54 l3 -9 3 9z" fill="#1d1222" />
      <rect x="60" y="44" width="2" height="4" fill="#1d1222" />
      <rect width="160" height="11" fill="#050505" />
      <rect y="69" width="160" height="11" fill="#050505" />
    </>
  );
}

function Documentary({ uid }) {
  return (
    <>
      <defs>
        <linearGradient id={`${uid}sky`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#a9c3c2" />
          <stop offset="1" stopColor="#dfe3cf" />
        </linearGradient>
      </defs>
      <rect width="160" height="80" fill={`url(#${uid}sky)`} />
      <path d="M0 52 L34 26 L58 44 L86 18 L122 46 L160 30 V80 H0z" fill="#6f8a73" />
      <path d="M0 62 C40 50 70 66 110 56 S150 58 160 54 V80 H0z" fill="#46604c" />
      <path d="M86 18 l6 6 -4 -1 -2 3 -2 -3 -4 1z" fill="#f2f4ee" />
      <g stroke="#ffffff" strokeWidth="2" fill="none" opacity=".9">
        <path d="M10 18 V10 H18" /><path d="M142 10 H150 V18" />
        <path d="M10 62 V70 H18" /><path d="M142 70 H150 V62" />
      </g>
      <circle cx="140" cy="20" r="3" fill="#e53935" />
    </>
  );
}

function News() {
  return (
    <>
      <rect width="160" height="80" fill="#0e2340" />
      <circle cx="116" cy="34" r="20" fill="none" stroke="#2c5d9c" strokeWidth="2" />
      <ellipse cx="116" cy="34" rx="9" ry="20" fill="none" stroke="#2c5d9c" strokeWidth="1.6" />
      <path d="M96 34 H136 M99 24 H133 M99 44 H133" stroke="#2c5d9c" strokeWidth="1.4" />
      <rect x="12" y="12" width="30" height="12" rx="2" fill="#e53935" />
      <text x="27" y="21.5" textAnchor="middle" fontFamily="Arial, sans-serif" fontWeight="700" fontSize="8.5" fill="#fff">LIVE</text>
      <rect x="0" y="56" width="160" height="16" fill="#f4f6f9" />
      <rect x="0" y="56" width="34" height="16" fill="#e53935" />
      <rect x="40" y="60" width="70" height="3.5" rx="1.5" fill="#1d2b40" />
      <rect x="40" y="66" width="48" height="2.5" rx="1.2" fill="#8b97a8" />
    </>
  );
}

function Educational() {
  const chalk = '#f1f5ea';
  return (
    <>
      <rect width="160" height="80" fill="#1f3d2f" />
      <rect x="3" y="3" width="154" height="74" fill="none" stroke="#7a5a3a" strokeWidth="4" />
      <text x="14" y="26" fontFamily="Georgia, 'Times New Roman', serif" fontStyle="italic" fontSize="14" fill={chalk}>a² + b² = c²</text>
      <text x="16" y="52" fontFamily="Georgia, serif" fontSize="17" fill="#d7f59a">π</text>
      <text x="34" y="52" fontFamily="Georgia, serif" fontStyle="italic" fontSize="11" fill={chalk}>≈ 3.14</text>
      <text x="16" y="68" fontFamily="Georgia, serif" fontStyle="italic" fontSize="10" fill={chalk} opacity=".85">∫ x dx = x²/2</text>
      <path d="M112 62 L112 26 L146 62 Z" fill="none" stroke={chalk} strokeWidth="1.8" />
      <path d="M112 56 h6 v6" fill="none" stroke={chalk} strokeWidth="1.3" />
      <text x="104" y="46" fontFamily="Georgia, serif" fontStyle="italic" fontSize="9" fill={chalk}>a</text>
      <text x="126" y="72" fontFamily="Georgia, serif" fontStyle="italic" fontSize="9" fill={chalk}>b</text>
      <text x="132" y="40" fontFamily="Georgia, serif" fontStyle="italic" fontSize="9" fill="#d7f59a">c</text>
    </>
  );
}

function Corporate({ uid }) {
  return (
    <>
      <defs>
        <linearGradient id={`${uid}bg`} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#eaf2fb" />
          <stop offset="1" stopColor="#cfe0f3" />
        </linearGradient>
      </defs>
      <rect width="160" height="80" fill={`url(#${uid}bg)`} />
      <path d="M20 66 H142" stroke="#8aa6c8" strokeWidth="1.2" />
      {[[30, 46], [52, 38], [74, 30], [96, 22], [118, 14]].map(([x, y], i) => (
        <rect key={i} x={x} y={y} width="14" height={66 - y} rx="2" fill={i === 4 ? '#1565c0' : '#5b8fd1'} opacity={0.55 + i * 0.1} />
      ))}
      <path d="M26 50 L50 40 L72 34 L94 24 L124 12" fill="none" stroke="#0b3d91" strokeWidth="2.2" strokeLinecap="round" />
      <path d="M124 12 l-7 0 m7 0 l-2 6.5" stroke="#0b3d91" strokeWidth="2.2" strokeLinecap="round" />
    </>
  );
}

function Minimalist() {
  return (
    <>
      <rect width="160" height="80" fill="#f4f3ef" />
      <circle cx="58" cy="38" r="17" fill="#111111" />
      <path d="M18 60 H142" stroke="#111111" strokeWidth="1.4" />
      <rect x="104" y="44" width="10" height="10" fill="none" stroke="#111111" strokeWidth="1.4" />
      <circle cx="128" cy="24" r="2.2" fill="#111111" />
    </>
  );
}

function Playful() {
  const ink = '#2b1d3a';
  return (
    <>
      <rect width="160" height="80" fill="#ffd9e6" />
      <path d="M0 64 C30 54 50 72 80 62 S130 54 160 64 V80 H0z" fill="#9be7c4" stroke={ink} strokeWidth="2" />
      <circle cx="52" cy="34" r="15" fill="#ffd23f" stroke={ink} strokeWidth="2.2" />
      <circle cx="47" cy="31" r="1.8" fill={ink} /><circle cx="57" cy="31" r="1.8" fill={ink} />
      <path d="M46 38 q6 6 12 0" fill="none" stroke={ink} strokeWidth="2" strokeLinecap="round" />
      <rect x="100" y="20" width="18" height="18" rx="4" fill="#5ac8fa" stroke={ink} strokeWidth="2" transform="rotate(14 109 29)" />
      <path d="M128 46 l7 -12 7 12z" fill="#ff7a59" stroke={ink} strokeWidth="2" strokeLinejoin="round" />
      {[[22, 14, '#ff7a59'], [88, 12, '#7c5cff'], [140, 18, '#ffd23f'], [86, 46, '#ff5ca8']].map(([x, y, c], i) => (
        <circle key={i} cx={x} cy={y} r="3" fill={c} stroke={ink} strokeWidth="1.2" />
      ))}
    </>
  );
}

function ThreeD({ uid }) {
  return (
    <>
      <defs>
        <linearGradient id={`${uid}bg`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#c7c2ff" />
          <stop offset="1" stopColor="#8f86f0" />
        </linearGradient>
        <radialGradient id={`${uid}body`} cx=".35" cy=".3" r=".8">
          <stop offset="0" stopColor="#fff6b0" />
          <stop offset=".45" stopColor="#ffd23f" />
          <stop offset="1" stopColor="#e09b0d" />
        </radialGradient>
        <radialGradient id={`${uid}beak`} cx=".3" cy=".3" r=".9">
          <stop offset="0" stopColor="#ffb27a" />
          <stop offset="1" stopColor="#e2601c" />
        </radialGradient>
        <radialGradient id={`${uid}ball`} cx=".35" cy=".3" r=".8">
          <stop offset="0" stopColor="#ffffff" />
          <stop offset=".4" stopColor="#7ee0ff" />
          <stop offset="1" stopColor="#1e88c8" />
        </radialGradient>
      </defs>
      <rect width="160" height="80" fill={`url(#${uid}bg)`} />
      <ellipse cx="74" cy="70" rx="34" ry="5" fill="#4b3fb0" opacity=".35" />
      {/* rubber duck */}
      <path d="M46 52 C44 38 60 34 74 38 C86 34 104 38 104 50 C104 62 90 68 74 68 C58 68 47 62 46 52 Z" fill={`url(#${uid}body)`} />
      <path d="M44 46 C40 42 42 36 48 40 Z" fill="#e8a614" />
      <circle cx="90" cy="30" r="14" fill={`url(#${uid}body)`} />
      <path d="M101 31 C110 29 114 32 113 35 C108 37 103 36 100 35 Z" fill={`url(#${uid}beak)`} />
      <circle cx="94" cy="26" r="2.6" fill="#1b1430" />
      <circle cx="95" cy="25" r=".9" fill="#ffffff" />
      <path d="M58 48 C64 44 76 44 82 50" fill="none" stroke="#e8a614" strokeWidth="2" strokeLinecap="round" opacity=".7" />
      <ellipse cx="84" cy="22" rx="4" ry="2.4" fill="#ffffff" opacity=".55" transform="rotate(-25 84 22)" />
      {/* floating ball */}
      <circle cx="132" cy="28" r="10" fill={`url(#${uid}ball)`} />
      <ellipse cx="134" cy="60" rx="9" ry="2.4" fill="#4b3fb0" opacity=".3" />
    </>
  );
}

function Colorful() {
  return (
    <>
      <rect width="160" height="80" fill="#ffe14d" />
      <rect x="0" y="0" width="58" height="80" fill="#ff3d7f" />
      <circle cx="58" cy="40" r="26" fill="#2979ff" />
      <path d="M96 0 L160 0 L160 50 Z" fill="#00c853" />
      <path d="M100 80 L130 30 L160 80 Z" fill="#ff6d00" />
      <circle cx="58" cy="40" r="10" fill="#ffe14d" />
      {[0, 1, 2, 3].map((r) => [0, 1, 2].map((c) => (
        <circle key={`${r}-${c}`} cx={10 + c * 12} cy={12 + r * 18} r="2.4" fill="#ffffff" opacity=".85" />
      )))}
    </>
  );
}

function Illustrated({ uid }) {
  return (
    <>
      <defs>
        <filter id={`${uid}soft`} x="-10%" y="-10%" width="120%" height="120%">
          <feGaussianBlur stdDeviation="1.2" />
        </filter>
      </defs>
      <rect width="160" height="80" fill="#f7f1e3" />
      <g filter={`url(#${uid}soft)`} opacity=".9">
        <circle cx="124" cy="22" r="12" fill="#f6c177" opacity=".8" />
        <path d="M0 60 C30 46 60 58 90 50 S140 46 160 54 V80 H0z" fill="#a8cfa1" opacity=".75" />
        <path d="M0 68 C40 60 80 74 120 64 S150 66 160 64 V80 H0z" fill="#7fb38a" opacity=".7" />
        <ellipse cx="46" cy="34" rx="16" ry="14" fill="#6aa57a" opacity=".8" />
        <ellipse cx="38" cy="40" rx="11" ry="9" fill="#8cc49b" opacity=".75" />
      </g>
      <path d="M46 44 V60" stroke="#7a5a3a" strokeWidth="3" strokeLinecap="round" />
      <path d="M36 52 q10 -6 20 0" fill="none" stroke="#5a4636" strokeWidth=".9" opacity=".6" />
      <path d="M96 30 q4 -4 8 0 q4 -4 8 0" fill="none" stroke="#5a4636" strokeWidth="1.2" strokeLinecap="round" />
    </>
  );
}

function Retro({ uid }) {
  return (
    <>
      <defs>
        <linearGradient id={`${uid}sky`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#1a0f3c" />
          <stop offset="1" stopColor="#5a1f6e" />
        </linearGradient>
        <linearGradient id={`${uid}sun`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#ffd23f" />
          <stop offset="1" stopColor="#ff3d7f" />
        </linearGradient>
        <clipPath id={`${uid}cut`}>
          <rect x="0" y="0" width="160" height="30" />
          <rect x="0" y="32" width="160" height="4" />
          <rect x="0" y="38.5" width="160" height="3" />
          <rect x="0" y="44" width="160" height="2" />
        </clipPath>
      </defs>
      <rect width="160" height="80" fill={`url(#${uid}sky)`} />
      <circle cx="80" cy="46" r="24" fill={`url(#${uid}sun)`} clipPath={`url(#${uid}cut)`} />
      <rect y="48" width="160" height="32" fill="#12082a" />
      <g stroke="#ff3dd0" strokeWidth=".9" opacity=".85">
        {[52, 57, 63, 71].map((y) => <path key={y} d={`M0 ${y} H160`} />)}
        {[-60, -30, 0, 30, 60, 90, 120, 150, 180, 210].map((x) => <path key={x} d={`M80 48 L${x} 80`} />)}
      </g>
    </>
  );
}

function Neon({ uid }) {
  return (
    <>
      <defs>
        <filter id={`${uid}glow`} x="-30%" y="-30%" width="160%" height="160%">
          <feGaussianBlur stdDeviation="1.6" result="b" />
          <feMerge><feMergeNode in="b" /><feMergeNode in="b" /><feMergeNode in="SourceGraphic" /></feMerge>
        </filter>
      </defs>
      <rect width="160" height="80" fill="#07061a" />
      <path d="M0 62 H18 V40 H32 V52 H44 V28 H60 V48 H72 V34 H88 V56 H100 V22 H116 V44 H128 V36 H144 V58 H160"
        fill="none" stroke="#00e5ff" strokeWidth="1.6" filter={`url(#${uid}glow)`} />
      <path d="M0 70 H160" stroke="#ff2bd6" strokeWidth="1.4" filter={`url(#${uid}glow)`} />
      <circle cx="132" cy="16" r="6" fill="none" stroke="#ff2bd6" strokeWidth="1.6" filter={`url(#${uid}glow)`} />
      {[[50, 38], [104, 30], [108, 38], [66, 42]].map(([x, y], i) => (
        <rect key={i} x={x} y={y} width="3" height="3" fill="#ffe14d" opacity=".9" />
      ))}
    </>
  );
}

function Dark({ uid }) {
  return (
    <>
      <defs>
        <linearGradient id={`${uid}sky`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#05080d" />
          <stop offset="1" stopColor="#172531" />
        </linearGradient>
        <filter id={`${uid}fog`}><feGaussianBlur stdDeviation="3" /></filter>
      </defs>
      <rect width="160" height="80" fill={`url(#${uid}sky)`} />
      <circle cx="118" cy="22" r="11" fill="#e8dcc0" />
      <circle cx="124" cy="18" r="10" fill="#0b121a" />
      <ellipse cx="80" cy="60" rx="90" ry="8" fill="#9fb3c2" opacity=".18" filter={`url(#${uid}fog)`} />
      {[[14, 44], [30, 36], [48, 48], [66, 40], [86, 50], [140, 42]].map(([x, y], i) => (
        <path key={i} d={`M${x} 80 L${x} ${y + 10} L${x - 9} ${y + 22} L${x - 3} ${y + 22} L${x - 11} ${y + 32} L${x + 11} ${y + 32} L${x + 3} ${y + 22} L${x + 9} ${y + 22} L${x} ${y + 10} L${x} ${y} Z`}
          fill="#04070a" />
      ))}
      <circle cx="30" cy="14" r=".9" fill="#dfe7ee" /><circle cx="70" cy="10" r=".7" fill="#dfe7ee" /><circle cx="92" cy="20" r=".8" fill="#dfe7ee" />
    </>
  );
}

function Custom() {
  return (
    <>
      <rect width="160" height="80" fill="#141c1c" />
      <rect x="8" y="8" width="144" height="64" rx="6" fill="none" stroke="#5f6f6a" strokeWidth="1.4" strokeDasharray="5 4" />
      <path d="M70 52 L92 30 L98 36 L76 58 L68 60 Z" fill="#b4e768" />
      <path d="M92 30 L98 36" stroke="#141c1c" strokeWidth="1.4" />
      <path d="M112 34 v12 M106 40 h12" stroke="#e8efe6" strokeWidth="2" strokeLinecap="round" />
    </>
  );
}

const ART = {
  auto: Auto, cinematic: Cinematic, documentary: Documentary, news: News, educational: Educational,
  corporate: Corporate, minimalist: Minimalist, playful: Playful, '3d': ThreeD, colorful: Colorful,
  illustrated: Illustrated, retro: Retro, neon: Neon, dark: Dark, custom: Custom,
};

export default function StyleArt({ id, fallback }) {
  const uid = `sa${useId().replace(/[^a-zA-Z0-9]/g, '')}`;
  const Art = ART[id];
  if (!Art) {
    // A style the server added later: keep the old neutral gradient rather than a blank card.
    return <span className="cx-style-sw" style={{ background: fallback }} aria-hidden="true" />;
  }
  return (
    <svg className="cx-style-sw cx-style-art" viewBox="0 0 160 80" preserveAspectRatio="xMidYMid slice" aria-hidden="true">
      <Art uid={uid} />
    </svg>
  );
}
