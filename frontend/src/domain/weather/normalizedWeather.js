import { getWeatherType } from "./weatherClassification";
import {
  classifyCurrentWeather,
  getWeatherPresentation,
  getWeatherSemanticByKey,
  WEATHER_SEMANTICS,
} from "./weatherSemantics";

const RAIN_ICON_TYPES = new Set(["LightRain", "Rain", "HeavyRain", "ExtremeRain", "Showers", "Sleet"]);
const STORM_ICON_TYPES = new Set(["Storm", "StrongStorm", "StormHail", "Hail"]);
const SNOW_ICON_TYPES = new Set(["Snow"]);
const FOG_ICON_TYPES = new Set(["Fog", "Mist", "Haze", "LowCloudFog"]);
const CLEAR_ICON_TYPES = new Set(["Sun", "MostlySunny", "ClearNight", "MostlyClearNight"]);
const PARTLY_ICON_TYPES = new Set(["PartlyCloudy", "PartlyCloudyNight"]);
const CLOUD_ICON_TYPES = new Set(["Overcast", "OvercastDay", "OvercastNight", "Cloud"]);

export function isIconLocalPilotWeather(data) {
  return (data?.primary_source ?? data?.primarySource ?? data?.raw?.primary_source) === "icon2i_local_pilot";
}

export function readWeatherNumber(value, fallback = null) {
  if (value === undefined || value === null || value === "") return fallback;

  const number = Number(value);
  return Number.isFinite(number) ? number : fallback;
}

export function readWeatherCode(data) {
  // ICON WW is not the Open-Meteo code table (notably code 96).
  if (isIconLocalPilotWeather(data)) return null;
  return readWeatherNumber(
    data?.weathercode ??
      data?.weather_code ??
      data?.current_weather?.weathercode ??
      data?.current?.weather_code,
  );
}

function getPrimaryTypeFromCode(code, night = false) {
  if (code === null || code === undefined || code === "") return null;

  const numericCode = Number(code);

  if (!Number.isFinite(numericCode)) return null;

  if ([95, 96, 99].includes(numericCode)) return "Storm";
  if ([71, 73, 75, 77, 85, 86].includes(numericCode)) return "Snow";
  if ([80, 81, 82].includes(numericCode)) return "Showers";
  if ([61, 63, 65].includes(numericCode)) return "Rain";
  if ([51, 53, 55].includes(numericCode)) return "LightRain";
  if ([45, 48].includes(numericCode)) return "Fog";
  if (numericCode === 0) return night ? "ClearNight" : "Sun";
  if (numericCode === 1) return night ? "MostlyClearNight" : "MostlySunny";
  if (numericCode === 2) return night ? "PartlyCloudyNight" : "PartlyCloudy";
  if (numericCode === 3) return night ? "OvercastNight" : "Overcast";

  return null;
}

