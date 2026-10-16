import { getWeatherIconProps } from "./normalizedWeather";
import { getConditionContext, getWeatherGroup } from "./weatherAdviceContext";

const LOCATION_TO_AREA_ID = Object.freeze({
  gorizia: "A7",
  lignano: "A8",
  "lignano sabbiadoro": "A8",
  pordenone: "A5",
  trieste: "A9",
  udine: "A6",
});

const SKY_BY_ID = Object.freeze({
  cloudy: { condition: "nuvoloso", headline: "Nuvoloso" },
  mostly_sunny: { condition: "poco nuvoloso", headline: "Poco nuvoloso" },
  overcast: { condition: "coperto", headline: "Coperto" },
  sun: { condition: "sereno", headline: "Sereno" },
  sun_fog: { condition: "nebbia", headline: "Sole e nebbia" },
  variable: { condition: "variabile", headline: "Variabile" },
});

const RAIN_BY_ID = Object.freeze({
  extreme_rain: { condition: "pioggia molto intensa", headline: "piogge molto intense" },
  heavy_rain: { condition: "pioggia abbondante", headline: "piogge abbondanti" },
  intense_rain: { condition: "pioggia intensa", headline: "piogge intense" },
  light_rain: { condition: "pioggia debole", headline: "piogge deboli" },
  moderate_rain: { condition: "pioggia", headline: "piogge" },
});

const SNOW_BY_ID = Object.freeze({
  heavy_snow: { condition: "neve", headline: "nevicate abbondanti" },
  intense_snow: { condition: "neve", headline: "nevicate intense" },
  moderate_snow: { condition: "neve", headline: "neve" },
});

const FOG_BY_ID = Object.freeze({
  fog: { condition: "nebbia", headline: "nebbia" },
  mist: { condition: "foschia", headline: "foschia" },
});

const STORM_IDS = new Set(["storm"]);
const WIND_IDS = new Set([
  "breeze",
  "east_moderate",
  "east_north_east_moderate",
  "east_north_east_very_strong",
  "east_strong",
  "north_east_moderate",
  "north_east_strong",
  "north_moderate",
  "north_strong",
  "north_west_moderate",
  "north_west_strong",
  "south_east_moderate",
  "south_east_strong",
  "south_moderate",
  "south_strong",
  "south_west_moderate",
  "south_west_strong",
  "west_moderate",
  "west_strong",
]);
const STRONG_WIND_IDS = new Set([...WIND_IDS].filter((id) => id.includes("strong")));
const REQUIRED_SYMBOLS = ["cielo", "pioggia", "neve", "temporale", "nebbia", "vento"];
const ADVICE_LABELS = Object.freeze({
  fog: "Prudenza per la visibilità ridotta",
  rain: "Ombrello consigliato",
  snow: "Prudenza in presenza di neve",
  storm: "Prudenza durante i temporali",
  wind: "Attenzione al vento",
});

function normalizeLocationName(location) {
  const value = typeof location === "string" ? location : location?.city;

  return String(value || "")
    .normalize("NFKC")
    .trim()
    .replace(/\s+/g, " ")
    .toLocaleLowerCase("it-IT");
}

export function getOsmerLocalAreaId(location) {
  return LOCATION_TO_AREA_ID[normalizeLocationName(location)] || null;
}

function hasItems(value) {
  return Array.isArray(value) && value.length > 0;
}

function isHealedDay(day) {
  const quality = day?.quality || {};

  return Boolean(
    day?.source_mix ||
    quality.source_mix ||
    day?.fallback_source_date ||
    hasItems(day?.healed_missing_areas) ||
    hasItems(quality.healed_missing_areas),
  );
}

function isFreshStructuredSource(day, area, source) {
  const sourceStatus = String(source?.source_status || "").toLowerCase();

  return Boolean(
    day?.source_kind === "structured_xml" &&
    area?.source_kind === "structured_xml" &&
    source?.id_emissione &&
    source?.data_emissione &&
    source?.raw_hash &&
    Number.isFinite(new Date(source.data_emissione).getTime()) &&
    source.is_stale === false &&
    day?.is_stale !== true &&
    area?.is_stale !== true &&
    area?.healed_from_previous_snapshot !== true &&
    !isHealedDay(day) &&
    !/(?:^|_)(?:mixed|healed|stale|unavailable|failed)(?:_|$)/.test(sourceStatus),
  );
}

function readSymbol(symbols, name, allowedIds) {
  const symbol = symbols?.[name];
  const id = String(symbol?.id || "").trim();
  const code = Number(symbol?.code);

  if (!id || !Number.isInteger(code)) return null;
  if (id === "none") return code === 100 ? { ...symbol, code, id } : null;
  if (!allowedIds.has(id) || code === 100) return null;

  return { ...symbol, code, id };
}

