import { Droplets, Flower2, Gauge, Umbrella, Wind } from "lucide-react";

const METRIC_ICONS = {
  wind: Wind,
  humidity: Droplets,
  pressure: Gauge,
  precipitation: Umbrella,
  pollen: Flower2,
};

export function HomeLocalMetrics({ model }) {
  const items = model?.items || [];
  if (!items.length) return null;
  const includesPollen = items.some((metric) => metric.id === "pollen");

  return (
    <dl
      aria-description={(
        includesPollen
          ? model.description
          : model.weatherDescription || model.description
      ) || undefined}
      aria-label={model.label}
      className="mf-home-local-metrics"
    >
      {items.map((metric) => {
        const Icon = METRIC_ICONS[metric.id];

        return (
          <div
            className={`mf-home-local-metric mf-home-local-metric--${metric.id}`}
            data-tone={metric.tone || undefined}
            key={metric.id}
          >
            <dt>
              <Icon aria-hidden="true" size={19} strokeWidth={2} />
              <span>{metric.label}</span>
            </dt>
            <dd aria-label={metric.ariaLabel}>
              <strong>{metric.value}</strong>
              {metric.unit ? <span className="mf-home-local-metric__unit">{metric.unit}</span> : null}
            </dd>
          </div>
        );
      })}
    </dl>
  );
}
