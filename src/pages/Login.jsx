import { useEffect, useRef, useState } from 'react';
import { useStore } from '../store.jsx';

const STAGES = ['Intelligence', 'Generation', 'Composition', 'Validation', 'Review'];

// Rising "video frame" cards: [left %, width px, duration s, delay s, tilt deg, label]
const FRAMES = [
  [6, 92, 17, 0, -6, 'scene 01'],
  [19, 120, 21, 5, 4, 'scene 02'],
  [37, 84, 15, 9, -3, 'scene 03'],
  [52, 132, 23, 2, 6, 'scene 04'],
  [68, 96, 18, 11, -5, 'scene 05'],
  [82, 112, 20, 7, 3, 'scene 06'],
];

// Lights the pipeline stages one after another, then starts over.
function Pipeline() {
  const [step, setStep] = useState(0);
  useEffect(() => {
    const id = setInterval(() => setStep((s) => (s + 1) % (STAGES.length + 2)), 1100);
    return () => clearInterval(id);
  }, []);
  const lit = Math.min(step, STAGES.length);
  return (
    <ol className="pipe" aria-label="Pipeline stages">
      <li className="pipe-track" aria-hidden="true"><i style={{ transform: `scaleX(${Math.max(0, lit - 1) / (STAGES.length - 1)})` }} /></li>
      {STAGES.map((s, i) => (
        <li key={s} className={i < lit ? 'is-on' : ''} style={{ '--k': i }}>
          <span className="pipe-node" />
          <span className="pipe-n">0{i + 1}</span>
          <span className="pipe-l">{s}</span>
        </li>
      ))}
    </ol>
  );
}

export default function Login() {
  const { login, register, go } = useStore();
  const [mode, setMode] = useState('signin'); // signin | register
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const alive = useRef(true);
  useEffect(() => {
    alive.current = true; // StrictMode mounts, unmounts and re-mounts in dev; re-arm on every mount
    return () => { alive.current = false; };
  }, []);
  const creating = mode === 'register';
  const root = useRef(null);
  const raf = useRef(0);

  // Pointer parallax: write -1..1 into CSS vars, once per frame.
  const onMove = (e) => {
    if (raf.current) return;
    const { clientX, clientY } = e;
    raf.current = requestAnimationFrame(() => {
      raf.current = 0;
      const el = root.current;
      if (!el) return;
      el.style.setProperty('--mx', ((clientX / window.innerWidth) * 2 - 1).toFixed(3));
      el.style.setProperty('--my', ((clientY / window.innerHeight) * 2 - 1).toFixed(3));
    });
  };
  useEffect(() => () => cancelAnimationFrame(raf.current), []);

  const submit = async (e) => {
    e.preventDefault();
    if (busy) return;
    const em = email.trim();
    if (!/^\S+@\S+\.\S+$/.test(em)) return setError('Enter a valid email address.');
    if (password.length < 6) return setError('Password must be at least 6 characters.');
    setError('');
    setBusy(true);
    try {
      await (creating ? register : login)(em, password);
    } catch (err) {
      if (!alive.current) return;
      if (err && err.status === 401) setError('Invalid email or password.');
      else if (err && err.status === 409) setError('That email is already registered. Sign in instead.');
      else setError((err && err.message) || 'Something went wrong. Try again.');
      setBusy(false);
    }
  };

  const switchMode = () => {
    setMode(creating ? 'signin' : 'register');
    setError('');
  };

  return (
    <section className="login" ref={root} onMouseMove={onMove}>
      <div className="login-side">
        <div className="lg-bg" aria-hidden="true">
          <i className="orb orb--a" />
          <i className="orb orb--b" />
          <i className="orb orb--c" />
          <div className="floor-grid"><i /></div>
          <div className="frames">
            {FRAMES.map(([left, w, dur, delay, tilt, label]) => (
              <div
                key={label}
                className="frame"
                style={{ left: `${left}%`, width: w, '--dur': `${dur}s`, '--delay': `${delay}s`, '--tilt': `${tilt}deg` }}
              >
                <div className="frame-art" />
                <div className="frame-meta"><span>{label}</span><b /></div>
              </div>
            ))}
          </div>
        </div>

        <button type="button" className="brand-plain rise" style={{ '--d': 0 }} onClick={() => go('landing')}>
          <span className="block-dot" />
          IdeaFeed AI
        </button>
        <div className="login-copy">
          <h1 className="login-h rise" style={{ '--d': 2 }}>Review, approve,<br />hand off<span className="dot-accent">.</span></h1>
          <p className="rise" style={{ '--d': 4 }}>Your jobs, credits and provider status are waiting inside.</p>
        </div>
        <div className="rise" style={{ '--d': 6 }}><Pipeline /></div>
      </div>

      <div className="login-main">
        <div className="main-bg" aria-hidden="true">
          <i className="beam" />
          <i className="dots" />
        </div>
        <form className="login-form" onSubmit={submit} noValidate>
          <div className="rise" style={{ '--d': 1 }}>
            <div className="kicker">{creating ? 'CREATE ACCOUNT' : 'SIGN IN'}</div>
            <h2>{creating ? 'Start creating' : 'Welcome back'}</h2>
          </div>
          <div className="field rise" style={{ '--d': 2 }}>
            <label className="cap" htmlFor="email">Email</label>
            <input id="email" className="input input-lg" type="email" placeholder="you@company.com" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" disabled={busy} />
          </div>
          <div className="field rise" style={{ '--d': 3 }}>
            <label className="cap" htmlFor="password">Password</label>
            <input id="password" className="input input-lg" type="password" placeholder="At least 6 characters" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete={creating ? 'new-password' : 'current-password'} disabled={busy} />
          </div>
          {error && <div className="alert" role="alert" aria-live="assertive">{error}</div>}
          <button className="btn btn-primary btn-lg login-btn rise" style={{ '--d': 4 }} type="submit" disabled={busy}>
            {busy ? <><i className="spin" />{creating ? 'Creating account…' : 'Signing in…'}</> : creating ? 'Create account' : 'Sign in'}
          </button>
          <button className="btn btn-secondary rise" style={{ '--d': 5 }} type="button" onClick={switchMode} disabled={busy}>
            {creating ? 'I already have an account' : 'Create an account'}
          </button>
          <button type="button" className="back-link rise" style={{ '--d': 6 }} onClick={() => go('landing')}>← Back to home</button>
        </form>
      </div>
    </section>
  );
}
