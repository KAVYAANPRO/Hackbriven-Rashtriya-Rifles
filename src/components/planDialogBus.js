import { useSyncExternalStore } from 'react';

// Tiny module-level store for "which plan is being purchased". null means the dialog is closed.
let current = null;
const listeners = new Set();

const emit = () => listeners.forEach((l) => l());

export function openPlanDialog(id) {
  if (current === id) return;
  current = id;
  emit();
}

export function closePlanDialog() {
  if (current === null) return;
  current = null;
  emit();
}

const subscribe = (l) => {
  listeners.add(l);
  return () => listeners.delete(l);
};
const getSnapshot = () => current;

// Returns { planId, close }. planId is a string or null (both stable primitives).
export function usePlanDialog() {
  const planId = useSyncExternalStore(subscribe, getSnapshot, () => null);
  return { planId, close: closePlanDialog };
}
