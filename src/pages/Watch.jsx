import { useEffect, useState } from 'react';
import QRCode from 'qrcode';
import { API_BASE } from '../api/client.js';
import { LogoMark } from '../components/Logo.jsx';

// Public watch page: #/watch/<jobId>?sig=<media signature>&t=<title>. No sign-in needed - the
// signature in the link is what authorises playback, exactly like the in-app player.
export function parseWatchHash(hash) {
  const m = String(hash || '').match(/^#\/watch\/([^?]+)(?:\?(.*))?$/);
  if (!m) return null;
  const q = new URLSearchParams(m[2] || '');
  let id = m[1];
  try { id = decodeURIComponent(id); } catch { /* keep raw */ }
  return { id, sig: q.get('sig') || '', title: q.get('t') || '' };
}

export function shareUrl(job) {
  const q = new URLSearchParams();
  if (job.media_sig) q.set('sig', job.media_sig);
  if (job.topic) q.set('t', job.topic.slice(0, 120));
  return `${window.location.origin}${window.location.pathname}#/watch/${encodeURIComponent(job.id)}?${q}`;
}

export function useQr(text, size = 220) {
  const [src, setSrc] = useState('');
  useEffect(() => {
    let dead = false;
    if (!text) { setSrc(''); return undefined; }
    QRCode.toDataURL(text, { width: size, margin: 1, color: { dark: '#0a1010', light: '#ffffff' } })
      .then((url) => { if (!dead) setSrc(url); })
      .catch(() => { if (!dead) setSrc(''); });
    return () => { dead = true; };
  }, [text, size]);
  return src;
}

export default function Watch({ id, sig, title }) {
  const [failed, setFailed] = useState(false);
  const page = window.location.href;
  const qr = useQr(page, 180);
  const video = `${API_BASE}/jobs/${encodeURIComponent(id)}/video${sig ? `?sig=${encodeURIComponent(sig)}` : ''}`;
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    try { await navigator.clipboard.writeText(page); setCopied(true); setTimeout(() => setCopied(false), 2000); } catch { /* clipboard blocked */ }
  };

  return (
    <main className="watch">
      <header className="watch-top">
        <a className="watch-brand" href="#/"><LogoMark size={24} /> IdeaFeed AI</a>
        <span className="watch-tag">Made with AI in one click</span>
      </header>
      <section className="watch-stage">
        <div className="watch-player">
          {failed
            ? <p className="watch-err">This video isn&apos;t available. The link may be wrong or the video was removed.</p>
            : <video src={video} controls autoPlay muted playsInline loop onError={() => setFailed(true)} />}
        </div>
        <aside className="watch-side">
          <span className="watch-kicker">AI-generated short</span>
          <h1>{title || 'An IdeaFeed AI video'}</h1>
          <p>Script, visuals, voice, captions and motion were all generated automatically from a single idea.</p>
          {qr && <img className="watch-qr" src={qr} alt="QR code to open this video on your phone" width={180} height={180} />}
          <span className="watch-hint">Scan to watch on your phone</span>
          <div className="watch-actions">
            <button type="button" className="watch-btn" onClick={copy}>{copied ? 'Link copied' : 'Copy link'}</button>
            <a className="watch-btn watch-btn--ghost" href={`${video}${sig ? '&' : '?'}download=1`} download>Download</a>
            <a className="watch-btn watch-btn--ghost" href="#/">Make your own</a>
          </div>
        </aside>
      </section>
    </main>
  );
}
