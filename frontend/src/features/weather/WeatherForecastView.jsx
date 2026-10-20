import { OfficialAlertCompactLink } from "../../ui/components/OfficialAlertCompactLink";
import { WeatherCamsCard } from "./WeatherCamsCard";
import { isDefinitiveAppExperience } from "../../services/localWeatherPilot";
import { WeatherForecastHeader } from "./WeatherForecastHeader";
import { WeatherEnvironmentOverview } from "./WeatherEnvironmentOverview";
import { WeatherHourlyForecast } from "./WeatherHourlyForecast";

const COPY = {
  it: {
    loadingBody: "Le previsioni saranno mostrate appena i dati saranno disponibili.",
    loadingTitle: "Dati meteo in arrivo",
    unavailableBody: "Al momento non sono disponibili previsioni per le prossime ore.",
    unavailableTitle: "Previsioni non disponibili",
  },
  fur: {
    loadingBody: "O mostrarìn lis previsions a pene che il dât verificât al sarà disponibil.",
    loadingTitle: "Dâts meteo in rivade",
    unavailableBody: "No son oris futuris verificadis di mostrâ in chest moment.",
    unavailableTitle: "Previsions no disponibii",
  },
};

function ForecastMessage({ body, title }) {
  return (
    <section aria-live="polite" className="mf-weather-forecast-section mf-weather-forecast-section--loading">
      <h2>{title}</h2>
      <p>{body}</p>
    </section>
  );
}

export function WeatherForecastView({
  location,
  weatherNow,
  officialAlert,
  language = "it",
  model,
  onChangeLocation,
  onOfficialAlertOpen,
  showLocationHeader = true,
}) {
  const copy = COPY[language === "fur" ? "fur" : "it"];

  if (!model) {
    return (
      <div className="mf-weather-forecast-view">
        <OfficialAlertCompactLink
          alert={officialAlert}
          language={language}
          onOpen={onOfficialAlertOpen}
        />
        <ForecastMessage body={copy.loadingBody} title={copy.loadingTitle} />
      </div>
    );
  }

  const localPilot = isDefinitiveAppExperience();
  const hasRenderableHourlyGroup = model.hourly?.groups?.some((group) => (
    model.hourly.items?.some((item) => item.dateKey === group.dateKey)
  ));
  const embedForecastHeader = localPilot && Boolean(hasRenderableHourlyGroup);

  return (
    <div className="mf-weather-forecast-view">
      <WeatherForecastHeader
        changeLocationLabel={model.changeLocationLabel}
        header={model.header}
        onChangeLocation={onChangeLocation}
        showLocation={showLocationHeader}
        showMetadata={!embedForecastHeader}
      />
      <OfficialAlertCompactLink
        alert={officialAlert}
        language={language}
        onOpen={onOfficialAlertOpen}
      />
      {model.hourly?.items?.length ? (
        <WeatherHourlyForecast
          cardHeader={embedForecastHeader ? model.header : null}
          key={model.hourly.items[0]?.timestamp}
          language={language}
          model={model.hourly}
        />
      ) : (
        <ForecastMessage body={copy.unavailableBody} title={copy.unavailableTitle} />
      )}
      {localPilot ? <WeatherEnvironmentOverview
        camsModel={model.cams}
        language={language}
        location={location}
        now={weatherNow}
        uvPoint={model.uvPoint}
      /> : <WeatherCamsCard language={language} model={model.cams} />}
    </div>
  );
}
