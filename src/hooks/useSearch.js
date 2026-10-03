import { useState, useMemo } from 'react';
import { useDebounce } from './useDebounce';

export function useSearch(items, searchFn, debounceMs = 300) {
  const [query, setQuery] = useState('');
  const debouncedQuery = useDebounce(query, debounceMs);

  const results = useMemo(() => {
    if (!debouncedQuery.trim()) return items;
    return items.filter((item) => searchFn(item, debouncedQuery.toLowerCase()));
  }, [items, debouncedQuery, searchFn]);

  const clear = () => setQuery('');

  return { query, setQuery, results, clear, isFiltered: Boolean(debouncedQuery) };
}
