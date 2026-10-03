// Job status and type constants
export const JOB_STATUS = {
  PENDING: 'pending',
  PROCESSING: 'processing',
  COMPLETED: 'completed',
  FAILED: 'failed',
  CANCELLED: 'cancelled',
};

export const JOB_TYPE = {
  GENERATE: 'generate',
  ADAPT: 'adapt',
  BOOST: 'boost',
  EXPORT: 'export',
};

export const ACTIVE_JOB_STATUSES = [JOB_STATUS.PENDING, JOB_STATUS.PROCESSING];
export const TERMINAL_JOB_STATUSES = [JOB_STATUS.COMPLETED, JOB_STATUS.FAILED, JOB_STATUS.CANCELLED];

export const isActiveJob = (status) => ACTIVE_JOB_STATUSES.includes(status);
export const isTerminalJob = (status) => TERMINAL_JOB_STATUSES.includes(status);

export const JOB_POLL_INTERVAL_MS = 3000;
export const JOB_MAX_RETRIES = 60;
