import { WEATHER_SECTION_IDS, getWeatherSectionNavCopy } from "./weatherSectionNavCopy";

export function WeatherSectionNav({
  activeId = "weather",
  compact = false,
  disabled = false,
  language = "it",
  onNavigate,
}) {
  const copy = getWeatherSectionNavCopy(language);
  const resolvedActiveId = WEATHER_SECTION_IDS.includes(activeId) ? activeId : "weather";

  return (
    <nav
      aria-label={copy.ariaLabel}
      className={`mf-weather-section-nav${compact ? " mf-weather-section-nav--compact" : ""}`}
    >
      {WEATHER_SECTION_IDS.map((id) => {
        const selected = resolvedActiveId === id;

        return (
          <button
            aria-current={selected ? "page" : undefined}
            className={`mf-weather-section-nav__item${selected ? " is-active" : ""}`}
            disabled={disabled}
            key={id}
            onClick={() => onNavigate?.(id)}
            type="button"
          >
            {copy.items[id]}
          </button>
        );
      })}
    </nav>
  );
}
