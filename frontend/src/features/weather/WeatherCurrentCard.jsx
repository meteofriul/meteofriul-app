import { Clock3, MapPin } from "lucide-react";

import { HomeMeteoconIcon } from "../home/HomeMeteoconIcon";
import { LocationChangeButton } from "../../ui/components/LocationChangeButton";

export function WeatherCurrentCard({
  changeLocationLabel,
  icon,
  locationTitle,
  onChangeLocation,
  weather,
}) {
  const conditionLabel = String(weather?.conditionLabel || "").trim();
  const rawTemperatureValue = weather?.temperature?.value;
  const hasTemperatureValue = rawTemperatureValue !== null
    && rawTemperatureValue !== undefined
    && String(rawTemperatureValue).trim() !== "";
  const temperatureLabel = String(weather?.temperature?.label || "").trim();
  const temperatureValue = hasTemperatureValue
    ? rawTemperatureValue
    : temperatureLabel;
  const temperatureUnit = hasTemperatureValue ? weather?.temperature?.unit || "" : "";
  const updatedLabel = weather?.updatedLabel || weather?.statusLabel || "";
  const weatherIcon = icon || weather?.icon || null;

  return (
    <section
      aria-describedby={updatedLabel ? "weather-current-updated" : undefined}
      aria-labelledby="weather-current-condition"
      className="mf-weather-current-card"
      data-status={weather?.statusTone || weather?.status || "unknown"}
    >
      <div className="mf-weather-current-card__location">
        <span>
          <MapPin aria-hidden="true" size={19} strokeWidth={2.25} />
          <strong>{locationTitle}</strong>
        </span>
        {onChangeLocation ? (
          <LocationChangeButton
            className="mf-weather-current-card__change"
            label={changeLocationLabel}
            onClick={onChangeLocation}
          />
        ) : null}
      </div>

      <div className="mf-weather-current-card__main">
        <div className="mf-weather-current-card__data">
          <h2 id="weather-current-condition">{conditionLabel}</h2>
          <p aria-label={temperatureLabel || undefined} className="mf-weather-current-card__temperature">
            <strong>{temperatureValue}</strong>
            {temperatureUnit ? <span>{temperatureUnit}</span> : null}
          </p>
          {weather?.feelsLike?.value ? (
            <p className="mf-weather-current-card__feels-like">
              <span>{weather.feelsLike.label}</span>
              {" "}
              <strong>{weather.feelsLike.value}</strong>
            </p>
          ) : null}
        </div>
        {weatherIcon ? (
          <HomeMeteoconIcon
            className="mf-weather-current-card__icon"
            icon={weatherIcon}
            size={88}
          />
        ) : null}
      </div>

      {updatedLabel ? (
        <p className="mf-weather-current-card__updated" id="weather-current-updated" role="status">
          <Clock3 aria-hidden="true" size={15} strokeWidth={2.25} />
          <span>{updatedLabel}</span>
        </p>
      ) : null}
    </section>
  );
}
