import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { useStore } from '../../store.jsx';
import { boostWithKey } from '../../api/boost.js';
import { boostPrompt } from '../../api/client.js';
import { providerName, styleList } from '../../data.js';
import Icon from '../Icon.jsx';

const MAX_HEIGHT = 320;
const TICK_MS = 15;

const reducedMotion = () =>
  typeof window !== 'undefined' && window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

function Sparkle({ size = 15 }) {
  return (
    <svg viewBox="0 0 24 24" width={size} height={size} fill="currentColor" stroke="currentColor" strokeWidth="1.2" strokeLinejoin="round" aria-hidden="true">
      <path d="M12 2.5l2.1 7.4 7.4 2.1-7.4 2.1L12 21.5l-2.1-7.4L2.5 12l7.4-2.1L12 2.5z" />
    </svg>
  );
}

export default function PromptStep({ onSubmit }) {
  const { topic, setTopic, geminiKey, lang, style, pricing, go } = useStore();
  const [phase, setPhase] = useState('idle'); // idle | loading | typing
  const [error, setError] = useState('');
  const [source, setSource] = useState(null); // 'mine' (own Gemini key) | 'gemini' | 'groq' | 'openrouter' | 'local' | null
  const [original, setOriginal] = useState(null);

  const taRef = useRef(null);
  const timerRef = useRef(null);
  const abortRef = useRef(null);
  const fullRef = useRef('');
  const setTopicRef = useRef(setTopic);
  useEffect(() => { setTopicRef.current = setTopic; });

  const empty = !topic.trim();
  const busy = phase === 'loading';

  // Auto-grow up to MAX_HEIGHT, then scroll.
  useLayoutEffect(() => {
    const el = taRef.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = Math.min(el.scrollHeight, MAX_HEIGHT) + 'px';
    if (phase === 'typing') el.scrollTop = el.scrollHeight;
  }, [topic, phase]);

  // On leave: stop timers, cancel the request, and don't strand half-typed text.
  useEffect(() => () => {
    if (abortRef.current) abortRef.current.abort();
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
      setTopicRef.current(fullRef.current);
    }
  }, []);

  const stopTyping = (finish) => {
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
    if (finish) setTopic(fullRef.current);
    setPhase('idle');
  };

  const startTyping = (text) => {
    if (reducedMotion()) {
      setTopic(text);
      setPhase('idle');
      return;
    }
    fullRef.current = text;
    const step = Math.max(2, Math.ceil(text.length / 150));
    let i = 0;
    setTopic('');
    setPhase('typing');
    timerRef.current = setInterval(() => {
      i = Math.min(text.length, i + step);
      const c = text.charCodeAt(i - 1);
      if (c >= 0xd800 && c <= 0xdbff && i < text.length) i += 1; // keep surrogate pairs whole
      setTopicRef.current(text.slice(0, i));
      if (i >= text.length) {
        clearInterval(timerRef.current);
        timerRef.current = null;
        setPhase('idle');
      }
    }, TICK_MS);
  };

  // Only a preset id is sent; "custom" has no id the server could use, and older backends send no styles at all.
  const boostStyle = styleList(pricing).length && style !== 'custom' ? style : null;

  const boost = async () => {
    if (busy) return;
    if (phase === 'typing') { stopTyping(true); return; }
    const before = topic;
    if (!before.trim()) return;
    setError('');
    setSource(null);
    setPhase('loading');
    const ac = new AbortController();
    abortRef.current = ac;
    try {
      const own = geminiKey.trim();
      const res = own
        ? await boostWithKey(before, own, { signal: ac.signal })
        : await boostPrompt(before, lang, boostStyle, { signal: ac.signal });
      if (!res || typeof res.text !== 'string' || !res.text.trim()) throw new Error('The booster returned an empty answer. Try rephrasing the idea.');
      if (ac.signal.aborted) return;
      setOriginal(before);
      setSource(own ? 'mine' : res.source || 'local');
      startTyping(res.text);
    } catch (e) {
      if (ac.signal.aborted) return;
      setError((e && e.message) || 'Boost failed. Try again.');
      setPhase('idle');
    }
  };

  const onChange = (e) => {
    if (phase === 'typing') stopTyping(false);
    setOriginal(null);
    setSource(null);
    setError('');
    setTopic(e.target.value);
  };

  const undo = () => {
    stopTyping(false);
    setTopic(original ?? '');
    setOriginal(null);
    setSource(null);
  };

  const submit = () => {
    if (empty || busy) return;
    if (phase === 'typing') stopTyping(true);
    onSubmit();
  };

  const onKeyDown = (e) => {
    if (e.key !== 'Enter' || e.shiftKey) return;
    if (e.nativeEvent.isComposing || e.keyCode === 229) return;
    e.preventDefault();
    submit();
  };

  const boostTitle = geminiKey.trim()
    ? 'Boost prompt with Gemini, using your own key'
    : 'Boost prompt with the server AI providers';

  return (
    <section className="cx-stage" aria-labelledby="cx-title">
      <h1 id="cx-title" className="cx-title">What video should we make?</h1>

      <div className="cx-box">
        <textarea
          ref={taRef}
          className="cx-input"
          rows={3}
          autoFocus
          aria-label="Describe your video idea"
          placeholder="Describe your video idea…"
          value={topic}
          readOnly={busy}
          onChange={onChange}
          onKeyDown={onKeyDown}
        />
        <div className="cx-bar">
          <div className="cx-bar-left">
            <button
              type="button"
              className={'cx-boost' + (busy ? ' is-busy' : '')}
              onClick={boost}
              disabled={empty || busy}
              title={boostTitle}
              aria-label={boostTitle}
            >
              {busy ? <span className="spin" aria-hidden="true" /> : <Sparkle />}
              <span>{busy ? 'Boosting…' : phase === 'typing' ? 'Skip' : 'Boost'}</span>
            </button>
            {original !== null && phase === 'idle' && (
              <button type="button" className="link-btn cx-undo" onClick={undo}>Undo</button>
            )}
          </div>
          <span className="cx-hint" aria-hidden="true">Enter to continue · Shift+Enter for a new line</span>
          <button type="button" className="cx-send" onClick={submit} disabled={empty || busy} aria-label="Continue">
            <Icon name="arrow" size={18} />
          </button>
        </div>
      </div>

      <div className="cx-msgs">
        {error && <p className="cx-err" role="alert">{error}</p>}
        {!error && source === 'local' && (
          <p className="cx-note" role="status">
            Built-in enhancer, not AI: the server had no AI provider available, so this text came from a fixed template.
            To get AI-written prompts, save a Gemini API key in Settings or configure a provider on the server.{' '}
            <button type="button" className="link-btn" onClick={() => go('settings')}>Open settings</button>
          </p>
        )}
        {!error && source === 'mine' && (
          <p className="cx-note" role="status">Written by Gemini with your own API key.</p>
        )}
        {!error && source && source !== 'local' && source !== 'mine' && (
          <p className="cx-note" role="status">Written by AI ({providerName(source)}) through the server.</p>
        )}
      </div>
    </section>
  );
}
