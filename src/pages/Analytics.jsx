import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { COMPLETED_STATES, FAILED_STATES, IN_PROGRESS, LABEL, LANGS, tierName } from '../data.js';
import { analyticsOverview } from '../api/client.js';
import { useStore } from '../store.jsx';
import { ErrorState, PageHeader, Skeleton } from '../components/common.jsx';
import { CountUp } from '../components/deck/parts.jsx';
import Icon from '../components/Icon.jsx';

const COLORS = {
  done: '#f4ebc3', manual_handoff: '#b4e768', approved: '#a9b3a9', published: '#c9cdb5',
  failed: '#1d9aa8', publish_failed: '#8a9696', cancelled: '#4a5656', queued: '#2a3434', publishing: '#c4ea7f',
};
const colorOf = (k) => COLORS[k] || '#7fd1a8';
const R = 70;
const C = 2 * Math.PI * R;
const sum = (obj, keys) => keys.reduce((a, k) => a + (Number(obj[k]) || 0), 0);
const entries = (obj) => Object.entries(obj || {}).map(([label, count]) => ({ label, count: Number(count) || 0 })).sort((a, b) => b.count - a.count);

function Breakdown({ title, rows, total, labeler, mono }) {
  return (
    <section className="panel spot-card rise" style={{ '--i': 9 }}>
      <div className="panel-head"><h3>{title}</h3><span className="mono">{rows.length} {mono}</span></div>
      <div className="brk">
        {rows.map((b, i) => (
          <div className="brk-row" key={b.label} style={{ '--k': i, '--w': `${total ? (b.count / total) * 100 : 0}%` }}>
            <span className="brk-dot" style={{ background: '#7fd1a8' }} />
            <span className="brk-l">{labeler(b.label)}<em className="mono">{b.label}</em></span>
            <span className="brk-track"><i style={{ background: '#7fd1a8' }} /></span>
            <b>{b.count}</b>
          </div>
        ))}
      </div>
    </section>
  );
}

