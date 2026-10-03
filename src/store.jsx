import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';
import * as api from './api/client.js';
import { adaptJob, isTerminalStatus } from './api/adapt.js';
import { loadRazorpay } from './api/razorpay.js';
import { closePlanDialog } from './components/planDialogBus.js';
import {
  DEFAULT_RESOLUTION, DEFAULT_STYLE, STYLE_PROMPT_MAX, effectiveResolution, effectiveStyle, planOf, resolutionList,
  styleList, tierList,
} from './data.js';

const StoreCtx = createContext(null);
export const useStore = () => useContext(StoreCtx);

const read = (k) => {
  try { return localStorage.getItem(k); } catch { return null; }
};
const write = (k, v) => {
  try { v == null ? localStorage.removeItem(k) : localStorage.setItem(k, v); } catch { /* storage unavailable */ }
};

// Re-renders the caller once a second; only mount it where a live clock is shown.
export function useNow(active = true) {
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    if (!active) return undefined;
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, [active]);
  return now;
}

// ---- routing: the URL hash is the source of truth (#/jobs, #/job/<id>, #/credits ...) ----
const ROUTES = ['login', 'create', 'jobs', 'orchestra', 'analytics', 'credits', 'settings'];

function parseHash(h) {
  const parts = String(h || '').replace(/^#\/?/, '').split('/').filter(Boolean);
  const [r, id] = parts;
  if (!r) return { route: 'landing', jobId: null };
  if (r === 'job') {
    if (!id) return { route: 'jobs', jobId: null };
    let decoded = id;
    try { decoded = decodeURIComponent(id); } catch { /* keep raw */ }
    return { route: 'job', jobId: decoded };
  }
  if (ROUTES.includes(r)) return { route: r, jobId: null };
  return { route: 'create', jobId: null };
}
const hashFor = (route, id) => {
  if (route === 'landing') return '#/';
  if (route === 'job' && id) return `#/job/${encodeURIComponent(id)}`;
  return `#/${route}`;
};

const newKey = () => {
  try {
    if (typeof crypto !== 'undefined' && crypto.randomUUID) return crypto.randomUUID();
  } catch { /* fall through */ }
  return 'k' + Date.now().toString(36) + Math.random().toString(36).slice(2, 10);
};

const errMsg = (e, fallback) => (e && e.message) || fallback;

// Runs fn every `ms` while enabled.
function useInterval(fn, ms, enabled) {
  const ref = useRef(fn);
  useEffect(() => { ref.current = fn; });
  useEffect(() => {
    if (!enabled) return undefined;
    const id = setInterval(() => ref.current(), ms);
    return () => clearInterval(id);
  }, [ms, enabled]);
}

export function StoreProvider({ children }) {
  // ---- routing ----
  const [hash, setHash] = useState(() => window.location.hash);
  const { route, jobId } = useMemo(() => parseHash(hash), [hash]);
  useEffect(() => {
    const on = () => setHash(window.location.hash);
    window.addEventListener('hashchange', on);
    return () => window.removeEventListener('hashchange', on);
  }, []);
  const nav = useCallback((h, replace = false) => {
    if (window.location.hash === h) return;
    if (replace) {
      try { window.history.replaceState(null, '', h); } catch { window.location.hash = h; }
      setHash(h);
    } else {
      window.location.hash = h;
      setHash(h);
    }
  }, []);

  // ---- UI state ----
  const [topic, setTopicRaw] = useState('');
  const [lang, setLangRaw] = useState(read('ideafeed_lang') || 'en');
  const [tier, setTierRaw] = useState(read('ideafeed_tier') || 'basic');
  const [styleRaw, setStyleRaw] = useState(read('ideafeed_style') || DEFAULT_STYLE);
  const [styleText, setStyleTextRaw] = useState('');
  const [resolutionRaw, setResolutionRaw] = useState(read('ideafeed_resolution') || DEFAULT_RESOLUTION);
  const [geminiKey, setGeminiKeyRaw] = useState(read('ideafeed_gemini') || '');
  const [apiKey, setApiKeyRaw] = useState(read('ideafeed_key') || '');
  const [filters, setFilters] = useState({ status: 'all', lang: 'all', tier: 'all' });
  const [cancelOpen, setCancelOpen] = useState(false);
  const [topupOpen, setTopupOpen] = useState(false);
  const [topupPack, setTopupPack] = useState(null);
  const [toast, setToastMsg] = useState('');
  const toastTimer = useRef();
  const [visible, setVisible] = useState(() => !document.hidden);

  const showToast = useCallback((m) => {
    setToastMsg(m);
    clearTimeout(toastTimer.current);
    toastTimer.current = setTimeout(() => setToastMsg(''), 3200);
  }, []);

  useEffect(() => {
    const on = () => setVisible(!document.hidden);
    document.addEventListener('visibilitychange', on);
    return () => document.removeEventListener('visibilitychange', on);
  }, []);

  const [gen, setGen] = useState({ busy: false, phase: '', error: '', insufficient: null, forbidden: null });

  // ---- auth ----
  const [user, setUser] = useState(null);
  const [booting, setBooting] = useState(() => !!api.getToken());
  const [bootError, setBootError] = useState('');
  const [bootTick, setBootTick] = useState(0);
  const [approverEdit, setApproverEdit] = useState(null);
  const authed = !!user;
  const approver = approverEdit ?? (user ? user.email : '');

  useEffect(() => {
    write('ideafeed_auth', null); // legacy keys from the earlier mocked build
    write('ideafeed_plan', null);
  }, []);

  // Restore the session from the saved token.
  const bootedOnce = useRef(false);
  useEffect(() => {
    if (!api.getToken()) { setBooting(false); return undefined; }
    let dead = false;
    setBooting(true);
    setBootError('');
    api.me()
      .then((u) => {
        if (dead) return;
        setUser(u);
        if (!bootedOnce.current) {
          bootedOnce.current = true;
          const h = window.location.hash;
          if (!h || h === '#' || h === '#/') nav('#/create', true);
        }
      })
      .catch((e) => {
        if (dead) return;
        if (e && e.status === 401) api.clearToken();
        else setBootError(errMsg(e, 'Could not reach the server.'));
      })
      .finally(() => { if (!dead) setBooting(false); });
    return () => { dead = true; };
  }, [bootTick, nav]);
  const retryBoot = useCallback(() => setBootTick((n) => n + 1), []);

  // ---- pricing (public) ----
  const [pricing, setPricing] = useState(null);
  const [pricingError, setPricingError] = useState('');
  const refreshPricing = useCallback(async () => {
    try {
      setPricing(await api.plans());
      setPricingError('');
    } catch (e) {
      setPricingError(errMsg(e, 'Could not load pricing.'));
    }
  }, []);
  useEffect(() => { refreshPricing(); }, [refreshPricing]);

  // ---- credits ----
  const [creditsInfo, setCreditsInfo] = useState(null);
  const [creditsError, setCreditsError] = useState('');
  const refreshCredits = useCallback(async () => {
    try {
      setCreditsInfo(await api.credits());
      setCreditsError('');
    } catch (e) {
      if (e && e.status === 401) return;
      setCreditsError(errMsg(e, 'Could not load your credits.'));
    }
  }, []);
  const refreshUser = useCallback(async () => {
    try { setUser(await api.me()); } catch { /* 401 is handled by the unauthorized hook */ }
  }, []);

  // ---- system status + providers (public) ----
  const [systemReady, setSystemReady] = useState({ state: 'checking', checks: null, failing: [] });
  const refreshReady = useCallback(async () => {
    try {
      const r = await api.ready();
      const checks = r.checks || {};
      const failing = Object.entries(checks).filter(([, v]) => v === false).map(([k]) => k);
      setSystemReady({ state: r.ready === false || failing.length ? 'degraded' : 'ok', checks, failing });
    } catch {
      try {
        await api.health();
        setSystemReady({ state: 'ok', checks: null, failing: [] });
      } catch {
        setSystemReady({ state: 'down', checks: null, failing: [] });
      }
    }
  }, []);
  // Check once on load even in a background tab (so status is never stuck on "Checking…"),
  // then again whenever the tab becomes visible; the interval below only polls while visible.
  const readyChecked = useRef(false);
  useEffect(() => {
    if (visible || !readyChecked.current) { readyChecked.current = true; refreshReady(); }
  }, [visible, refreshReady]);
  useInterval(refreshReady, 20000, visible);

  const [providers, setProviders] = useState(null);
  const [providersError, setProvidersError] = useState('');
  const refreshProviders = useCallback(async () => {
    try {
      setProviders(await api.providersStatus());
      setProvidersError('');
    } catch (e) {
      setProvidersError(errMsg(e, 'Could not load provider status.'));
    }
  }, []);
  useEffect(() => { refreshProviders(); }, [refreshProviders]);

  // ---- jobs list ----
  const [jobs, setJobs] = useState([]);
  const [jobsStatus, setJobsStatus] = useState('idle'); // idle | loading | ready | error
  const [jobsError, setJobsError] = useState('');
  const jobsReq = useRef(0);
  const jobsRef = useRef(jobs);
  useEffect(() => { jobsRef.current = jobs; }, [jobs]);

  const refreshJobs = useCallback(async ({ silent = false } = {}) => {
    const req = ++jobsReq.current;
    if (!silent) setJobsStatus((s) => (s === 'ready' ? s : 'loading'));
    try {
      const raw = await api.listJobs();
      if (req !== jobsReq.current) return;
      setJobs((Array.isArray(raw) ? raw : (raw && raw.jobs) || []).map(adaptJob));
      setJobsStatus('ready');
      setJobsError('');
    } catch (e) {
      if (req !== jobsReq.current || (e && e.status === 401)) return;
      setJobsError(errMsg(e, 'Could not load your jobs.'));
      setJobsStatus((s) => (s === 'ready' ? s : 'error'));
    }
  }, []);

  const mergeJob = useCallback((j) => {
    setJobs((list) => (list.some((x) => x.id === j.id) ? list.map((x) => (x.id === j.id ? j : x)) : [j, ...list]));
  }, []);

  const anyRunning = jobs.some((j) => j.live || j.status === 'publishing');

  // ---- the open job ----
  const [jobData, setJobData] = useState(null);
  const [jobStatus, setJobStatus] = useState('idle'); // idle | loading | ready | error
  const [jobError, setJobError] = useState(null); // ApiError | null
  const [jobStale, setJobStale] = useState('');
  const jobDataRef = useRef(null);
  useEffect(() => { jobDataRef.current = jobData; }, [jobData]);
  const job = useMemo(() => {
    if (!jobId) return null;
    if (jobData && jobData.id === jobId) return jobData;
    return jobs.find((x) => x.id === jobId) || null;
  }, [jobId, jobData, jobs]);
  const jobLive = !!job && !isTerminalStatus(job.status);

  const fetchJob = useCallback(async (id, { initial = false } = {}) => {
    if (initial) { setJobStatus('loading'); setJobError(null); }
    try {
      const j = adaptJob(await api.getJob(id));
      setJobData(j);
      jobDataRef.current = j;
      setJobStatus('ready');
      setJobError(null);
      setJobStale('');
      mergeJob(j);
      return j;
    } catch (e) {
      if (e && e.status === 401) return null;
      const have = jobDataRef.current && jobDataRef.current.id === id;
      if (have && !(e && e.status === 404)) {
        setJobStale(errMsg(e, 'Could not refresh this job.'));
      } else {
        setJobError(e);
        setJobStatus('error');
      }
      return null;
    }
  }, [mergeJob]);

  const refreshJob = useCallback((id) => fetchJob(id || jobId, { initial: false }), [fetchJob, jobId]);
  const retryJob = useCallback(() => { if (jobId) fetchJob(jobId, { initial: true }); }, [fetchJob, jobId]);

  // Load the job when it is opened, then poll every 1.5 s while it is not terminal.
  const fetchedFor = useRef(null);
  useEffect(() => {
    if (!authed || !jobId) { setJobStatus('idle'); return undefined; }
    const first = fetchedFor.current !== jobId;
    // In a background tab, still load a newly opened job once (never show stale list data), but don't poll.
    if (!visible && !first) return undefined;
    let dead = false;
    let timer = 0;
    fetchedFor.current = jobId;
    const have = jobDataRef.current && jobDataRef.current.id === jobId;
    const tick = async (initial) => {
      if (dead) return;
      const j = await fetchJob(jobId, { initial });
      if (dead) return;
      const cur = j || jobDataRef.current;
      const alive = cur && cur.id === jobId && !isTerminalStatus(cur.status);
      if (alive && visible) timer = setTimeout(() => tick(false), j ? 1500 : 4000);
    };
    if (first || !have || jobLive) tick(first && !have);
    else setJobStatus('ready');
    return () => { dead = true; clearTimeout(timer); };
  }, [authed, jobId, visible, jobLive, fetchJob]);

  // ---- credits / jobs refresh triggers ----
  useEffect(() => {
    if (!authed) { setCreditsInfo(null); return; }
    refreshJobs({ silent: true });
  }, [authed, refreshJobs]);
  useEffect(() => { if (authed && visible) refreshCredits(); }, [authed, visible, refreshCredits]);
  useEffect(() => {
    if (!authed) return undefined;
    const on = () => { if (!document.hidden) refreshCredits(); };
    window.addEventListener('focus', on);
    return () => window.removeEventListener('focus', on);
  }, [authed, refreshCredits]);
  useInterval(refreshCredits, 30000, authed && visible);
  useEffect(() => {
    if (authed && (route === 'jobs' || route === 'analytics')) refreshJobs({ silent: jobsRef.current.length > 0 });
  }, [authed, route, refreshJobs]);
  useInterval(() => refreshJobs({ silent: true }), 3000, authed && visible && anyRunning);

  // ---- navigation helpers ----
  const go = useCallback((r) => {
    setCancelOpen(false);
    setTopupOpen(false);
    nav(hashFor(r));
  }, [nav]);
  const openJob = useCallback((id) => {
    setCancelOpen(false);
    nav(hashFor('job', id));
  }, [nav]);

  // ---- session actions ----
  const resetSession = useCallback(() => {
    api.clearToken();
    setUser(null);
    setCreditsInfo(null);
    setJobs([]);
    setJobsStatus('idle');
    setJobData(null);
    jobDataRef.current = null;
    fetchedFor.current = null;
    setTopicRaw('');
    setApproverEdit(null);
    setCancelOpen(false);
    setTopupOpen(false);
    setGen({ busy: false, phase: '', error: '', insufficient: null, forbidden: null });
    closePlanDialog();
  }, []);

  const signOut = useCallback(() => {
    resetSession();
    nav('#/', false);
  }, [resetSession, nav]);

  useEffect(() => {
    api.onUnauthorized(() => {
      resetSession();
      nav('#/login', false);
      showToast('Your session expired. Sign in again.');
    });
    return () => api.onUnauthorized(null);
  }, [resetSession, nav, showToast]);

  const finishAuth = useCallback((res) => {
    api.setToken(res.token);
    setUser(res.user);
    setApproverEdit(null);
    setBootError('');
    const r = parseHash(window.location.hash).route;
    if (r === 'login' || r === 'landing') nav('#/create');
  }, [nav]);

  // With email verification on, sign-up returns { verification_required, email } and no session yet;
  // the Login page then collects the emailed code and calls verifyEmail.
  const register = useCallback(async (email, password) => {
    const res = await api.register(email, password);
    if (res && res.verification_required) return { verify: res.email, minutes: res.expires_in_minutes };
    finishAuth(res);
    return null;
  }, [finishAuth]);
  const verifyEmail = useCallback(async (email, code) => finishAuth(await api.verifyEmail(email, code)), [finishAuth]);
  const resendCode = useCallback((email) => api.resendCode(email), []);
  const login = useCallback(async (email, password) => finishAuth(await api.login(email, password)), [finishAuth]);

  // ---- style + resolution: the stored choice, corrected against what the server offers and the plan allows ----
  // Until /credits answers (it is skipped while the tab is in the background), fall back to what the
  // signed-in user's plan allows according to /plans, so locked options are never offered.
  const userPlanDef = user && pricing ? planOf(pricing, user.plan) : null;
  const resolutionsAllowed = creditsInfo && Array.isArray(creditsInfo.resolutions_allowed)
    ? creditsInfo.resolutions_allowed
    : (userPlanDef && Array.isArray(userPlanDef.resolutions) ? userPlanDef.resolutions : null);
  const style = useMemo(() => effectiveStyle(pricing, styleRaw), [pricing, styleRaw]);
  const resolution = useMemo(
    () => effectiveResolution(pricing, resolutionRaw, resolutionsAllowed),
    [pricing, resolutionRaw, resolutionsAllowed],
  );
  const hasStyles = styleList(pricing).length > 0;
  const hasResolutions = resolutionList(pricing).length > 0;

  // ---- generate ----
  const attempt = useRef(null); // { sig, key, uploadIds, retryable }
  const genBusy = useRef(false);

  const clearGenError = useCallback(() => {
    setGen((g) => (g.error || g.insufficient || g.forbidden ? { ...g, error: '', insufficient: null, forbidden: null } : g));
  }, []);

  const generate = useCallback(async ({ files = [] } = {}) => {
    const clean = topic.trim();
    if (!clean || genBusy.current) return;
    genBusy.current = true;
    const customText = style === 'custom' ? styleText.trim().slice(0, STYLE_PROMPT_MAX) : '';
    if (hasStyles && style === 'custom' && !customText) {
      genBusy.current = false;
      setGen({ busy: false, phase: '', error: 'Describe your custom style, or pick another style.', insufficient: null, forbidden: null });
      return;
    }
    const sig = JSON.stringify([
      clean, lang, tier, hasStyles ? style : null, customText, hasResolutions ? resolution : null,
      files.map((f) => [f.name, f.size, f.lastModified]),
    ]);
    if (!attempt.current || attempt.current.sig !== sig || !attempt.current.retryable) {
      attempt.current = { sig, key: newKey(), uploadIds: null, retryable: false };
    }
    const at = attempt.current;
    setGen({ busy: true, phase: files.length && !at.uploadIds ? 'uploading' : 'creating', error: '', insufficient: null, forbidden: null });
    let stage = 'upload';
    try {
      if (files.length && !at.uploadIds) {
        const up = await api.uploadImages(files);
        at.uploadIds = (up.files || []).map((f) => f.id);
        setGen((g) => ({ ...g, phase: 'creating' }));
      }
      stage = 'create';
      const body = { topic: clean, language: lang, motion_tier: tier };
      if (hasStyles) {
        body.style = style;
        if (style === 'custom') body.style_prompt = customText;
      }
      if (hasResolutions) body.resolution = resolution;
      if (at.uploadIds && at.uploadIds.length) body.reference_images = at.uploadIds;
      const raw = await api.createJob(body, at.key);
      const j = adaptJob(raw);
      attempt.current = null;
      mergeJob(j);
      refreshCredits();
      setTopicRaw('');
      setGen({ busy: false, phase: '', error: '', insufficient: null, forbidden: null });
      openJob(j.id);
    } catch (e) {
      at.retryable = !!e && (e.status === 0 || e.status >= 500);
      const d = e && e.detail && typeof e.detail === 'object' ? e.detail : null;
      if (e && e.status === 402) {
        setGen({ busy: false, phase: '', error: '', forbidden: null, insufficient: { message: e.message, required: d && d.required, available: d && d.available } });
      } else if (e && e.status === 403) {
        setGen({ busy: false, phase: '', error: '', insufficient: null, forbidden: { message: e.message, requiredPlan: d && d.required_plan, plan: d && d.plan } });
      } else {
        const prefix = stage === 'upload' ? 'Image upload failed: ' : '';
        setGen({ busy: false, phase: '', error: prefix + errMsg(e, 'Could not create the job.'), insufficient: null, forbidden: null });
      }
      refreshCredits();
    } finally {
      genBusy.current = false;
    }
  }, [topic, lang, tier, style, styleText, resolution, hasStyles, hasResolutions, mergeJob, refreshCredits, openJob]);

  // ---- job actions ----
  const [jobAction, setJobAction] = useState({ busy: null, error: '' }); // busy: approve | publish | cancel | null
  const applyJobResponse = useCallback((resp, id) => {
    if (resp && typeof resp === 'object' && resp.id && resp.status) {
      const j = adaptJob(resp);
      setJobData(j);
      jobDataRef.current = j;
      setJobStatus('ready');
      mergeJob(j);
      return j;
    }
    return fetchJob(id);
  }, [mergeJob, fetchJob]);

  const runAction = useCallback(async (kind, id, call, okMsg) => {
    setJobAction({ busy: kind, error: '' });
    try {
      await applyJobResponse(await call(), id);
      setJobAction({ busy: null, error: '' });
      if (okMsg) showToast(okMsg);
      return true;
    } catch (e) {
      setJobAction({ busy: null, error: errMsg(e, `Could not ${kind} this job.`) });
      fetchJob(id); // the state may have changed under us (409)
      return false;
    }
  }, [applyJobResponse, fetchJob, showToast]);

  useEffect(() => { setJobAction({ busy: null, error: '' }); }, [jobId]);

  const approve = useCallback((id) => {
    const who = approver.trim();
    if (!who) return Promise.resolve(false);
    return runAction('approve', id, () => api.approveJob(id, who), 'Approved by ' + who);
  }, [approver, runAction]);

  const publish = useCallback((id) => runAction('publish', id, () => api.publishJob(id), null), [runAction]);

  const cancelJob = useCallback(async (id) => {
    const ok = await runAction('cancel', id, () => api.cancelJob(id), 'Cancelled');
    if (ok) setCancelOpen(false);
  }, [runAction]);

  const retryAsNew = useCallback((j) => {
    setTopicRaw(j.topic);
    setLangRaw(j.language);
    setTierRaw(j.tier);
    if (j.style) setStyleRaw(j.style);
    setStyleTextRaw(j.styleText || '');
    if (j.resolution) setResolutionRaw(j.resolution);
    clearGenError();
    nav('#/create');
  }, [nav, clearGenError]);

  // ---- payments ----
  const [checkout, setCheckout] = useState({ busy: false, error: '' });
  const checkoutBusy = useRef(false);
  const startCheckout = useCallback(async (target) => {
    if (checkoutBusy.current) return;
    checkoutBusy.current = true;
    setCheckout({ busy: true, error: '' });
    try {
      let order;
      try {
        order = await api.createOrder(target);
      } catch (e) {
        if (e && e.status === 503) throw new Error('Payments are not configured on this server.');
        throw e;
      }
      const Razorpay = await loadRazorpay();
      const outcome = await new Promise((resolve, reject) => {
        let handled = false;
        let failure = '';
        const rz = new Razorpay({
          key: order.key_id,
          order_id: order.order_id,
          amount: order.amount,
          currency: order.currency,
          name: 'IdeaFeed AI',
          description: order.kind === 'plan'
            ? `${planOf(pricing, order.plan).name} plan`
            : `${order.credits} credits`,
          prefill: { email: user ? user.email : '' },
          handler: (r) => {
            handled = true;
            api.verifyPayment(r.razorpay_order_id, r.razorpay_payment_id, r.razorpay_signature)
              .then(resolve)
              .catch((e) => reject(new Error(
                `Payment ${r.razorpay_payment_id} went through but could not be verified: ${errMsg(e, 'unknown error')} `
                + 'Your credits are added once it verifies; refresh in a minute or contact support with that payment id.',
              )));
          },
          modal: {
            ondismiss: () => { if (!handled) (failure ? reject(new Error(failure)) : resolve(null)); },
          },
        });
        rz.on('payment.failed', (resp) => {
          failure = (resp && resp.error && resp.error.description) || 'The payment failed. Try again.';
        });
        rz.open();
      });
      if (outcome) {
        await Promise.all([refreshCredits(), refreshUser()]);
        setTopupOpen(false);
        closePlanDialog();
        const added = outcome.credits_added ?? order.credits;
        if (outcome.already_processed) showToast('This payment was already applied.');
        else if (order.kind === 'plan') showToast(`${planOf(pricing, order.plan).name} plan active. ${added} credits added`);
        else showToast(`${added} credits added`);
      }
      setCheckout({ busy: false, error: '' });
    } catch (e) {
      setCheckout({ busy: false, error: errMsg(e, 'Checkout failed.') });
    } finally {
      checkoutBusy.current = false;
    }
  }, [pricing, user, refreshCredits, refreshUser, showToast]);

  const clearCheckoutError = useCallback(() => setCheckout((c) => (c.error ? { ...c, error: '' } : c)), []);

  // ---- derived account values ----
  const plan = (creditsInfo && creditsInfo.plan) || (user && user.plan) || 'free';
  const credits = creditsInfo ? creditsInfo.balance : (user ? user.balance : null);
  const planExpiresAt = creditsInfo ? creditsInfo.plan_expires_at : (user ? user.plan_expires_at : null);
  const tiersAllowed = creditsInfo
    ? creditsInfo.tiers_allowed
    : (userPlanDef && Array.isArray(userPlanDef.tiers) ? userPlanDef.tiers : null); // null = not known yet
  const costByTier = (pricing && pricing.cost_by_tier) || (creditsInfo && creditsInfo.cost_by_tier) || null;
  const tiers = useMemo(() => tierList({ cost_by_tier: costByTier }), [costByTier]);

  const value = useMemo(() => ({
    route, jobId, authed, booting, bootError, user, approver, topic, lang, tier, style, styleText, resolution, resolutionsAllowed, geminiKey, apiKey, filters,
    pricing, pricingError, plan, credits, planExpiresAt, tiersAllowed, costByTier, tiers, creditsError,
    jobs, jobsStatus, jobsError, anyRunning,
    job, jobStatus, jobError, jobStale, jobAction,
    providers, providersError, systemReady,
    cancelOpen, topupOpen, topupPack, toast, gen, checkout,
    go, openJob, register, login, verifyEmail, resendCode, signOut, retryBoot, generate, clearGenError,
    approve, publish, cancelJob, retryAsNew, refreshJobs, refreshJob, retryJob,
    refreshPricing, refreshCredits, refreshProviders, refreshReady, startCheckout, clearCheckoutError, showToast,
    setApprover: setApproverEdit, setCancelOpen, setTopupOpen, setTopupPack, setFilters,
    setTopic: (v) => { setTopicRaw(v); clearGenError(); },
    setLang: (v) => { setLangRaw(v); write('ideafeed_lang', v); },
    setTier: (v) => { setTierRaw(v); write('ideafeed_tier', v); clearGenError(); },
    setStyle: (v) => { setStyleRaw(v); write('ideafeed_style', v); clearGenError(); },
    setStyleText: (v) => { setStyleTextRaw(String(v).slice(0, STYLE_PROMPT_MAX)); clearGenError(); },
    setResolution: (v) => { setResolutionRaw(v); write('ideafeed_resolution', v); clearGenError(); },
    setGeminiKey: (v) => { setGeminiKeyRaw(v); write('ideafeed_gemini', v || null); },
    setApiKey: (v) => { setApiKeyRaw(v); write('ideafeed_key', v || null); },
  }), [route, jobId, authed, booting, bootError, user, approver, topic, lang, tier, style, styleText, resolution, resolutionsAllowed, geminiKey, apiKey, filters,
    pricing, pricingError, plan, credits, planExpiresAt, tiersAllowed, costByTier, tiers, creditsError,
    jobs, jobsStatus, jobsError, anyRunning, job, jobStatus, jobError, jobStale, jobAction,
    providers, providersError, systemReady, cancelOpen, topupOpen, topupPack, toast, gen, checkout,
    go, openJob, register, login, verifyEmail, resendCode, signOut, retryBoot, generate, clearGenError, approve, publish, cancelJob, retryAsNew,
    refreshJobs, refreshJob, retryJob, refreshPricing, refreshCredits, refreshProviders, refreshReady, startCheckout,
    clearCheckoutError, showToast]);

  return <StoreCtx.Provider value={value}>{children}</StoreCtx.Provider>;
}
