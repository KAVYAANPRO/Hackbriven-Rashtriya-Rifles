import { useState } from 'react';
import { cn } from '../../utils/classnames';

export function Tabs({ tabs, defaultTab, onChange, className }) {
  const [active, setActive] = useState(defaultTab || tabs[0]?.id);

  const handleSelect = (id) => {
    setActive(id);
    onChange?.(id);
  };

  const activeTab = tabs.find((t) => t.id === active);

  return (
    <div className={cn('tabs', className)}>
      <div className="tabs-list" role="tablist">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            role="tab"
            aria-selected={active === tab.id}
            className={cn('tab', active === tab.id && 'tab-active')}
            onClick={() => handleSelect(tab.id)}
          >
            {tab.label}
          </button>
        ))}
      </div>
      <div className="tabs-content" role="tabpanel">
        {activeTab?.content}
      </div>
    </div>
  );
}
