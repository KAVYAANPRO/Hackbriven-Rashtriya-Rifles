import { useState, useRef, useEffect } from 'react';
import { cn } from '../../utils/classnames';

export function Tooltip({ children, content, placement = 'top', delay = 200 }) {
  const [visible, setVisible] = useState(false);
  const timerRef = useRef(null);

  const show = () => {
    timerRef.current = setTimeout(() => setVisible(true), delay);
  };

  const hide = () => {
    clearTimeout(timerRef.current);
    setVisible(false);
  };

  useEffect(() => () => clearTimeout(timerRef.current), []);

  return (
    <span className="tooltip-wrapper" onMouseEnter={show} onMouseLeave={hide} onFocus={show} onBlur={hide}>
      {children}
      {visible && content && (
        <span className={cn('tooltip', `tooltip-${placement}`)} role="tooltip">
          {content}
        </span>
      )}
    </span>
  );
}
