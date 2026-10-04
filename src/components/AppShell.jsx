import { useEffect, useRef } from 'react';
import { NAV, navFor, formatPrice, hms, periodLabel, planOf, tierName } from '../data.js';
import { useNow, useStore } from '../store.jsx';
import Icon from './Icon.jsx';
import { LogoMark } from './Logo.jsx';
import { ErrorState } from './common.jsx';
import { CountUp } from './deck/parts.jsx';
import { usePlanDialog } from './planDialogBus.js';
import { useTheme } from '../theme.js';

const NAV_ICON = { create: 'create', jobs: 'jobs', orchestra: 'orchestra', analytics: 'analytics', credits: 'credits', settings: 'settings' };

function ActiveChip({ job }) {
  const now = useNow();
  const { openJob } = useStore();
  return (
    <button type="button" className="chip-live" onClick={() => openJob(job.id)}>
      <i className="live" />
      <span>Job running</span>
      <b className="mono">{job.created ? hms(now - job.created) : '—'}</b>
    </button>
  );
}

function Sidebar() {
  const { route, go, credits, user, plan, pricing } = useStore();
  const nav = navFor(user);
  const current = route === 'job' ? 'jobs' : route;
  const index = Math.max(0, nav.findIndex(([, k]) => k === current));
  const email = (user && user.email) || '';
  const planInfo = planOf(pricing, plan);
  const level = credits != null && planInfo.credits ? Math.min(100, (credits / planInfo.credits) * 100) : 0;

  return (
    <aside className="st-side">
      <button type="button" className="st-brand" onClick={() => go('create')}>
        <LogoMark size={22} />
        <span>IdeaFeed AI</span>
      </button>

      <nav className="st-nav" aria-label="Main" style={{ '--i': index }}>
        <i className="st-nav-ind" />
        {nav.map(([label, key], n) => (
          <button
            key={key}
            type="button"
            className={'st-nav-item' + (current === key ? ' is-on' : '')}
            aria-current={current === key ? 'page' : undefined}
            onClick={() => go(key)}
            style={{ '--n': n }}
          >
            <Icon name={NAV_ICON[key]} />
            <span>{label}</span>
          </button>
        ))}
      </nav>

      <div className="st-foot">
        <button type="button" className="st-credits spot-card" onClick={() => go('credits')}>
          <span className="st-credits-top">
            <span className="pl-side-label">
              <span className="kicker">CREDITS</span>
              <span className="pl-side-plan">{planInfo.name}</span>
            </span>
            <Icon name="arrow" size={14} />
          </span>
          <b className="st-credits-n">{credits == null ? '—' : <CountUp to={credits} on duration={600} />}</b>
          <span className="st-meter"><i style={{ width: `${level}%` }} /></span>
          {plan === 'free' && (
            <span className="pl-side-up" onClick={(e) => { e.stopPropagation(); go('credits'); }}>Upgrade</span>
          )}
        </button>
        <div className="st-user">
          <span className="st-avatar">{email ? email[0].toUpperCase() : '?'}</span>
          <span className="st-user-mail" title={email}>{email}</span>
        </div>
      </div>
    </aside>
  );
}

function statusView(sys) {
  if (sys.state === 'ok') return { cls: 'ok', label: 'All systems ready' };
  if (sys.state === 'degraded') {
    return { cls: 'warn', label: sys.failing.length ? `Degraded: ${sys.failing.join(', ')}` : 'Degraded' };
  }
  if (sys.state === 'down') return { cls: 'bad', label: 'Backend unreachable' };
  return { cls: 'wait', label: 'Checking…' };
}

