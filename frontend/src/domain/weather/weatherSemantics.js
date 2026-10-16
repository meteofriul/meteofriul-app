const CLEAR_TEXT = ["sereno", "sole", "soleg", "soreli", "clear", "sun"];
const MOSTLY_SUNNY_TEXT = ["poco nuvol", "poco nuv"];
const PARTLY_TEXT = ["parzial", "parz. nuv", "parz nuv", "partly"];
const VARIABLE_TEXT = ["variabil"];
const CLOUDY_TEXT = ["nuvol", "nuv.", "cloudy"];
const OVERCAST_TEXT = ["coperto", "overcast", "cuviert"];

const WIND_TEXT_PATTERN = /\b(vento|venti|ventoso|bora|borino|scirocco|libeccio|maestrale|raffich\w*|vint|buere)\b/;

export const WEATHER_SEMANTICS = {
  clear: {
    key: "clear",
    family: "clear",
    intensity: "none",
    labelKey: "conditionSun",
    nightLabelKey: "conditionClearNight",
    meteoconType: "Sun",
    nightMeteoconType: "ClearNight",
    sceneVariant: "clear",
    nightSceneVariant: "night",
    themeClass: "theme-sole",
    nightThemeClass: "theme-notte",
  },
  mostly_sunny: {
    key: "mostly_sunny",
    family: "clear",
    intensity: "light",
    labelKey: "conditionMostlySunny",
    nightLabelKey: "conditionMostlyClearNight",
    meteoconType: "MostlySunny",
    nightMeteoconType: "MostlyClearNight",
    sceneVariant: "partly",
    nightSceneVariant: "night",
    themeClass: "theme-sole",
    nightThemeClass: "theme-notte",
  },
  partly_cloudy: {
    key: "partly_cloudy",
    family: "cloud",
    intensity: "light",
    labelKey: "conditionPartlyCloudy",
    nightLabelKey: "conditionPartlyCloudyNight",
    meteoconType: "PartlyCloudy",
    nightMeteoconType: "PartlyCloudyNight",
    sceneVariant: "partly",
    nightSceneVariant: "night",
    themeClass: "theme-nuvoloso",
    nightThemeClass: "theme-notte",
  },
  variable: {
    key: "variable",
    family: "cloud",
    intensity: "light",
    labelKey: "conditionVariable",
    fallbackLabelKey: "conditionPartlyCloudy",
    nightLabelKey: "conditionPartlyCloudyNight",
    meteoconType: "PartlyCloudy",
    nightMeteoconType: "PartlyCloudyNight",
    sceneVariant: "partly",
    nightSceneVariant: "night",
    themeClass: "theme-nuvoloso",
    nightThemeClass: "theme-notte",
  },
  cloudy: {
    key: "cloudy",
    family: "cloud",
    intensity: "moderate",
    labelKey: "conditionCloudy",
    fallbackLabelKey: "conditionOvercast",
    meteoconType: "Cloud",
    nightMeteoconType: "OvercastNight",
    sceneVariant: "cloud",
    nightSceneVariant: "night",
    themeClass: "theme-nuvoloso",
    nightThemeClass: "theme-notte",
  },
  overcast: {
    key: "overcast",
    family: "cloud",
    intensity: "heavy",
    labelKey: "conditionOvercast",
    meteoconType: "Overcast",
    nightMeteoconType: "OvercastNight",
    sceneVariant: "cloud",
    nightSceneVariant: "night",
    themeClass: "theme-nuvoloso",
    nightThemeClass: "theme-notte",
  },
  low_cloud_fog: {
    key: "low_cloud_fog",
    family: "fog",
    intensity: "moderate",
    labelKey: "conditionLowCloudFog",
    meteoconType: "LowCloudFog",
    sceneVariant: "fog",
    themeClass: "theme-nebbia",
  },
  fog: {
    key: "fog",
    family: "fog",
    intensity: "moderate",
    labelKey: "conditionFog",
    meteoconType: "Fog",
    sceneVariant: "fog",
    themeClass: "theme-nebbia",
  },
  mist: {
    key: "mist",
    family: "fog",
    intensity: "light",
    labelKey: "conditionMist",
    meteoconType: "Mist",
    sceneVariant: "fog",
    themeClass: "theme-nebbia",
  },
  haze: {
    key: "haze",
    family: "fog",
    intensity: "light",
    labelKey: "conditionHaze",
    meteoconType: "Haze",
    sceneVariant: "fog",
    themeClass: "theme-nebbia",
  },
  drizzle: {
    key: "drizzle",
    family: "rain",
    intensity: "light",
    labelKey: "conditionLightRain",
    meteoconType: "LightRain",
    sceneVariant: "rain",
    themeClass: "theme-pioggia",
  },
  freezing_drizzle: {
    key: "freezing_drizzle",
    family: "mixed",
    intensity: "light",
    labelKey: "conditionFreezingDrizzle",
    fallbackLabelKey: "conditionSleet",
    meteoconType: "Sleet",
    sceneVariant: "rain",
    themeClass: "theme-pioggia",
  },
  rain: {
    key: "rain",
    family: "rain",
    intensity: "moderate",
    labelKey: "conditionRain",
    meteoconType: "Rain",
    sceneVariant: "rain",
    themeClass: "theme-pioggia",
  },
  heavy_rain: {
    key: "heavy_rain",
    family: "rain",
    intensity: "heavy",
    labelKey: "conditionHeavyRain",
    meteoconType: "HeavyRain",
    sceneVariant: "rain",
    themeClass: "theme-pioggia",
  },
  intense_rain: {
    key: "intense_rain",
    family: "rain",
    intensity: "intense",
    labelKey: "conditionIntenseRain",
    fallbackLabelKey: "conditionHeavyRain",
    meteoconType: "ExtremeRain",
    sceneVariant: "rain",
    themeClass: "theme-pioggia",
  },
  extreme_rain: {
    key: "extreme_rain",
    family: "rain",
    intensity: "extreme",
    labelKey: "conditionExtremeRain",
    fallbackLabelKey: "conditionIntenseRain",
    meteoconType: "ExtremeRain",
    sceneVariant: "rain",
    themeClass: "theme-pioggia",
  },
  freezing_rain: {
    key: "freezing_rain",
    family: "mixed",
    intensity: "heavy",
    labelKey: "conditionFreezingRain",
    fallbackLabelKey: "conditionSleet",
    meteoconType: "Sleet",
    sceneVariant: "rain",
    themeClass: "theme-pioggia",
  },
  showers: {
    key: "showers",
    family: "rain",
    intensity: "moderate",
    labelKey: "conditionShowers",
    meteoconType: "Showers",
    sceneVariant: "rain",
    themeClass: "theme-pioggia",
  },
  snow: {
    key: "snow",
    family: "snow",
    intensity: "moderate",
    labelKey: "conditionSnow",
    meteoconType: "Snow",
    sceneVariant: "snow",
    themeClass: "theme-neve",
  },
  snow_grains: {
    key: "snow_grains",
    family: "snow",
    intensity: "light",
    labelKey: "conditionSnow",
    meteoconType: "Snow",
    sceneVariant: "snow",
    themeClass: "theme-neve",
  },
  snow_showers: {
    key: "snow_showers",
    family: "snow",
    intensity: "moderate",
    labelKey: "conditionSnow",
    meteoconType: "Snow",
    sceneVariant: "snow",
    themeClass: "theme-neve",
  },
  sleet: {
    key: "sleet",
    family: "mixed",
    intensity: "moderate",
    labelKey: "conditionSleet",
    meteoconType: "Sleet",
    sceneVariant: "rain",
    themeClass: "theme-pioggia",
  },
  storm: {
    key: "storm",
    family: "storm",
    intensity: "moderate",
    labelKey: "conditionStorm",
    meteoconType: "Storm",
    sceneVariant: "storm",
    themeClass: "theme-temporale",
  },
  strong_storm: {
    key: "strong_storm",
    family: "storm",
    intensity: "heavy",
    labelKey: "conditionStrongStorm",
    meteoconType: "StrongStorm",
    sceneVariant: "storm",
    themeClass: "theme-temporale",
  },
  storm_hail: {
    key: "storm_hail",
    family: "storm",
    intensity: "heavy",
    labelKey: "conditionStormHail",
    meteoconType: "StormHail",
    sceneVariant: "storm",
    themeClass: "theme-temporale",
  },
  hail: {
    key: "hail",
    family: "hail",
    intensity: "heavy",
    labelKey: "conditionHail",
    meteoconType: "Hail",
    sceneVariant: "storm",
    themeClass: "theme-temporale",
  },
};

