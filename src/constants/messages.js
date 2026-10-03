// User-facing strings and messages
export const MSG = {
  // Auth
  AUTH_LOGIN_SUCCESS: 'Welcome back!',
  AUTH_LOGOUT_SUCCESS: 'You have been logged out.',
  AUTH_SESSION_EXPIRED: 'Your session has expired. Please log in again.',

  // Generation
  GEN_STARTED: 'Deck generation started. This may take a moment.',
  GEN_COMPLETE: 'Your deck is ready!',
  GEN_FAILED: 'Generation failed. Please try again.',
  GEN_INSUFFICIENT_CREDITS: 'Not enough credits. Top up to continue.',

  // Credits
  CREDITS_PURCHASE_SUCCESS: 'Credits added to your account.',
  CREDITS_PURCHASE_FAILED: 'Payment failed. Please try again.',
  CREDITS_LOW_WARNING: (n) => `Running low on credits — ${n} remaining.`,

  // Export
  EXPORT_STARTED: 'Preparing your download…',
  EXPORT_COMPLETE: 'Download ready!',
  EXPORT_FAILED: 'Export failed. Please try again.',

  // Settings
  SETTINGS_SAVED: 'Settings saved.',
  PROFILE_UPDATED: 'Profile updated successfully.',

  // Generic
  COPIED: 'Copied to clipboard!',
  NETWORK_ERROR: 'Network error. Check your connection.',
  UNKNOWN_ERROR: 'Something went wrong. Please try again.',
};
