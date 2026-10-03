import { useEffect, useState } from 'react';
import {
  ORDER, STAGE_NAMES, VIDEO_STATES, fmt, formatList, hms, providerName, resolutionOf, stageStates, styleLabel,
} from '../data.js';
import { getQualityReport, handoffUrl, sceneImageUrl, videoUrl } from '../api/client.js';
import { adaptQuality } from '../api/adapt.js';
import { useNow, useStore } from '../store.jsx';
import { ErrorState, Pill, Skeleton } from '../components/common.jsx';
import Icon from '../components/Icon.jsx';
import DownloadMenu from '../components/DownloadMenu.jsx';

const NOT_CANCELLABLE = ['approved', 'manual_handoff', 'published', 'failed', 'cancelled', 'publish_failed'];

function buildStages(j, now) {
  const states = stageStates(j);
  const at = {};
  j.history.forEach((h) => { at[h.status] = h.at; });
  return STAGE_NAMES.map((label, i) => {
    const state = states[i];
    const started = at[ORDER[i]];
    const nextAt = at[ORDER[i + 1]];
    let dur = '—';
    if (started && nextAt) dur = hms(nextAt - started);
    else if (started && state === 'active') dur = hms(now - started);
    const sub = state === 'active' ? `${dur === '—' ? '' : dur + ' · '}running` : state === 'failed' ? 'stopped' : state === 'stopped' ? 'cancelled' : state === 'pending' ? 'waiting' : dur;
    return { n: '0' + (i + 1), label, state, sub };
  });
}

function SceneTile({ j, scene, i }) {
  const idx = scene && scene.index != null ? scene.index : i;
  const ready = j.readyScenes.includes(idx);
  const [broken, setBroken] = useState(false);
  return (
    <div className={'scene' + (ready ? ' is-ready' : '')}>
      {ready && !broken && <img src={sceneImageUrl(j.raw, idx)} alt={`Scene ${idx + 1}`} loading="lazy" onError={() => setBroken(true)} />}
      <span className="mono">{ready ? `scene ${idx + 1}` : 'rendering'}</span>
    </div>
  );
}

function SceneTiles({ j }) {
  if (!j.planScenes.length) return <p className="fine2">The scene plan appears once the Intelligence stage finishes.</p>;
  return (
    <div className="scene-grid">
      {j.planScenes.map((s, i) => <SceneTile key={s.index ?? i} j={j} scene={s} i={i} />)}
    </div>
  );
}

function VideoPlayer({ j }) {
  const [failed, setFailed] = useState(false);
  const poster = j.readyScenes.includes(0) ? sceneImageUrl(j.raw, 0) : undefined;
  if (!j.hasVideo) {
    return <div className="player player--empty"><span className="mono">The video file is not available for this job.</span></div>;
  }
  return (
    <>
      <video
        className="player-video"
        controls
        playsInline
        preload="metadata"
        poster={poster}
        src={videoUrl(j.raw)}
        onError={() => setFailed(true)}
      />
      {failed && (
        <p className="err-text" role="alert">
          The video could not be played in the browser. You can still{' '}
          <a href={videoUrl(j.raw, { download: true })} download>download it</a>.
        </p>
      )}
    </>
  );
}

