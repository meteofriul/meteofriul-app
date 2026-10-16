import { mapOsmerAreaToCondition } from "./osmerAdapter";

const MOUNTAIN_AREA_IDS = new Set(["A1", "A2", "A3", "A4"]);
const PLAIN_COAST_AREA_IDS = new Set(["A5", "A6", "A7", "A8", "A9"]);
const DAYTIME_TERMS = ["mattino", "mattina", "mattinata", "pomeriggio", "giornata", "in giornata", "ore centrali"];
const NIGHT_RESIDUAL_TERMS = ["nella notte", "notte", "prime ore", "sera", "serata"];

function normalizeText(value = "") {
  return String(value || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase();
}
function classifyMarkerCondition(markerCondition) {
  const value = normalizeText(markerCondition?.condition);

  if (markerCondition?.lightning || markerCondition?.emphasis === "storm" || value.includes("tempor")) return "storm";
  if (value.includes("piogg") || value.includes("rovesc")) return "rain";
  if (value.includes("neve")) return "snow";
  if (value.includes("nebbia") || value.includes("foschia")) return "fog";
  if (value.includes("variabile")) return "partly";
  if (value.includes("coperto") || value.includes("nuvoloso")) {
    return value.includes("poco") ? "partly" : "cloud";
  }
  if (value.includes("sereno") || value.includes("sole")) return "sun";
  return null;
}

function getWeightedWinner(entries = [], requiredShare = 0.5) {
  const totalWeight = entries.reduce((sum, entry) => sum + entry.weight, 0);

  if (!totalWeight) return null;

  const totals = entries.reduce((acc, entry) => {
    acc[entry.type] = (acc[entry.type] || 0) + entry.weight;
    return acc;
  }, {});
  const [winner, weight] = Object.entries(totals).sort(([, weightA], [, weightB]) => weightB - weightA)[0] || [];

  return weight > totalWeight * requiredShare ? winner : null;
}

function buildAreaEntries(areas9 = {}) {
  return Object.entries(areas9)
    .map(([areaId, area]) => {
      const group = MOUNTAIN_AREA_IDS.has(areaId) ? "mountain" : "plainCoast";
      const markerCondition = mapOsmerAreaToCondition(area);

      return {
        areaId,
        group,
        markerCondition,
        type: classifyMarkerCondition(markerCondition),
        weight: PLAIN_COAST_AREA_IDS.has(areaId) ? 1.35 : 1,
      };
    })
    .filter((entry) => entry.type);
}

function summarizeFromAreas(areas9 = {}) {
  const areaEntries = buildAreaEntries(areas9);

  if (!areaEntries.length) return null;

  const hasMountainStorm = areaEntries.some((entry) => entry.group === "mountain" && entry.type === "storm");
  const hasPlainCoastStorm = areaEntries.some((entry) => entry.group === "plainCoast" && entry.type === "storm");
  const stormCount = areaEntries.filter((entry) => entry.type === "storm").length;

  if (hasPlainCoastStorm && (hasMountainStorm || stormCount >= 3)) {
    return {
      tabCondition: "storm",
      dominantDaytimeCondition: "storm",
      severeDaytimeCondition: "storm",
      confidence: "high",
      source: "areas9",
      reason: "severe_diffuse_storm",
      areaEntries,
    };
  }

  const plainCoastEntries = areaEntries.filter((entry) => entry.group === "plainCoast");
  const plainCoastWinner = getWeightedWinner(plainCoastEntries, 0.5);
  const regionalWinner = getWeightedWinner(areaEntries, 0.5);

  if (plainCoastWinner) {
    const localizedRisk = areaEntries.some((entry) => ["rain", "storm", "cloud", "partly"].includes(entry.type));
    const tabCondition = plainCoastWinner === "sun" && localizedRisk ? "partly" : plainCoastWinner;

    return {
      tabCondition,
      dominantDaytimeCondition: plainCoastWinner,
      severeDaytimeCondition: null,
      confidence: "high",
      source: "areas9",
      reason: "plain_coast_majority",
      areaEntries,
    };
  }

  if (regionalWinner) {
    return {
      tabCondition: regionalWinner,
      dominantDaytimeCondition: regionalWinner,
      severeDaytimeCondition: null,
      confidence: "medium",
      source: "areas9",
      reason: "regional_majority",
      areaEntries,
    };
  }

  return {
    tabCondition: "partly",
    dominantDaytimeCondition: null,
    severeDaytimeCondition: null,
    confidence: "low",
    source: "areas9",
    reason: "mixed_without_majority",
    areaEntries,
  };
}
function summarizeFromText(text = "") {
  const value = normalizeText(text);
  const hasDaytime = DAYTIME_TERMS.some((term) => value.includes(term));
  const hasNightResidual = NIGHT_RESIDUAL_TERMS.some((term) => value.includes(term));
  const hasFairWeather = value.includes("sereno") || value.includes("poco nuvoloso");
  const hasPlainOrCoast = value.includes("pianura") || value.includes("costa");
  const hasMountain = value.includes("montan") || value.includes("monti") || value.includes("carnia") || value.includes("cadore");
  const hasRain = value.includes("piogg") || value.includes("rovesc");
  const hasStorm = value.includes("tempor");
  const hasDiffuseRisk =
    value.includes("tutta la regione") ||
    value.includes("tutte le zone") ||
    value.includes("diffus") ||
    value.includes("a piu riprese") ||
    value.includes("gran parte");

  if (hasDiffuseRisk && hasStorm) {
    return {
      tabCondition: "storm",
      dominantDaytimeCondition: "storm",
      severeDaytimeCondition: "storm",
      nightResidualCondition: null,
      confidence: "medium",
      source: "text",
      reason: "text_diffuse_storm",
    };
  }

  if (hasNightResidual && hasDaytime && hasFairWeather) {
    return {
      tabCondition: value.includes("sereno") ? "sun" : "partly",
      dominantDaytimeCondition: value.includes("sereno") ? "sun" : "partly",
      severeDaytimeCondition: null,
      nightResidualCondition: hasStorm ? "storm" : hasRain ? "rain" : null,
      confidence: "medium",
      source: "text",
      reason: "night_residual_daytime_improves",
    };
  }

  if (hasPlainOrCoast && hasFairWeather && hasMountain && hasRain) {
    return {
      tabCondition: "partly",
      dominantDaytimeCondition: "partly",
      severeDaytimeCondition: null,
      nightResidualCondition: null,
      confidence: "medium",
      source: "text",
      reason: "localized_mountain_rain_plain_coast_fair",
    };
  }

  if (hasStorm) return { tabCondition: "storm", dominantDaytimeCondition: "storm", confidence: "low", source: "text", reason: "text_storm" };
  if (hasRain) return { tabCondition: "rain", dominantDaytimeCondition: "rain", confidence: "low", source: "text", reason: "text_rain" };
  if (value.includes("coperto")) return { tabCondition: "cloud", dominantDaytimeCondition: "cloud", confidence: "low", source: "text", reason: "text_cloud" };
  if (value.includes("variabile") || value.includes("poco nuvoloso")) {
    return { tabCondition: "partly", dominantDaytimeCondition: "partly", confidence: "low", source: "text", reason: "text_partly" };
  }
  if (value.includes("sereno")) return { tabCondition: "sun", dominantDaytimeCondition: "sun", confidence: "low", source: "text", reason: "text_sun" };

  return null;
}

export function summarizeOsmerTemporalDay(day = {}) {
  const areas9 = day?.areas9 || day?.osmer_structured_day?.areas9 || day?.osmerStructuredDay?.areas9 || day?.structured_osmer_day?.areas9;
  const areasSummary = areas9 ? summarizeFromAreas(areas9) : null;

  if (areasSummary) {
    return {
      validDate: day?.valid_date || day?.date || null,
      ...areasSummary,
    };
  }

  const textSummary = summarizeFromText(day?.text || day?.sourceOfficialText || day?.officialText || day?.displayText || day?.condition || "");

  if (textSummary) {
    return {
      validDate: day?.valid_date || day?.date || null,
      ...textSummary,
    };
  }

  return {
    validDate: day?.valid_date || day?.date || null,
    tabCondition: "cloud",
    dominantDaytimeCondition: null,
    severeDaytimeCondition: null,
    nightResidualCondition: null,
    confidence: "low",
    source: "fallback",
    reason: "insufficient_data",
  };
}