function TopBar({ topRef }) {
  const { route, jobs, credits, go, signOut, systemReady, user } = useStore();
  const [theme, toggleTheme] = useTheme();
  const active = jobs.find((j) => j.live);
  const label = navFor(user).find(([, k]) => k === (route === 'job' ? 'jobs' : route));
  const sv = statusView(systemReady);
  const isLight = theme === 'light';
  return (
    <header className="st-top" ref={topRef}>
      <div className="st-crumb">
        <span className="mono">workspace</span>
        <i>/</i>
        <b>{route === 'job' ? 'job detail' : (label ? label[0] : '').toLowerCase()}</b>
      </div>
      <div className="st-top-right">
        {active && <ActiveChip job={active} />}
        <div className="st-status" title="GET /ready" role="status"><i className={'live ' + sv.cls} />{sv.label}</div>
        <button type="button" className="st-pill-credits" onClick={() => go('credits')}>
          <Icon name="bolt" size={14} /><b>{credits == null ? '—' : credits}</b>
        </button>
        <button
          type="button"
          className="icon-btn"
          onClick={toggleTheme}
          aria-label={isLight ? 'Switch to dark theme' : 'Switch to light theme'}
          title={isLight ? 'Switch to dark theme' : 'Switch to light theme'}
        >
          <Icon name={isLight ? 'moon' : 'sun'} size={17} />
        </button>
        <button type="button" className="icon-btn" onClick={signOut} aria-label="Sign out" title="Sign out">
          <Icon name="logout" size={17} />
        </button>
      </div>
    </header>
  );
}

function CancelDialog() {
  const { cancelOpen, setCancelOpen, cancelJob, jobId, jobAction } = useStore();
  if (!cancelOpen) return null;
  const busy = jobAction.busy === 'cancel';
  return (
    <div className="overlay2" role="dialog" aria-modal="true" aria-labelledby="cancel-h" onMouseDown={(e) => e.target === e.currentTarget && !busy && setCancelOpen(false)}>
      <div className="modal2">
        <div className="modal2-icon modal2-icon--warn"><Icon name="alert" size={22} /></div>
        <h3 id="cancel-h">Cancel this job?</h3>
        <p>The pipeline stops at the current stage and the job will not continue.</p>
        {jobAction.error && <p className="modal2-err" role="alert">{jobAction.error}</p>}
        <div className="modal2-actions">
          <button type="button" className="btn2 btn2--danger" onClick={() => cancelJob(jobId)} disabled={busy}>
            {busy ? <><i className="spin" />Cancelling…</> : 'Cancel job'}
          </button>
          <button type="button" className="btn2 btn2--ghost" onClick={() => setCancelOpen(false)} disabled={busy}>Keep running</button>
        </div>
      </div>
    </div>
  );
}

function PayNote({ pricing }) {
  if (!pricing) return null;
  return pricing.payments && pricing.payments.razorpay_configured
    ? <p className="modal2-note">Opens Razorpay Checkout. Credits are added only after your payment is verified.</p>
    : <p className="modal2-note modal2-err" role="alert">Payments are not configured on this server.</p>;
}