function getPrimaryTypeFromCondition(condition = "", night = false) {
  const text = String(condition || "").toLowerCase();

  if (text.includes("grandine") || text.includes("grandinat")) {
    return text.includes("tempor") ? "StormHail" : "Hail";
  }
  if (text.includes("nevischio") || text.includes("mista neve") || text.includes("misto neve") || text.includes("gelicidio") || text.includes("pioggia congel")) return "Sleet";
  if (text.includes("tempor")) return "Storm";
  if (text.includes("neve") || text.includes("nÃªf") || text.includes("snow")) return "Snow";
  if (text.includes("rovesc") || text.includes("showers")) return "Showers";
  if (text.includes("pioggia molto intensa") || text.includes("piogge molto intense") || text.includes("precipitazioni molto intense")) return "ExtremeRain";
  if (text.includes("pioggia intensa") || text.includes("piogge intense") || text.includes("precipitazioni intense")) return "ExtremeRain";
  if (text.includes("pioggia abbondante") || text.includes("piogge abbondanti") || text.includes("precipitazioni abbondanti")) return "HeavyRain";
  if (text.includes("piovigg") || text.includes("pioggia debole") || text.includes("piogge deboli") || text.includes("pioggia leggera") || text.includes("piogge leggere")) return "LightRain";
  if (text.includes("piogg") || text.includes("pluie") || text.includes("rain")) return "Rain";
  if (text.includes("nubi basse") || text.includes("sole, nebbia") || text.includes("nebbia e nubi basse")) return "LowCloudFog";
  if (text.includes("foschia") || text.includes("foschie") || text.includes("caligine") || text.includes("mist")) return "Mist";
  if (text.includes("haze")) return "Haze";
  if (text.includes("nebb") || text.includes("foschi") || text.includes("fog")) return "Fog";
  if (text.includes("sereno") || text.includes("sole") || text.includes("soleg") || text.includes("soreli") || text.includes("clear") || text.includes("sun")) return night ? "ClearNight" : "Sun";
  if (text.includes("parzial") || text.includes("parz. nuv") || text.includes("parz nuv") || text.includes("partly")) return night ? "PartlyCloudyNight" : "PartlyCloudy";
  if (text.includes("poco nuvol") || text.includes("poco nuv") || text.includes("variabil")) return night ? "MostlyClearNight" : "MostlySunny";
  if (text.includes("nuvol") || text.includes("nÃ»l") || text.includes("coperto") || text.includes("cloud") || text.includes("overcast")) return night ? "OvercastNight" : "Overcast";

  return null;
}

function isPrimaryIconType(type) {
  return (
    RAIN_ICON_TYPES.has(type) ||
    STORM_ICON_TYPES.has(type) ||
    SNOW_ICON_TYPES.has(type) ||
    FOG_ICON_TYPES.has(type) ||
    CLEAR_ICON_TYPES.has(type) ||
    PARTLY_ICON_TYPES.has(type) ||
    CLOUD_ICON_TYPES.has(type)
  );
}

function hasSemanticEvidence(normalized) {
  return (
    Boolean(String(normalized?.condition || "").trim()) ||
    normalized?.code !== null && normalized?.code !== undefined ||
    readWeatherNumber(normalized?.precipitation, 0) > 0 ||
    readWeatherNumber(normalized?.rain, 0) > 0 ||
    readWeatherNumber(normalized?.showers, 0) > 0 ||
    readWeatherNumber(normalized?.snowfall, 0) > 0 ||
    readWeatherNumber(normalized?.windSpeed, 0) > 0 ||
    readWeatherNumber(normalized?.windGusts, 0) > 0 ||
    normalized?.isBora === true
  );
}

function getSemanticInput(normalized) {
  return {
    ...(normalized?.raw || {}),
    condition: normalized?.condition,
    weathercode: normalized?.code ?? normalized?.weathercode,
    is_day: normalized?.isNight ? 0 : normalized?.isDay ? 1 : undefined,
    precipitation: normalized?.precipitation,
    rain: normalized?.rain,
    showers: normalized?.showers,
    snowfall: normalized?.snowfall,
    wind_speed: normalized?.windSpeed,
    wind_gusts: normalized?.windGusts,
    wind_direction: normalized?.windDirection,
    is_bora: normalized?.isBora,
  };
}

function getWeatherSemanticPresentation(normalized) {
  const night = Boolean(normalized?.isNight || normalized?.night);
  const quality = normalized?.dataQuality || normalized?.raw?.data_quality || {};
  const nativeSemanticKey = quality.native_semantic_key;

  if (
    isIconLocalPilotWeather(normalized) &&
    typeof nativeSemanticKey === "string" &&
    Object.prototype.hasOwnProperty.call(WEATHER_SEMANTICS, nativeSemanticKey)
  ) {
    return getWeatherPresentation(
      getWeatherSemanticByKey(nativeSemanticKey, { source: "icon2i_condition" }),
      { night },
    );
  }

  return normalized?.semantic || classifyCurrentWeather(getSemanticInput(normalized), { night });
}

