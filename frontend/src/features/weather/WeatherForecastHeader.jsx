import { Clock3, MapPin } from "lucide-react";

import { LocationChangeButton } from "../../ui/components/LocationChangeButton";

export function WeatherForecastHeader({
  changeLocationLabel,
  header,
  onChangeLocation,
  showLocation = true,
  showMetadata = true,
}) {
  if (!header || (!showLocation && !showMetadata)) return null;

  return (
    <header className="mf-weather-forecast-header">
      {showLocation ? (
        <div className="mf-weather-forecast-header__location">
          <span>
            <span className="mf-weather-forecast-header__pin"><MapPin aria-hidden="true" size={20} strokeWidth={2} /></span>
            <strong>{header.locationTitle}</strong>
          </span>
          {onChangeLocation ? (
            <LocationChangeButton
              className="mf-weather-forecast-header__change"
              label={changeLocationLabel}
              onClick={onChangeLocation}
            />
          ) : null}
        </div>
      ) : null}
      {showMetadata && header.dateLabel ? <div><time className="mf-weather-forecast-header__date" dateTime={header.dateKey}>{header.dateLabel}</time>{header.dateNote ? <small>{header.dateNote}</small> : null}</div> : null}
      {showMetadata ? (
        <div className="mf-weather-forecast-header__source">
          <span>
            <Clock3 aria-hidden="true" size={14} strokeWidth={2.2} />
            {header.sourceTimingLabel}
          </span>
        </div>
      ) : null}
    </header>
  );
}

export function WeatherForecastCardHeader({ header }) {
  if (!header) return null;
  const compactSource = header.compactSourceLabel || header.sourceTimingLabel;
  const compactRun = header.compactRunLabel;
  if (!header.dateLabel && !compactSource) return null;

  return (
    <header className="mf-weather-hourly-card__pilot-header">
      {header.dateLabel ? (
        <time dateTime={header.dateKey}>{header.dateLabel}</time>
      ) : <span />}
      {compactSource ? (
        <span
          aria-label={header.sourceTimingLabel || undefined}
          className="mf-weather-hourly-card__pilot-model"
          title={header.sourceTimingLabel || undefined}
        >
          {compactSource}
          {compactRun ? <> · <time dateTime={header.runAt || undefined}>{compactRun}</time></> : null}
        </span>
      ) : null}
    </header>
  );
}
