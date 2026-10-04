import { useEffect, useRef, useState } from 'react';
import { useStore } from '../store.jsx';
import { LogoMark } from '../components/Logo.jsx';

const STAGES = ['Intelligence', 'Generation', 'Composition', 'Validation', 'Review'];

// Rising "video frame" cards: [left %, width px, duration s, delay s, tilt deg, label]
// Labels are sample topics (what this product actually turns into a video),
// not generic "scene N" placeholders - makes the animation read as real
// product output instead of decorative loading boxes.
const FRAMES = [
  [6, 92, 17, 0, -6, 'phone review'],
  [19, 120, 21, 5, 4, 'morning routine'],
  [37, 84, 15, 9, -3, 'startup pitch'],
  [52, 132, 23, 2, 6, 'diwali recipe'],
  [68, 96, 18, 11, -5, 'AI explained'],
  [82, 112, 20, 7, 3, 'match recap'],
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
  const { login, register, verifyEmail, resendCode, go } = useStore();
  const [mode, setMode] = useState('signin'); // signin | register | verify
  const [code, setCode] = useState('');
  const [notice, setNotice] = useState('');
  const [cooldown, setCooldown] = useState(0); // seconds until another code may be requested
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
  const verifying = mode === 'verify';

  useEffect(() => {
    if (cooldown <= 0) return undefined;
    const id = setTimeout(() => setCooldown((s) => s - 1), 1000);
    return () => clearTimeout(id);
  }, [cooldown]);

  const toVerify = (em, message) => {
    setEmail(em);
    setCode('');
    setMode('verify');
    setNotice(message);
    setCooldown(45);
  };
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
      if (creating) {
        const pending = await register(em, password);
        if (!alive.current) return;
        if (pending && pending.verify) {
          toVerify(pending.verify, `We sent a 6-digit code to ${pending.verify}. It expires in ${pending.minutes || 15} minutes.`);
          setBusy(false);
        }
      } else {
        await login(em, password);
      }
    } catch (err) {
      if (!alive.current) return;
      const d = err && err.detail && typeof err.detail === 'object' ? err.detail : null;
      if (d && d.verification_required) {
        // Signed up but never confirmed: send a fresh code and ask for it.
        let msg = `Confirm your email to continue. Enter the code we sent to ${d.email || em}.`;
        try { await resendCode(d.email || em); msg = `We sent a new 6-digit code to ${d.email || em}.`; } catch { /* the earlier code may still work */ }
        if (!alive.current) return;
        toVerify(d.email || em, msg);
      } else if (err && err.status === 401) setError('Invalid email or password.');
      else if (err && err.status === 409) setError('That email is already registered. Sign in instead.');
      else setError((err && err.message) || 'Something went wrong. Try again.');
      setBusy(false);
    }
  };

  const submitCode = async (e) => {
    e.preventDefault();
    if (busy) return;
    const digits = code.replace(/\D/g, '');
    if (digits.length !== 6) return setError('Enter the 6-digit code from the email.');
    setError('');
    setBusy(true);
    try {
      await verifyEmail(email, digits);
    } catch (err) {
      if (!alive.current) return;
      const msg = (err && err.message) || 'That code did not work. Try again.';
      setError(msg.charAt(0).toUpperCase() + msg.slice(1));
      setBusy(false);
    }
  };

  const resend = async () => {
    if (cooldown > 0 || busy) return;
    setError('');
    try {
      await resendCode(email);
      if (!alive.current) return;
      setNotice(`We sent a new code to ${email}.`);
      setCooldown(45);
    } catch (err) {
      if (!alive.current) return;
      setError((err && err.message) || 'Could not send a new code. Try again in a minute.');
    }
  };

  const switchMode = () => {
    setMode(creating ? 'signin' : 'register');
    setError('');
    setNotice('');
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
          <LogoMark size={26} />
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
        {verifying ? (
          <form className="login-form" onSubmit={submitCode} noValidate>
            <div className="rise" style={{ '--d': 1 }}>
              <div className="kicker">VERIFY EMAIL</div>
              <h2>Check your email</h2>
            </div>
            {notice && <p className="verify-note rise" style={{ '--d': 2 }} role="status">{notice}</p>}
            <div className="field rise" style={{ '--d': 2 }}>
              <label className="cap" htmlFor="code">Verification code</label>
              <input
                id="code"
                className="input input-lg verify-code"
                inputMode="numeric"
                autoComplete="one-time-code"
                pattern="[0-9]*"
                maxLength={6}
                placeholder="000000"
                value={code}
                onChange={(e) => setCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
                disabled={busy}
                autoFocus
              />
            </div>
            {error && <div className="alert" role="alert" aria-live="assertive">{error}</div>}
            <button className="btn btn-primary btn-lg login-btn rise" style={{ '--d': 3 }} type="submit" disabled={busy || code.length !== 6}>
              {busy ? <><i className="spin" />Verifying…</> : 'Verify and continue'}
            </button>
            <button className="btn btn-secondary rise" style={{ '--d': 4 }} type="button" onClick={resend} disabled={busy || cooldown > 0}>
              {cooldown > 0 ? `Resend code in ${cooldown}s` : 'Resend code'}
            </button>
            <button type="button" className="back-link rise" style={{ '--d': 5 }} onClick={() => { setMode('register'); setError(''); setNotice(''); }}>
              ← Use a different email
            </button>
          </form>
        ) : (
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
        )}
      </div>
    </section>
  );
}
