import { useState } from 'react';
import { cn } from '../../utils/classnames';

export function Accordion({ items, allowMultiple = false, className }) {
  const [openIds, setOpenIds] = useState(new Set());

  const toggle = (id) => {
    setOpenIds((prev) => {
      const next = new Set(allowMultiple ? prev : []);
      prev.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  };

  return (
    <div className={cn('accordion', className)}>
      {items.map((item) => {
        const isOpen = openIds.has(item.id);
        return (
          <div key={item.id} className={cn('accordion-item', isOpen && 'accordion-item-open')}>
            <button className="accordion-trigger" onClick={() => toggle(item.id)} aria-expanded={isOpen}>
              <span>{item.title}</span>
              <span className="accordion-icon">{isOpen ? '−' : '+'}</span>
            </button>
            {isOpen && <div className="accordion-content">{item.content}</div>}
          </div>
        );
      })}
    </div>
  );
}
