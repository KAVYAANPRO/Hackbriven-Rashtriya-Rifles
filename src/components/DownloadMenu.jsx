import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { downloadUrl, videoUrl } from '../api/client.js';
import { kindLabel } from '../data.js';
import Icon from './Icon.jsx';

// Reads the FastAPI `detail` out of an error response (string, validation list or {message}).
async function errorText(res) {
  let detail = null;
  try {
    const text = await res.text();
    try {
      const data = JSON.parse(text);
      detail = data && typeof data === 'object' && 'detail' in data ? data.detail : null;
    } catch { /* not JSON */ }
  } catch { /* unreadable body */ }
  if (typeof detail === 'string' && detail.trim()) return detail;
  if (detail && typeof detail === 'object' && !Array.isArray(detail) && typeof detail.message === 'string') return detail.message;
  if (Array.isArray(detail) && detail.length && detail[0] && detail[0].msg) return detail.map((d) => d.msg).join('; ');
  if (res.status === 409) return 'The video is not ready to download yet.';
  if (res.status === 422) return 'That format is not supported.';
  if (res.status === 404) return 'This video could not be found.';
  if (res.status >= 500) return `The server could not convert the video (${res.status}). Try again.`;
  return `Download failed (${res.status}).`;
}

function saveBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.rel = 'noopener';
  a.style.display = 'none';
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 60000);
}

// Download control for a finished job. `job` is the adapted job, `formats` is pricing.formats.
export default function DownloadMenu({ job, formats }) {
  const [open, setOpen] = useState(false);
  const [state, setState] = useState({}); // formatId -> { busy: bool, error: string }
  const wrapRef = useRef(null);
  const btnRef = useRef(null);
  const aborts = useRef({});

  const busyAny = Object.values(state).some((s) => s.busy);
  const errAny = Object.entries(state).find(([, s]) => s.error);

  // Items grouped by kind, kinds in order of first appearance.
  const groups = useMemo(() => {
    const out = [];
    formats.forEach((f) => {
      let g = out.find((x) => x.kind === f.kind);
      if (!g) { g = { kind: f.kind, items: [] }; out.push(g); }
      g.items.push(f);
    });
    return out;
  }, [formats]);

  const close = useCallback((refocus) => {
    setOpen(false);
    if (refocus && btnRef.current) btnRef.current.focus();
  }, []);

  // Close on outside click / focus leaving / Escape.
  useEffect(() => {
    if (!open) return undefined;
    const onDown = (e) => { if (wrapRef.current && !wrapRef.current.contains(e.target)) setOpen(false); };
    const onKey = (e) => {
      if (e.key === 'Escape') { e.stopPropagation(); close(true); }
    };
    document.addEventListener('mousedown', onDown);
    document.addEventListener('touchstart', onDown);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onDown);
      document.removeEventListener('touchstart', onDown);
      document.removeEventListener('keydown', onKey);
    };
  }, [open, close]);

  // Cancel in-flight conversions when the page goes away.
  useEffect(() => () => { Object.values(aborts.current).forEach((ac) => ac.abort()); }, []);

  const items = () => (wrapRef.current ? Array.from(wrapRef.current.querySelectorAll('.dl-item:not([aria-disabled="true"])')) : []);

  const onMenuKey = (e) => {
    if (!['ArrowDown', 'ArrowUp', 'Home', 'End'].includes(e.key)) return;
    const els = items();
    if (!els.length) return;
    e.preventDefault();
    const i = els.indexOf(document.activeElement);
    let n;
    if (e.key === 'Home') n = 0;
    else if (e.key === 'End') n = els.length - 1;
    else if (e.key === 'ArrowDown') n = i < 0 ? 0 : (i + 1) % els.length;
    else n = i <= 0 ? els.length - 1 : i - 1;
    els[n].focus();
  };

  const toggle = () => {
    if (open) { setOpen(false); return; }
    setOpen(true);
    // Focus the first item once the menu has rendered.
    setTimeout(() => { const els = items(); if (els[0]) els[0].focus(); }, 0);
  };

  const run = async (f) => {
    const id = f.id;
    if (state[id] && state[id].busy) return;
    const ac = new AbortController();
    aborts.current[id] = ac;
    setState((s) => ({ ...s, [id]: { busy: true, error: '' } }));
    try {
      let res;
      try {
        res = await fetch(downloadUrl(job.raw, id), { signal: ac.signal });
      } catch (e) {
        if (e && e.name === 'AbortError') throw e;
        throw new Error('Could not reach the server. Check your connection and try again.');
      }
      if (!res.ok) throw new Error(await errorText(res));
      const blob = await res.blob();
      if (!blob.size) throw new Error('The server sent an empty file. Try again.');
      saveBlob(blob, `ideafeed-${job.id}.${f.ext || id}`);
      setState((s) => ({ ...s, [id]: { busy: false, error: '' } }));
      close(true);
    } catch (e) {
      if (e && e.name === 'AbortError') return;
      setState((s) => ({ ...s, [id]: { busy: false, error: (e && e.message) || 'Download failed. Try again.' } }));
      setOpen(true); // keep the error and its Retry in view
    } finally {
      delete aborts.current[id];
    }
  };

  const onItemClick = (e, f) => {
    // The stored master is a plain download; everything else is converted on the server on first request.
    if (f.id === 'mp4') { close(false); return; }
    e.preventDefault();
    run(f);
  };

  return (
    <div className="dl" ref={wrapRef}>
      <button
        ref={btnRef}
        type="button"
        className="btn2 btn2--ghost btn2--sm"
        aria-haspopup="true"
        aria-expanded={open}
        aria-controls="dl-panel"
        onClick={toggle}
      >
        {busyAny ? <i className="spin" /> : <Icon name="download" size={14} />}
        {busyAny ? 'Preparing…' : 'Download'}
        <span className={'dl-caret' + (open ? ' is-open' : '')} aria-hidden="true" />
      </button>

      {!open && errAny && (
        <p className="err-text dl-err" role="alert">Download failed. Open the menu to retry.</p>
      )}

      {open && (
        <div id="dl-panel" className="dl-panel" role="group" aria-label="Download formats" onKeyDown={onMenuKey}>
          {groups.map((g) => (
            <div key={g.kind || '_'} className="dl-group">
              <span className="dl-gh mono">{kindLabel(g.kind)}</span>
              {g.items.map((f) => {
                const s = state[f.id] || {};
                const href = f.id === 'mp4' ? videoUrl(job.raw, { download: true }) : downloadUrl(job.raw, f.id);
                return (
                  <div key={f.id} className="dl-row">
                    <a
                      className={'dl-item' + (s.busy ? ' is-busy' : '')}
                      href={href}
                      download={`ideafeed-${job.id}.${f.ext || f.id}`}
                      aria-disabled={s.busy ? 'true' : undefined}
                      aria-busy={s.busy ? 'true' : undefined}
                      tabIndex={s.busy ? -1 : 0}
                      onClick={(e) => onItemClick(e, f)}
                    >
                      <span className="dl-item-top">
                        <b>{f.label || f.id}</b>
                        <span className="mono dl-ext">.{f.ext || f.id}</span>
                        {s.busy && <span className="dl-wait mono"><i className="spin" />Preparing…</span>}
                      </span>
                      {f.description && <span className="dl-desc">{f.description}</span>}
                    </a>
                    {s.error && (
                      <div className="dl-rowerr" role="alert">
                        <span className="err-text">{s.error}</span>
                        <button type="button" className="link-btn" onClick={() => run(f)}>Retry</button>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