const WEATHER_CODE_KEY_BY_CODE = new Map([
  [0, "clear"],
  [1, "mostly_sunny"],
  [2, "partly_cloudy"],
  [3, "overcast"],
  [45, "fog"],
  [48, "fog"],
  [51, "drizzle"],
  [53, "drizzle"],
  [55, "drizzle"],
  [56, "freezing_drizzle"],
  [57, "freezing_drizzle"],
  [61, "rain"],
  [63, "rain"],
  [65, "heavy_rain"],
  [66, "freezing_rain"],
  [67, "freezing_rain"],
  [71, "snow"],
  [73, "snow"],
  [75, "snow"],
  [77, "snow_grains"],
  [80, "showers"],
  [81, "showers"],
  [82, "showers"],
  [85, "snow_showers"],
  [86, "snow_showers"],
  [95, "storm"],
  [96, "storm_hail"],
  [99, "storm_hail"],
]);

const OSMER_SYMBOL_KEY_BY_KIND_ID = {
  cielo: {
    sun: "clear",
    mostly_sunny: "mostly_sunny",
    variable: "variable",
    cloudy: "cloudy",
    overcast: "overcast",
    sun_fog: "low_cloud_fog",
  },
  pioggia: {
    light_rain: "drizzle",
    moderate_rain: "rain",
    heavy_rain: "heavy_rain",
    intense_rain: "intense_rain",
    extreme_rain: "extreme_rain",
  },
  neve: {
    moderate_snow: "snow",
    heavy_snow: "snow",
    intense_snow: "snow",
  },
  temporale: {
    storm: "storm",
  },
  nebbia: {
    fog: "fog",
    mist: "mist",
  },
  evoluzione: {
    sun: "clear",
    variable: "variable",
    overcast: "overcast",
    variable_moderate_rain: "rain",
    variable_heavy_rain: "heavy_rain",
    variable_heavy_rain_storm: "storm",
    variable_storm: "storm",
    variable_moderate_rain_snow: "sleet",
    variable_snow: "snow",
    overcast_moderate_rain: "rain",
    overcast_heavy_rain: "heavy_rain",
    overcast_intense_rain: "intense_rain",
    overcast_heavy_rain_storm: "storm",
    overcast_storm: "storm",
    overcast_heavy_rain_snow: "sleet",
    overcast_snow: "snow",
  },
};

