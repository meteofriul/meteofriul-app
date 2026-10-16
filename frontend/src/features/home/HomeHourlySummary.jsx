import { Droplets } from "lucide-react";

import { HomeMeteoconIcon } from "./HomeMeteoconIcon";
import { getHourlyScrollTarget } from "./homeHourlyKeyboard";

export function HomeHourlySummary({ model }) {
  if (!model?.items?.length) return null;

  const handleKeyDown = (event) => {
    const grid = event.currentTarget;
    const target = getHourlyScrollTarget(event.key, {
      scrollLeft: grid.scrollLeft,
      scrollWidth: grid.scrollWidth,
      clientWidth: grid.clientWidth,
      slotWidth: grid.firstElementChild?.getBoundingClientRect().width,
    });
    if (target === null) return;
    event.preventDefault();
    grid.scrollTo({ left: target, behavior: "instant" });
  };

  return (
    <section aria-description={model.sourceLabel || undefined} aria-label={model.title} className="mf-home-hourly">
      <div aria-label={model.scrollLabel || model.title} className="mf-home-hourly__grid" onKeyDown={handleKeyDown} role="list" tabIndex={0}>
        {model.items.map((slot, index) => (
          <div
            aria-label={slot.ariaLabel}
            className={`mf-home-hourly__slot mf-home-hourly__slot--${slot.temperatureTone || "mild"}${index > 0 && slot.dateKey && slot.dateKey !== model.items[index - 1].dateKey ? " mf-home-hourly__slot--new-day" : ""}`}
            key={slot.timestamp || `${slot.time}-${index}`}
            role="listitem"
          >
            {slot.dayLabel ? <span className="mf-home-hourly__day">{slot.dayLabel}</span> : null}
            <time className="mf-home-hourly__time" dateTime={slot.timestamp}>{slot.time}</time>
            <HomeMeteoconIcon className="mf-home-hourly__icon" icon={slot.icon} size={26} />
            <strong>{slot.temperature}</strong>
            {slot.precipitationProbability !== null && slot.precipitationProbability !== undefined ? (
              <span className="mf-home-hourly__rain">
                <Droplets aria-hidden="true" size={11} strokeWidth={2.2} />
                {slot.precipitationProbability}%
              </span>
            ) : null}
          </div>
        ))}
      </div>
    </section>
  );
}
