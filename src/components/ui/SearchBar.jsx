import { cn } from '../../utils/classnames';

export function SearchBar({ value, onChange, placeholder = 'Search…', onClear, className }) {
  return (
    <div className={cn('search-bar', className)}>
      <span className="search-icon" aria-hidden="true">🔍</span>
      <input
        type="search"
        className="search-input"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        aria-label={placeholder}
      />
      {value && onClear && (
        <button className="search-clear" onClick={onClear} aria-label="Clear search">✕</button>
      )}
    </div>
  );
}
