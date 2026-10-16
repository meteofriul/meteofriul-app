import { Flower2, Sun, SunMoon, Wind } from "lucide-react";

import { SkyCard } from "../almanac/AlmanacView";
import { buildAlmanacViewModel } from "../almanac/almanacViewModel";
import { WeatherCamsCard } from "./WeatherCamsCard";
import { WeatherEnvironmentGrid } from "./WeatherEnvironmentGrid";
import {
  UvCurve,
  WeatherUvContent,
} from "./WeatherUvCard";
import { uvLevel } from "./uvLevels";
import { getUvVisualTone } from "./uvVisualTone";
import { useWeatherUvCardState } from "./useWeatherUvCardState";

const AIR_FIELDS = [
  ["particulate_matter_2.5um", "PM2.5"],
  ["particulate_matter_10um", "PM10"],
  ["ozone", "O₃"],
  ["nitrogen_dioxide", "NO₂"],
];

const COPY = {
  it: {
    airData: "Dati Copernicus CAMS",
    airLastKnown: "Ultimo dato CAMS",
    airTitle: "Qualità dell’aria",
    airUnavailable: "Dati dell’aria non disponibili",
    activeSpecies: "attive",
    daylight: "Luce del giorno",
    pollenModel: "Previsione modellistica CAMS",
    pollenNoDominant: "Nessun valore sopra 0",
    pollenTitle: "Pollini",
    particulateUnavailable: "PM2.5 e PM10 non disponibili",
    species: "specie",
    uvLastKnown: "Ultimo dato verificato",
    uvPeak: "Picco",
    uvTitle: "Indice UV",
    uvUnavailable: "Previsione non disponibile",
  },
  fur: {
    airData: "Dâts Copernicus CAMS",
    airLastKnown: "Ultin dât CAMS",
    airTitle: "Cualitât de arie",
    airUnavailable: "Dâts de arie no disponibii",
    activeSpecies: "ativis",
    daylight: "Lus dal dì",
    pollenModel: "Prevision modelistiche CAMS",
    pollenNoDominant: "Nissun valôr parsore 0",
    pollenTitle: "Polins",
    particulateUnavailable: "PM2.5 e PM10 no disponibii",
    species: "speciis",
    uvLastKnown: "Ultin dât verificât",
    uvPeak: "Pic",
    uvTitle: "Indiç UV",
    uvUnavailable: "Prevision no disponibile",
  },
};

function finite(value) {
  return typeof value === "number" && Number.isFinite(value);
}

function formatNumber(value) {
  return finite(value)
    ? new Intl.NumberFormat("it-IT", { maximumFractionDigits: 1 }).format(value)
    : "—";
}

function formatHour(value) {
  const date = value ? new Date(value) : null;
  return date && Number.isFinite(date.getTime())
    ? new Intl.DateTimeFormat("it-IT", {
      timeZone: "Europe/Rome",
      hour: "2-digit",
      minute: "2-digit",
    }).format(date)
    : "";
}

function AirSummary({ copy, model }) {
  const values = model?.air?.values || {};
  const pm25 = values["particulate_matter_2.5um"];
  const pm10 = values["particulate_matter_10um"];
  const chosen = finite(pm25)
    ? AIR_FIELDS[0]
    : finite(pm10) ? AIR_FIELDS[1] : null;
  const hasAnyAirValue = AIR_FIELDS.some(([id]) => finite(values[id]));

  if (!hasAnyAirValue) return <p className="mf-weather-environment-empty">{copy.airUnavailable}</p>;

  return <>
    {chosen ? <span className="mf-weather-environment-metric">
      <b>{chosen[1]}</b>
      <strong>{formatNumber(values[chosen[0]])}<small>µg/m³</small></strong>
    </span> : <p className="mf-weather-environment-empty">{copy.particulateUnavailable}</p>}
    {chosen && chosen[0] !== AIR_FIELDS[1][0] && finite(pm10) ? (
      <span className="mf-weather-environment-secondary">PM10: <b>{formatNumber(pm10)} µg/m³</b></span>
    ) : null}
    <span className="mf-weather-environment-badge-row">
      <span className="mf-weather-environment-badge"><i aria-hidden="true" />{model.airSampleStatus === "last_known" ? copy.airLastKnown : copy.airData}</span>
    </span>
  </>;
}