export function readPopPercent(data) {
  if (typeof data?.pop === "string") {
    const match = data.pop.match(/\d+/);
    return match ? Number(match[0]) : null;
  }

  return readWeatherNumber(
    data?.pop ??
      data?.precipitation_probability ??
      data?.precipitation_probability_max,
  );
}

export function readPrecipitationAmount(data) {
  // TOT_PREC includes the water equivalent of snow. Missing is not dry,
  // and snowfall in cm must not be mixed into this model's mm total.
  if (isIconLocalPilotWeather(data)) return readWeatherNumber(data?.precipitation);
  return Math.max(
    readWeatherNumber(data?.precipitation, 0),
    readWeatherNumber(data?.rain, 0),
    readWeatherNumber(data?.showers, 0),
    readWeatherNumber(data?.snowfall, 0),
  );
}

function normalizeHourlySlot(slot, primarySource) {
  const sourceSlot = primarySource === "icon2i_local_pilot"
    ? { ...slot, primary_source: primarySource }
    : slot;
  const code = readWeatherCode(sourceSlot);
  const missingPrecipitation = isIconLocalPilotWeather(sourceSlot) ? null : 0;

  return {
    ...sourceSlot,
    code,
    weathercode: code,
    condition: String(slot?.condition || ""),
    temperature: readWeatherNumber(slot?.temperature ?? slot?.temp),
    precipitation: readWeatherNumber(slot?.precipitation, missingPrecipitation),
    rain: readWeatherNumber(slot?.rain, missingPrecipitation),
    showers: readWeatherNumber(slot?.showers, missingPrecipitation),
    snowfall: readWeatherNumber(slot?.snowfall, missingPrecipitation),
    windSpeed: readWeatherNumber(slot?.wind_speed ?? slot?.windSpeed),
    windGusts: readWeatherNumber(slot?.wind_gusts ?? slot?.windGusts),
    isNight: isIconLocalPilotWeather(sourceSlot)
      ? readWeatherNumber(slot?.is_day) === 0 : Number(slot?.is_day) === 0,
  };
}

export function normalizeWeatherData(data = {}) {
  const pilot = isIconLocalPilotWeather(data);
  const missingPrecipitation = pilot ? null : 0;
  const semanticData = pilot
    ? { ...data, weathercode: null, weather_code: null, is_day: readWeatherNumber(data?.is_day) ?? undefined }
    : data;
  const code = readWeatherCode(data);
  const rawCondition = String(data?.condition ?? data?.weather ?? data?.description ?? "").trim();
  const temperature = readWeatherNumber(
    data?.temperature ??
      data?.temp ??
      data?.current_weather?.temperature ??
      data?.current?.temperature_2m,
  );
  const feelsLike = readWeatherNumber(
    data?.feels_like ??
      data?.apparent_temperature ??
      data?.current?.apparent_temperature,
  );
  const precipitationAmount = readPrecipitationAmount(data);
  const hourlyNext12h = Array.isArray(data?.hourly_next_12h)
    ? data.hourly_next_12h.map((slot) => normalizeHourlySlot(slot, data.primary_source))
    : [];
  const hourlyForecast = Array.isArray(data?.hourly_forecast) && data.hourly_forecast.length
    ? data.hourly_forecast.map((slot) => normalizeHourlySlot(slot, data.primary_source))
    : hourlyNext12h;
  const type = getWeatherType(semanticData);
  const isNight = (pilot ? readWeatherNumber(data?.is_day) === 0 : Number(data?.is_day) === 0)
    || data?.isNight === true || data?.night === true;
  const isDay = Number(data?.is_day) === 1 || data?.isDay === true;
  const semantic = classifyCurrentWeather(semanticData, { night: isNight });

  return {
    raw: data,
    primarySource: data?.primary_source ?? null,
    type,
    semantic,
    code,
    weathercode: code,
    condition: rawCondition,
    isDay,
    isNight,
    temperature,
    feelsLike,
    minTemperature: readWeatherNumber(data?.temperature_min ?? data?.min_temperature),
    maxTemperature: readWeatherNumber(data?.temperature_max ?? data?.max_temperature),
    humidity: readWeatherNumber(data?.humidity),
    pressure: readWeatherNumber(data?.pressure),
    windSpeed: readWeatherNumber(data?.wind_speed ?? data?.wind ?? data?.windspeed),
    windGusts: readWeatherNumber(data?.wind_gusts ?? data?.gusts),
    windDirection: data?.wind_direction ?? null,
    visibilityMeters: readWeatherNumber(data?.visibility),
    visibilityKm: readWeatherNumber(data?.visibility) === null
      ? null
      : readWeatherNumber(data.visibility) / 1000,
    cloudCover: readWeatherNumber(data?.cloud_cover),
    precipitation: readWeatherNumber(data?.precipitation, missingPrecipitation),
    rain: readWeatherNumber(data?.rain, missingPrecipitation),
    showers: readWeatherNumber(data?.showers, missingPrecipitation),
    snowfall: readWeatherNumber(data?.snowfall, missingPrecipitation),
    precipitationAmount,
    popPercent: readPopPercent(data),
    pollen: data?.pollen ?? null,
    pollenData: data?.pollen_data ?? null,
    pollenLevel: data?.pollen_data?.level ?? null,
    isBora: data?.is_bora === true,
    sunrise: data?.sunrise ?? null,
    sunset: data?.sunset ?? null,
    hourlyNext12h,
    hourlyForecast,
    source: data?.source ?? null,
    dataQuality: data?.data_quality ?? null,
    station: data?.station ?? null,
    official: data?.official ?? null,
  };
}

