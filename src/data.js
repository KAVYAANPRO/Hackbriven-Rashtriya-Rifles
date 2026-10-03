// Static UI vocabulary only. Prices, plans, packs, costs, providers and jobs all come from the backend.

export const ORDER = [
  'queued',
  'running_intelligence',
  'running_generation',
  'running_composition',
  'running_validation',
  'done',
];

export const LABEL = {
  queued: 'Queued',
  running_intelligence: 'Intelligence',
  running_generation: 'Generation',
  running_composition: 'Composition',
  running_validation: 'Validation',
  done: 'Done',
  approved: 'Approved',
  publishing: 'Publishing',
  published: 'Published',
  publish_failed: 'Publish failed',
  manual_handoff: 'Manual handoff',
  failed: 'Failed',
  cancelled: 'Cancelled',
};

// Every status in INTEGRATION.md, in lifecycle order.
export const ALL_STATUSES = [
  ...ORDER,
  'approved', 'publishing', 'manual_handoff', 'published', 'publish_failed', 'failed', 'cancelled',
];

export const STAGE_NAMES = ['Queued', 'Intelligence', 'Generation', 'Composition', 'Validation'];

export const LANGS = [
  { v: 'en', label: 'English', code: 'en' },
  { v: 'hi', label: 'हिन्दी', code: 'hi' },
  { v: 'hinglish', label: 'Hinglish', code: 'hinglish' },
];

// Tier labels and descriptions. Costs are NOT here: they come from GET /plans (cost_by_tier).
export const TIER_META = {
  basic: { label: 'Basic', desc: 'Still frames, light pan' },
  balanced: { label: 'Balanced', desc: 'Ken-Burns on every scene' },
  max: { label: 'Max', desc: 'Full motion render' },
};
const cap = (s) => (s ? s[0].toUpperCase() + s.slice(1) : s);

export const NAV = [
  ['Create', 'create'],
  ['Jobs', 'jobs'],
  ['Orchestra', 'orchestra'],
  ['Analytics', 'analytics'],
  ['Plans and Credits', 'credits'],
  ['Settings', 'settings'],
];

