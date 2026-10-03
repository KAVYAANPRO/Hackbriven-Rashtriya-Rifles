import { useCallback, useEffect, useRef, useState } from 'react';

export const MAX_IMAGES = 8;
export const MAX_BYTES = 10 * 1024 * 1024;

export function fmtSize(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

// Reference-image state with validation. Owns the object URLs: they are revoked on remove and on unmount.
export function useImages() {
  const [files, setFiles] = useState([]);
  const [errors, setErrors] = useState([]);
  const filesRef = useRef([]);
  const seq = useRef(0);

  const commit = (next) => {
    filesRef.current = next;
    setFiles(next);
  };

  const add = useCallback((list) => {
    const incoming = Array.from(list || []);
    if (!incoming.length) return;
    const errs = [];
    const next = [...filesRef.current];
    let overflow = 0;
    for (const f of incoming) {
      if (!f.type || !f.type.startsWith('image/')) {
        errs.push(`${f.name} is not an image.`);
      } else if (f.size > MAX_BYTES) {
        errs.push(`${f.name} is ${fmtSize(f.size)}. The limit is 10 MB per image.`);
      } else if (next.some((x) => x.name === f.name && x.size === f.size && x.file.lastModified === f.lastModified)) {
        errs.push(`${f.name} is already added.`);
      } else if (next.length >= MAX_IMAGES) {
        overflow += 1;
      } else {
        seq.current += 1;
        next.push({ id: 'img' + seq.current, file: f, name: f.name, size: f.size, url: URL.createObjectURL(f) });
      }
    }
    if (overflow) errs.push(`You can add up to ${MAX_IMAGES} images. ${overflow} not added.`);
    setErrors(errs);
    if (next.length !== filesRef.current.length) commit(next);
  }, []);

  const remove = useCallback((id) => {
    const hit = filesRef.current.find((f) => f.id === id);
    if (hit) URL.revokeObjectURL(hit.url);
    commit(filesRef.current.filter((f) => f.id !== id));
    setErrors([]);
  }, []);

  useEffect(() => () => {
    filesRef.current.forEach((f) => URL.revokeObjectURL(f.url));
  }, []);

  return { files, errors, add, remove };
}
