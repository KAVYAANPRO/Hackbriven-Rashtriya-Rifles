// Thin client for the IdeaFeed FastAPI backend. See INTEGRATION.md for the contract.
// The session token lives in localStorage ("ideafeed_token"); it is never logged or displayed.

export const API_BASE = (import.meta.env.VITE_API_URL || '/api').replace(/\/+$/, '');

const TOKEN_KEY = 'ideafeed_token';
const LEGACY_KEY = 'ideafeed_key';

const read = (k) => {
  try { return localStorage.getItem(k); } catch { return null; }
};
const write = (k, v) => {
  try { v == null ? localStorage.removeItem(k) : localStorage.setItem(k, v); } catch { /* storage unavailable */ }
};

export const getToken = () => read(TOKEN_KEY) || '';
export const setToken = (t) => write(TOKEN_KEY, t || null);
export const clearToken = () => write(TOKEN_KEY, null);

let unauthorizedHandler = null;
export const onUnauthorized = (fn) => { unauthorizedHandler = fn; };

export class ApiError extends Error {
  constructor(status, detail, message, body) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.detail = detail;
    this.body = body;
  }
}

function messageFrom(status, detail) {
  if (typeof detail === 'string' && detail.trim()) return detail;
  if (Array.isArray(detail) && detail.length) {
    // FastAPI validation errors: [{loc, msg, type}]
    return detail
      .map((d) => {
        if (!d || typeof d !== 'object') return String(d);
        const field = Array.isArray(d.loc) ? d.loc.filter((x) => x !== 'body').join('.') : '';
        return field ? `${field}: ${d.msg}` : d.msg;
      })
      .join('; ');
  }
  if (detail && typeof detail === 'object' && typeof detail.message === 'string') return detail.message;
  if (status === 401) return 'You are not signed in, or your session has expired.';
  if (status === 402) return 'Not enough credits.';
  if (status === 403) return 'Your plan cannot do that.';
  if (status === 404) return 'Not found.';
  if (status === 409) return 'That is not allowed in the current state.';
  if (status === 413) return 'The upload is too large.';
  if (status === 415) return 'That file type is not supported.';
  if (status === 422) return 'The request was not valid.';
  if (status === 503) return 'That service is not available on this server.';
  if (status >= 500) return `The server had a problem (${status}). Try again.`;
  return `Request failed (${status}).`;
}

export async function request(method, path, { body, form, auth = true, idempotencyKey, signal } = {}) {
  const headers = { Accept: 'application/json' };
  if (auth) {
    const t = getToken() || read(LEGACY_KEY);
    if (t) headers.Authorization = `Bearer ${t}`;
  }
  if (idempotencyKey) headers['Idempotency-Key'] = idempotencyKey;
  let payload;
  if (form) {
    payload = form; // the browser sets the multipart boundary
  } else if (body !== undefined) {
    headers['Content-Type'] = 'application/json';
    payload = JSON.stringify(body);
  }

  let res;
  try {
    res = await fetch(`${API_BASE}${path}`, { method, headers, body: payload, signal });
  } catch (e) {
    if (e && e.name === 'AbortError') throw e;
    throw new ApiError(0, null, 'Could not reach the server. Check your connection and try again.');
  }

  const text = await res.text();
  let data = null;
  if (text) {
    try { data = JSON.parse(text); } catch { data = text; }
  }

  if (!res.ok) {
    const detail = data && typeof data === 'object' && 'detail' in data ? data.detail : (typeof data === 'string' ? data : null);
    if (res.status === 401 && auth && getToken() && unauthorizedHandler) unauthorizedHandler();
    throw new ApiError(res.status, detail, messageFrom(res.status, detail), data);
  }
  if (typeof data === 'string' && /^\s*</.test(data)) {
    // An HTML page where JSON was expected: the API proxy / base URL is wrong.
    throw new ApiError(res.status, null, 'The server returned a web page instead of API data. Check that the backend and the /api proxy are running.');
  }
  return data;
}

const get = (path, opts) => request('GET', path, opts);
const post = (path, body, opts) => request('POST', path, { ...opts, body });
const enc = encodeURIComponent;

// ---- meta (public) ----
export const health = (opts) => get('/health', { ...opts, auth: false });
// /ready answers 503 with a body when something is down; surface that body instead of throwing.
export async function ready(opts) {
  try {
    return await get('/ready', { ...opts, auth: false });
  } catch (e) {
    if (e instanceof ApiError && e.status === 503 && e.body && typeof e.body === 'object') {
      if (e.body.checks) return e.body;
      if (e.body.detail && typeof e.body.detail === 'object' && e.body.detail.checks) return e.body.detail;
    }
    throw e;
  }
}
export const providersStatus = (opts) => get('/providers/status', { ...opts, auth: false });
export const plans = (opts) => get('/plans', { ...opts, auth: false });

// ---- accounts ----
export const register = (email, password) => post('/auth/register', { email, password }, { auth: false });
export const login = (email, password) => post('/auth/login', { email, password }, { auth: false });
export const me = (opts) => get('/auth/me', opts);

// ---- credits & payments ----
export const credits = (opts) => get('/credits', opts);
export const createOrder = (target) => post('/credits/create-order', target); // {pack} | {plan}
export const verifyPayment = (razorpay_order_id, razorpay_payment_id, razorpay_signature) =>
  post('/credits/verify-payment', { razorpay_order_id, razorpay_payment_id, razorpay_signature });

// ---- jobs ----
export const createJob = (body, idempotencyKey) => post('/jobs', body, { idempotencyKey });
export const listJobs = (opts) => get('/jobs', opts);
export const getJob = (id, opts) => get(`/jobs/${enc(id)}`, opts);
export const getResult = (id, opts) => get(`/jobs/${enc(id)}/result`, opts);
export const getQualityReport = (id, opts) => get(`/jobs/${enc(id)}/quality-report`, opts);
export const approveJob = (id, approver) => post(`/jobs/${enc(id)}/approve`, { approver });
export const cancelJob = (id) => post(`/jobs/${enc(id)}/cancel`);
export const publishJob = (id) => post(`/jobs/${enc(id)}/publish`);

// ---- uploads, boost, analytics ----
export function uploadImages(files) {
  const form = new FormData();
  files.forEach((f) => form.append('files', f, f.name));
  return request('POST', '/uploads', { form });
}
export const boostPrompt = (prompt, language, style, opts) => {
  const body = { prompt, language };
  if (style) body.style = style;
  return post('/prompt/boost', body, opts);
};
export const analyticsOverview = (opts) => get('/analytics/overview', opts);

// ---- media URLs (img/video tags cannot send headers, so the signature rides in the query) ----
// `job` is the raw API job object.
const sigQuery = (job, extra = '') => {
  const q = [];
  if (job && job.media_sig) q.push(`sig=${enc(job.media_sig)}`);
  if (extra) q.push(extra);
  return q.length ? `?${q.join('&')}` : '';
};
export const videoUrl = (job, { download = false } = {}) =>
  `${API_BASE}/jobs/${enc(job.id)}/video${sigQuery(job, download ? 'download=1' : '')}`;
export const sceneImageUrl = (job, index) => `${API_BASE}/jobs/${enc(job.id)}/scenes/${index}/image${sigQuery(job)}`;
// Converted download. The server converts on the first request (then caches), so callers should show a busy state.
export const downloadUrl = (job, formatId) =>
  `${API_BASE}/jobs/${enc(job.id)}/download${sigQuery(job, `format=${enc(formatId)}`)}`;
export const handoffUrl = (job) => `${API_BASE}/jobs/${enc(job.id)}/handoff${sigQuery(job)}`;
