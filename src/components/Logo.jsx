import { useId } from 'react';

// IdeaFeed AI brand mark: a lime-to-teal tile holding a play button (the video) with a spark at its
// corner (the idea / AI). The same drawing is used for the favicon (public/favicon.svg).
export function LogoMark({ size = 22, className = '' }) {
  const uid = `lg${useId().replace(/[^a-zA-Z0-9]/g, '')}`;
  return (
    <svg className={'logo-mark ' + className} width={size} height={size} viewBox="0 0 64 64" aria-hidden="true" focusable="false">
      <defs>
        <linearGradient id={`${uid}t`} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#d4f58f" />
          <stop offset=".55" stopColor="#b4e768" />
          <stop offset="1" stopColor="#3fbf9f" />
        </linearGradient>
      </defs>
      <rect x="2" y="2" width="60" height="60" rx="16" fill={`url(#${uid}t)`} />
      <path d="M23 18.5 L46 32 L23 45.5 Z" fill="#0a1010" stroke="#0a1010" strokeWidth="5" strokeLinejoin="round" />
      <path d="M49 7.5 l2.4 6.1 6.1 2.4 -6.1 2.4 -2.4 6.1 -2.4 -6.1 -6.1 -2.4 6.1 -2.4z" fill="#ffffff" />
    </svg>
  );
}

// Mark + wordmark, e.g. in the sidebar and on the landing card.
export default function Logo({ size = 22, className = '' }) {
  return (
    <span className={'logo-lockup ' + className}>
      <LogoMark size={size} />
      <span className="logo-word">IdeaFeed<span className="logo-ai">AI</span></span>
    </span>
  );
}