function Storyboard({ j }) {
  if (!j.hook && !j.sceneList.length) return null;
  return (
    <section className="panel spot-card rise" style={{ '--i': 5 }}>
      <div className="panel-head"><h3>Script &amp; storyboard</h3><span className="mono">{j.sceneList.length} scenes</span></div>
      {j.hook && <div className="hook-line"><span className="mono">hook</span>{j.hook}</div>}
      {j.mood && <div className="hook-line"><span className="mono">mood</span>{j.mood}</div>}
      {j.sceneList.length > 0 && (
        <ol className="story">
          {j.sceneList.map((s, i) => {
            const idx = s.index != null ? s.index : i;
            const ready = j.readyScenes.includes(idx);
            return (
              <li key={idx} className="story-row">
                <span className="story-img">
                  {ready ? <img src={sceneImageUrl(j.raw, idx)} alt={`Scene ${idx + 1}`} loading="lazy" /> : <em className="mono">{idx + 1}</em>}
                </span>
                <div className="story-body">
                  <div className="story-top">
                    <b className="mono">scene {idx + 1}</b>
                    {s.duration_seconds != null && <span className="mono">{Number(s.duration_seconds).toFixed(1)} s</span>}
                  </div>
                  {s.narration && <p className="story-n">{s.narration}</p>}
                  {s.image_prompt && <p className="story-p"><span className="mono">image prompt</span>{s.image_prompt}</p>}
                </div>
              </li>
            );
          })}
        </ol>
      )}
    </section>
  );
}

const firstLine = (t) => String(t).split(/\r?\n/)[0];

function ProvidersUsed({ j }) {
  if (!j.providerEvents.length) return null;
  return (
    <section className="panel spot-card rise" style={{ '--i': 6 }}>
      <div className="panel-head"><h3>Providers used</h3><span className="mono">{j.providerEvents.length} attempts</span></div>
      <ul className="prov-list">
        {j.providerEvents.map((e, i) => (
          <li key={i} className={e.ok ? 'is-ok' : 'is-bad'}>
            <span className="mono prov-st">{e.stage}</span>
            <b>{providerName(e.provider)}</b>
            <span className={'verdict2 ' + (e.ok ? 'is-ok' : 'is-bad')}><Icon name={e.ok ? 'check' : 'x'} size={12} />{e.ok ? 'ok' : 'failed'}</span>
            {!e.ok && e.error && <p className="prov-err mono" title={e.error}>{firstLine(e.error)}</p>}
          </li>
        ))}
      </ul>
    </section>
  );
}