function readStructuredSymbols(area) {
  const symbols = area?.symbols;
  if (!symbols || REQUIRED_SYMBOLS.some((name) => !symbols[name])) return null;

  const cielo = readSymbol(symbols, "cielo", new Set(Object.keys(SKY_BY_ID)));
  const pioggia = readSymbol(symbols, "pioggia", new Set(Object.keys(RAIN_BY_ID)));
  const neve = readSymbol(symbols, "neve", new Set(Object.keys(SNOW_BY_ID)));
  const temporale = readSymbol(symbols, "temporale", STORM_IDS);
  const nebbia = readSymbol(symbols, "nebbia", new Set(Object.keys(FOG_BY_ID)));
  const vento = readSymbol(symbols, "vento", WIND_IDS);

  if (!cielo || !pioggia || !neve || !temporale || !nebbia || !vento) return null;

  return { cielo, nebbia, neve, pioggia, temporale, vento };
}

function joinHeadline(skyHeadline, phenomenon) {
  return `${skyHeadline} con ${phenomenon}`;
}

function buildPresentation(symbols) {
  const sky = SKY_BY_ID[symbols.cielo.id];
  const rain = RAIN_BY_ID[symbols.pioggia.id] || null;
  const snow = SNOW_BY_ID[symbols.neve.id] || null;
  const fog = FOG_BY_ID[symbols.nebbia.id] || null;
  const hasStorm = symbols.temporale.id !== "none";
  const hasAdvisoryWind = symbols.vento.id !== "none" && symbols.vento.id !== "breeze";

  if (hasStorm) {
    return {
      condition: "temporale",
      headline: joinHeadline(sky.headline, rain ? `${rain.headline} e temporali` : "temporali"),
      weatherType: "Storm",
    };
  }
  if (snow) {
    return {
      condition: snow.condition,
      headline: joinHeadline(sky.headline, snow.headline),
      weatherType: "Snow",
    };
  }
  if (rain) {
    return {
      condition: rain.condition,
      headline: joinHeadline(sky.headline, rain.headline),
      weatherType: null,
    };
  }
  if (fog) {
    return {
      condition: fog.condition,
      headline: joinHeadline(sky.headline, fog.headline),
      weatherType: null,
    };
  }
  if (hasAdvisoryWind) {
    return {
      condition: sky.condition,
      headline: `${sky.headline} e ventoso`,
      weatherType: "Wind",
    };
  }

  return { condition: sky.condition, headline: sky.headline, weatherType: null };
}

function buildAdvice(presentation, symbols, icon) {
  const weatherGroup = getWeatherGroup(presentation.weatherType || icon.type);
  const context = getConditionContext({ condition: presentation.condition }, weatherGroup);
  const adviceGroup = context.adviceGroup;

  if (!Object.prototype.hasOwnProperty.call(ADVICE_LABELS, adviceGroup)) return null;

  const label = adviceGroup === "wind" && STRONG_WIND_IDS.has(symbols.vento.id)
    ? "Prudenza per vento forte"
    : ADVICE_LABELS[adviceGroup];

  return Object.freeze({
    group: adviceGroup,
    label,
    umbrellaLevel: context.umbrellaLevel,
  });
}

/**
 * Builds one immutable, internally consistent local OSMER snapshot.
 * Returns null whenever locality, structured symbols or per-day provenance
 * cannot prove that all fields come from the same fresh XML emission.
 */
export function buildOsmerLocalAdviceSnapshot(day, location) {
  const areaId = getOsmerLocalAreaId(location);
  const validDate = String(day?.valid_date || "").trim();
  const source = day?.osmer_structured_source;
  const area = areaId ? day?.areas9?.[areaId] : null;

  if (!areaId || !/^\d{4}-\d{2}-\d{2}$/.test(validDate)) return null;
  if (!area || area.id !== areaId || !isFreshStructuredSource(day, area, source)) return null;
  if (area.valid_date && area.valid_date !== validDate) return null;

  const symbols = readStructuredSymbols(area);
  if (!symbols) return null;

  const presentation = buildPresentation(symbols);
  const icon = Object.freeze(getWeatherIconProps({ condition: presentation.condition }));
  const advice = buildAdvice(presentation, symbols, icon);
  const issuedAt = source.data_emissione;
  const rawHash = source.raw_hash;

  return Object.freeze({
    advice,
    areaId,
    headline: presentation.headline,
    icon,
    isStale: false,
    issuedAt,
    snapshotKey: `osmer:${source.id_emissione}:${issuedAt}:${rawHash}:${validDate}:${areaId}`,
    validDate,
  });
}
