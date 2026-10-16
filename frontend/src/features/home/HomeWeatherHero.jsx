import { Clock3, MapPin } from "lucide-react";

import { LocationChangeButton } from "../../ui/components/LocationChangeButton";

import { HomeWeatherScene } from "./HomeWeatherScene";
import { useHomeWeatherVisual } from "./useHomeWeatherVisual";

function getAtmosphereType(weatherVariant) {
  if (["rain", "rain-night", "storm", "storm-night"].includes(weatherVariant)) return "rain";
  if (["snow", "snow-night"].includes(weatherVariant)) return "snow";
  if (weatherVariant === "fog") return "fog";

  return null;
}

function WeatherAtmosphere({ enabled, type }) {
  if (!enabled || !type) return null;

  const particleCount = type === "rain" ? 14 : type === "snow" ? 12 : 3;

  return (
    <div className={`mf-home-atmosphere mf-home-atmosphere--${type}`} aria-hidden="true">
      {Array.from({ length: particleCount }, (_, index) => (
        <span key={`${type}-${index}`} />
      ))}
    </div>
  );
}

function HomeWeatherHeroWithSolarState(props) {
  const visualState = useHomeWeatherVisual(props.weather, { now: props.sceneNow });

  return <HomeWeatherHeroContent {...props} visualState={visualState} />;
}

export function HomeWeatherHero(props) {
  return props.visualState
    ? <HomeWeatherHeroContent {...props} />
    : <HomeWeatherHeroWithSolarState {...props} />;
}

function HomeWeatherHeroContent({
  changeLocationLabel = "Cambia",
  onChangeLocation,
  sceneMode = "regional",
  showUpdateStatus = true,
  visualState,
  weather,
  locationTitle,
}) {
  const showUpdatedNotice = Boolean(showUpdateStatus && weather.showStatus && weather.updatedLabel);
  const weatherVariant = weather.weatherVariant || "cloud";
  const { scenePhase, sceneIcon } = visualState;
  const atmosphereType = getAtmosphereType(weatherVariant);
  const atmosphereEnabled = Boolean(atmosphereType && !weather.isStale && !weather.error);

  return (
    <section
      className="mf-home-hero"
      aria-labelledby="home-weather-title"
      data-atmosphere-active={atmosphereEnabled ? "true" : "false"}
      data-day-phase={scenePhase}
      data-scene-mode={sceneMode}
      data-weather-variant={weatherVariant}
    >
      <HomeWeatherScene
        dayPhase={scenePhase}
        icon={sceneIcon}
        locationTitle={locationTitle}
        sceneMode={sceneMode}
        weatherVariant={weatherVariant}
      />
      <WeatherAtmosphere enabled={atmosphereEnabled} type={atmosphereType} />

      <div className="mf-home-hero__topline">
        <span className="mf-home-location">
          <MapPin aria-hidden="true" size={18} strokeWidth={2.25} />
          <span className="mf-home-location__name">{locationTitle}</span>
          {onChangeLocation ? (
            <LocationChangeButton
              className="mf-home-location__change"
              label={changeLocationLabel}
              onClick={onChangeLocation}
              tone="surface"
            />
          ) : null}
        </span>
      </div>

      <div className="mf-home-hero__main">
        <div className="mf-home-conditions">
          <h2 id="home-weather-title">{weather.conditionLabel}</h2>
          <div className="mf-home-temperature" data-severity={weather.temperature.severity}>
            <span>{weather.temperature.value || "--"}</span>
            <small>{weather.temperature.unit}</small>
          </div>
          {weather.feelsLike?.value ? (
            <p className="mf-home-feels-like">
              <span>{weather.feelsLike.label}</span>
              {" "}
              <strong>{weather.feelsLike.value}</strong>
            </p>
          ) : null}
        </div>

        {sceneMode === "regional" ? (
          <picture className="mf-home-eagle" aria-hidden="true">
            <source
              media="(prefers-reduced-motion: reduce)"
              srcSet="/brand/home-eagle-still.webp"
            />
            <img
              alt=""
              decoding="async"
              fetchPriority="high"
              loading="eager"
              src="/brand/home-eagle-kling-3.png"
            />
          </picture>
        ) : null}
        <span className="mf-home-weather-icon-reserve" aria-hidden="true" />
      </div>

      {showUpdatedNotice ? (
        <div className="mf-home-hero__insights">
          <span className="mf-home-updated-text">
            <Clock3 aria-hidden="true" size={14} strokeWidth={2.25} />
            {weather.updatedLabel}
          </span>
        </div>
      ) : null}
    </section>
  );
}
