import { useRef, useState } from 'react';
import Icon from '../Icon.jsx';
import { MAX_IMAGES, fmtSize } from './useImages.js';

export default function ImageDrop({ files, errors, onAdd, onRemove }) {
  const inputRef = useRef(null);
  const depth = useRef(0);
  const [over, setOver] = useState(false);

  const hasFiles = (e) => Array.from(e.dataTransfer?.types || []).includes('Files');

  const onDragEnter = (e) => {
    if (!hasFiles(e)) return;
    e.preventDefault();
    depth.current += 1;
    setOver(true);
  };
  const onDragOver = (e) => {
    if (!hasFiles(e)) return;
    e.preventDefault();
    e.dataTransfer.dropEffect = 'copy';
  };
  const onDragLeave = () => {
    depth.current = Math.max(0, depth.current - 1);
    if (depth.current === 0) setOver(false);
  };
  const onDrop = (e) => {
    if (!hasFiles(e)) return;
    e.preventDefault();
    depth.current = 0;
    setOver(false);
    onAdd(e.dataTransfer.files);
  };
  const onPick = (e) => {
    onAdd(e.target.files);
    e.target.value = ''; // allow picking the same file again after removing it
  };

  return (
    <div className="cx-images">
      <input ref={inputRef} type="file" accept="image/*" multiple hidden onChange={onPick} tabIndex={-1} />
      <button
        type="button"
        className={'cx-drop' + (over ? ' is-over' : '')}
        onClick={() => inputRef.current && inputRef.current.click()}
        onDragEnter={onDragEnter}
        onDragOver={onDragOver}
        onDragLeave={onDragLeave}
        onDrop={onDrop}
      >
        <Icon name="plus" size={20} />
        <span className="cx-drop-t">{over ? 'Drop to add' : 'Drop images here'}</span>
        <span className="cx-drop-s">or <u>browse files</u> · image files, up to {MAX_IMAGES}, 10 MB each</span>
      </button>

      {errors.length > 0 && (
        <ul className="cx-errs" role="alert">
          {errors.map((m) => <li key={m}>{m}</li>)}
        </ul>
      )}

      {files.length > 0 && (
        <ul className="cx-thumbs" aria-label="Selected reference images">
          {files.map((f) => (
            <li key={f.id} className="cx-thumb">
              <img src={f.url} alt={f.name} />
              <div className="cx-thumb-meta">
                <b title={f.name}>{f.name}</b>
                <span>{fmtSize(f.size)}</span>
              </div>
              <button type="button" className="cx-thumb-x" onClick={() => onRemove(f.id)} aria-label={`Remove ${f.name}`}>
                <Icon name="x" size={13} />
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
