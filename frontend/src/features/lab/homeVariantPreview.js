import { getTemperatureSeverity } from "../../domain/weather/temperatureSeverity";
import { buildAlmanacViewModel } from "../almanac/almanacViewModel";
import { getHomeStaticViewModel } from "../home/homeFixture";
import { buildHomeAlmanacStateFromModel } from "../home/homeViewModel";

const HOME_LAB_EVENT_IMAGE = "/municipalities/photos/030129-photo.webp";

export const HOME_WEATHER_VARIANT_PREVIEWS = [
  {
    id: "clear",
    label: { it: "Sole", fur: "Soreli" },
    conditionLabel: { it: "Soleggiato", fur: "Soreli" },
    iconType: "Sun",
    semanticFamily: "clear",
    temperatureValue: "23",
    rawTemperature: 23,
    detailValues: {
      "feels-like": "24",
      precipitation: "0 mm",
      wind: "12 km/h",
      humidity: "62%",
    },
  },
  {
    id: "partly",
    label: { it: "Variabile", fur: "Variabil" },
    conditionLabel: { it: "Poco nuvoloso", fur: "Poc nul" },
    iconType: "PartlyCloudy",
    semanticFamily: "partly",
    temperatureValue: "21",
    rawTemperature: 21,
    detailValues: {
      "feels-like": "21",
      precipitation: "0 mm",
      wind: "10 km/h",
      humidity: "66%",
    },
  },
  {
    id: "cloud",
    label: { it: "Nuvoloso", fur: "Nul" },
    conditionLabel: { it: "Nuvoloso", fur: "Nul" },
    iconType: "Cloud",
    semanticFamily: "cloud",
    temperatureValue: "18",
    rawTemperature: 18,
    detailValues: {
      "feels-like": "18",
      precipitation: "0 mm",
      wind: "8 km/h",
      humidity: "74%",
    },
  },
  {
    id: "rain",
    label: { it: "Pioggia", fur: "Pluie" },
    conditionLabel: { it: "Pioggia", fur: "Pluie" },
    iconType: "Rain",
    semanticFamily: "rain",
    temperatureValue: "16",
    rawTemperature: 16,
    detailValues: {
      "feels-like": "16",
      precipitation: "6 mm",
      wind: "18 km/h",
      humidity: "88%",
    },
  },
  {
    id: "storm",
    label: { it: "Temporale", fur: "Tempor\u00e2l" },
    conditionLabel: { it: "Temporale", fur: "Tempor\u00e2l" },
    iconType: "Storm",
    semanticFamily: "storm",
    temperatureValue: "19",
    rawTemperature: 19,
    detailValues: {
      "feels-like": "20",
      precipitation: "14 mm",
      wind: "32 km/h",
      humidity: "91%",
    },
  },
  {
    id: "snow",
    label: { it: "Neve", fur: "Nef" },
    conditionLabel: { it: "Neve", fur: "Nef" },
    iconType: "Snow",
    semanticFamily: "snow",
    temperatureValue: "1",
    rawTemperature: 1,
    detailValues: {
      "feels-like": "-1",
      precipitation: "4 mm",
      wind: "14 km/h",
      humidity: "86%",
    },
  },
  {
    id: "fog",
    label: { it: "Nebbia", fur: "Nebie" },
    conditionLabel: { it: "Nebbia", fur: "Nebie" },
    iconType: "Fog",
    semanticFamily: "fog",
    temperatureValue: "9",
    rawTemperature: 9,
    detailValues: {
      "feels-like": "9",
      precipitation: "0 mm",
      wind: "4 km/h",
      humidity: "95%",
    },
  },
  {
    id: "night",
    label: { it: "Notte", fur: "Gnot" },
    conditionLabel: { it: "Sereno", fur: "Seren" },
    iconType: "ClearNight",
    semanticFamily: "clear",
    temperatureValue: "13",
    rawTemperature: 13,
    night: true,
    detailValues: {
      "feels-like": "13",
      precipitation: "0 mm",
      wind: "7 km/h",
      humidity: "78%",
    },
  },
  {
    id: "cloud-night",
    label: { it: "Nuvoloso notte", fur: "Nul gnot" },
    conditionLabel: { it: "Nuvoloso", fur: "Nul" },
    iconType: "OvercastNight",
    semanticFamily: "cloud",
    temperatureValue: "11",
    rawTemperature: 11,
    night: true,
    detailValues: {
      "feels-like": "11",
      precipitation: "0 mm",
      wind: "9 km/h",
      humidity: "82%",
    },
  },
  {
    id: "rain-night",
    label: { it: "Pioggia notte", fur: "Pluie gnot" },
    conditionLabel: { it: "Pioggia", fur: "Pluie" },
    iconType: "Rain",
    semanticFamily: "rain",
    temperatureValue: "12",
    rawTemperature: 12,
    night: true,
    detailValues: {
      "feels-like": "12",
      precipitation: "8 mm",
      wind: "19 km/h",
      humidity: "90%",
    },
  },
  {
    id: "storm-night",
    label: { it: "Temporale notte", fur: "Tempor\u00e2l gnot" },
    conditionLabel: { it: "Temporale", fur: "Tempor\u00e2l" },
    iconType: "Storm",
    semanticFamily: "storm",
    temperatureValue: "14",
    rawTemperature: 14,
    night: true,
    detailValues: {
      "feels-like": "14",
      precipitation: "18 mm",
      wind: "35 km/h",
      humidity: "92%",
    },
  },
  {
    id: "snow-night",
    label: { it: "Neve notte", fur: "Nef gnot" },
    conditionLabel: { it: "Neve", fur: "Nef" },
    iconType: "Snow",
    semanticFamily: "snow",
    temperatureValue: "-1",
    rawTemperature: -1,
    night: true,
    detailValues: {
      "feels-like": "-4",
      precipitation: "5 mm",
      wind: "13 km/h",
      humidity: "88%",
    },
  },
];