function History({ j }) {
  const [open, setOpen] = useState(true);
  return (
    <section className="panel spot-card">
      <button type="button" className="panel-head panel-head--btn" onClick={() => setOpen(!open)} aria-expanded={open}>
        <h3>Stage history</h3>
        <span className="mono">{open ? 'hide' : 'show'}</span>
      </button>
      {open && (
        <ol className="timeline">
          {j.history.map((h, i) => (
            <li key={i} style={{ '--i': i }}>
              <i />
              <b className="mono">
                {h.status}
                {h.stage && h.stage !== h.status ? ` · ${h.stage}` : ''}
                {h.note ? ` · ${h.note}` : ''}
              </b>
              <span className="mono">{fmt(h.at)}</span>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}

function DetailSkeleton() {
  return (
    <div aria-busy="true" aria-label="Loading job">
      <Skeleton h={14} w={90} style={{ marginBottom: 16 }} />
      <Skeleton h={30} w="70%" style={{ marginBottom: 14 }} />
      <Skeleton h={26} w="50%" style={{ marginBottom: 20 }} />
      <Skeleton h={78} r={10} style={{ marginBottom: 20 }} />
      <div className="jd-cols">
        <div className="jd-left"><Skeleton h={260} r={10} /></div>
        <div className="jd-right"><Skeleton h={160} r={10} /><Skeleton h={120} r={10} /></div>
      </div>
    </div>
  );
}

export default function JobDetail() {
  const {
    job: j, jobId, jobStatus, jobError, jobStale, jobAction, retryJob, refreshJob, go, approver, setApprover,
    approve, publish, retryAsNew, setCancelOpen, cancelOpen, pricing,
  } = useStore();
  const st = j ? j.status : '';
  const now = useNow(!!j && (j.live || st === 'publishing'));

  // Quality report: fetch once the video exists; fall back to the report embedded in the job.
  const showQ = !!j && VIDEO_STATES.includes(st);
  const jid = j ? j.id : null;
  const [qr, setQr] = useState({ id: null, report: null, error: '', loading: false });
  const [qTick, setQTick] = useState(0);
  useEffect(() => {
    if (!showQ || !jid) return undefined;
    let dead = false;
    setQr((p) => ({ id: jid, report: p.id === jid ? p.report : null, error: '', loading: true }));
    getQualityReport(jid)
      .then((r) => { if (!dead) setQr({ id: jid, report: adaptQuality(r), error: '', loading: false }); })
      .catch((e) => { if (!dead) setQr({ id: jid, report: null, error: (e && e.message) || 'Could not load the quality report.', loading: false }); });
    return () => { dead = true; };
  }, [showQ, jid, qTick]);

  if (!j) {
    if (jobStatus === 'error' && jobError) {
      const missing = jobError.status === 404;
      return (
        <ErrorState
          title={missing ? 'Job not found' : 'Could not load this job'}
          message={missing ? `No job with id ${jobId} exists for your account.` : jobError.message}
          onRetry={missing ? undefined : retryJob}
        >
          <button type="button" className="btn2 btn2--ghost" onClick={() => go('jobs')}><Icon name="back" size={16} />Back to jobs</button>
        </ErrorState>
      );
    }
    return <DetailSkeleton />;
  }

  const running = j.live;
  const done = VIDEO_STATES.includes(st);
  const mine = qr.id === j.id ? qr : { report: null, error: '', loading: false };
  const q = mine.report || j.quality;
  const stages = buildStages(j, now);
  const meta = [['id', j.id], ['language', j.language], ['tier', j.tier], ['created', fmt(j.created)], ['updated', fmt(j.updated)]];
  if (j.style) meta.push(['style', styleLabel(pricing, j.style), j.style === 'custom' && j.styleText ? j.styleText : undefined]);
  if (j.resolution) meta.push(['resolution', (resolutionOf(pricing, j.resolution) || {}).label || j.resolution]);
  if (j.referenceCount) meta.push(['reference images', String(j.referenceCount)]);
  const formats = formatList(pricing);
  const busy = jobAction.busy;

  return (
    <>
      <button type="button" className="back2 rise" style={{ '--i': 0 }} onClick={() => go('jobs')}>
        <Icon name="back" size={16} />All jobs
      </button>

      <header className="jd-head rise" style={{ '--i': 1 }}>
        <h1 title={j.topic}>{j.topic}</h1>
        <Pill status={st} large />
      </header>
      <div className="meta2 rise" style={{ '--i': 2 }}>
        {meta.map(([k, v, title]) => (<span key={k} title={title}><em>{k}</em><b className="mono">{v}</b></span>))}
      </div>

      {jobStale && (
        <div className="notice notice--bad live-banner" role="alert">
          <Icon name="alert" size={18} />
          <div><b>Connection problem</b><span>{jobStale} Retrying automatically while the job runs.</span></div>
          <button type="button" className="btn2 btn2--ghost btn2--sm" onClick={() => refreshJob(j.id)}>Retry now</button>
        </div>
      )}

      {jobAction.error && !cancelOpen && (
        <div className="notice notice--bad live-banner" role="alert">
          <Icon name="alert" size={18} />
          <div><b>That did not work</b><span>{jobAction.error}</span></div>
        </div>
      )}

      <section className="track rise" style={{ '--i': 3 }} aria-label="Pipeline stages">
        {stages.map((s) => (
          <div className={`tstep is-${s.state}`} key={s.n}>
            <span className="tstep-bar"><i /></span>
            <span className="tstep-ic">
              {s.state === 'done' && <Icon name="check" size={13} />}
              {s.state === 'active' && <i className="spin" />}
              {(s.state === 'failed' || s.state === 'stopped') && <Icon name="x" size={13} />}
              {s.state === 'pending' && <em>{s.n}</em>}
            </span>
            <b>{s.label}</b>
            <span className="mono">{s.sub}</span>
          </div>
        ))}
      </section>

      <div className="jd-cols">
        <div className="jd-left">
          {running && (
            <section className="panel spot-card live-panel rise" style={{ '--i': 4 }} aria-live="polite">
              <div className="panel-head">
                <h3><i className="live" />Live</h3>
                <span className="mono">{j.created ? `${hms(now - j.created)} elapsed` : 'elapsed —'}</span>
              </div>
              <div className="mono live-label">script.hook</div>
              <div className="live-hook">
                {j.hook ? <>{j.hook}<span className="caret2" /></> : <span className="wait">Waiting for the script stage…</span>}
              </div>
              <div className="mono live-label">scene_plan.scenes · {j.scenes || '—'}</div>
              <SceneTiles j={j} />
              <p className="fine2">Polling GET /jobs/:id every 1.5s while the job runs. Times are real elapsed time; no percentage is estimated.</p>
            </section>
          )}

          {done && (
            <section className="panel spot-card rise" style={{ '--i': 4 }}>
              <div className="panel-head">
                <h3>Result</h3>
                {j.hasVideo && (formats.length > 0
                  ? <DownloadMenu key={j.id} job={j} formats={formats} />
                  : (
                    <a className="btn2 btn2--ghost btn2--sm" href={videoUrl(j.raw, { download: true })} download>
                      <Icon name="download" size={14} />Download video
                    </a>
                  ))}
              </div>
              <VideoPlayer j={j} />
              {j.hook && <div className="hook-line"><span className="mono">hook</span>{j.hook}</div>}
            </section>
          )}

          {st === 'failed' && (
            <section className="notice notice--bad notice--block rise" style={{ '--i': 4 }} role="alert">
              <Icon name="alert" size={22} />
              <div>
                <h3>Job failed</h3>
                <p className="mono">error_stage: {j.errorStageRaw || '—'}<br />error_reason: {j.errorReason || '—'}</p>
                <button type="button" className="btn2 btn2--primary" onClick={() => retryAsNew(j)}><Icon name="refresh" size={16} />Retry as new job</button>
              </div>
            </section>
          )}

          {st === 'cancelled' && (
            <section className="notice notice--muted notice--block rise" style={{ '--i': 4 }}>
              <Icon name="x" size={22} />
              <div><h3>Cancelled</h3><p>This job was cancelled and will not continue.</p></div>
            </section>
          )}

          {st === 'publish_failed' && (
            <section className="notice notice--bad notice--block rise" style={{ '--i': 5 }} role="alert">
              <Icon name="alert" size={22} />
              <div>
                <h3>Publish failed</h3>
                <p className="mono">publish_error: {j.publishError || '—'}</p>
                <button type="button" className="btn2 btn2--primary" disabled={!!busy} onClick={() => publish(j.id)}>
                  {busy === 'publish' ? <><i className="spin" />Retrying…</> : <><Icon name="refresh" size={16} />Retry publish</>}
                </button>
              </div>
            </section>
          )}

          {st === 'manual_handoff' && (
            <section className="handoff2 rise" style={{ '--i': 5 }}>
              <div className="mono handoff2-st"><i className="live" />STATUS · manual_handoff</div>
              <h3>Manual handoff — not automatically published</h3>
              <dl>
                {(j.note
                  ? [['Title', j.note.title], ['Caption', j.note.caption], ['Language', j.note.language], ['Motion tier', j.note.tier]]
                  : [['Note', 'The handoff note is not available for this job.']]
                ).map(([k, v]) => (<div key={k}><dt>{k}</dt><dd>{v}</dd></div>))}
              </dl>
              {j.note && j.note.text && <pre className="handoff-pre">{j.note.text}</pre>}
              <a className="btn2 btn2--primary" href={handoffUrl(j.raw)} download>
                <Icon name="download" size={16} />Download handoff package
              </a>
            </section>
          )}

          {st === 'published' && (
            <section className="notice notice--ok notice--block rise" style={{ '--i': 5 }}>
              <Icon name="check" size={22} />
              <div><h3>Published</h3><p className="mono">published_at: {fmt(j.publishedAt)}</p></div>
            </section>
          )}

          {st === 'publishing' && (
            <section className="notice notice--live notice--block rise" style={{ '--i': 5 }} aria-live="polite">
              <i className="spin" />
              <div><h3>Publishing…</h3><p>Waiting for the backend result.</p></div>
            </section>
          )}

          <Storyboard j={j} />
        </div>

        <div className="jd-right">
          {done && (q || mine.loading || mine.error) && (
            <section className="panel spot-card rise" style={{ '--i': 5 }}>
              <div className="panel-head">
                <h3>Quality report</h3>
                {q && <span className={'verdict2 ' + (q.passed ? 'is-ok' : 'is-bad')}><Icon name={q.passed ? 'check' : 'x'} size={13} />{q.passed ? 'Passed' : 'Failed'}</span>}
              </div>
              {!q && mine.loading && <div className="live-skel"><Skeleton h={14} /><Skeleton h={14} /><Skeleton h={14} /></div>}
              {!q && !mine.loading && mine.error && (
                <>
                  <p className="err-text" role="alert">{mine.error}</p>
                  <button type="button" className="btn2 btn2--ghost btn2--sm" onClick={() => setQTick((n) => n + 1)}><Icon name="refresh" size={14} />Retry</button>
                </>
              )}
              {q && (
                <>
                  <div className="qrows">
                    {[['Resolution', q.resolution], ['Duration', q.duration], ['Audio track', q.audio]].map(([k, v]) => (
                      <div key={k}><span>{k}</span><b className="mono">{v}</b></div>
                    ))}
                  </div>
                  {q.reasons.length > 0 && (
                    <ul className="reasons">{q.reasons.map((x) => <li key={x}><Icon name="alert" size={14} />{x}</li>)}</ul>
                  )}
                </>
              )}
            </section>
          )}

          {st === 'done' && (
            <section className="panel spot-card approve rise" style={{ '--i': 6 }}>
              <div className="panel-head"><h3>Approve</h3><Icon name="shield" size={18} /></div>
              <div className="field2">
                <div className="field2-head"><label htmlFor="approver">Approver name or email</label></div>
                <input id="approver" className="input2" placeholder="you@company.com" value={approver} onChange={(e) => setApprover(e.target.value)} disabled={!!busy} />
              </div>
              <button type="button" className="btn2 btn2--primary btn2--block" disabled={!approver.trim() || !!busy} onClick={() => approve(j.id)}>
                {busy === 'approve' ? <><i className="spin" />Approving…</> : <><Icon name="check" size={17} />Approve video</>}
              </button>
            </section>
          )}

          {j.approvedBy && (
            <section className="panel spot-card rise" style={{ '--i': 6 }}>
              <div className="panel-head"><h3>Approval receipt</h3><Icon name="shield" size={18} /></div>
              <div className="qrows">
                <div><span>approved_by</span><b className="mono">{j.approvedBy}</b></div>
                <div><span>approved_at</span><b className="mono">{fmt(j.approvedAt)}</b></div>
              </div>
              {st === 'approved' && (
                <button type="button" className="btn2 btn2--primary btn2--block" disabled={!!busy} onClick={() => publish(j.id)}>
                  {busy === 'publish' ? <><i className="spin" />Publishing…</> : <><Icon name="arrow" size={17} />Publish</>}
                </button>
              )}
            </section>
          )}

          <ProvidersUsed j={j} />

          {!NOT_CANCELLABLE.includes(st) && (
            <button type="button" className="btn2 btn2--ghost btn2--block rise" style={{ '--i': 7 }} disabled={busy === 'cancel'} onClick={() => setCancelOpen(true)}>
              {busy === 'cancel' ? <><i className="spin" />Cancelling…</> : 'Cancel job'}
            </button>
          )}

          <History j={j} />
        </div>
      </div>
    </>
  );
}
