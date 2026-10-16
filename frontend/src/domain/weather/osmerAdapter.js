export const OSMER_AREA_TO_MAP_ZONE_ID = {
  A1: "carnia",
  A2: "giulie",
  A3: "pedemontana-ovest",
  A4: "pedemontana-est",
  A5: "pordenonese",
  A6: "friuli",
  A7: "gorizia",
  A8: "laguna",
  A9: "carso",
};

const SKY_CONDITION_BY_ID = {
  sun: { condition: "sereno", emphasis: "light" },
  mostly_sunny: { condition: "poco nuvoloso", emphasis: "light" },
  variable: { condition: "variabile", emphasis: "soft" },
  cloudy: { condition: "nuvoloso", emphasis: "normal" },
  overcast: { condition: "coperto", emphasis: "normal" },
  sun_fog: { condition: "nebbia", emphasis: "soft" },
};

const RAIN_CONDITION_BY_ID = {
  light_rain: { condition: "pioggia debole", emphasis: "loaded" },
  moderate_rain: { condition: "pioggia", emphasis: "loaded" },
  heavy_rain: { condition: "pioggia abbondante", emphasis: "loaded" },
  intense_rain: { condition: "pioggia intensa", emphasis: "loaded" },
  extreme_rain: { condition: "pioggia molto intensa", emphasis: "loaded" },
};

const SNOW_CONDITION_BY_ID = {
  moderate_snow: { condition: "neve", emphasis: "loaded" },
  heavy_snow: { condition: "neve", emphasis: "loaded" },
  intense_snow: { condition: "neve", emphasis: "loaded" },
};

const FOG_CONDITION_BY_ID = {
  fog: { condition: "nebbia", emphasis: "soft" },
  mist: { condition: "foschia", emphasis: "soft" },
};

function symbolId(area, name) {
  return area?.symbols?.[name]?.id || "none";
}

function symbolCode(area, name) {
  return area?.symbols?.[name]?.code;
}

function isActiveSymbol(area, name) {
  const id = symbolId(area, name);
  const code = symbolCode(area, name);

  return id !== "none" && code !== 100 && code !== null && code !== undefined;
}

function mapOfficialProjectedSkySymbol(area) {
  const sky = SKY_CONDITION_BY_ID[symbolId(area, "cielo")] || SKY_CONDITION_BY_ID.variable;
  return { ...sky, lightning: false, source: "official_projected" };
}

function mapOfficialProjectedCondition(area) {
  const projectedCondition = String(area?.projected_condition || "").trim().toLowerCase();
  if (!projectedCondition || area?.source_kind !== "official_projected") return null;

  const hasWindSignal =
    projectedCondition.includes("vento") ||
    projectedCondition.includes("ventoso") ||
    projectedCondition.includes("bora");

  if (projectedCondition.includes("tempor")) {
    return {
      condition: projectedCondition,
      emphasis: "storm",
      lightning: true,
      source: "official_projected",
    };
  }

  if (projectedCondition.includes("pioggia molto intensa") || projectedCondition.includes("piogge molto intense")) {
    return { condition: "pioggia molto intensa", emphasis: "loaded", lightning: false, source: "official_projected" };
  }

  if (projectedCondition.includes("pioggia intensa") || projectedCondition.includes("piogge intense")) {
    return { condition: "pioggia intensa", emphasis: "loaded", lightning: false, source: "official_projected" };
  }

  if (projectedCondition.includes("pioggia abbondante")) {
    return { condition: "pioggia abbondante", emphasis: "loaded", lightning: false, source: "official_projected" };
  }

  if (projectedCondition.includes("piogg")) {
    return { condition: "pioggia", emphasis: "loaded", lightning: false, source: "official_projected" };
  }

  if (projectedCondition.includes("neve")) {
    return { condition: "neve", emphasis: "loaded", lightning: false, source: "official_projected" };
  }

  if (projectedCondition.includes("nebb") || projectedCondition.includes("fosch")) {
    return { condition: "nebbia", emphasis: "soft", lightning: false, source: "official_projected" };
  }

  if (projectedCondition.includes("copert")) {
    return { condition: "coperto", emphasis: "normal", lightning: false, source: "official_projected" };
  }

  if (projectedCondition.includes("poco nuvol")) {
    return { condition: "poco nuvoloso", emphasis: "light", lightning: false, source: "official_projected" };
  }

  if (projectedCondition.includes("seren")) {
    return { condition: "sereno", emphasis: "light", lightning: false, source: "official_projected" };
  }

  if (projectedCondition.includes("variabil")) {
    return { condition: "variabile", emphasis: "soft", lightning: false, source: "official_projected" };
  }

  if (hasWindSignal) {
    return mapOfficialProjectedSkySymbol(area);
  }

  return { condition: projectedCondition, emphasis: "soft", lightning: false, source: "official_projected" };
}

