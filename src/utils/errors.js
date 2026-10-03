// Error handling utilities

export const ERROR_CODES = {
  NETWORK: 'NETWORK_ERROR',
  TIMEOUT: 'TIMEOUT_ERROR',
  AUTH: 'AUTH_ERROR',
  NOT_FOUND: 'NOT_FOUND',
  SERVER: 'SERVER_ERROR',
  VALIDATION: 'VALIDATION_ERROR',
  CREDITS: 'INSUFFICIENT_CREDITS',
};

export function getErrorMessage(error) {
  if (!error) return 'An unknown error occurred';

  // AbortError = timeout
  if (error.name === 'AbortError') return 'Request timed out. Please try again.';

  // Network error
  if (error.name === 'TypeError' && !navigator.onLine) return 'You appear to be offline.';

  // ApiError with status codes
  if (error.status) {
    if (error.status === 401) return 'Session expired. Please log in again.';
    if (error.status === 403) return 'You do not have permission to do this.';
    if (error.status === 404) return 'The requested resource was not found.';
    if (error.status === 402) return 'Insufficient credits for this action.';
    if (error.status >= 500) return 'Server error. Please try again later.';
  }

  return error.message || 'Something went wrong. Please try again.';
}

export function isAuthError(error) {
  return error?.status === 401;
}

export function isCreditError(error) {
  return error?.status === 402;
}
