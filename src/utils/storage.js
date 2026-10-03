// Storage utilities (wraps localStorage/sessionStorage safely)

const safeJSON = {
  parse: (str, fallback = null) => {
    try {
      return JSON.parse(str);
    } catch {
      return fallback;
    }
  },
  stringify: (val) => {
    try {
      return JSON.stringify(val);
    } catch {
      return null;
    }
  },
};

export const local = {
  get: (key, fallback = null) => {
    const raw = localStorage.getItem(key);
    if (raw === null) return fallback;
    return safeJSON.parse(raw, raw);
  },
  set: (key, value) => {
    const str = typeof value === 'string' ? value : safeJSON.stringify(value);
    if (str !== null) localStorage.setItem(key, str);
  },
  remove: (key) => localStorage.removeItem(key),
  clear: () => localStorage.clear(),
};

export const session = {
  get: (key, fallback = null) => {
    const raw = sessionStorage.getItem(key);
    if (raw === null) return fallback;
    return safeJSON.parse(raw, raw);
  },
  set: (key, value) => {
    const str = typeof value === 'string' ? value : safeJSON.stringify(value);
    if (str !== null) sessionStorage.setItem(key, str);
  },
  remove: (key) => sessionStorage.removeItem(key),
  clear: () => sessionStorage.clear(),
};

export const STORAGE_KEYS = {
  AUTH_TOKEN: 'ideafeed_token',
  USER: 'ideafeed_user',
  THEME: 'ideafeed_theme',
  LAST_ROUTE: 'ideafeed_last_route',
};