export function getOsmerStructuredDay(forecastDay) {
  if (forecastDay?.osmer_structured_day?.areas9) return forecastDay.osmer_structured_day;
  if (forecastDay?.osmerStructuredDay?.areas9) return forecastDay.osmerStructuredDay;
  if (forecastDay?.structured_osmer_day?.areas9) return forecastDay.structured_osmer_day;
  return null;
}

export function mergeForecastWithOsmer(forecastDays = [], osmerStructured = null) {
  if (!Array.isArray(forecastDays) || !osmerStructured?.days) return forecastDays;

  const osmerDaysByDate = new Map(
    osmerStructured.days
      .filter((day) => day?.valid_date)
      .map((day) => [day.valid_date, day]),
  );

  return forecastDays.map((forecastDay) => {
    const structuredDay = osmerDaysByDate.get(forecastDay?.date) || null;

    return {
      ...forecastDay,
      osmer_structured_day: structuredDay,
    };
  });
}

export function mapOsmerAreaToCondition(area) {
  if (!area) {
    return { condition: "poco nuvoloso", emphasis: "light", source: "osmer_structured_missing" };
  }

  const officialProjectedState = mapOfficialProjectedCondition(area);
  if (officialProjectedState) return officialProjectedState;

  if (isActiveSymbol(area, "temporale")) {
    const rain = RAIN_CONDITION_BY_ID[symbolId(area, "pioggia")];
    if (!rain) {
      const sky = SKY_CONDITION_BY_ID[symbolId(area, "cielo")] || SKY_CONDITION_BY_ID.variable;
      return { ...sky, lightning: true, source: "osmer_structured" };
    }

    return { condition: "temporale", emphasis: "storm", lightning: true, source: "osmer_structured" };
  }

  const snow = SNOW_CONDITION_BY_ID[symbolId(area, "neve")];
  if (snow) {
    return { ...snow, lightning: false, source: "osmer_structured" };
  }

  const rain = RAIN_CONDITION_BY_ID[symbolId(area, "pioggia")];
  if (rain) {
    return { ...rain, lightning: false, source: "osmer_structured" };
  }

  const fog = FOG_CONDITION_BY_ID[symbolId(area, "nebbia")];
  if (fog) {
    return { ...fog, lightning: false, source: "osmer_structured" };
  }

  const sky = SKY_CONDITION_BY_ID[symbolId(area, "cielo")] || SKY_CONDITION_BY_ID.variable;
  return { ...sky, lightning: false, source: "osmer_structured" };
}

export function buildStructuredOsmerZones(areas9 = {}, mapZones = []) {
  const mapZonesById = new Map(mapZones.map((zone) => [zone.id, zone]));

  return Object.entries(OSMER_AREA_TO_MAP_ZONE_ID)
    .map(([areaId, zoneId]) => {
      const zone = mapZonesById.get(zoneId);
      const area = areas9?.[areaId];

      if (!zone || !area) return null;

      const markerState = mapOsmerAreaToCondition(area);

      return {
        ...zone,
        ...markerState,
        osmerAreaId: areaId,
        osmerAreaName: area.name || areaId,
        osmerSymbols: area.symbols || {},
        osmerStructuredArea: area,
        showTemperature: false,
        alert: null,
      };
    })
    .filter(Boolean);
}
