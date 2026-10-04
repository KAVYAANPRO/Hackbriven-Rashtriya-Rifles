import { useState } from 'react';
import { LANGS, fmt, planFor, planOf } from '../data.js';
import { toMs } from '../api/adapt.js';
import { useStore } from '../store.jsx';
import { PageHeader, Seg } from '../components/common.jsx';
import Icon from '../components/Icon.jsx';

export default function Settings() {
  const {
    apiKey, setApiKey, geminiKey, setGeminiKey, lang, setLang, tier, setTier, tiers, tiersAllowed, pricing,
    user, plan, credits, planExpiresAt, providers, signOut, go,
  } = useStore();
  const isTierAllowed = (t) => !tiersAllowed || tiersAllowed.includes(t);
  const [reveal, setReveal] = useState(false);
  const [revealG, setRevealG] = useState(false);
  const legacyAuth = !!(providers && providers.auth && providers.auth.enabled);
  const email = (user && user.email) || '';
  const expiry = toMs(planExpiresAt);
  let n = 3;

  return (
    <>
      <PageHeader kicker="06 / SETTINGS" title="Settings" sub="Your account, and the defaults that pre-fill the Create screen." />

      <div className="set-grid">
        {legacyAuth && (
          <section className="panel spot-card rise" style={{ '--i': n++ }}>
            <div className="panel-head"><h3>API key</h3><Icon name="key" size={18} /></div>
            <p className="muted2">This server also accepts a shared API key. If you set one, it is kept in this browser and sent as a Bearer token only when you are not signed in with an account. It is never displayed back.</p>
            <div className="field2">
              <div className="field2-head"><label htmlFor="apikey">Key</label><span className={'key-state' + (apiKey ? ' is-set' : '')}><i />{apiKey ? 'Saved in this browser' : 'No key set'}</span></div>
              <div className="input-wrap">
                <input id="apikey" className="input2" type={reveal ? 'text' : 'password'} placeholder="Paste key" value={apiKey} onChange={(e) => setApiKey(e.target.value)} autoComplete="off" />
                <button type="button" className="icon-btn" onClick={() => setReveal(!reveal)} aria-label={reveal ? 'Hide key' : 'Show key'} aria-pressed={reveal}><Icon name="eye" size={17} /></button>
              </div>
            </div>
          </section>
        )}

        <section className="panel spot-card rise" style={{ '--i': n++ }}>
          <div className="panel-head"><h3>Gemini API key</h3><Icon name="create" size={18} /></div>
          <p className="muted2">Optional. Used only by the Boost button on the Create screen. The key is stored only in this browser and sent directly to Google when you press Boost; it never goes to our server. Without it, Boost uses the server&apos;s own providers.</p>
          <div className="field2">
            <div className="field2-head"><label htmlFor="geminikey">Key</label><span className={'key-state' + (geminiKey ? ' is-set' : '')}><i />{geminiKey ? 'Saved in this browser' : 'No key set'}</span></div>
            <div className="input-wrap">
              <input id="geminikey" className="input2" type={revealG ? 'text' : 'password'} placeholder="Paste Gemini key" value={geminiKey} onChange={(e) => setGeminiKey(e.target.value)} autoComplete="off" spellCheck={false} />
              <button type="button" className="icon-btn" onClick={() => setRevealG(!revealG)} aria-label={revealG ? 'Hide Gemini key' : 'Show Gemini key'} aria-pressed={revealG}><Icon name="eye" size={17} /></button>
            </div>
          </div>
        </section>

        <section className="panel spot-card rise" style={{ '--i': n++ }}>
          <div className="panel-head"><h3>Defaults</h3><span className="mono">stored locally</span></div>
          <div className="field2">
            <div className="field2-head"><label>Language</label></div>
            <Seg label="Default language" options={LANGS.map((l) => ({ v: l.v, label: l.label }))} value={lang} onChange={setLang} />
          </div>
          <div className="field2">
            <div className="field2-head">
              <label>Motion tier</label>
              {tiers.some((t) => !isTierAllowed(t.v)) && (
                <button type="button" className="link-btn" onClick={() => go('credits')}>Upgrade to unlock more</button>
              )}
            </div>
            <Seg
              label="Default motion tier"
              value={tier}
              onChange={setTier}
              options={tiers.map((t) => {
                const ok = isTierAllowed(t.v);
                const need = !ok ? planFor(pricing, t.v) : null;
                return { v: t.v, label: t.label, disabled: !ok, note: !ok ? `Needs ${need ? need.name : 'a paid plan'}` : '' };
              })}
            />
          </div>
        </section>

        <section className="panel spot-card rise" style={{ '--i': n++ }}>
          <div className="panel-head"><h3>Account</h3><Icon name="user" size={18} /></div>
          <div className="acct">
            <span className="st-avatar st-avatar--lg">{email ? email[0].toUpperCase() : '?'}</span>
            <div>
              <b>{email}</b>
              <span className="mono">signed in</span>
            </div>
          </div>
          <div className="qrows">
            <div><span>Plan</span><b className="mono">{planOf(pricing, plan).name}</b></div>
            <div><span>Plan expires</span><b className="mono">{expiry ? fmt(expiry) : plan === 'free' ? 'never' : '—'}</b></div>
            <div><span>Credit balance</span><b className="mono">{credits == null ? '—' : credits}</b></div>
          </div>
          <button type="button" className="btn2 btn2--ghost" onClick={signOut}><Icon name="logout" size={16} />Sign out</button>
        </section>
      </div>
    </>
  );
}
