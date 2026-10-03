export function SlideCounter({ current, total, className }) {
  return (
    <div className={`slide-counter ${className || ''}`}>
      <span className="slide-current">{current}</span>
      <span className="slide-separator">/</span>
      <span className="slide-total">{total}</span>
    </div>
  );
}