export const fmt = (ts) => {
  if (ts == null || Number.isNaN(Number(ts))) return '—';
  const d = new Date(ts);
  if (Number.isNaN(d.getTime())) return '—';
  // Local time, not UTC: a job created at 18:45 should not read 13:15.
  const p = (n) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`;
};

export const hms = (ms) => {
  const s = Math.max(0, Math.floor(ms / 1000));
  return `${Math.floor(s / 60)}m ${String(s % 60).padStart(2, '0')}s`;
};

export const isRun = (s) => s === 'queued' || String(s).indexOf('running_') === 0;

// Past the pipeline: the video exists (or was handed off).
export const DONE_STATES = ['done', 'approved', 'publishing', 'manual_handoff', 'published', 'publish_failed'];
// Statuses the backend is still working on.
export const IN_PROGRESS = ['queued', 'running_intelligence', 'running_generation', 'running_composition', 'running_validation', 'publishing'];
// What counts toward the completion rate.
export const COMPLETED_STATES = ['done', 'approved', 'manual_handoff', 'published'];
export const FAILED_STATES = ['failed', 'publish_failed'];
// States where the video can be shown.
export const VIDEO_STATES = ['done', 'approved', 'publishing', 'manual_handoff', 'published', 'publish_failed'];

// One state per pipeline stage: done | active | failed | stopped | pending
export function stageStates(j) {
  const st = j.status;
  const runIdx = ORDER.indexOf(st);
  const failIdx = st === 'failed' ? Math.max(0, ORDER.indexOf(j.errorStage)) : -1;
  const at = {};
  j.history.forEach((h) => { at[h.status] = h.at; });
  return STAGE_NAMES.map((_, i) => {
    const started = at[ORDER[i]];
    const nextAt = at[ORDER[i + 1]];
    if (st === 'failed') return i < failIdx ? 'done' : i === failIdx ? 'failed' : 'pending';
    if (st === 'cancelled') return started && nextAt ? 'done' : started ? 'stopped' : 'pending';
    if (runIdx < 0 || runIdx >= 5) return 'done';
    return i < runIdx ? 'done' : i === runIdx ? 'active' : 'pending';
  });
}

// ---- pricing helpers: all take the object returned by GET /plans ----

export const formatPrice = (paise) => {
  if (paise == null || Number.isNaN(Number(paise))) return '—';
  const rupees = Number(paise) / 100;
  return '₹' + (Number.isInteger(rupees)
    ? rupees.toLocaleString('en-IN')
    : rupees.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 }));
};

export const planList = (pricing) => (pricing && Array.isArray(pricing.plans) ? pricing.plans : []);

export const planOf = (pricing, id) => planList(pricing).find((p) => p.id === id)
  || { id: id || 'free', name: cap(id || 'free'), price_paise: 0, credits: 0, period_days: null, tiers: [] };

export const canUseTier = (pricing, planId, tier) => {
  const p = planList(pricing).find((x) => x.id === planId);
  return p ? p.tiers.includes(tier) : true; // unknown plan: let the server decide
};

// Cheapest plan that unlocks a tier, for "needs <plan>" hints.
export const planFor = (pricing, tier) => planList(pricing)
  .filter((p) => p.tiers.includes(tier))
  .sort((a, b) => a.price_paise - b.price_paise)[0] || null;

export const tierCost = (pricing, tier) => {
  const c = pricing && pricing.cost_by_tier ? pricing.cost_by_tier[tier] : null;
  return typeof c === 'number' ? c : null;
};

// Tiers sorted cheapest first. While pricing loads, falls back to the labels only (cost: null).
export function tierList(pricing) {
  const costs = pricing && pricing.cost_by_tier;
  const keys = costs ? Object.keys(costs).sort((a, b) => costs[a] - costs[b]) : Object.keys(TIER_META);
  return keys.map((v) => ({
    v,
    label: (TIER_META[v] || {}).label || cap(v),
    desc: (TIER_META[v] || {}).desc || '',
    cost: costs && typeof costs[v] === 'number' ? costs[v] : null,
  }));
}

// ---- v2 pricing helpers: styles, resolutions, download formats (all lists come from GET /plans) ----

export const styleList = (pricing) => (pricing && Array.isArray(pricing.styles) ? pricing.styles : []);
export const resolutionList = (pricing) => (pricing && Array.isArray(pricing.resolutions) ? pricing.resolutions : []);
export const formatList = (pricing) => (pricing && Array.isArray(pricing.formats) ? pricing.formats : []);

export const styleLabel = (pricing, id) => {
  const s = styleList(pricing).find((x) => x.id === id);
  return s && s.label ? s.label : id;
};

export const resolutionOf = (pricing, id) => resolutionList(pricing).find((r) => r.id === id) || null;

// Credits added on top of the tier cost. 0 when the resolution is unknown or has no surcharge.
export const resolutionSurcharge = (pricing, id) => {
  const r = resolutionOf(pricing, id);
  const n = r ? Number(r.credit_surcharge) : 0;
  return Number.isFinite(n) && n > 0 ? n : 0;
};

// Cheapest plan that lists a resolution in plan.resolutions, for "needs <plan>" hints.
export const planForResolution = (pricing, id) => planList(pricing)
  .filter((p) => Array.isArray(p.resolutions) && p.resolutions.includes(id))
  .sort((a, b) => a.price_paise - b.price_paise)[0] || null;

// The resolution that will actually be sent: the wanted one when valid and usable, else a sensible default.
// `allowed` is credits.resolutions_allowed (null = not known yet / older backend).
export function effectiveResolution(pricing, wanted, allowed) {
  const list = resolutionList(pricing);
  if (!list.length) return wanted;
  const usable = (id) => list.some((r) => r.id === id) && (!allowed || allowed.includes(id));
  if (usable(wanted)) return wanted;
  if (usable(DEFAULT_RESOLUTION)) return DEFAULT_RESOLUTION;
  const first = list.find((r) => usable(r.id));
  return first ? first.id : wanted;
}

export const effectiveStyle = (pricing, wanted) => {
  const list = styleList(pricing);
  if (!list.length) return wanted;
  return list.some((s) => s.id === wanted) ? wanted : DEFAULT_STYLE;
};

export const DEFAULT_STYLE = 'auto';
export const DEFAULT_RESOLUTION = '1080p';
export const STYLE_PROMPT_MAX = 300;
// Visual-only note per resolution id, shown after the label. Never names a vendor.
export const RES_NOTE = { '4k': 'enhanced' };

// Small visual map keyed by style id (decoration only). Unknown ids get the neutral gradient.
const SWATCH_NEUTRAL = 'linear-gradient(135deg, #1b2626 0%, #2c3c3c 100%)';
const STYLE_SWATCH = {
  auto: 'linear-gradient(135deg, #1b2626 0%, #3a4d4d 55%, #b4e768 160%)',
  custom: 'repeating-linear-gradient(135deg, #1b2626 0 8px, #243030 8px 16px)',
  cinematic: 'linear-gradient(135deg, #0b1f2a 0%, #1d4a5c 50%, #e0a458 100%)',
  minimalist: 'linear-gradient(135deg, #e9e6dc 0%, #bdbab0 100%)',
  playful: 'linear-gradient(135deg, #ff9ecb 0%, #ffd166 50%, #7bdff2 100%)',
  '3d': 'linear-gradient(135deg, #3a1c71 0%, #6a4fd8 50%, #4fd1c5 100%)',
  colorful: 'linear-gradient(135deg, #ff5f6d 0%, #ffc371 35%, #47e891 70%, #3a8dff 100%)',
  anime: 'linear-gradient(135deg, #ff7eb3 0%, #7a5cff 100%)',
  retro: 'linear-gradient(135deg, #d9a05b 0%, #b5503c 60%, #5c3a2e 100%)',
  vintage: 'linear-gradient(135deg, #c9b79c 0%, #8a7560 100%)',
  neon: 'linear-gradient(135deg, #0a0a1a 0%, #ff2bd6 50%, #20e3ff 100%)',
  cyberpunk: 'linear-gradient(135deg, #0a0a1a 0%, #ff2bd6 50%, #20e3ff 100%)',
  documentary: 'linear-gradient(135deg, #3b4a3f 0%, #8d9a86 100%)',
  watercolor: 'linear-gradient(135deg, #bde0fe 0%, #ffc8dd 50%, #cdb4db 100%)',
  noir: 'linear-gradient(135deg, #0a0a0a 0%, #6b6b6b 100%)',
  comic: 'linear-gradient(135deg, #ffd23f 0%, #ee4266 100%)',
  corporate: 'linear-gradient(135deg, #0f3057 0%, #00909e 100%)',
  nature: 'linear-gradient(135deg, #1e5631 0%, #a4de02 100%)',
};
export const styleSwatch = (id) => STYLE_SWATCH[id] || SWATCH_NEUTRAL;

export const KIND_LABEL = { video: 'Video', animation: 'Animation', audio: 'Audio' };
export const kindLabel = (k) => KIND_LABEL[k] || cap(k || 'other');

export const periodLabel = (p) => {
  if (!p.period_days) return p.price_paise > 0 ? 'one-time' : 'forever';
  if (p.period_days === 30) return 'per month';
  if (p.period_days === 365) return 'per year';
  return `per ${p.period_days} days`;
};

export const tierName = (t) => (TIER_META[t] || {}).label || cap(t);

// Backend ids -> readable provider names; unknown ids render as-is.
const PROVIDER_NAMES = {
  gemini: 'Gemini', groq: 'Groq', openrouter: 'OpenRouter', local_template: 'Local template',
  nvidia: 'NVIDIA FLUX', nvidia_sd35: 'NVIDIA FLUX', pollinations: 'Pollinations',
  placeholder: 'Placeholder', local_placeholder: 'Placeholder',
  'edge-tts': 'Edge TTS', gtts: 'gTTS', groq_whisper: 'Groq Whisper', local_whisper: 'Local Whisper',
  eightscale: '8Scale', magic_hour: 'Magic Hour', ken_burns: 'Ken Burns',
  cloudflare: 'FLUX (Cloudflare)',
  // Resolution enhancement is presented neutrally on purpose: the UI never names the service doing it.
  enhancer: 'Enhancer', local_scale: 'Standard scaling',
};
export const providerName = (id) => PROVIDER_NAMES[id] || id;

// The Orchestra (provider internals) is for the master admin only.
export const ADMIN_ROUTES = ['orchestra'];
export const navFor = (user) => NAV.filter(([, key]) => !ADMIN_ROUTES.includes(key) || !!(user && user.is_admin));
