import { Glasses, Info, ShieldCheck, Sun, TreePalm } from "lucide-react";
import { useId } from "react";
import { UV_LEVELS, uvLevel } from "./uvLevels";
import { selectUvCurveSamples } from "./uvCurveWindow";
import { useWeatherUvCardState } from "./useWeatherUvCardState";

const number = value => new Intl.NumberFormat("it-IT", { maximumFractionDigits: 1 }).format(value);
const hour = time => new Intl.DateTimeFormat("it-IT", { timeZone: "Europe/Rome", hour: "2-digit", minute: "2-digit" }).format(time);
const stamp = time => new Intl.DateTimeFormat("it-IT", {
  timeZone: "Europe/Rome", day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit",
}).format(time);
const ink = ["#28752c", "#806500", "#ad4b00", "#ba2828", "#803c9e"];

export function UvCurve({ model, point, fur }) {
  const id = useId();
  const samples = selectUvCurveSamples(model, point);
  if (samples.length < 2) return null;
  const first = samples[0], last = samples.at(-1);
  const ceiling = Math.max(1, ...samples.map(sample => sample.value));
  const curveColor = ink[UV_LEVELS.indexOf(uvLevel(model.maximum ?? Math.max(...samples.map(sample => sample.value))))];
  const x = time => 12 + (time - first.time) / (last.time - first.time) * 336;
  const y = value => 64 - value / ceiling * 42;
  const points = samples.map(sample => `${x(sample.time)},${y(sample.value)}`).join(" ");
  const peak = samples.find(sample => sample.time === model.peakTime);
  const current = samples.find(sample => sample.time === model.current.time);
  const closeLabels = current && peak && Math.abs(x(current.time) - x(peak.time)) < 48;
  return <figure className="mf-weather-uv-curve" style={{ "--uv-curve-color": curveColor }}>
    <svg viewBox="0 0 360 82" role="img" aria-labelledby={`${id}-title ${id}-desc`}>
      <title id={`${id}-title`}>{fur ? "Andament UV previodût" : "Andamento UV previsto"}</title>
      <desc id={`${id}-desc`}>{samples.map(sample => `${hour(sample.time)}: ${number(sample.value)}`).join("; ")}</desc>
      <defs><linearGradient id={`${id}-fill`} x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor={curveColor} stopOpacity=".18" /><stop offset="100%" stopColor={curveColor} stopOpacity=".02" /></linearGradient></defs>
      <path d={`M ${x(first.time)} 64 L ${points} L ${x(last.time)} 64 Z`} fill={`url(#${id}-fill)`} />
      {/* Join real hourly samples only; no synthetic bell or interpolated UV value. */}
      <polyline points={points} className="mf-weather-uv-curve__line" />
      {peak ? <g data-uv-peak={peak.time}>
        <circle cx={x(peak.time)} cy={y(peak.value)} r="4" className="mf-weather-uv-curve__peak" />
        <text x={Math.max(28, Math.min(332, x(peak.time)))} y={y(peak.value) - 11} textAnchor="middle">{hour(peak.time)}</text>
      </g> : null}
      {current ? <g data-uv-current={current.time}>
        <circle cx={x(current.time)} cy={y(current.value)} r="5" className="mf-weather-uv-curve__current" />
        {current.time !== peak?.time ? <text className="mf-weather-uv-curve__current-label"
          x={Math.max(28, Math.min(332, x(current.time)))}
          y={closeLabels ? Math.min(59, y(current.value) + 18) : y(current.value) - 11}
          textAnchor="middle">{hour(current.time)}</text> : null}
      </g> : null}
      <text x="12" y="80">{hour(first.time)}</text>
      <text x="348" y="80" textAnchor="end">{hour(last.time)}</text>
    </svg>
  </figure>;
}

export function UvValues({ model, point, language = "it" }) {
  const fur = language === "fur";
  const currentUsable = model.currentUsable !== false;
  const label = level => level?.[fur ? "fur" : "it"];
  const currentLevel = uvLevel(model.current.value);
  const peakLevel = uvLevel(model.maximum);
  const currentColor = ink[UV_LEVELS.indexOf(currentLevel)];
  return <>
    <dl className="mf-weather-uv-values">
      <div>
        <dt className="mf-weather-uv-sr-only">{currentUsable
          ? (fur ? "Previodût cumò" : "Previsto adesso")
          : (fur ? "Ultin dât disponibil" : "Ultimo dato disponibile")}</dt>
        <dd><span className="mf-weather-uv-current-number" style={{ color: currentColor }}>{number(model.current.value)}</span>
          <span className="mf-weather-uv-current-meta">{label(currentLevel)}<small>{currentUsable
            ? `${fur ? "aes" : "ore"} ${hour(model.current.time)}`
            : stamp(model.current.time)}</small></span></dd>
      </div>
      {currentUsable ? <div className="mf-weather-uv-values__peak">
        <dt>{fur ? "Pic" : "Picco"}<span className="mf-weather-uv-sr-only">{fur ? " previodût par vuê" : " previsto oggi"}</span></dt>
        <dd><span className="mf-weather-uv-peak-number">{model.maximum === null ? "—" : number(model.maximum)}</span>
          {model.maximum === null ? <small>{fur ? "Zornade incomplete" : "Giornata incompleta"}</small>
            : <small><span className="mf-weather-uv-sr-only">{label(peakLevel)}</span> · {hour(model.peakTime)}</small>}</dd>
      </div> : null}
    </dl>
    {currentUsable ? <UvCurve model={model} point={point} fur={fur} /> : null}
  </>;
}

