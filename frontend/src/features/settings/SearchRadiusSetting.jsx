import { useId } from "react";
import { MapPin } from "lucide-react";
import { DEFAULT_EVENTS_RADIUS_KM, normalizeEventsRadius } from "../../app/eventsRadiusPreference";
import { EVENT_RADII } from "../events/eventsRadius";

export function SearchRadiusSetting({ language = "it", radius = DEFAULT_EVENTS_RADIUS_KM, onChange }) {
  const id = useId();
  const title = language === "fur" ? "Rai di ricercje" : "Raggio di ricerca";
  const detail = language === "fur"
    ? "Events e marcjâts ator de localitât selezionade."
    : "Eventi e mercati intorno alla località selezionata.";
  return <div className="mf-settings-search-radius">
    <span className="mf-settings-row__icon"><MapPin size={20} aria-hidden="true" /></span>
    <label htmlFor={id}>{title}</label>
    <select id={id} aria-describedby={`${id}-description`} value={normalizeEventsRadius(radius) ?? DEFAULT_EVENTS_RADIUS_KM}
      onChange={event => onChange?.(normalizeEventsRadius(event.target.value) ?? DEFAULT_EVENTS_RADIUS_KM)}>
      {EVENT_RADII.map(value => <option key={value} value={value}>{value} km</option>)}
    </select>
    <p id={`${id}-description`}>{detail}</p>
  </div>;
}