export function getLocalizedWeatherCondition(weather, translations = {}) {
  const normalized = weather?.type ? weather : normalizeWeatherData(weather || {});
  if (isIconLocalPilotWeather(normalized)) {
    const quality = normalized.dataQuality || normalized.raw?.data_quality || {};
    if (quality.native_condition_status && quality.native_condition_status !== "valid") {
      return translations?.conditionUnavailable || "Condizione non disponibile";
    }
    // ICON's native label is Italian-only. The canonical semantic selected
    // from the validated ICON condition drives both the icon and localized copy.
    const semantic = getWeatherSemanticPresentation(normalized);
    return (
      translations?.[semantic?.labelKey] ||
      translations?.[semantic?.fallbackLabelKey] ||
      translations?.[`condition${normalized.type}`] ||
      normalized.condition ||
      translations?.conditionUnavailable ||
      "Condizione non disponibile"
    );
  }
  const semantic = getWeatherSemanticPresentation(normalized);
  const semanticLabel =
    hasSemanticEvidence(normalized) &&
    (
      translations?.[semantic?.labelKey] ||
      translations?.[semantic?.fallbackLabelKey]
    );

  return (
    semanticLabel ||
    translations?.[`condition${normalized.type}`] ||
    normalized.condition ||
    translations?.conditionOvercast ||
    ""
  );
}

export function getWeatherIconProps(weather) {
  const normalized = weather?.type ? weather : normalizeWeatherData(weather || {});
  const code = normalized.code ?? normalized.weathercode;
  const condition = normalized.condition || "";
  const night = Boolean(normalized.isNight || normalized.night);
  const semantic = getWeatherSemanticPresentation(normalized);
  const fallbackType =
    (isPrimaryIconType(normalized.type) && normalized.type !== "Wind" ? normalized.type : null) ||
    getPrimaryTypeFromCode(code, night) ||
    getPrimaryTypeFromCondition(condition, night) ||
    (night ? "OvercastNight" : "Overcast");
  const semanticType = hasSemanticEvidence(normalized) ? semantic?.meteoconType : null;
  const iconType = isPrimaryIconType(semanticType) ? semanticType : fallbackType;

  return {
    type: iconType,
    code,
    condition,
    night,
    semanticKey: semantic?.key,
    semanticFamily: semantic?.family,
    semanticIntensity: semantic?.intensity,
    labelKey: semantic?.labelKey,
    fallbackLabelKey: semantic?.fallbackLabelKey,
    overlays: semantic?.overlays || {},
  };
}