export function UvAdvice({ model, language = "it" }) {
  const fur = language === "fur";
  const currentLevel = uvLevel(model.current.value);
  const peakLevel = uvLevel(model.maximum);
  // Keep advice tied to the daily peak, not to a low evening UV.
  // For a partial day only the current forecast hour is available.
  const risk = UV_LEVELS.indexOf(peakLevel || currentLevel);
  const advice = fur
    ? (risk === 0 ? "Ocjâi di soreli" : risk < 3 ? "Ombre tes oris centrâls" : "Evite il soreli tes oris centrâls")
    : (risk === 0 ? "Occhiali da sole" : risk < 3 ? "Ombra nelle ore centrali" : "Evita il sole nelle ore centrali");
  const AdviceIcon = risk === 0 ? Glasses : TreePalm;
  return <ul className="mf-weather-uv-advice" aria-label={fur ? "Conseis di protezion" : "Consigli di protezione"}>
      <li><AdviceIcon size={17} aria-hidden="true" />{advice}</li>
      {risk > 0 ? <li><ShieldCheck size={17} aria-hidden="true" />{fur ? "Proteç piel e voi" : "Proteggi pelle e occhi"}</li> : null}
    </ul>;
}

export function WeatherUvContent({ compactDetail = false, error, forecastDate, language = "it", model, point, saved }) {
  const fur = language === "fur";
  return <>
    {model ? <UvValues model={model} point={point} language={language} /> : <p>{fur ? "Prevision UV no ancjemò disponibile." : "Previsione UV non ancora disponibile."}</p>}
    {model && model.currentUsable === false ? <p className="mf-weather-uv-note" role="status">
      {fur ? "Ultin dât verificât disponibil; la prevision no je inzornade."
        : "Ultimo dato verificato disponibile; la previsione non è aggiornata."}
    </p> : model && saved && error ? <p className="mf-weather-uv-note" role="status">
      {compactDetail
        ? (fur ? "Prevision orarie de radiazion solâr." : "Previsione oraria della radiazione solare.")
        : (fur ? "Prevision za cjariade. Inzornament no disponibile." : "Previsione già caricata. Aggiornamento non disponibile.")}
    </p> : null}
    <footer className="mf-weather-cams-card__footer mf-weather-uv-footer">
      {model && model.currentUsable !== false ? <UvAdvice model={model} language={language} /> : null}
      {model ? <details className="mf-weather-uv-source">
        <summary aria-label={fur ? "Font e detais de prevision UV" : "Fonte e dettagli della previsione UV"}>
          <span>{fur ? "Font" : "Fonte"}: Copernicus CAMS</span><Info size={16} aria-hidden="true" />
        </summary>
        <div>
          <p>{fur ? "Prevision dal" : "Previsione del"} {forecastDate} · {fur ? "Corse" : "Corsa"} {stamp(model.run)}</p>
          <p>{fur ? "Dâts oraris di model, no misuris in timp reâl." : "Dati orari di modello, non misure in tempo reale."}</p>
          {saved ? <p>{fur ? "Prevision za cjariade." : "Previsione già caricata."}</p> : null}
          <ul>{UV_LEVELS.map(level => <li key={level.range}>{level.range} · {level[fur ? "fur" : "it"]}</li>)}</ul>
        </div>
      </details> : <small>{fur ? "In spiete di dâts UV verificâts." : "In attesa di dati UV verificati."}</small>}
    </footer>
  </>;
}

export function WeatherUvCard({ language = "it", point }) {
  const fur = language === "fur";
  const state = useWeatherUvCardState({ point });

  return <section className="mf-weather-cams-card mf-weather-uv-card" aria-label={fur ? "Indiç UV" : "Indice UV"}>
    <header className="mf-weather-cams-card__header">
      <Sun size={24} aria-hidden="true" />
      <div><h2>{fur ? "Indiç UV" : "Indice UV"}</h2>
        <p>{fur ? "Prevision de radiazion ultraviolet" : "Previsione della radiazione ultravioletta"}</p>
      </div>
    </header>
    <WeatherUvContent {...state} language={language} point={point} />
  </section>;
}
