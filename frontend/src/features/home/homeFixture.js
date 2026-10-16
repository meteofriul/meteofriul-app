import { buildHomeViewModel } from "./homeViewModel";

const HOME_LAB_ALERT_LEVELS = new Set(["yellow", "orange", "red"]);

function getHomeLabAlertLevel() {
  const search = globalThis.window?.location?.search || "";
  const level = new URLSearchParams(search).get("alertTone");

  return HOME_LAB_ALERT_LEVELS.has(level) ? level : "orange";
}

const HOME_STATIC_DATA = {
  location: {
    city: "Udine",
    region: "Friuli Venezia Giulia",
  },
  weather: {
    status: "cache",
    city: "Udine",
    current: {
      condition: "Sereno",
      weathercode: 0,
      isDay: true,
      temperature: 23.4,
      feelsLike: 24.1,
      windSpeed: 12,
      humidity: 62,
      precipitationAmount: 0,
      visibilityKm: 22,
      pressure: 1014,
      cloudCover: 18,
      semantic: {
        key: "clear",
        family: "clear",
        labelKey: "conditionSun",
        meteoconType: "Sun",
        overlays: {},
      },
      type: "Sun",
      code: 0,
    },
    forecast: {
      daily: [],
    },
    // The Lab can preview every official level through ?alertTone=... without
    // affecting runtime data. Orange remains the default reference state.
    officialAlerts: [{ id: "pc-fvg", level: getHomeLabAlertLevel() }],
    osmerAudit: null,
    updatedAt: "2026-06-21T10:00:00.000Z",
    updatedAgoMinutes: 5,
    fromCache: true,
  },
  hourly: {
    sourceLabel: "Evoluzione Open-Meteo",
    items: [
      {
        ariaLabel: "12:00, 23 gradi, precipitazioni 0%",
        icon: { type: "Sun" },
        precipitationProbability: 0,
        temperature: "23°",
        time: "12:00",
      },
      {
        ariaLabel: "14:00, 25 gradi, precipitazioni 0%",
        icon: { type: "Sun" },
        precipitationProbability: 0,
        temperature: "25°",
        time: "14:00",
      },
      {
        ariaLabel: "16:00, 24 gradi, precipitazioni 10%",
        icon: { type: "PartlyCloudy" },
        precipitationProbability: 10,
        temperature: "24°",
        time: "16:00",
      },
      {
        ariaLabel: "18:00, 22 gradi, precipitazioni 20%",
        icon: { type: "PartlyCloudy" },
        precipitationProbability: 20,
        temperature: "22°",
        time: "18:00",
      },
      {
        ariaLabel: "20:00, 19 gradi, precipitazioni 25%",
        icon: { type: "Cloud" },
        precipitationProbability: 25,
        temperature: "19°",
        time: "20:00",
      },
      {
        ariaLabel: "22:00, 18 gradi, precipitazioni 20%",
        icon: { type: "OvercastNight" },
        precipitationProbability: 20,
        temperature: "18°",
        time: "22:00",
      },
    ],
  },
  events: {
    status: "cache",
    items: [
      {
        id: "event-udine-1",
        title: "Notte di musica in centro",
        city: "Udine",
        date_label: "Oggi",
      },
      {
        id: "event-udine-2",
        title: "Mercato agricolo locale",
        city: "Cividale",
        date_label: "Domani",
      },
      {
        id: "event-udine-3",
        title: "Passeggiata lungo il Natisone",
        city: "San Pietro al Natisone",
        date_label: "Weekend",
      },
    ],
    total: 12,
    loadedLimit: 100,
    fromCache: true,
  },
  bulletin: {
    sourceLabel: "OSMER ARPA FVG",
    dateLabel: "domenica 28 giugno",
    headline: "Stabile, con nubi alte sui monti",
    body: "La giornata resta in prevalenza soleggiata in pianura. Sui rilievi passano nubi alte, con vento debole e visibilita buona.",
  },
  almanac: {
    eyebrow: "Oggi in Friuli",
    dateLabel: "domenica 28 giugno",
    cardTitle: "L'almanacco del giorno",
    headline: "Santo, luna e tradizione",
    saintLabel: "Sant'Ireneo, vescovo, martire e dottore della Chiesa.",
    body: "Sant'Ireneo, vescovo, martire e dottore della Chiesa.",
    moonLabel: "Luna",
  },
};

function cloneStaticData(data) {
  return JSON.parse(JSON.stringify(data));
}

export function getHomeStaticData(language = "it") {
  if (language !== "fur") return cloneStaticData(HOME_STATIC_DATA);

  return cloneStaticData({
    ...HOME_STATIC_DATA,
    bulletin: {
      sourceLabel: "OSMER ARPA FVG",
      dateLabel: "domenie 28 Jugn",
      headline: "Stabil, cun nuls alts sui monts",
      body: "La zornade e reste soreliose in planure. Sui rilieus a passin nuls alts, cun vint debil e buine visibilitat.",
    },
    almanac: {
      eyebrow: "Vu\u00ea in Friul",
      dateLabel: "domenie 28 Jugn",
      cardTitle: "L'almanac dal d\u00ec",
      headline: "Sant, lune e tradizion",
      saintLabel: "Sant Ireneu, vescul, martar e dot\u00f4r de Glesie.",
      body: "Sant Ireneu, vescul, martar e dot\u00f4r de Glesie.",
      moonLabel: "Lune",
    },
  });
}

const HOME_STATIC_VIEW_MODELS = {
  it: buildHomeViewModel(getHomeStaticData("it"), {
    language: "it",
    maxEvents: 3,
  }),
  fur: buildHomeViewModel(getHomeStaticData("fur"), {
    language: "fur",
    maxEvents: 3,
  }),
};

export function getHomeStaticViewModel(language = "it") {
  return HOME_STATIC_VIEW_MODELS[language === "fur" ? "fur" : "it"];
}

export const HOME_STATIC_VIEW_MODEL = getHomeStaticViewModel("it");
