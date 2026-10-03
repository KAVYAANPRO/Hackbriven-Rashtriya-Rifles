import { createContext, useContext, useState, useCallback } from 'react';

const CreditsContext = createContext(null);

export function CreditsProvider({ children, initialCredits = 0 }) {
  const [credits, setCredits] = useState(initialCredits);
  const [history, setHistory] = useState([]);

  const deduct = useCallback((amount, reason = 'generation') => {
    setCredits((prev) => {
      if (prev < amount) throw new Error('Insufficient credits');
      const next = prev - amount;
      setHistory((h) => [{ type: 'debit', amount, reason, balance: next, ts: Date.now() }, ...h]);
      return next;
    });
  }, []);

  const add = useCallback((amount, reason = 'purchase') => {
    setCredits((prev) => {
      const next = prev + amount;
      setHistory((h) => [{ type: 'credit', amount, reason, balance: next, ts: Date.now() }, ...h]);
      return next;
    });
  }, []);

  const sync = useCallback((serverCredits) => {
    setCredits(serverCredits);
  }, []);

  const hasEnough = (amount) => credits >= amount;

  return (
    <CreditsContext.Provider value={{ credits, history, deduct, add, sync, hasEnough }}>
      {children}
    </CreditsContext.Provider>
  );
}

export function useCreditsCtx() {
  const ctx = useContext(CreditsContext);
  if (!ctx) throw new Error('useCreditsCtx must be used within CreditsProvider');
  return ctx;
}
