import { useCallback, useEffect, useRef, useState } from 'react';
import { useAuth, useClerk } from '@clerk/react';
import { useStore } from '../store.jsx';
import { LogoMark } from '../components/Logo.jsx';
import StyleArt from '../components/create/StyleArt.jsx';

const CLERK_ON = !!import.meta.env.VITE_CLERK_PUBLISHABLE_KEY;
const PENDING = 'ideafeed_clerk_pending'; // set when the user starts Google sign-in, so we never auto-sign-in uninvited
const pending = {
  get: () => { try { return sessionStorage.getItem(PENDING) === '1'; } catch { return false; } },
  set: (on) => { try { if (on) sessionStorage.setItem(PENDING, '1'); else sessionStorage.removeItem(PENDING); } catch { /* storage blocked */ } },
};

function GoogleMark() {
  return (
    <svg width="18" height="18" viewBox="0 0 48 48" aria-hidden="true">
      <path fill="#FFC107" d="M43.6 20.5H42V20H24v8h11.3C33.7 32.7 29.2 36 24 36c-6.6 0-12-5.4-12-12s5.4-12 12-12c3.1 0 5.8 1.2 7.9 3.1l5.7-5.7C34 6.1 29.3 4 24 4 12.9 4 4 12.9 4 24s8.9 20 20 20 20-8.9 20-20c0-1.3-.1-2.4-.4-3.5z" />
      <path fill="#FF3D00" d="M6.3 14.7l6.6 4.8C14.7 15.1 19 12 24 12c3.1 0 5.8 1.2 7.9 3.1l5.7-5.7C34 6.1 29.3 4 24 4 16.3 4 9.7 8.3 6.3 14.7z" />
      <path fill="#4CAF50" d="M24 44c5.2 0 9.9-2 13.4-5.2l-6.2-5.2C29.2 35.1 26.7 36 24 36c-5.2 0-9.6-3.3-11.3-7.9l-6.5 5C9.5 39.6 16.2 44 24 44z" />
      <path fill="#1976D2" d="M43.6 20.5H42V20H24v8h11.3c-.8 2.2-2.2 4.2-4.1 5.6l6.2 5.2C37 39.2 44 34 44 24c0-1.3-.1-2.4-.4-3.5z" />
    </svg>
  );
}

// "Continue with Google": Clerk handles the Google sign-in, then its session token is exchanged for
// this app's own session (same account, credits and jobs as an email login with that address).
function GoogleContinue({ disabled, onError }) {
  const { isLoaded, isSignedIn, getToken } = useAuth();
  const clerk = useClerk();
  const { loginWithClerk } = useStore();
  const [busy, setBusy] = useState(false);
  const running = useRef(false);

  const exchange = useCallback(async () => {
    if (running.current) return;
    running.current = true;
    setBusy(true);
    try {
      const token = await getToken();
      if (!token) throw new Error('Google sign-in did not finish. Try again.');
      await loginWithClerk(token);
      pending.set(false);
    } catch (err) {
      pending.set(false);
      running.current = false;
      setBusy(false);
      onError(err && err.status === 503
        ? 'Google sign-in is not set up on the server yet.'
        : (err && err.message) || 'Google sign-in failed. Try again.');
    }
  }, [getToken, loginWithClerk, onError]);

  // Back from Google (or the sign-in modal closed signed-in): finish the app sign-in.
  useEffect(() => {
    if (isLoaded && isSignedIn && pending.get()) exchange();
  }, [isLoaded, isSignedIn, exchange]);

  const start = () => {
    onError('');
    if (!isLoaded || !clerk.loaded || clerk.status === 'degraded' || clerk.status === 'error') {
      onError('Could not reach Google sign-in. Check your internet connection and reload the page.');
      return;
    }
    pending.set(true);
    if (isSignedIn) { exchange(); return; }
    const back = window.location.href;
    clerk.openSignIn({ forceRedirectUrl: back, signUpForceRedirectUrl: back });
  };

  return (
    <button type="button" className="btn btn-secondary btn-lg google-btn rise" style={{ '--d': 5 }} onClick={start} disabled={disabled || busy}>
      {busy ? <><i className="spin" />Signing in with Google…</> : <><GoogleMark />Continue with Google</>}
    </button>
  );
}

const STAGES = ['Intelligence', 'Generation', 'Composition', 'Validation', 'Review'];

// Rising "video frame" cards: [left %, width px, duration s, delay s, tilt deg, label, styleId].
// Each card shows a real StyleArt.jsx illustration (the same art used in the
// Create flow's style picker) labeled with that style's own name - reuses
// the product's real art instead of a generic placeholder or a stock image.
const FRAMES = [
  [6, 92, 17, 0, -6, '3D', '3d'],
  [19, 120, 21, 5, 4, 'Playful', 'playful'],
  [37, 84, 15, 9, -3, 'Corporate', 'corporate'],
  [52, 132, 23, 2, 6, 'Illustrated', 'illustrated'],
  [68, 96, 18, 11, -5, 'Neon', 'neon'],
  [82, 112, 20, 7, 3, 'Retro', 'retro'],
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
            {FRAMES.map(([left, w, dur, delay, tilt, label, styleId]) => (
              <div
                key={label}
                className="frame"
                style={{ left: `${left}%`, width: w, '--dur': `${dur}s`, '--delay': `${delay}s`, '--tilt': `${tilt}deg` }}
              >
                <div className="frame-art"><StyleArt id={styleId} fallback="linear-gradient(160deg, #0c5068, #0a2b34)" /></div>
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
          {CLERK_ON && (
            <>
              <div className="or-sep rise" style={{ '--d': 5 }} aria-hidden="true"><span>or</span></div>
              <GoogleContinue disabled={busy} onError={setError} />
            </>
          )}
          <button className="btn btn-secondary rise" style={{ '--d': 6 }} type="button" onClick={switchMode} disabled={busy}>
            {creating ? 'I already have an account' : 'Create an account'}
          </button>
          <button type="button" className="back-link rise" style={{ '--d': 7 }} onClick={() => go('landing')}>← Back to home</button>
        </form>
        )}
      </div>
    </section>
  );
}
