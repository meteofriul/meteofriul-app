import { HomeMeteoconIcon } from "./HomeMeteoconIcon";

const COASTAL_PLACES = new Set([
  "aquileia",
  "duino aurisina",
  "grado",
  "lignano sabbiadoro",
  "marano lagunare",
  "monfalcone",
  "muggia",
  "sistiana",
  "trieste",
]);

const HILL_PLACES = new Set([
  "cividale del friuli",
  "cormons",
  "gemona del friuli",
  "gorizia",
  "maniago",
  "san daniele del friuli",
  "spilimbergo",
  "venzone",
]);

const MOUNTAIN_PLACES = new Set([
  "barcis",
  "claut",
  "forni di sopra",
  "forni di sotto",
  "piancavallo",
  "sappada",
  "sauris",
  "tarvisio",
  "tolmezzo",
]);

const HOME_DAY_PHASES = new Set([
  "night",
  "dawn",
  "morning",
  "midday",
  "afternoon",
  "sunset",
]);

function normalizePlace(value) {
  return String(value || "")
    .trim()
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "");
}

function getHomeSceneEnvironment(locationTitle, sceneMode) {
  if (sceneMode === "neutral") return "neutral";

  const place = normalizePlace(locationTitle);

  if (COASTAL_PLACES.has(place)) return "coast";
  if (MOUNTAIN_PLACES.has(place)) return "mountain";
  if (HILL_PLACES.has(place)) return "hills";

  return "plain";
}

function getHomeSceneWeatherVariant(weatherVariant) {
  const normalized = String(weatherVariant || "cloud").replace(/-night$/, "");

  return normalized === "night" ? "clear" : normalized;
}

function LandscapeStrip({ layer }) {
  return (
    <span className="mf-home-flight-scene__strip">
      {layer === "far" ? <span className="mf-home-flight-scene__ridge mf-home-flight-scene__ridge--far" /> : null}
      {layer === "mid" ? (
        <>
          <span className="mf-home-flight-scene__ridge mf-home-flight-scene__ridge--near" />
          <span className="mf-home-flight-scene__hills" />
        </>
      ) : null}
      {layer === "near" ? (
        <>
          <span className="mf-home-flight-scene__fields" />
          <span className="mf-home-flight-scene__river" />
          <span className="mf-home-flight-scene__village" />
          <span className="mf-home-flight-scene__trees mf-home-flight-scene__trees--left" />
          <span className="mf-home-flight-scene__trees mf-home-flight-scene__trees--right" />
        </>
      ) : null}
    </span>
  );
}

function LandscapeLoop({ layer }) {
  return (
    <span className={`mf-home-flight-scene__loop mf-home-flight-scene__loop--${layer}`}>
      <LandscapeStrip layer={layer} />
      <LandscapeStrip layer={layer} />
    </span>
  );
}

export function HomeWeatherScene({
  dayPhase,
  icon,
  locationTitle,
  sceneMode = "regional",
  weatherVariant = "cloud",
}) {
  const environment = getHomeSceneEnvironment(locationTitle, sceneMode);
  const isNeutral = environment === "neutral";
  const phase = HOME_DAY_PHASES.has(dayPhase)
    ? dayPhase
    : icon?.night || weatherVariant.includes("night")
      ? "night"
      : "midday";
  const visualWeatherVariant = getHomeSceneWeatherVariant(weatherVariant);

  return (
    <div
      aria-hidden="true"
      className={`mf-home-flight-scene mf-home-flight-scene--${visualWeatherVariant} mf-home-flight-scene--phase-${phase} mf-home-flight-scene--env-${environment}`}
      data-day-phase={phase}
      data-scene-environment={environment}
    >
      <div className="mf-home-flight-scene__sky">
        {!isNeutral ? (
          <>
            <span className="mf-home-flight-scene__stars" />
            <span className="mf-home-flight-scene__cloud mf-home-flight-scene__cloud--one" />
            <span className="mf-home-flight-scene__cloud mf-home-flight-scene__cloud--two" />
          </>
        ) : null}
      </div>
      {!isNeutral ? (
        <div className="mf-home-flight-scene__landscape">
          <LandscapeLoop layer="far" />
          <LandscapeLoop layer="mid" />
          <LandscapeLoop layer="near" />
        </div>
      ) : null}
      <span className="mf-home-flight-scene__weather-icon">
        <HomeMeteoconIcon icon={icon} />
      </span>
      <span className="mf-home-flight-scene__wash" />
    </div>
  );
}
