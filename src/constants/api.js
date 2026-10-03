// API endpoint constants
export const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000';

export const ENDPOINTS = {
  // Auth
  LOGIN: '/auth/login',
  LOGOUT: '/auth/logout',
  REFRESH: '/auth/refresh',

  // Jobs
  JOBS: '/jobs',
  JOB_BY_ID: (id) => `/jobs/${id}`,
  JOB_STATUS: (id) => `/jobs/${id}/status`,

  // AI Deck generation
  GENERATE: '/generate',
  ADAPT: '/generate/adapt',
  BOOST: '/generate/boost',

  // Analytics
  ANALYTICS: '/analytics',
  ANALYTICS_SUMMARY: '/analytics/summary',

  // Credits
  CREDITS: '/credits',
  CREDITS_HISTORY: '/credits/history',
  CREDITS_PURCHASE: '/credits/purchase',

  // Settings
  SETTINGS: '/settings',
  PROFILE: '/settings/profile',
};

export const TIMEOUT_MS = 30_000;
export const MAX_RETRIES = 3;
