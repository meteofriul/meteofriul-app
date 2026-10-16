import {
  Cloud,
  Droplets,
  Flower2,
  Gauge,
  MapPin,
  Umbrella,
  Wind,
} from "lucide-react";

import { LocationChangeButton } from "../../ui/components/LocationChangeButton";
import { LocalWeatherPilotBanner } from "../../ui/components/LocalWeatherPilotBanner";

const METRIC_ICONS = {
  humidity: Droplets,
  precipitation: Umbrella,
  pressure: Gauge,
  wind: Wind,
};

export function BulletinLocalCard({ model, onChangeLocation }) {
  if (!model) return null;

  return (
    <section aria-labelledby="bulletin-local-title" className="mf-bulletin-local-card">
      <LocalWeatherPilotBanner metadata={model.localPilot} />
      <header className="mf-bulletin-local-card__header">
        <div className="mf-bulletin-local-card__heading">
          <div className="mf-bulletin-local-card__title-row">
            <div className="mf-bulletin-local-card__title-label">
              <MapPin aria-hidden="true" size={18} strokeWidth={2.25} />
              <h2 id="bulletin-local-title">{model.title}</h2>
            </div>
            {onChangeLocation ? (
              <LocationChangeButton
                label={model.changeLabel}
                onClick={onChangeLocation}
              />
            ) : null}
          </div>
          {model.observationLabel ? <p>{model.observationLabel}</p> : null}
        </div>
      </header>

      {model.metrics.length ? (
        <dl aria-label={model.currentDataLabel} className="mf-bulletin-local-metrics">
          {model.metrics.map((metric) => {
            const MetricIcon = METRIC_ICONS[metric.id] || Cloud;
            const toneClass = metric.tone
              ? ` mf-bulletin-local-metric--${metric.id}-${metric.tone}`
              : "";

            return (
              <div
                className={`mf-bulletin-local-metric mf-bulletin-local-metric--${metric.id}${toneClass}`}
                key={metric.id}
              >
                <dt>
                  <MetricIcon aria-hidden="true" size={17} strokeWidth={2.15} />
                  <span>{metric.label}</span>
                </dt>
                <dd>
                  <strong>{metric.value}</strong>
                  {metric.detail ? <span>{metric.detail}</span> : null}
                </dd>
              </div>
            );
          })}
        </dl>
      ) : null}

      {model.pollen ? (
        <div className={`mf-bulletin-local-pollen mf-bulletin-local-pollen--${model.pollen.tone || "available"}`}>
          <span className="mf-bulletin-local-pollen__icon">
            <Flower2 aria-hidden="true" size={20} strokeWidth={2.05} />
          </span>
          <div>
            <span className="mf-bulletin-local-pollen__label">{model.pollen.label}</span>
            <strong>{model.pollen.level}</strong>
            {model.pollen.values?.length ? (
              <dl aria-label={`Concentrazioni polliniche CAMS (${model.pollen.units})`}>
                {model.pollen.values.map((entry) => (
                  <div key={entry.id}>
                    <dt>{entry.label}</dt>
                    <dd title={entry.value === null ? "Dato non disponibile" : String(entry.value)}>
                      {entry.displayValue}{entry.value === null ? "" : ` ${model.pollen.units}`}
                    </dd>
                  </div>
                ))}
              </dl>
            ) : null}
            {model.pollen.detail ? (
              <small>{model.pollen.strongestLabel}: {model.pollen.detail}</small>
            ) : null}
          </div>
        </div>
      ) : null}

      {model.detailsSourceLabel ? <p className="mf-bulletin-local-card__source">{model.detailsSourceLabel}</p> : null}
    </section>
  );
}