const PREVIEW_COPY = {
  it: {
    ariaLabel: "Anteprima varianti meteo",
    title: "Varianti meteo",
  },
  fur: {
    ariaLabel: "Anteprime variantis meteo",
    title: "Variantis meteo",
  },
};

function getLanguageKey(language) {
  return language === "fur" ? "fur" : "it";
}

function getLocalizedValue(value, language) {
  const key = getLanguageKey(language);

  if (typeof value === "string") return value;

  return value?.[key] || value?.it || "";
}

function getPreviewById(variantId) {
  return (
    HOME_WEATHER_VARIANT_PREVIEWS.find((preview) => preview.id === variantId) ||
    HOME_WEATHER_VARIANT_PREVIEWS[0]
  );
}

function getPreviewDate(value) {
  const date = value instanceof Date ? new Date(value.getTime()) : new Date(value);

  return Number.isFinite(date.getTime()) ? date : new Date();
}

function buildPreviewTemperature(baseTemperature, preview) {
  const unit = baseTemperature?.unit || "";
  const value = preview.temperatureValue;

  return {
    ...baseTemperature,
    label: `${value}${unit}`,
    severity: getTemperatureSeverity(preview.rawTemperature, "current"),
    unit,
    value,
  };
}

function buildPreviewDetails(baseDetails, preview, unit) {
  return baseDetails.map((detail) => {
    const previewValue = preview.detailValues?.[detail.id];
    const normalizedValue =
      detail.id === "feels-like" && previewValue && !String(previewValue).includes(unit)
        ? `${previewValue}${unit}`
        : previewValue;

    return normalizedValue
      ? {
          ...detail,
          value: normalizedValue,
        }
      : detail;
  });
}

export function getHomeWeatherVariantPreviewCopy(language = "it") {
  const key = getLanguageKey(language);

  return PREVIEW_COPY[key] || PREVIEW_COPY.it;
}

export function buildHomeWeatherVariantPreviewModel(
  language = "it",
  variantId = "clear",
  { now = new Date() } = {},
) {
  const baseModel = getHomeStaticViewModel(language);
  const preview = getPreviewById(variantId);
  const previewDate = getPreviewDate(now);
  const almanacState = buildHomeAlmanacStateFromModel(
    buildAlmanacViewModel({
      date: previewDate,
      language,
      now: previewDate,
    }),
    { language },
  );
  const conditionLabel = getLocalizedValue(preview.conditionLabel, language);
  const unit = baseModel.weather.temperature.unit || "";
  const details = buildPreviewDetails(baseModel.weather.details, preview, unit);
  const feelsLike = details.find((detail) => detail.id === "feels-like") || null;

  return {
    ...baseModel,
    almanac: {
      ...baseModel.almanac,
      ...almanacState,
    },
    bulletin: {
      ...baseModel.bulletin,
      dateLabel: almanacState.dateLabel,
    },
    events: {
      ...baseModel.events,
      items: (baseModel.events?.items || []).map((event, index) => (
        index === 0
          ? { ...event, image: HOME_LAB_EVENT_IMAGE }
          : event
      )),
    },
    weather: {
      ...baseModel.weather,
      conditionLabel,
      details,
      feelsLike,
      icon: {
        ...(baseModel.weather.icon || {}),
        condition: conditionLabel,
        night: Boolean(preview.night),
        semanticFamily: preview.semanticFamily,
        semanticKey: preview.id,
        type: preview.iconType,
      },
      temperature: buildPreviewTemperature(baseModel.weather.temperature, preview),
      scenePhaseOverride: preview.night ? "night" : "midday",
      weatherVariant: preview.id,
    },
  };
}

export function getHomeWeatherVariantPreviewOptions(language = "it") {
  return HOME_WEATHER_VARIANT_PREVIEWS.map((preview) => ({
    id: preview.id,
    label: getLocalizedValue(preview.label, language),
  }));
}
