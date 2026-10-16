import { EVENT_RADII } from "./eventsRadius";

export function EventsRadiusSelect({ radius = 20, onChange, disabled = false, language = "it" }) {
  return <select
    className="mf-events-radius"
    aria-label={language === "fur" ? "Rai di ricercje events" : "Raggio di ricerca eventi"}
    value={radius}
    disabled={disabled}
    onChange={(event) => {
      const value = Number(event.target.value);
      if (EVENT_RADII.includes(value)) onChange?.(value);
    }}
  >{EVENT_RADII.map((value) => <option key={value} value={value}>{value} km</option>)}</select>;
}
