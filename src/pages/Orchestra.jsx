import { useEffect, useMemo, useState } from 'react';
import { providerName } from '../data.js';
import { useStore } from '../store.jsx';
import { ErrorState, PageHeader, Skeleton } from '../components/common.jsx';
import Icon from '../components/Icon.jsx';

const STAGES = [['script', 'Script'], ['image', 'Image'], ['voice', 'Voice'], ['captions', 'Captions'], ['motion', 'Motion']];

// key_pool_size is a number, or a {provider: n} map.
const poolText = (p) => (typeof p === 'object'
  ? Object.entries(p).map(([k, v]) => `${providerName(k)}: ${v} keys`).join(' · ')
  : `${p} key${p === 1 ? '' : 's'} in pool`);

// Which chain does a recorded event belong to? Events carry stages like "generation.image".
// Match on the provider id first (ids are unique across chains), then on the stage text.
function eventStage(e, providers) {
  if (providers) {
    const hit = STAGES.find(([k]) => providers[k] && (providers[k].chain || []).includes(e.provider));
    if (hit) return hit[0];
  }
  const v = String(e.stage || '').toLowerCase();
  if (/story|script|intelligence/.test(v)) return 'script';
  if (/image/.test(v)) return 'image';
  if (/voice|tts/.test(v)) return 'voice';
  if (/caption|whisper/.test(v)) return 'captions';
  if (/motion|composition|video/.test(v)) return 'motion';
  return v;
}

// Replay of real recorded attempts: `shown` = events revealed so far, in order.
function nodeView(stage, name, idx, configured, firstOk, shown) {
  let cls = 'fallback';
  let sub = 'Fallback · idle';
  if (!configured) { cls = 'off'; sub = 'Not configured'; }
  else if (idx === firstOk) { cls = 'primary'; sub = 'Active primary'; }
  if (shown) {
    const mine = shown.filter((e) => e.stage === stage && e.provider === name);
    if (mine.length) {
      const last = mine[mine.length - 1];
      const earlierFail = shown.some((e) => e.stage === stage && !e.ok && e.provider !== name);
      const laterOk = shown.some((e, i) => e.stage === stage && e.ok && i > shown.lastIndexOf(last));
      if (!last.ok) {
        const newest = shown[shown.length - 1] === last;
        cls = 'failed' + (newest ? ' flash' : '');
        sub = laterOk ? 'Failed · rerouted' : 'Failed';
      } else {
        cls = 'primary';
        sub = earlierFail ? 'Took over' : 'Succeeded';
      }
    }
  }
  return { cls, sub };
}

