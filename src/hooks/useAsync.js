import { useState, useCallback } from 'react';

export function useAsync(asyncFn) {
  const [status, setStatus] = useState('idle');
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  const execute = useCallback(async (...args) => {
    setStatus('loading');
    setError(null);
    try {
      const result = await asyncFn(...args);
      setData(result);
      setStatus('success');
      return result;
    } catch (err) {
      setError(err);
      setStatus('error');
      throw err;
    }
  }, [asyncFn]);

  const reset = useCallback(() => {
    setStatus('idle');
    setData(null);
    setError(null);
  }, []);

  return {
    execute,
    reset,
    status,
    data,
    error,
    isIdle: status === 'idle',
    isLoading: status === 'loading',
    isSuccess: status === 'success',
    isError: status === 'error',
  };
}
