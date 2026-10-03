import { formatCredits } from '../utils/format';

export function CreditBadge({ credits, low = 10, className }) {
  const isLow = credits <= low;
  return (
    <span className={`credit-badge ${isLow ? 'credit-badge-low' : ''} ${className || ''}`}>
      <span className="credit-icon">⬡</span>
      <span className="credit-count">{formatCredits(credits)}</span>
      {isLow && <span className="credit-low-label">Low</span>}
    </span>
  );
}
