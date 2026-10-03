// Application routes
export const ROUTES = {
  HOME: '/',
  LOGIN: '/login',
  DASHBOARD: '/dashboard',
  CREATE: '/create',
  JOBS: '/jobs',
  JOB_DETAIL: '/jobs/:id',
  ANALYTICS: '/analytics',
  SETTINGS: '/settings',
  CREDITS: '/credits',
  ORCHESTRA: '/orchestra',
  PROFILE: '/profile',
  NOT_FOUND: '*',
};

export const getJobDetailRoute = (jobId) => `/jobs/${jobId}`;

export const isPublicRoute = (path) => {
  return [ROUTES.HOME, ROUTES.LOGIN].includes(path);
};