function normalizeText(value = "") {
  return String(value || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase();
}

function includesAny(text, terms) {
  return terms.some((term) => text.includes(term));
}

function readNumber(value, fallback = null) {
  if (value === undefined || value === null || value === "") return fallback;
  const number = Number(value);
  return Number.isFinite(number) ? number : fallback;
}

function withMetadata(semantic, metadata = {}) {
  if (!semantic) return null;

  return {
    ...semantic,
    source: metadata.source || semantic.source || "semantic_map",
    certainty: metadata.certainty || semantic.certainty || "classified",
    overlays: {
      wind: null,
      probability: null,
      areaScope: null,
      ...(semantic.overlays || {}),
      ...(metadata.overlays || {}),
    },
  };
}

export function getWeatherSemanticByKey(key, metadata = {}) {
  const semantic = WEATHER_SEMANTICS[key] || WEATHER_SEMANTICS.overcast;
  return withMetadata(semantic, metadata);
}

export function getWeatherPresentation(semanticOrKey, { night = false } = {}) {
  const semantic =
    typeof semanticOrKey === "string"
      ? getWeatherSemanticByKey(semanticOrKey)
      : withMetadata(semanticOrKey || WEATHER_SEMANTICS.overcast);
  const isNight = Boolean(night);

  return {
    ...semantic,
    labelKey: isNight && semantic.nightLabelKey ? semantic.nightLabelKey : semantic.labelKey,
    meteoconType: isNight && semantic.nightMeteoconType ? semantic.nightMeteoconType : semantic.meteoconType,
    sceneVariant: isNight && semantic.nightSceneVariant ? semantic.nightSceneVariant : semantic.sceneVariant,
    themeClass: isNight && semantic.nightThemeClass ? semantic.nightThemeClass : semantic.themeClass,
    dayNightMode: isNight ? "night" : "day",
  };
}

export function classifyWeatherCode(code, { night = false, source = "weather_code" } = {}) {
  const numericCode = Number(code);
  const key = Number.isFinite(numericCode) ? WEATHER_CODE_KEY_BY_CODE.get(numericCode) : null;

  return getWeatherPresentation(getWeatherSemanticByKey(key || "overcast", { source }), { night });
}

export function classifyConditionText(text = "", { night = false, source = "condition_text" } = {}) {
  const value = normalizeText(text);

  if (!value.trim()) return null;

  let key = null;

  if (value.includes("grandine") || value.includes("grandinat")) {
    key = value.includes("tempor") ? "storm_hail" : "hail";
  } else if (
    value.includes("gelicidio") ||
    value.includes("pioggia congel") ||
    value.includes("freezing rain")
  ) {
    key = "freezing_rain";
  } else if (
    value.includes("nevischio") ||
    value.includes("pioggia mista neve") ||
    value.includes("mista a neve") ||
    value.includes("sleet")
  ) {
    key = "sleet";
  } else if (
    value.includes("tempor") ||
    value.includes("thunder") ||
    value.includes("storm") ||
    value.includes("burasce") ||
    value.includes("burasche")
  ) {
    key = (
      value.includes("localmente forte") ||
      value.includes("localmente forti") ||
      value.includes("temporali forti") ||
      value.includes("temporale forte") ||
      value.includes("forti temporali") ||
      value.includes("temporali intensi") ||
      value.includes("intensi temporali")
    )
      ? "strong_storm"
      : "storm";
  } else if (value.includes("neve") || value.includes("nef") || value.includes("snow")) {
    key = "snow";
  } else if (value.includes("rovesc") || value.includes("showers")) {
    key = "showers";
  } else if (
    value.includes("pioggia molto intensa") ||
    value.includes("piogge molto intense") ||
    value.includes("precipitazioni molto intense")
  ) {
    key = "extreme_rain";
  } else if (
    value.includes("pioggia intensa") ||
    value.includes("piogge intense") ||
    value.includes("precipitazioni intense")
  ) {
    key = "intense_rain";
  } else if (
    value.includes("pioggia abbondante") ||
    value.includes("piogge abbondanti") ||
    value.includes("precipitazioni abbondanti")
  ) {
    key = "heavy_rain";
  } else if (
    value.includes("drizzle") ||
    value.includes("piovigg") ||
    value.includes("pioggia debole") ||
    value.includes("piogge deboli") ||
    value.includes("pioggia leggera") ||
    value.includes("piogge leggere")
  ) {
    key = "drizzle";
  } else if (
    value.includes("piogg") ||
    value.includes("pluie") ||
    value.includes("ploe") ||
    value.includes("rain")
  ) {
    key = "rain";
  } else if (
    value.includes("nubi basse") ||
    value.includes("sole, nebbia") ||
    value.includes("nebbia e nubi basse")
  ) {
    key = "low_cloud_fog";
  } else if (value.includes("foschia") || value.includes("foschie") || value.includes("mist")) {
    key = "mist";
  } else if (value.includes("caligine") || value.includes("haze")) {
    key = "haze";
  } else if (value.includes("nebb") || value.includes("nibl") || value.includes("fog")) {
    key = "fog";
  } else if (includesAny(value, CLEAR_TEXT)) {
    key = "clear";
  } else if (includesAny(value, PARTLY_TEXT)) {
    key = "partly_cloudy";
  } else if (includesAny(value, MOSTLY_SUNNY_TEXT)) {
    key = "mostly_sunny";
  } else if (includesAny(value, VARIABLE_TEXT)) {
    key = "variable";
  } else if (includesAny(value, OVERCAST_TEXT)) {
    key = "overcast";
  } else if (includesAny(value, CLOUDY_TEXT)) {
    key = "cloudy";
  }

  return key ? getWeatherPresentation(getWeatherSemanticByKey(key, { source }), { night }) : null;
}

export function getWindOverlay(input = {}) {
  const rawId = String(input?.id || input?.symbolId || "").toLowerCase();
  const text = normalizeText(input?.condition || input?.description || input?.text || "");
  const windSpeed = readNumber(input?.wind_speed ?? input?.windSpeed ?? input?.windspeed);
  const windGusts = readNumber(input?.wind_gusts ?? input?.windGusts ?? input?.gusts);
  const isBora = input?.is_bora === true || input?.isBora === true || text.includes("bora");
  const hasWindText = WIND_TEXT_PATTERN.test(text);

  if (rawId && rawId !== "none") {
    const intensity = rawId.includes("very_strong")
      ? "very_strong"
      : rawId.includes("strong")
        ? "strong"
        : rawId.includes("moderate")
          ? "moderate"
          : rawId.includes("breeze")
            ? "breeze"
            : "unknown";

    return {
      key: "wind_overlay",
      source: "osmer_symbol",
      id: rawId,
      direction: input?.direction ?? null,
      intensity,
    };
  }

  if (isBora || windSpeed >= 70 || windGusts >= 85) {
    return {
      key: "wind_overlay",
      source: "current_weather",
      direction: input?.wind_direction ?? input?.windDirection ?? null,
      intensity: "strong",
      isBora,
      windSpeed,
      windGusts,
    };
  }

  if (hasWindText || windSpeed >= 40 || windGusts >= 55) {
    return {
      key: "wind_overlay",
      source: "current_weather",
      direction: input?.wind_direction ?? input?.windDirection ?? null,
      intensity: "moderate",
      isBora,
      windSpeed,
      windGusts,
    };
  }

  return null;
}

export function classifyOsmerSymbol(kind, id, { night = false, source = "osmer_symbol" } = {}) {
  const normalizedKind = String(kind || "").toLowerCase();
  const normalizedId = String(id || "").toLowerCase();

  if (normalizedKind === "vento") {
    return {
      semantic: null,
      overlay: getWindOverlay({ id: normalizedId, source }),
    };
  }

  const key = OSMER_SYMBOL_KEY_BY_KIND_ID[normalizedKind]?.[normalizedId] || null;
  if (!key || normalizedId === "none") {
    return {
      semantic: null,
      overlay: null,
    };
  }

  return {
    semantic: getWeatherPresentation(getWeatherSemanticByKey(key, { source }), { night }),
    overlay: null,
  };
}

export function classifyCurrentWeather(data = {}, { night = Number(data?.is_day) === 0 } = {}) {
  const text = data?.condition ?? data?.weather ?? data?.description ?? "";
  const code = data?.weathercode ?? data?.weather_code ?? data?.current_weather?.weathercode ?? data?.current?.weather_code;
  const overlay = getWindOverlay(data);
  const textSemantic = classifyConditionText(text, { night, source: "current_condition" });

  const metricSemantic = (() => {
    if (readNumber(data?.snowfall, 0) > 0) return getWeatherSemanticByKey("snow", { source: "current_metrics" });
    if (readNumber(data?.showers, 0) > 0.05) return getWeatherSemanticByKey("showers", { source: "current_metrics" });
    if (readNumber(data?.rain, 0) > 0.05 || readNumber(data?.precipitation, 0) > 0.05) {
      return getWeatherSemanticByKey("rain", { source: "current_metrics" });
    }
    return null;
  })();

  const codeSemantic = classifyWeatherCode(code, { night, source: "current_weather_code" });
  const semantic = textSemantic || (text ? null : metricSemantic) || codeSemantic;

  return getWeatherPresentation(
    {
      ...semantic,
      overlays: {
        ...(semantic?.overlays || {}),
        wind: overlay,
      },
    },
    { night },
  );
}
