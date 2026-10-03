import { useState, useCallback } from 'react';
import { useAsync } from './useAsync';

export function useCredits(initialCredits = 0) {
  const [credits, setCredits] = useState(initialCredits);

  const deduct = useCallback((amount) => {
    setCredits((prev) => {
      if (prev < amount) throw new Error('Insufficient credits');
      return prev - amount;
    });
  }, []);

  const add = useCallback((amount) => {
    setCredits((prev) => prev + amount);
  }, []);

  const reset = useCallback((amount = 0) => {
    setCredits(amount);
  }, []);

  const hasEnough = useCallback((amount) => credits >= amount, [credits]);

  return { credits, deduct, add, reset, hasEnough };
}
