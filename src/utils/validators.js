// Validation utilities

export const isEmail = (email) => {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
};

export const isPhone = (phone) => {
  return /^(\+91|91)?[6-9]\d{9}$/.test(phone.replace(/\s/g, ''));
};

export const isUrl = (url) => {
  try {
    new URL(url);
    return true;
  } catch {
    return false;
  }
};

export const isEmpty = (value) => {
  if (value === null || value === undefined) return true;
  if (typeof value === 'string') return value.trim().length === 0;
  if (Array.isArray(value)) return value.length === 0;
  if (typeof value === 'object') return Object.keys(value).length === 0;
  return false;
};

export const isWithinLength = (str, min = 0, max = Infinity) => {
  const len = str?.trim().length ?? 0;
  return len >= min && len <= max;
};

export const validatePrompt = (prompt) => {
  if (isEmpty(prompt)) return 'Prompt cannot be empty';
  if (!isWithinLength(prompt, 10, 2000)) return 'Prompt must be 10–2000 characters';
  return null;
};
