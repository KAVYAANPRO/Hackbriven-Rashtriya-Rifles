import { useState, useMemo } from 'react';

export function usePagination({ total, pageSize = 10, initialPage = 1 }) {
  const [page, setPage] = useState(initialPage);

  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const offset = (page - 1) * pageSize;
  const hasPrev = page > 1;
  const hasNext = page < totalPages;

  const goTo = (p) => setPage(Math.min(Math.max(1, p), totalPages));
  const next = () => goTo(page + 1);
  const prev = () => goTo(page - 1);
  const reset = () => setPage(1);

  const pages = useMemo(() => {
    const list = [];
    for (let i = 1; i <= totalPages; i++) list.push(i);
    return list;
  }, [totalPages]);

  return { page, totalPages, offset, hasPrev, hasNext, goTo, next, prev, reset, pages };
}