function TopupDialog() {
  const { topupOpen, setTopupOpen, topupPack, setTopupPack, pricing, pricingError, refreshPricing, startCheckout, checkout, clearCheckoutError } = useStore();
  useEffect(() => { if (topupOpen) clearCheckoutError(); }, [topupOpen, clearCheckoutError]);
  if (!topupOpen) return null;
  const packs = (pricing && pricing.packs) || [];
  const picked = packs.find((p) => p.id === topupPack) || packs[0];
  const configured = !!(pricing && pricing.payments && pricing.payments.razorpay_configured);
  const busy = checkout.busy;
  const close = () => { if (!busy) setTopupOpen(false); };

  return (
    <div className="overlay2" role="dialog" aria-modal="true" aria-labelledby="topup-h" onMouseDown={(e) => e.target === e.currentTarget && close()}>
      <div className="modal2">
        <div className="kicker">POST /credits/create-order</div>
        <h3 id="topup-h">Top up credits</h3>
        {!pricing ? (
          pricingError
            ? <ErrorState compact title="Could not load packs" message={pricingError} onRetry={refreshPricing} />
            : <div className="modal2-load"><i className="spin" />Loading packs…</div>
        ) : packs.length === 0 ? (
          <p>No top-up packs are available right now.</p>
        ) : (
          <div className="pack-list">
            {packs.map((p) => (
              <button key={p.id} type="button" disabled={busy} className={'pack2' + (picked && picked.id === p.id ? ' is-on' : '')} onClick={() => setTopupPack(p.id)}>
                <span className="pack2-radio"><Icon name="check" size={12} /></span>
                <span className="pack2-c"><b>{p.credits}</b> credits</span>
                <span className="mono">{formatPrice(p.price_paise)}</span>
              </button>
            ))}
          </div>
        )}
        <PayNote pricing={pricing} />
        {checkout.error && <p className="modal2-err" role="alert">{checkout.error}</p>}
        <div className="modal2-actions">
          <button type="button" className="btn2 btn2--primary" onClick={() => picked && startCheckout({ pack: picked.id })} disabled={busy || !picked || !configured}>
            {busy ? <><i className="spin" />Waiting for payment…</> : <>Pay {picked ? formatPrice(picked.price_paise) : ''}</>}
          </button>
          <button type="button" className="btn2 btn2--ghost" onClick={close} disabled={busy}>Close</button>
        </div>
      </div>
    </div>
  );
}

function PlanDialog() {
  const { planId, close } = usePlanDialog();
  const { pricing, startCheckout, checkout, clearCheckoutError } = useStore();
  const confirmRef = useRef(null);
  const cancelRef = useRef(null);
  const busy = checkout.busy;
  const busyRef = useRef(false);
  busyRef.current = busy;
  const isOpen = !!planId && planId !== 'free';

  useEffect(() => { if (isOpen) clearCheckoutError(); }, [isOpen, clearCheckoutError]);

  useEffect(() => {
    if (!isOpen) return undefined;
    const prev = document.activeElement;
    confirmRef.current?.focus();
    const onKey = (e) => {
      if (e.key === 'Escape') {
        if (!busyRef.current) close();
      } else if (e.key === 'Tab') {
        const a = confirmRef.current;
        const b = cancelRef.current;
        if (!a || !b) return;
        const els = [a, b].filter((el) => !el.disabled);
        if (!els.length) { e.preventDefault(); return; }
        const i = els.indexOf(document.activeElement);
        const next = e.shiftKey ? (i <= 0 ? els.length - 1 : i - 1) : (i === els.length - 1 ? 0 : i + 1);
        e.preventDefault();
        els[next].focus();
      }
    };
    window.addEventListener('keydown', onKey);
    return () => {
      window.removeEventListener('keydown', onKey);
      if (prev && typeof prev.focus === 'function' && document.contains(prev)) prev.focus();
    };
  }, [isOpen, planId, close]);

  if (!isOpen) return null;
  const known = !!(pricing && pricing.plans && pricing.plans.some((x) => x.id === planId));
  const p = planOf(pricing, planId);
  const configured = !!(pricing && pricing.payments && pricing.payments.razorpay_configured);

  return (
    <div className="overlay2" role="dialog" aria-modal="true" aria-labelledby="plan-h" onMouseDown={(e) => e.target === e.currentTarget && !busy && close()}>
      <div className="modal2 pl-modal">
        <div className="kicker">Plan checkout</div>
        <h3 id="plan-h">Upgrade to {p.name}</h3>
        {known ? (
          <>
            <div className="pl-modal-price"><b>{formatPrice(p.price_paise)}</b><span>{periodLabel(p)}</span></div>
            <ul className="pl-modal-list">
              <li><Icon name="check" size={15} /><span><b>{p.credits} credits</b> added to your balance once the payment is verified</span></li>
              <li><Icon name="check" size={15} /><span>Unlocks {p.tiers.map(tierName).join(', ')}</span></li>
              {p.period_days ? <li><Icon name="check" size={15} /><span>Active for {p.period_days} days, then back to Free</span></li> : null}
            </ul>
          </>
        ) : (
          <p className="modal2-load"><i className="spin" />Loading plan…</p>
        )}
        <PayNote pricing={pricing} />
        {checkout.error && <p className="modal2-err" role="alert">{checkout.error}</p>}
        <div className="modal2-actions">
          <button type="button" ref={confirmRef} className="btn2 btn2--primary" onClick={() => startCheckout({ plan: p.id })} disabled={busy || !known || !configured}>
            {busy ? <><i className="spin" />Waiting for payment…</> : <>Pay {known ? formatPrice(p.price_paise) : ''}</>}
          </button>
          <button type="button" ref={cancelRef} className="btn2 btn2--ghost" onClick={close} disabled={busy}>Cancel</button>
        </div>
      </div>
    </div>
  );
}

