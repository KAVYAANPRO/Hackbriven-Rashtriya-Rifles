import { useEffect, useRef, useState } from 'react';
import { emailJob } from '../api/client.js';
import { useStore } from '../store.jsx';
import Icon from './Icon.jsx';
import { shareUrl } from '../pages/Watch.jsx';

// Send the finished video + its manual-handoff package to any email address (defaults to the account's).
export default function EmailVideoPanel({ job }) {
  const store = useStore();
  const showToast = store && store.showToast;
  const accountEmail = (store && store.user && store.user.email) || '';
  const [to, setTo] = useState(accountEmail);
  const [state, setState] = useState('idle'); // idle | busy | sent | error
  const [message, setMessage] = useState('');
  const mounted = useRef(true);

  useEffect(() => () => { mounted.current = false; }, []);
  useEffect(() => { setTo((cur) => cur || accountEmail); }, [accountEmail]);

  const valid = /^\S+@\S+\.\S+$/.test(to.trim());
  const send = async (e) => {
    e.preventDefault();
    if (state === 'busy' || !valid) return;
    setState('busy');
    setMessage('');
    try {
      const res = await emailJob(job.id, to.trim(), shareUrl(job.raw));
      if (!mounted.current) return;
      const msg = `Sent to ${(res && res.to) || to.trim()} - it should arrive within seconds`;
      setState('sent');
      setMessage(msg);
      if (showToast) showToast(msg);
    } catch (err) {
      if (!mounted.current) return;
      setState('error');
      setMessage((err && err.message) || 'Could not send the email. Try again.');
    }
  };

  const busy = state === 'busy';
  return (
    <section className="panel spot-card rise" style={{ '--i': 6 }}>
      <div className="panel-head"><h3>Send by email</h3><Icon name="mail" size={18} /></div>
      <form className="field2" onSubmit={send} noValidate>
        <div className="field2-head"><label htmlFor="email-to">Recipient</label></div>
        <input
          id="email-to"
          className="input2"
          type="email"
          placeholder="name@example.com"
          value={to}
          onChange={(e) => { setTo(e.target.value); if (state !== 'busy') setState('idle'); }}
          disabled={busy}
          autoComplete="email"
        />
        <p className="fine2">A link to watch the video and the manual handoff package. Arrives in seconds.</p>
        <button type="submit" className="btn2 btn2--primary btn2--block" disabled={busy || !valid}>
          {busy ? <><i className="spin" />Sending…</> : <><Icon name="mail" size={16} />Send video + handoff</>}
        </button>
        {message && <p className={state === 'error' ? 'err-text' : 'fine2'} role={state === 'error' ? 'alert' : 'status'}>{message}</p>}
      </form>
    </section>
  );
}
