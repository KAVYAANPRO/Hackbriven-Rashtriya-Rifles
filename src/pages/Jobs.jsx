import { useMemo, useState } from 'react';
import { ALL_STATUSES, DONE_STATES, FAILED_STATES, IN_PROGRESS, LABEL, LANGS, fmt, stageStates } from '../data.js';
import { sceneImageUrl } from '../api/client.js';
import { useStore } from '../store.jsx';
import { Chips, ErrorState, PageHeader, Pill, Skeleton } from '../components/common.jsx';
import { CountUp } from '../components/deck/parts.jsx';
import Icon from '../components/Icon.jsx';

const all = (list, labeler = (v) => v) => ['all', ...list].map((v) => ({ v, label: v === 'all' ? 'All' : labeler(v) }));

function Stat({ icon, label, value, tone, i }) {
  return (
    <div className={'stat spot-card rise' + (tone ? ' stat--' + tone : '')} style={{ '--i': i }}>
      <span className="stat-ic"><Icon name={icon} size={18} /></span>
      <b><CountUp to={value} on duration={700} /></b>
      <span>{label}</span>
    </div>
  );
}

// Scene 0 of the job when it exists, otherwise the status icon.
function Thumb({ job }) {
  const [broken, setBroken] = useState(false);
  const dead = job.status === 'failed' || job.status === 'cancelled';
  const hasImg = job.readyScenes.includes(0) && !broken;
  return (
    <span className={'thumb2' + (dead && !hasImg ? ' is-empty' : '') + (hasImg ? ' has-img' : '')}>
      {hasImg
        ? <img src={sceneImageUrl(job.raw, 0)} alt="" loading="lazy" onError={() => setBroken(true)} />
        : dead ? <Icon name="x" size={18} /> : <Icon name="play" size={16} />}
    </span>
  );
}

function ListSkeleton() {
  return (
    <section className="job-list" aria-busy="true" aria-label="Loading jobs">
      {[0, 1, 2, 3].map((i) => (
        <div className="job-card job-card--sk" key={i}>
          <Skeleton h={35} w={56} r={5} />
          <span className="job-main"><Skeleton h={14} w="60%" /><Skeleton h={11} w="40%" /><Skeleton h={3} w={150} r={2} /></span>
          <Skeleton h={22} w={80} r={5} />
          <span />
        </div>
      ))}
    </section>
  );
}

export default function Jobs() {
  const { jobs, jobsStatus, jobsError, refreshJobs, filters, setFilters, openJob, go, tiers } = useStore();
  const [q, setQ] = useState('');

  const groups = useMemo(() => {
    const present = new Set(jobs.map((j) => j.status));
    const statuses = [...ALL_STATUSES.filter((s) => present.has(s)), ...[...present].filter((s) => !ALL_STATUSES.includes(s))];
    if (filters.status !== 'all' && !statuses.includes(filters.status)) statuses.push(filters.status);
    return [
      { key: 'status', label: 'Status', options: all(statuses, (v) => LABEL[v] || v) },
      { key: 'lang', label: 'Language', options: all(LANGS.map((l) => l.v)) },
      { key: 'tier', label: 'Tier', options: all(tiers.map((t) => t.v)) },
    ];
  }, [jobs, tiers, filters.status]);

  const rows = useMemo(() => {
    const needle = q.trim().toLowerCase();
    return jobs
      .filter((j) => (filters.status === 'all' || j.status === filters.status)
        && (filters.lang === 'all' || j.language === filters.lang)
        && (filters.tier === 'all' || j.tier === filters.tier)
        && (!needle || j.topic.toLowerCase().includes(needle) || j.id.toLowerCase().includes(needle)))
      .sort((a, b) => (b.created || 0) - (a.created || 0));
  }, [jobs, filters, q]);

  const running = jobs.filter((j) => IN_PROGRESS.includes(j.status)).length;
  const ready = jobs.filter((j) => DONE_STATES.includes(j.status)).length;
  const failed = jobs.filter((j) => FAILED_STATES.includes(j.status)).length;
  const loading = jobs.length === 0 && (jobsStatus === 'idle' || jobsStatus === 'loading');
  const failedLoad = jobs.length === 0 && jobsStatus === 'error';
  const filtering = filters.status !== 'all' || filters.lang !== 'all' || filters.tier !== 'all' || q.trim() !== '';

  return (
    <>
      <PageHeader kicker="02 / LIBRARY" title="Jobs" sub="Every video you have generated, with its pipeline progress.">
        <button type="button" className="btn2 btn2--primary" onClick={() => go('create')}><Icon name="plus" size={17} />New video</button>
      </PageHeader>

      <div className="stats-row">
        <Stat i={3} icon="layers" label="Total jobs" value={jobs.length} />
        <Stat i={4} icon="bolt" label="In progress" value={running} tone="lime" />
        <Stat i={5} icon="shield" label="Ready or shipped" value={ready} />
        <Stat i={6} icon="alert" label="Failed" value={failed} tone="bad" />
      </div>

      {jobsError && jobs.length > 0 && (
        <div className="notice notice--bad live-banner" role="alert">
          <Icon name="alert" size={18} />
          <div><b>Could not refresh jobs</b><span>{jobsError}</span></div>
          <button type="button" className="btn2 btn2--ghost btn2--sm" onClick={() => refreshJobs()}>Retry</button>
        </div>
      )}

      <div className="toolbar rise" style={{ '--i': 7 }}>
        <label className="search">
          <Icon name="search" size={16} />
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search topic or job id" aria-label="Search jobs" />
        </label>
        <div className="filters2">
          {groups.map((g) => (
            <div className="fgroup" key={g.key}>
              <span>{g.label}</span>
              <div><Chips options={g.options} value={filters[g.key]} onChange={(v) => setFilters({ ...filters, [g.key]: v })} /></div>
            </div>
          ))}
        </div>
      </div>

      {loading && <ListSkeleton />}

      {failedLoad && <ErrorState title="Could not load your jobs" message={jobsError} onRetry={() => refreshJobs()} />}

      {!loading && !failedLoad && rows.length > 0 && (
        <section className="job-list">
          {rows.map((j, n) => {
            const states = stageStates(j);
            return (
              <button type="button" key={j.id} className="job-card spot-card rise" style={{ '--i': Math.min(n, 9) + 8 }} onClick={() => openJob(j.id)}>
                <Thumb job={j} />
                <span className="job-main">
                  <b>{j.topic}</b>
                  <span className="mono">{j.id} · {j.language} · {j.tier} · {fmt(j.created)}</span>
                  <span className="mini-track" aria-hidden="true">
                    {states.map((s, i) => <i key={i} className={s} />)}
                  </span>
                </span>
                <Pill status={j.status} />
                <span className="job-go"><Icon name="arrow" size={16} /></span>
              </button>
            );
          })}
        </section>
      )}

      {!loading && !failedLoad && rows.length === 0 && (
        <section className="empty2 rise" style={{ '--i': 8 }}>
          <span className="empty2-ic"><Icon name={filtering ? 'search' : 'create'} size={24} /></span>
          <h3>{filtering ? 'No jobs match' : 'No videos yet'}</h3>
          <p>{filtering ? 'Clear the filters or create a new video.' : 'Create your first video and it will show up here.'}</p>
          <button type="button" className="btn2 btn2--primary" onClick={() => go('create')}>Create a video</button>
        </section>
      )}
    </>
  );
}