export default function AppShell({ children }) {
  const { route, jobId, user } = useStore();
  const rootRef = useRef(null);
  const pageRef = useRef(null);
  const topRef = useRef(null);
  const prevIdx = useRef(0);

  // Which way did the user move through the sidebar? Content enters from that direction.
  const current = route === 'job' ? 'jobs' : route;
  const idx = Math.max(0, navFor(user).findIndex(([, k]) => k === current));
  const dir = idx >= prevIdx.current ? 'down' : 'up';
  const pageKey = route + (route === 'job' ? jobId : '');

  useEffect(() => {
    prevIdx.current = idx;
    window.scrollTo(0, 0);
  }, [pageKey, idx]);

  // Reveal blocks as they scroll into view. A MutationObserver picks up blocks that mount later
  // (for example the result panel appearing when a job finishes).
  useEffect(() => {
    const page = pageRef.current;
    if (!page) return undefined;
    const t0 = performance.now();
    const io = new IntersectionObserver((entries) => {
      entries.forEach((e) => {
        if (!e.isIntersecting) return;
        const el = e.target;
        const i = parseInt(el.style.getPropertyValue('--i'), 10) || 0;
        const first = performance.now() - t0 < 500;
        el.style.transitionDelay = `${first ? i * 50 : (i % 4) * 40}ms`;
        el.classList.add('is-in');
        setTimeout(() => { el.style.transitionDelay = ''; }, 1100);
        io.unobserve(el);
      });
    }, { threshold: 0.1, rootMargin: '0px 0px -6% 0px' });
    const scan = () => page.querySelectorAll('.rise:not([data-seen])').forEach((el) => {
      el.setAttribute('data-seen', '1');
      io.observe(el);
    });
    scan();
    const mo = new MutationObserver(scan);
    mo.observe(page, { childList: true, subtree: true });
    return () => { io.disconnect(); mo.disconnect(); };
  }, [pageKey]);

  // Scroll progress line + top bar edge once the page has scrolled.
  useEffect(() => {
    let raf = 0;
    const update = () => {
      raf = 0;
      const max = document.documentElement.scrollHeight - window.innerHeight;
      rootRef.current?.style.setProperty('--scroll', max > 0 ? (window.scrollY / max).toFixed(4) : '0');
      topRef.current?.classList.toggle('is-scrolled', window.scrollY > 4);
    };
    const onScroll = () => { if (!raf) raf = requestAnimationFrame(update); };
    update();
    window.addEventListener('scroll', onScroll, { passive: true });
    window.addEventListener('resize', onScroll);
    return () => {
      window.removeEventListener('scroll', onScroll);
      window.removeEventListener('resize', onScroll);
      cancelAnimationFrame(raf);
    };
  }, [pageKey]);

  return (
    <div className="studio" ref={rootRef}>
      <i className="st-sweep" key={pageKey} aria-hidden="true" />
      <i className="st-progress" aria-hidden="true" />
      <Sidebar />
      <div className="st-main">
        <TopBar topRef={topRef} />
        <main className="st-page" key={pageKey} data-dir={dir} ref={pageRef}>{children}</main>
      </div>
      <CancelDialog />
      <TopupDialog />
      <PlanDialog />
    </div>
  );
}
