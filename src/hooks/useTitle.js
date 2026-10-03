import { useEffect } from 'react';

const BASE_TITLE = 'IdeaFeed AI';

export function useTitle(title) {
  useEffect(() => {
    document.title = title ? `${title} — ${BASE_TITLE}` : BASE_TITLE;
    return () => { document.title = BASE_TITLE; };
  }, [title]);
}
