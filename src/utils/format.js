// Formatting utilities

export const formatDate = (date, options = {}) => {
  const d = date instanceof Date ? date : new Date(date);
  return new Intl.DateTimeFormat('en-IN', {
    dateStyle: 'medium',
    ...options,
  }).format(d);
};

export const formatRelativeTime = (date) => {
  const d = date instanceof Date ? date : new Date(date);
  const now = new Date();
  const diffMs = now - d;
  const diffSecs = Math.floor(diffMs / 1000);
  const diffMins = Math.floor(diffSecs / 60);
  const diffHours = Math.floor(diffMins / 60);
  const diffDays = Math.floor(diffHours / 24);

  if (diffSecs < 60) return 'just now';
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays < 7) return `${diffDays}d ago`;
  return formatDate(d);
};

export const formatCredits = (n) => {
  if (n >= 1000) return `${(n / 1000).toFixed(1)}k`;
  return String(n);
};

export const truncate = (str, maxLen = 80, suffix = '…') => {
  if (!str || str.length <= maxLen) return str;
  return str.slice(0, maxLen - suffix.length) + suffix;
};

export const capitalize = (str) => {
  if (!str) return '';
  return str.charAt(0).toUpperCase() + str.slice(1).toLowerCase();
};

export const slugify = (str) => {
  return str
    .toLowerCase()
    .trim()
    .replace(/[^\w\s-]/g, '')
    .replace(/[\s_-]+/g, '-')
    .replace(/^-+|-+$/g, '');
};