function PollenSummary({ copy, model }) {
  const values = Array.isArray(model?.values) ? model.values.filter((entry) => finite(entry?.value)) : [];
  if (model?.status !== "available" || !values.length) {
    return <p className="mf-weather-environment-empty">{model?.note || copy.airUnavailable}</p>;
  }
  const positive = values.filter((entry) => entry.value > 0);
  const dominant = positive.reduce((highest, entry) => !highest || entry.value > highest.value ? entry : highest, null);
  const activeSpecies = values.filter((entry) => entry.value >= 0.01).length;

  return <>
    {dominant ? <span className="mf-weather-environment-metric mf-weather-environment-metric--pollen">
      <b>{dominant.label}</b>
      <strong>{dominant.displayValue}<small>{model.units}</small></strong>
    </span> : <p className="mf-weather-environment-empty">{model?.status === "available" ? copy.pollenNoDominant : model?.note || copy.airUnavailable}</p>}
    <span className="mf-weather-environment-secondary mf-weather-environment-secondary--pollen-count">
      <b>{values.length}</b> {copy.species} · <b>{activeSpecies}</b> {copy.activeSpecies}
    </span>
    <span className="mf-weather-environment-badge-row">
      <span className="mf-weather-environment-badge"><i aria-hidden="true" />{model?.pollenSampleStatus === "last_known" ? copy.airLastKnown : copy.pollenModel}</span>
    </span>
  </>;
}

function SkySummary({ copy, model }) {
  const cycle = model.sun.cycle;
  return <>
    <span className="mf-weather-environment-metric">
      <strong>{model.sun.daylight}</strong>
      <small>{copy.daylight}</small>
    </span>
    <span className="mf-weather-environment-sky-times">
      <small>{model.sun.sunriseLabel} {model.sun.sunrise}</small>
      <small>{model.sun.sunsetLabel} {model.sun.sunset}</small>
    </span>
    {cycle ? <span className="mf-weather-environment-cycle" aria-label={`${cycle.label}: ${cycle.progress}%`} role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={cycle.progress}>
      <i style={{ "--environment-cycle-progress": `${cycle.progress}%` }} />
    </span> : null}
    <span className="mf-weather-environment-secondary">{model.moon.phase}</span>
  </>;
}

function UvSummary({ copy, language, model, point }) {
  if (!model) return <p className="mf-weather-environment-empty">{copy.uvUnavailable}</p>;
  const level = uvLevel(model.current.value);
  const currentUsable = model.currentUsable !== false;

  return <>
    <span className="mf-weather-environment-metric">
      <strong className="mf-weather-environment-uv-value">{formatNumber(model.current.value)}</strong>
      <small>{currentUsable ? level?.[language === "fur" ? "fur" : "it"] : copy.uvLastKnown}</small>
    </span>
    {currentUsable && model.maximum !== null ? <span className="mf-weather-environment-secondary">
      {copy.uvPeak} <b>{formatNumber(model.maximum)}</b> · {formatHour(model.peakTime)}
    </span> : null}
    {currentUsable ? <UvCurve fur={language === "fur"} model={model} point={point} /> : null}
  </>;
}

export function WeatherEnvironmentOverview({ camsModel, language = "it", location, now, uvPoint }) {
  const languageKey = language === "fur" ? "fur" : "it";
  const copy = COPY[languageKey];
  const skyModel = buildAlmanacViewModel({ location, language: languageKey, date: now, now });
  const uvState = useWeatherUvCardState({ point: uvPoint });
  const place = location?.city || location?.municipality?.name || "";
  const items = [
    {
      id: "sky",
      title: languageKey === "fur" ? "Soreli e Lune" : "Sole e Luna",
      tone: "sky",
      icon: SunMoon,
      summary: <SkySummary copy={copy} model={skyModel} />,
      detail: <div className="mf-weather-environment-detail mf-weather-sky">
        <p className="mf-weather-environment-detail__context">{place} · {skyModel.dayLabel}</p>
        <SkyCard model={skyModel} />
      </div>,
    },
    {
      id: "uv",
      title: copy.uvTitle,
      tone: "uv",
      visualTone: getUvVisualTone(uvState.model),
      icon: Sun,
      summary: <UvSummary copy={copy} language={languageKey} model={uvState.model} point={uvPoint} />,
      detail: <div className="mf-weather-environment-detail mf-weather-environment-detail--uv">
        <WeatherUvContent {...uvState} compactDetail language={languageKey} point={uvPoint} />
      </div>,
    },
    {
      id: "air",
      title: copy.airTitle,
      tone: "air",
      icon: Wind,
      summary: <AirSummary copy={copy} model={camsModel} />,
      detail: camsModel
        ? <WeatherCamsCard detailMode language={languageKey} model={camsModel} section="air" />
        : <p>{copy.airUnavailable}</p>,
    },
    {
      id: "pollen",
      title: copy.pollenTitle,
      tone: "pollen",
      icon: Flower2,
      status: camsModel?.status,
      summary: <PollenSummary copy={copy} model={camsModel} />,
      detail: camsModel
        ? <WeatherCamsCard detailMode language={languageKey} model={camsModel} section="pollen" />
        : <p>{copy.airUnavailable}</p>,
    },
  ];

  return <WeatherEnvironmentGrid items={items} language={languageKey} />;
}
