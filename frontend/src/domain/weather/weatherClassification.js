import { classifyWeatherCode } from "./weatherSemantics";

export function getWeatherCode(data) {
  return Number(
    data?.weathercode ??
      data?.weather_code ??
      data?.current_weather?.weathercode ??
      data?.current?.weather_code ??
      3
  );
}

function readWeatherCode(data) {
  const rawCode =
    data?.weathercode ??
    data?.weather_code ??
    data?.current_weather?.weathercode ??
    data?.current?.weather_code;
  const code = Number(rawCode);

  return Number.isFinite(code) ? code : null;
}

function hasPositiveMetric(data, keys, threshold = 0) {
  return keys.some((key) => {
    const value = Number(data?.[key] ?? data?.current?.[key]);
    return Number.isFinite(value) && value > threshold;
  });
}

export function getWeatherType(data) {
  const code = readWeatherCode(data);
  const text = String(data?.condition ?? data?.weather ?? data?.description ?? "").toLowerCase();
  const windSpeed = Number(data?.wind_speed ?? 0);
  const windGusts = Number(data?.wind_gusts ?? 0);
  const isBora = data?.is_bora === true;
  const night = Number(data?.is_day) === 0;
  const codePresentation = classifyWeatherCode(code, { night, source: "current_weather_code" });

  if ([56, 57, 65, 66, 67, 96, 99].includes(code)) {
    return codePresentation.meteoconType;
  }

  if (text.includes("grandine") || text.includes("grandinat")) {
    return text.includes("tempor") ? "StormHail" : "Hail";
  }

  if (
    text.includes("nevischio") ||
    text.includes("pioggia mista neve") ||
    text.includes("mista a neve") ||
    text.includes("gelicidio") ||
    text.includes("pioggia congel")
  ) {
    return "Sleet";
  }

  if (
    text.includes("tempor") ||
    text.includes("thunder") ||
    text.includes("storm") ||
    [95, 96, 99].includes(code)
  ) {
    if (
      text.includes("localmente forte") ||
      text.includes("localmente forti") ||
      text.includes("temporali forti") ||
      text.includes("temporale forte") ||
      text.includes("forti temporali") ||
      text.includes("temporali intensi")
    ) {
      return "StrongStorm";
    }

    return "Storm";
  }

  if (
    text.includes("neve") ||
    text.includes("nêf") ||
    text.includes("snow") ||
    hasPositiveMetric(data, ["snowfall"], 0) ||
    [71, 73, 75, 77, 85, 86].includes(code)
  ) {
    return "Snow";
  }

  if (
    text.includes("rovesc") ||
    text.includes("showers") ||
    [80, 81, 82].includes(code)
  ) {
    return "Showers";
  }

  if (
    text.includes("pioggia molto intensa") ||
    text.includes("piogge molto intense") ||
    text.includes("precipitazioni molto intense") ||
    text.includes("pioggia intensa") ||
    text.includes("piogge intense") ||
    text.includes("precipitazioni intense")
  ) {
    return "ExtremeRain";
  }

  if (
    text.includes("pioggia abbondante") ||
    text.includes("piogge abbondanti") ||
    text.includes("precipitazioni abbondanti")
  ) {
    return "HeavyRain";
  }

  if (
    text.includes("drizzle") ||
    text.includes("piovigg") ||
    text.includes("pioggia debole") ||
    text.includes("piogge deboli") ||
    text.includes("pioggia leggera") ||
    text.includes("piogge leggere") ||
    [51, 53, 55].includes(code)
  ) {
    return "LightRain";
  }

  if (
    text.includes("piogg") ||
    text.includes("pluie") ||
    text.includes("rain") ||
    hasPositiveMetric(data, ["precipitation", "rain", "showers"], 0.05) ||
    [61, 63, 65].includes(code)
  ) {
    return "Rain";
  }

  if (
    text.includes("nubi basse") ||
    text.includes("sole, nebbia") ||
    text.includes("nebbia e nubi basse")
  ) {
    return "LowCloudFog";
  }

  if (isBora || windSpeed >= 70 || windGusts >= 85) return "Wind";

  if (
    text.includes("foschia") ||
    text.includes("foschie") ||
    text.includes("caligine") ||
    text.includes("mist")
  ) {
    return "Mist";
  }

  if (text.includes("haze")) return "Haze";

  if (
    text.includes("nebb") ||
    text.includes("foschi") ||
    text.includes("fog") ||
    [45, 48].includes(code)
  ) {
    return "Fog";
  }

  if (
    text.includes("sereno") ||
    text.includes("sole") ||
    text.includes("soleg") ||
    text.includes("soreli") ||
    text.includes("clear") ||
    text.includes("sun") ||
    code === 0
  ) {
    return night ? "ClearNight" : "Sun";
  }

  if (
    text.includes("parzial") ||
    text.includes("parz. nuv") ||
    text.includes("parz nuv") ||
    text.includes("partly") ||
    code === 2
  ) {
    return night ? "PartlyCloudyNight" : "PartlyCloudy";
  }

  if (
    text.includes("poco nuvol") ||
    text.includes("poco nuv") ||
    text.includes("variabil") ||
    code === 1
  ) {
    return night ? "MostlyClearNight" : "MostlySunny";
  }

  if (
    text.includes("nuvol") ||
    text.includes("nûl") ||
    text.includes("coperto") ||
    text.includes("cloud") ||
    text.includes("overcast") ||
    code === 3
  ) {
    return night ? "OvercastNight" : "Overcast";
  }

  return "Overcast";
}

export function getSceneWeatherVariant(data) {
  const type = getWeatherType(data);

  if (["Storm", "StrongStorm", "StormHail", "Hail"].includes(type)) return "storm";
  if (["LightRain", "Rain", "HeavyRain", "ExtremeRain", "Showers", "Sleet"].includes(type)) return "rain";
  if (type === "Snow") return "snow";
  if (["Fog", "Mist", "Haze", "LowCloudFog"].includes(type)) return "fog";
  if (Number(data?.is_day) === 0) return "night";
  if (["Sun", "MostlySunny", "ClearNight", "MostlyClearNight"].includes(type)) {
    return "sun";
  }

  return "cloud";
}

export function getThemeClassFromWeather(data) {
  const variant = getSceneWeatherVariant(data);

  if (variant === "sun") return "theme-sole";
  if (variant === "night") return "theme-notte";
  if (variant === "rain") return "theme-pioggia";
  if (variant === "storm") return "theme-temporale";
  if (variant === "snow") return "theme-neve";
  if (variant === "fog") return "theme-nebbia";
  return "theme-nuvoloso";
}
