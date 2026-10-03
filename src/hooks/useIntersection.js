import { useState, useEffect, useRef } from 'react';

export function useIntersection(options = {}) {
  const [entry, setEntry] = useState(null);
  const ref = useRef(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const observer = new IntersectionObserver(([e]) => setEntry(e), options);
    observer.observe(el);
    return () => observer.disconnect();
  }, [options.threshold, options.root, options.rootMargin]);

  return { ref, entry, isIntersecting: entry?.isIntersecting ?? false };
}

export function useLazyLoad() {
  const { ref, isIntersecting } = useIntersection({ rootMargin: '200px' });
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    if (isIntersecting) setLoaded(true);
  }, [isIntersecting]);

  return { ref, loaded };
}
