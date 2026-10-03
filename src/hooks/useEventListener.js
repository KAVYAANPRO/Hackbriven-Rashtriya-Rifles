import { useEffect, useRef } from 'react';

export function useEventListener(eventName, handler, element = window, options) {
  const handlerRef = useRef(handler);
  handlerRef.current = handler;

  useEffect(() => {
    const target = element?.current ?? element;
    if (!target?.addEventListener) return;
    const listener = (e) => handlerRef.current(e);
    target.addEventListener(eventName, listener, options);
    return () => target.removeEventListener(eventName, listener, options);
  }, [eventName, element, options]);
}
