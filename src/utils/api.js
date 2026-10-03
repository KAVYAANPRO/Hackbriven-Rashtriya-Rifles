// Generic API fetch wrapper with auth header injection
import { local, STORAGE_KEYS } from './storage';
import { API_BASE, TIMEOUT_MS } from '../constants/api';

export class ApiError extends Error {
  constructor(message, status, body) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.body = body;
  }
}

async function request(path, options = {}) {
  const token = local.get(STORAGE_KEYS.AUTH_TOKEN);
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);

  const headers = {
    'Content-Type': 'application/json',
    ...(token && { Authorization: `Bearer ${token}` }),
    ...options.headers,
  };

  try {
    const res = await fetch(`${API_BASE}${path}`, {
      ...options,
      headers,
      signal: controller.signal,
    });

    clearTimeout(timer);
    const body = res.headers.get('content-type')?.includes('application/json')
      ? await res.json()
      : await res.text();

    if (!res.ok) throw new ApiError(body?.detail || res.statusText, res.status, body);
    return body;
  } catch (err) {
    clearTimeout(timer);
    throw err;
  }
}

export const api = {
  get: (path, opts) => request(path, { ...opts, method: 'GET' }),
  post: (path, data, opts) => request(path, { ...opts, method: 'POST', body: JSON.stringify(data) }),
  put: (path, data, opts) => request(path, { ...opts, method: 'PUT', body: JSON.stringify(data) }),
  patch: (path, data, opts) => request(path, { ...opts, method: 'PATCH', body: JSON.stringify(data) }),
  delete: (path, opts) => request(path, { ...opts, method: 'DELETE' }),
};