export default function Orchestra() {
  const { providers, providersError, refreshProviders, systemReady, pricing, jobs, refreshJobs } = useStore();
  const [step, setStep] = useState(-1);

  useEffect(() => {
    refreshProviders();
    refreshJobs({ silent: true });
  }, [refreshProviders, refreshJobs]);

  // The most recent job that recorded provider attempts.
  const replayJob = useMemo(
    () => [...jobs].filter((j) => j.providerEvents.length).sort((a, b) => (b.created || 0) - (a.created || 0))[0] || null,
    [jobs],
  );
  const events = useMemo(
    () => (replayJob ? replayJob.providerEvents.map((e) => ({ ...e, stage: eventStage(e, providers) })) : []),
    [replayJob, providers],
  );
  const replaying = step >= 0 && replayJob;

  useEffect(() => {
    if (step < 0) return undefined;
    const id = setTimeout(() => setStep((s) => (s >= events.length + 2 ? -1 : s + 1)), 900);
    return () => clearTimeout(id);
  }, [step, events.length]);

  const shown = replaying ? events.slice(0, Math.min(step, events.length)) : null;
  const latest = shown && shown.length ? shown[shown.length - 1] : null;

  const checks = systemReady.checks || {};
  const boolWord = (v, yes, no) => (v === true ? yes : v === false ? no : '—');
  const payConf = providers && providers.payments ? providers.payments.razorpay_configured : pricing && pricing.payments ? pricing.payments.razorpay_configured : undefined;
  const flags = providers ? [
    { k: 'Accounts', v: boolWord(providers.accounts && providers.accounts.enabled, 'Enabled', 'Disabled') },
    { k: 'Shared API key auth', v: boolWord(providers.auth && providers.auth.enabled, 'Enabled', 'Off') },
    { k: 'MongoDB persistence', v: boolWord(providers.persistence && providers.persistence.mongodb_configured, 'Configured', 'Not configured') },
    { k: 'FFmpeg', v: boolWord(checks.ffmpeg, 'Available', 'Missing') },
    { k: 'MongoDB connection', v: checks.mongodb === null ? 'Not used' : boolWord(checks.mongodb, 'Connected', 'Unreachable') },
    { k: 'Razorpay', v: boolWord(payConf, 'Configured', 'Not configured') },
  ] : [];

  return (
    <>
      <PageHeader kicker="03 / AI ORCHESTRA" title="Provider chains" sub="Each stage tries its providers in order. If one fails, the next takes over and the job continues.">
        <button
          type="button"
          className="btn2 btn2--primary"
          onClick={() => setStep(0)}
          disabled={step >= 0 || !replayJob}
          title={replayJob ? `Replays the recorded attempts of ${replayJob.id}` : 'Run a job to record real provider attempts'}
        >
          <Icon name="refresh" size={16} />{step >= 0 ? 'Replaying…' : 'Replay a reroute'}
        </button>
      </PageHeader>

      <div className="legend2 rise" style={{ '--i': 3 }}>
        <span><i className="lg lg--primary" />Active primary</span>
        <span><i className="lg lg--fallback" />Configured fallback</span>
        <span><i className="lg lg--off" />Not configured</span>
        <span><i className="lg lg--failed" />Failed attempt (replay)</span>
      </div>

      {!replayJob && <p className="fine2 orch-hint">Run a job to record real provider attempts.</p>}
      {replaying && (
        <p className="fine2 orch-hint" role="status" aria-live="polite">
          Replaying real attempts from <b className="mono">{replayJob.id}</b>
          {latest ? <> · {latest.stage} → {providerName(latest.provider)} {latest.ok ? 'succeeded' : `failed${latest.error ? `: ${latest.error}` : ''}`}</> : ' · starting'}
        </p>
      )}

      {!providers && providersError && <ErrorState title="Could not load provider status" message={providersError} onRetry={refreshProviders} />}
      {!providers && !providersError && (
        <section className="chains2" aria-busy="true" aria-label="Loading provider chains">
          {STAGES.map(([k]) => <Skeleton key={k} h={110} r={10} />)}
        </section>
      )}

      {providers && (
        <>
          {providersError && (
            <div className="notice notice--bad live-banner" role="alert">
              <Icon name="alert" size={18} />
              <div><b>Could not refresh provider status</b><span>{providersError}</span></div>
              <button type="button" className="btn2 btn2--ghost btn2--sm" onClick={refreshProviders}>Retry</button>
            </div>
          )}
          <section className="chains2">
            {STAGES.map(([key, label], ci) => {
              const s = providers[key];
              if (!s) {
                return (
                  <div className="chain2 spot-card rise" style={{ '--i': ci + 4 }} key={key}>
                    <div className="chain2-head"><span className="mono">0{ci + 1}</span><h3>{label}</h3></div>
                    <p className="fine2">The server did not report this stage.</p>
                  </div>
                );
              }
              const chain = s.chain || [];
              const conf = s.configured || {};
              const firstOk = chain.findIndex((n) => conf[n]);
              return (
                <div className="chain2 spot-card rise" style={{ '--i': ci + 4 }} key={key}>
                  <div className="chain2-head">
                    <span className="mono">0{ci + 1}</span><h3>{label}</h3>
                    {key === 'motion' && s.key_pool_size != null && <span className="mono chain2-meta">{poolText(s.key_pool_size)}</span>}
                  </div>
                  <div className="chain2-nodes">
                    {chain.map((name, ni) => {
                      const v = nodeView(key, name, ni, !!conf[name], firstOk, shown);
                      return (
                        <div key={name} className="node-wrap">
                          <div className={'pnode ' + v.cls}>
                            <b className="mono">{providerName(name)}</b>
                            <span>{v.sub}</span>
                          </div>
                          {ni < chain.length - 1 && <span className={'conn' + (v.cls.startsWith('primary') ? ' is-live' : '')} aria-hidden="true" />}
                        </div>
                      );
                    })}
                  </div>
                </div>
              );
            })}
          </section>

          <section className="flags2">
            {flags.map((f, i) => (
              <div className="flag2 spot-card rise" style={{ '--i': i + 9 }} key={f.k}>
                <span className="mono">{f.k}</span>
                <b>{f.v}</b>
              </div>
            ))}
          </section>
        </>
      )}
      <p className="fine2">Chains and configured state come from GET /providers/status; FFmpeg and MongoDB connection from GET /ready. The replay shows the real provider attempts recorded on your most recent job.</p>
    </>
  );
}
