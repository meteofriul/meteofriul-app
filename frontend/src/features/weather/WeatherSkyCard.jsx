import { SunMoon } from "lucide-react";
import { SkyCard } from "../almanac/AlmanacView";
import { buildAlmanacViewModel } from "../almanac/almanacViewModel";

export function WeatherSkyCard({ location, language = "it", now = new Date() }) {
  const model = buildAlmanacViewModel({ location, language, date: now, now });
  const title = language === "fur" ? "Soreli e Lune" : "Sole e Luna";
  return <section className="mf-weather-sky" aria-label={title}>
    <header><SunMoon aria-hidden="true" size={22} /><span>
      <strong>{title}</strong>
    </span></header>
    <div className="mf-weather-sky__details">
      <p>{location?.city || location?.municipality?.name} · {model.dayLabel}</p>
      <SkyCard model={model} separateNight />
    </div>
  </section>;
}
