import { normalizeWeatherData, readWeatherNumber } from "./normalizedWeather";

const SUN_TYPES = ["Sun", "MostlySunny", "ClearNight", "MostlyClearNight"];
const CLOUD_TYPES = [
  "PartlyCloudy",
  "PartlyCloudyNight",
  "Overcast",
  "OvercastDay",
  "OvercastNight",
  "Cloud",
];
const RAIN_TYPES = ["LightRain", "Rain", "HeavyRain", "ExtremeRain", "Showers", "Sleet"];
const STORM_TYPES = ["Storm", "StrongStorm", "StormHail", "Hail"];
const FOG_TYPES = ["Fog", "Mist", "Haze", "LowCloudFog"];

export function readNumber(value, fallback = 0) {
  return readWeatherNumber(value, fallback);
}

export function getWeatherGroup(type) {
  if (SUN_TYPES.includes(type)) return "sun";
  if (CLOUD_TYPES.includes(type)) return "cloud";
  if (RAIN_TYPES.includes(type)) return "rain";
  if (STORM_TYPES.includes(type)) return "storm";
  if (type === "Snow") return "snow";
  if (FOG_TYPES.includes(type)) return "fog";
  if (type === "Wind") return "wind";

  return "cloud";
}

export function getTemperatureBand(value) {
  const temperature = Number(value);

  if (!Number.isFinite(temperature)) return "unknown";
  if (temperature < 12) return "cold";
  if (temperature < 22) return "mild";
  if (temperature < 28) return "warm";

  return "hot";
}

export function getPrecipitationAmount(data) {
  return normalizeWeatherData(data).precipitationAmount;
}

export function getPopValue(data) {
  return normalizeWeatherData(data).popPercent ?? 0;
}

export function getConditionContext(data, baseWeatherGroup, placeType) {
  const normalized = normalizeWeatherData(data);
  const temperature = normalized.temperature;
  const feelsLike = normalized.feelsLike;
  const humidity = normalized.humidity ?? 0;
  const wind = normalized.windSpeed ?? 0;
  const gusts = normalized.windGusts ?? 0;
  const visibilityKm = normalized.visibilityKm;
  const precipitation = normalized.precipitationAmount;
  const pop = normalized.popPercent ?? 0;
  const hourly = normalized.hourlyNext12h;
  const rainHours = hourly.filter((slot) => {
    const code = Number(slot?.code ?? slot?.weathercode ?? 3);
    const amount = Math.max(slot?.precipitation ?? 0, slot?.rain ?? 0, slot?.showers ?? 0);

    return (
      amount > 0.2 ||
      [51, 53, 55, 61, 63, 65, 80, 81, 82, 95, 96, 99].includes(code)
    );
  }).length;
  const exposed = ["sea", "mountain", "hills", "river"].includes(placeType);

  const context = {
    baseWeatherGroup,
    temperature,
    feelsLike,
    humidity,
    wind,
    gusts,
    visibilityKm,
    precipitation,
    pop,
    rainHours,
    isBora: normalized.isBora,
    temperatureBand: getTemperatureBand(feelsLike ?? temperature),
    highHumidity: humidity >= 75,
    lowVisibility: visibilityKm !== null && visibilityKm < 5,
    strongWind:
      normalized.isBora ||
      wind >= (exposed ? 28 : 32) ||
      gusts >= (exposed ? 38 : 45),
    relevantRain: precipitation >= 0.2 || pop >= 60 || rainHours >= 2,
  };

  if (precipitation >= 0.2 || baseWeatherGroup === "rain" || baseWeatherGroup === "storm") {
    context.umbrellaLevel = "needed";
  } else if (pop >= 60 || rainHours >= 2) {
    context.umbrellaLevel = "recommended";
  } else if (pop >= 35 || rainHours === 1) {
    context.umbrellaLevel = "foldable";
  } else if (pop >= 20) {
    context.umbrellaLevel = "watch";
  } else {
    context.umbrellaLevel = "none";
  }

  if (baseWeatherGroup === "storm") context.adviceGroup = "storm";
  else if (baseWeatherGroup === "snow") context.adviceGroup = "snow";
  else if (context.relevantRain || baseWeatherGroup === "rain") context.adviceGroup = "rain";
  else if (context.lowVisibility || baseWeatherGroup === "fog") context.adviceGroup = "fog";
  else if (context.strongWind || baseWeatherGroup === "wind") context.adviceGroup = "wind";
  else context.adviceGroup = baseWeatherGroup;

  context.heatCaution =
    (feelsLike !== null && feelsLike >= 28) ||
    (temperature !== null && temperature >= 28) ||
    ((feelsLike !== null ? feelsLike : temperature) >= 25 && context.highHumidity);
  context.coldRisk =
    (feelsLike !== null && feelsLike <= 5) ||
    (temperature !== null && temperature <= 5);

  return context;
}
