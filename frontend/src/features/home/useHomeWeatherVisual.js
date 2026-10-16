import { useHomeSolarState } from "./homeDayPhase";

const HOME_DAY_PHASES = new Set(["night", "dawn", "morning", "midday", "afternoon", "sunset"]);
const DAY_ICON_BY_NIGHT_ICON = {
  ClearNight: "Sun",
  MostlyClearNight: "MostlySunny",
  OvercastNight: "Overcast",
  PartlyCloudyNight: "PartlyCloudy",
};
const NIGHT_ICON_BY_DAY_ICON = {
  MostlySunny: "MostlyClearNight",
  Overcast: "OvercastNight",
  PartlyCloudy: "PartlyCloudyNight",
  Sun: "ClearNight",
};

function getSolarAwareIcon(icon, isNight) {
  if (!icon) return icon;

  const type = isNight
    ? NIGHT_ICON_BY_DAY_ICON[icon.type] || icon.type
    : DAY_ICON_BY_NIGHT_ICON[icon.type] || icon.type;

  if (type === icon.type && Boolean(icon.night) === isNight) return icon;

  return { ...icon, night: isNight, type };
}

export function useHomeWeatherVisual(weather, { now } = {}) {
  const solarState = useHomeSolarState(weather.solarContext, {
    fallbackIsNight: Boolean(weather.icon?.night),
    now,
  });
  const hasScenePhaseOverride = HOME_DAY_PHASES.has(weather.scenePhaseOverride);
  const scenePhase = hasScenePhaseOverride ? weather.scenePhaseOverride : solarState.phase;
  const sceneIsNight = hasScenePhaseOverride ? scenePhase === "night" : solarState.isNight;

  return { scenePhase, sceneIcon: getSolarAwareIcon(weather.icon, sceneIsNight) };
}
