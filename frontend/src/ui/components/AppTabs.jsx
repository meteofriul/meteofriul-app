import { getNextAppTabIndex } from "./appTabsKeyboard";

export function AppTabs({ activeId, ariaLabel, items, onChange }) {
  const handleKeyDown = (event, currentIndex) => {
    const nextIndex = getNextAppTabIndex(event.key, currentIndex, items.length);
    if (nextIndex === null) return;

    event.preventDefault();
    onChange(items[nextIndex].id);

    const tablist = event.currentTarget.closest('[role="tablist"]');
    const tabs = tablist ? Array.from(tablist.querySelectorAll('[role="tab"]')) : [];
    tabs[nextIndex]?.focus();
  };

  return (
    <div aria-label={ariaLabel} aria-orientation="horizontal" className="mf-tabs" role="tablist">
      {items.map((item, index) => {
        const selected = item.id === activeId;
        const describedLabel = item.meta ? `${item.label} ${item.meta}` : item.label;

        return (
          <button
            aria-controls={item.controlsId}
            aria-label={item.ariaLabel || describedLabel}
            aria-selected={selected}
            className={`mf-tab ${selected ? "is-active" : ""}`}
            id={item.tabId}
            key={item.id}
            onClick={() => onChange(item.id)}
            onKeyDown={(event) => handleKeyDown(event, index)}
            role="tab"
            tabIndex={selected ? 0 : -1}
            type="button"
          >
            <span className="mf-tab__label">{item.label}</span>
            {item.meta ? <span className="mf-tab__meta">{item.meta}</span> : null}
          </button>
        );
      })}
    </div>
  );
}