export default function Analytics() {
  const { jobs, anyRunning } = useStore();
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  const load = useCallback(async (silent) => {
    if (!silent) setLoading(true);
    try {
      setData(await analyticsOverview());
      setError('');
    } catch (e) {
      if (e && e.status === 401) return;
      setError((e && e.message) || 'Could not load analytics.');
    } finally {
      setLoading(false);
    }
  }, []);

  // Load on entry; reload quietly whenever the jobs list changes size or a job starts or stops running.
  const loadedOnce = useRef(false);
  useEffect(() => {
    const silent = loadedOnce.current;
    loadedOnce.current = true;
    load(silent);
  }, [load, jobs.length, anyRunning]);

  const view = useMemo(() => {
    if (!data) return null;
    const byStatus = data.by_status || {};
    const bars = entries(byStatus);
    const total = Number.isFinite(Number(data.total_jobs)) ? Number(data.total_jobs) : bars.reduce((a, b) => a + b.count, 0);
    return {
      bars,
      total,
      byTier: entries(data.by_tier),
      byLang: entries(data.by_language),
      completed: sum(byStatus, COMPLETED_STATES),
      failed: sum(byStatus, FAILED_STATES),
      active: sum(byStatus, IN_PROGRESS),
    };
  }, [data]);

  const sub = data && data.note ? data.note : 'Internal workflow metrics only.';

  if (!view) {
    return (
      <>
        <PageHeader kicker="04 / ANALYTICS" title="Overview" sub={error ? sub : 'Loading workflow metrics…'} />
        {error ? (
          <ErrorState title="Could not load analytics" message={error} onRetry={() => load(false)} />
        ) : (
          <div aria-busy={loading} aria-label="Loading analytics">
            <div className="kpis"><div className="kpi"><Skeleton h={40} /></div><div className="kpi"><Skeleton h={40} /></div><div className="kpi"><Skeleton h={40} /></div><div className="kpi"><Skeleton h={40} /></div></div>
            <div className="an-grid"><Skeleton h={260} r={10} /><Skeleton h={260} r={10} /></div>
          </div>
        )}
      </>
    );
  }

  const { bars, total, byTier, byLang, completed, failed, active } = view;
  const rate = total ? Math.round((completed / total) * 100) : 0;
  let acc = 0;

  return (
    <>
      <PageHeader kicker="04 / ANALYTICS" title="Overview" sub={sub} />

      {error && (
        <div className="notice notice--bad live-banner" role="alert">
          <Icon name="alert" size={18} />
          <div><b>Could not refresh analytics</b><span>{error}</span></div>
          <button type="button" className="btn2 btn2--ghost btn2--sm" onClick={() => load(false)}>Retry</button>
        </div>
      )}

      <div className="kpis">
        {[
          { l: 'Total jobs', v: total, ic: 'layers' },
          { l: 'Completion rate', v: rate, suf: '%', ic: 'trend', tone: 'lime' },
          { l: 'In progress', v: active, ic: 'bolt' },
          { l: 'Failed', v: failed, ic: 'alert', tone: 'bad' },
        ].map((k, i) => (
          <div key={k.l} className={'kpi spot-card rise' + (k.tone ? ' kpi--' + k.tone : '')} style={{ '--i': i + 3 }}>
            <span className="stat-ic"><Icon name={k.ic} size={18} /></span>
            <b><CountUp to={k.v} on duration={900} />{k.suf}</b>
            <span>{k.l}</span>
          </div>
        ))}
      </div>

      {total === 0 ? (
        <section className="empty2 rise" style={{ '--i': 7 }}>
          <span className="empty2-ic"><Icon name="analytics" size={24} /></span>
          <h3>No jobs yet</h3>
          <p>Metrics appear here once you have generated a video.</p>
        </section>
      ) : (
        <>
          <div className="an-grid">
            <section className="panel spot-card rise" style={{ '--i': 7 }}>
              <div className="panel-head"><h3>Jobs by status</h3><span className="mono">total_jobs {total}</span></div>
              <div className="donut-wrap">
                <svg className="donut" viewBox="0 0 180 180" role="img" aria-label="Jobs by status">
                  <circle cx="90" cy="90" r={R} className="donut-track" />
                  {bars.map((b) => {
                    const len = (b.count / total) * C;
                    const seg = (
                      <circle
                        key={b.label}
                        cx="90" cy="90" r={R}
                        className="donut-seg"
                        stroke={colorOf(b.label)}
                        strokeDashoffset={-acc}
                        style={{ '--len': Math.max(0, len - 3) }}
                      />
                    );
                    acc += len;
                    return seg;
                  })}
                </svg>
                <div className="donut-center"><b><CountUp to={total} whenVisible duration={800} /></b><span className="mono">jobs</span></div>
              </div>
            </section>

            <section className="panel spot-card rise" style={{ '--i': 8 }}>
              <div className="panel-head"><h3>Breakdown</h3><span className="mono">{bars.length} states</span></div>
              <div className="brk">
                {bars.map((b, i) => (
                  <div className="brk-row" key={b.label} style={{ '--k': i, '--w': `${(b.count / total) * 100}%` }}>
                    <span className="brk-dot" style={{ background: colorOf(b.label) }} />
                    <span className="brk-l">{LABEL[b.label] || b.label}<em className="mono">{b.label}</em></span>
                    <span className="brk-track"><i style={{ background: colorOf(b.label) }} /></span>
                    <b>{b.count}</b>
                  </div>
                ))}
              </div>
            </section>
          </div>

          <div className="an-grid an-grid--pair">
            <Breakdown title="Jobs by tier" rows={byTier} total={total} labeler={tierName} mono="tiers" />
            <Breakdown title="Jobs by language" rows={byLang} total={total} labeler={(l) => (LANGS.find((x) => x.v === l) || { label: l }).label} mono="languages" />
          </div>
        </>
      )}
    </>
  );
}
