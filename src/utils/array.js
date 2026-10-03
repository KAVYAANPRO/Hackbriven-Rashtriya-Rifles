// Array utility functions

export const groupBy = (arr, keyFn) => {
  return arr.reduce((acc, item) => {
    const key = keyFn(item);
    if (!acc[key]) acc[key] = [];
    acc[key].push(item);
    return acc;
  }, {});
};

export const sortBy = (arr, keyFn, dir = 'asc') => {
  return [...arr].sort((a, b) => {
    const ka = keyFn(a);
    const kb = keyFn(b);
    const cmp = ka < kb ? -1 : ka > kb ? 1 : 0;
    return dir === 'asc' ? cmp : -cmp;
  });
};

export const uniqueBy = (arr, keyFn) => {
  const seen = new Set();
  return arr.filter((item) => {
    const key = keyFn(item);
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
};

export const chunk = (arr, size) => {
  const chunks = [];
  for (let i = 0; i < arr.length; i += size) {
    chunks.push(arr.slice(i, i + size));
  }
  return chunks;
};

export const last = (arr) => arr[arr.length - 1];
export const first = (arr) => arr[0];
export const sum = (arr, fn = (x) => x) => arr.reduce((acc, x) => acc + fn(x), 0);
export const avg = (arr, fn = (x) => x) => arr.length ? sum(arr, fn) / arr.length : 0;
