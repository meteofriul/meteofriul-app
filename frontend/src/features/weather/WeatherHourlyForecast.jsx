import {
  ArrowUp,
  ChevronDown,
  Cloud,
  Droplets,
  Gauge,
  Moon,
  Umbrella,
  Wind,
  X,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { isDefinitiveAppExperience } from "../../services/localWeatherPilot";
import { registerPilotBackHandler } from "../../services/pilotBackNavigation";

import { HomeMeteoconIcon } from "../home/HomeMeteoconIcon";
import { ForecastMeteoconIcon } from "./ForecastMeteoconIcon";
import { WeatherForecastCardHeader } from "./WeatherForecastHeader";
import { WeatherForecastCharts } from "./WeatherForecastCharts";
import { buildThreeHourForecast } from "./threeHourForecast";

const COPY = {
  it: {
    cloudCover: "Nuvolosità",
    details: "Dettaglio dell'ora",
    openDetails: "Dettaglio e grafici",
    feelsLike: "Percepita",
    gusts: "Raffiche",
    humidity: "Umidità",
    interval: "Intervallo",
    listEyebrow: "Evoluzione oraria",
    precipitation: "Precipitazioni",
    pressure: "Pressione",
    retained: "Ultimo dato valido",
    more: "Mostra le successive",
    less: "Mostra solo le prime 12 ore",
    unavailable: "Dato non disponibile",
    wind: "Vento",
  },
  fur: {
    cloudCover: "Cuviert",
    details: "Detai de ore",
    openDetails: "Detai e grafics",
    feelsLike: "Percepide",
    gusts: "Rafichis",
    humidity: "Umiditât",
    interval: "Interval",
    listEyebrow: "Evoluzion par ore",
    precipitation: "Precipitazions",
    pressure: "Pression",
    retained: "Ultin dât valit",
    more: "Mostre lis successivis",
    less: "Mostre dome lis primis 12 oris",
    unavailable: "Dât no disponibil",
    wind: "Vint",
  },
};
const EMPTY_ITEMS = Object.freeze([]);

function getSlotKey(slot, index) {
  return slot?.timestamp || `${slot?.dateKey || ""}-${slot?.time || index}`;
}

function getDisclosureId(slot, index) {
  return `weather-hour-${getSlotKey(slot, index).replace(/[^a-zA-Z0-9_-]/g, "-")}`;
}

function ForecastMetric({ icon: Icon, label, meta, retained = false, retainedLabel, unavailable, value }) {
  const displayValue = value === null || value === undefined || value === "" ? unavailable : value;
  return (
    <div className="mf-weather-hourly-detail__metric" data-retained={retained ? "true" : undefined}>
      <dt>
        <Icon aria-hidden="true" size={18} strokeWidth={2} />
        <span>{label}</span>
      </dt>
      <dd>
        <strong>{displayValue}</strong>
        {meta ? <span>{meta}</span> : null}
        {retained ? <small>{retainedLabel}</small> : null}
      </dd>
    </div>
  );
}

function DailySummaries({ model }) {
  if (!model?.summaries?.length) return null;
  return (
    <div aria-label={model.title} className="mf-weather-day-summaries">
      {model.summaries.map((summary) => {
        return (
          <div
            className="mf-weather-day-summary"
            key={summary.id}
          >
            <span className="mf-weather-day-summary__heading">
              <span>
                <strong>{summary.label}</strong>
                <small>{summary.coverageLabel}</small>
              </span>
              {summary.icon ? <HomeMeteoconIcon className="mf-weather-day-summary__icon" icon={summary.icon} size={48} /> : null}
            </span>
            {summary.conditionLabel ? (
              <span className="mf-weather-day-summary__condition">{summary.conditionLabel}</span>
            ) : null}
            {summary.minTemperature && summary.maxTemperature ? (
              <span className="mf-weather-day-summary__range">
                <b>{summary.minTemperature}</b>
                <span>/</span>
                <b>{summary.maxTemperature}</b>
              </span>
            ) : null}
            <span className="mf-weather-day-summary__metrics">
              {summary.precipitationLabel ? (
                <span>{summary.precipitationTitle} <b>{summary.precipitationLabel}</b></span>
              ) : null}
            </span>
          </div>
        );
      })}
    </div>
  );
}

function SelectedHourDetails({ allItems, copy, language, selected, selectedIndex, compact = false }) {
  const details = selected.details || {};
  const retainedFields = new Set(selected.retainedFields || []);
  const selectedWhen = [selected.groupLabel || selected.dayLabel, selected.time]
    .filter(Boolean)
    .join(" · ");
  const regionId = getDisclosureId(selected, selectedIndex);

  return (
    <div
      aria-label={`${copy.details}: ${selectedWhen}`}
      className="mf-weather-hourly-selection"
      id={regionId}
      role="region"
    >
      {compact ? <header className="mf-weather-hourly-compact-heading">
        <strong><time dateTime={selected.timestamp}>{selectedWhen}</time> — {selected.conditionLabel || copy.unavailable}</strong>
        <p>{selected.temperature || copy.unavailable} · {copy.feelsLike} <b>{details.apparentTemperature || copy.unavailable}</b>
          {retainedFields.has("apparentTemperature") ? <small> · {copy.retained}</small> : null}
        </p>
      </header> : <div className="mf-weather-hourly-feature">
        <div className="mf-weather-hourly-feature__copy">
          <time dateTime={selected.timestamp}>{selectedWhen}</time>
          <strong>{selected.conditionLabel || copy.unavailable}</strong>
          <p>{selected.temperature || copy.unavailable}</p>
          <span>
            {copy.feelsLike}{" "}
            <b>{details.apparentTemperature || copy.unavailable}</b>
            {retainedFields.has("apparentTemperature") ? <small>{copy.retained}</small> : null}
          </span>
        </div>
        <HomeMeteoconIcon
          className="mf-weather-hourly-feature__icon"
          icon={selected.icon}
          size={82}
        />
      </div>}

      <dl className="mf-weather-hourly-detail">
        <ForecastMetric
          icon={Umbrella}
          label={copy.precipitation}
          meta={details.intervalLabel ? `${copy.interval} ${details.intervalLabel}` : ""}
          retained={retainedFields.has("precipitation")}
          retainedLabel={copy.retained}
          unavailable={copy.unavailable}
          value={details.precipitation}
        />
        <ForecastMetric
          icon={Wind}
          label={copy.wind}
          meta={details.windDirection || ""}
          retained={retainedFields.has("windSpeed") || retainedFields.has("windDirection")}
          retainedLabel={copy.retained}
          unavailable={copy.unavailable}
          value={details.windSpeed}
        />
        <ForecastMetric
          icon={Wind}
          label={copy.gusts}
          meta={details.intervalLabel ? `${copy.interval} ${details.intervalLabel}` : ""}
          retained={retainedFields.has("windGusts")}
          retainedLabel={copy.retained}
          unavailable={copy.unavailable}
          value={details.windGusts}
        />
        <ForecastMetric
          icon={Droplets}
          label={copy.humidity}
          retained={retainedFields.has("humidity")}
          retainedLabel={copy.retained}
          unavailable={copy.unavailable}
          value={details.humidity}
        />
        <ForecastMetric
          icon={Gauge}
          label={copy.pressure}
          retained={retainedFields.has("pressure")}
          retainedLabel={copy.retained}
          unavailable={copy.unavailable}
          value={details.pressure}
        />
        <ForecastMetric
          icon={Cloud}
          label={copy.cloudCover}
          retained={retainedFields.has("cloudCover")}
          retainedLabel={copy.retained}
          unavailable={copy.unavailable}
          value={details.cloudCover}
        />
      </dl>

      <WeatherForecastCharts
        items={allItems}
        language={language}
        selectedKey={selected.timestamp}
      />
    </div>
  );
}

export function PilotHourlyForecast({ cardHeader = null, model, language = "it" }) {
  const copy = COPY[language === "fur" ? "fur" : "it"];
  const [day, setDay] = useState(null);
  const [selectedKey, setSelectedKey] = useState(null);
  const [highlightedKey, setHighlightedKey] = useState(null);
  const dialog = useRef(null);
  const opener = useRef(null);
  const ribbon = useRef(null);
  const items = model.items || [];
  const groups = (model.groups || []).filter(group => items.some(item => item.dateKey === group.dateKey));
  const active = groups.find(group => group.dateKey === day) || groups[0];
  const selected = items.find(item => item.timestamp === selectedKey);
  const detailOpen = Boolean(selected);
  useEffect(() => {
    if (!detailOpen) return undefined;
    dialog.current?.showModal();
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const unregisterBack = registerPilotBackHandler(() => setSelectedKey(null), {
      isActive: () => dialog.current?.open === true,
    });
    return () => {
      unregisterBack();
      document.body.style.overflow = previous;
      opener.current?.focus();
    };
  }, [detailOpen]);
  if (!active) return null;
  return <section className="mf-weather-hourly-card mf-weather-hourly-card--ribbon" aria-label={model.title}>
    <WeatherForecastCardHeader header={cardHeader} />
    <div className="mf-weather-day-picker" aria-label={language === "fur" ? "Zornade" : "Giorno"}>
      {groups.map(group => {
        const summary = model.summaries?.find(item => item.dateKey === group.dateKey);
        const minimum = summary?.fullDayMinTemperature || summary?.minTemperature || "—";
        const maximum = summary?.fullDayMaxTemperature || summary?.maxTemperature || "—";
        const dayLabel = group.shortLabel || group.label;
        const dateLabel = group.dateLabel || group.label;
        const accessibleLabel = dateLabel.startsWith(dayLabel) ? dateLabel : `${dayLabel}, ${dateLabel}`;
        return <button key={group.dateKey} type="button" aria-label={`${accessibleLabel} ${minimum} / ${maximum}`} aria-pressed={active.dateKey === group.dateKey} onClick={() => {
          setDay(group.dateKey);
          const first = Array.from(ribbon.current?.children || []).find(node => node.dataset.day === group.dateKey);
          if (first) ribbon.current.scrollTo({ left: ribbon.current.scrollLeft + first.getBoundingClientRect().left - ribbon.current.getBoundingClientRect().left, behavior: "smooth" });
        }}>
          <strong title={dateLabel}>{dayLabel}</strong>
          {summary?.icon ? <ForecastMeteoconIcon icon={summary.icon} size={30} /> : null}
          <span>{minimum} / {maximum}</span>
        </button>;
      })}
    </div>
    {model.retainedValuesLabel ? <p role="status">{model.retainedValuesLabel}</p> : null}
    <div className="mf-weather-hour-ribbon" data-has-selection={highlightedKey ? "true" : "false"} ref={ribbon} aria-label={model.title} onScroll={event => {
      const container = event.currentTarget;
      const left = container.getBoundingClientRect().left;
      const firstVisible = Array.from(container.children).find(node => node.getBoundingClientRect().right > left + 40);
      if (firstVisible?.dataset.day) setDay(firstVisible.dataset.day);
    }}>
      {items.map(slot => {
        const isNight = Boolean(slot.icon?.night);
        const isClearNight = isNight && slot.icon?.type === "ClearNight";
        const isCurrent = slot.timestamp === items[0]?.timestamp;
        const precipitation = slot.details?.precipitation;
        const hasPrecipitation = Number.isFinite(slot.values?.precipitation) && slot.values.precipitation > 0;

        return <button type="button" data-day={slot.dateKey} key={slot.timestamp} aria-current={isCurrent ? "time" : undefined} aria-pressed={highlightedKey === slot.timestamp} aria-haspopup="dialog" aria-label={`${groups.find(group => group.dateKey === slot.dateKey)?.label || slot.dateKey} · ${slot.time} · ${slot.conditionLabel} · ${slot.temperature}`} onClick={event => { opener.current = event.currentTarget; setHighlightedKey(slot.timestamp); setSelectedKey(slot.timestamp); }}>
          <time dateTime={slot.timestamp}>{slot.time}</time>
          <span
            aria-hidden="true"
            className="mf-weather-hour-ribbon__icon-frame"
            data-phase={isNight ? "night" : "day"}
          >
            {isNight && !isClearNight ? (
              <Moon
                className="mf-weather-hour-ribbon__night-crescent"
                fill="currentColor"
                size={15}
              />
            ) : null}
            {isClearNight ? (
              <Moon
                className="mf-weather-hour-ribbon__moon"
                fill="currentColor"
                size={28}
              />
            ) : <ForecastMeteoconIcon icon={slot.icon} size={42} />}
          </span>
          <strong>{slot.temperature}</strong>
          <small
            aria-hidden={precipitation ? undefined : "true"}
            data-wet={hasPrecipitation ? "true" : undefined}
            className={precipitation ? undefined : "mf-weather-hour-ribbon__precipitation--empty"}
          >{precipitation || "\u00a0"}</small>
        </button>;
      })}
    </div>
    {selected ? <dialog ref={dialog} className="mf-weather-hour-sheet" aria-label={copy.details} onCancel={() => setSelectedKey(null)} onClose={() => setSelectedKey(null)} onClick={event => { if (event.target === event.currentTarget) setSelectedKey(null); }}>
      <button className="mf-weather-hour-sheet__close" aria-label={language === "fur" ? "Siere" : "Chiudi"} type="button" autoFocus onClick={() => setSelectedKey(null)}><X size={19} aria-hidden="true" /></button>
      <SelectedHourDetails compact allItems={items} copy={copy} language={language} selected={selected} selectedIndex={items.indexOf(selected)} />
    </dialog> : null}
  </section>;
}

export function WeatherHourlyForecast(props) {
  return isDefinitiveAppExperience() ? <PilotHourlyForecast {...props} /> : <LegacyHourlyForecast {...props} />;
}

function LegacyHourlyForecast({
  language = "it",
  model,
}) {
  const items = model?.items || EMPTY_ITEMS;
  const copy = COPY[language === "fur" ? "fur" : "it"];
  const [expanded, setExpanded] = useState(false);

  if (!items.length) return null;

  const periods = buildThreeHourForecast(items);
  const groups = model.groups.map((group) => ({
    ...group, items: periods.filter((item) => item.dateKey === group.dateKey),
  })).filter((group) => group.items.length);

  return (
    <section aria-labelledby="weather-forecast-hourly-title" className="mf-weather-hourly-card">
      <DailySummaries model={model} />

      <div className="mf-weather-hourly-card__heading">
        <div>
          <span>{copy.listEyebrow}</span>
          <h2 id="weather-forecast-hourly-title">{model.title}</h2>
        </div>
      </div>
      {model.retainedValuesLabel ? (
        <p className="mf-weather-hourly-card__retained" role="status">{model.retainedValuesLabel}</p>
      ) : null}

      <div aria-label={model.scrollLabel || model.title} className="mf-weather-hourly-list">
        {groups.map((group) => (
          <section aria-labelledby={`weather-day-${group.dateKey}`} key={group.dateKey}>
            <h3 id={`weather-day-${group.dateKey}`}>{group.label}</h3>
            <ol>
              {group.items.map((slot) => {
                const index = items.findIndex((item) => item.timestamp === slot.timestamp);
                const key = getSlotKey(slot, index);
                const canExpand = index === 0;
                const isSelected = canExpand && expanded;
                const Row = canExpand ? "button" : "div";
                const regionId = getDisclosureId(slot, index);
                const direction = slot.values?.windDirection;
                const hasDirection = typeof direction === "number" && Number.isFinite(direction);
                const windDescription = `${copy.wind}${slot.details?.windDirection ? ` ${language === "fur" ? "di" : "da"} ${slot.details.windDirection}` : ""}`;

                return (
                  <li data-selected={isSelected ? "true" : undefined} key={key}>
                    <Row
                      aria-controls={isSelected ? regionId : undefined}
                      aria-expanded={canExpand ? expanded : undefined}
                      className="mf-weather-hourly-row"
                      onClick={canExpand ? () => setExpanded((current) => !current) : undefined}
                      type={canExpand ? "button" : undefined}
                    >
                      <span className="mf-weather-hourly-row__when">
                        <time dateTime={slot.timestamp}>{slot.time}</time>
                        <HomeMeteoconIcon icon={slot.icon} size={44} />
                      </span>
                      <span className="mf-weather-hourly-row__copy">
                        <strong>{slot.conditionLabel || copy.unavailable}</strong>
                        {slot.details?.windSpeed ? (
                          <small className="mf-weather-hourly-row__wind">
                            <span aria-label={windDescription} title={windDescription}>
                              {hasDirection ? <ArrowUp aria-hidden="true" size={14} style={{ transform: `rotate(${(direction + 180) % 360}deg)` }} /> : null}
                              <span className="mf-weather-wind-label">{windDescription}</span>
                            </span>
                            {slot.details.windSpeed}
                            {slot.periodGust ? ` · ${copy.gusts} ${slot.periodGust}` : ""}
                          </small>
                        ) : null}
                        {slot.rainTotalValue === null || slot.rainTotalValue > 0 ? (
                          <small className="mf-weather-hourly-row__rain">
                            <Droplets aria-hidden="true" size={12} /> {slot.rainTotal || `${copy.precipitation}: ${copy.unavailable}`}
                          </small>
                        ) : null}
                        {canExpand ? <span className="mf-weather-hourly-row__action">{copy.openDetails}</span> : null}
                      </span>
                      <span className="mf-weather-hourly-row__temperature">
                        {slot.temperature || copy.unavailable}
                        {slot.details?.apparentTemperature ? (
                          <small>{copy.feelsLike} {slot.details.apparentTemperature}</small>
                        ) : null}
                      </span>
                      {canExpand ? <ChevronDown aria-hidden="true" className="mf-weather-hourly-row__chevron" size={18} /> : <span />}
                    </Row>
                    {isSelected ? (
                      <SelectedHourDetails
                        allItems={items}
                        copy={copy}
                        language={language}
                        selected={slot}
                        selectedIndex={0}
                      />
                    ) : null}
                  </li>
                );
              })}
            </ol>
          </section>
        ))}
      </div>
    </section>
  );
}
