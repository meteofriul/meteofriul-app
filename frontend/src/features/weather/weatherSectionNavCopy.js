const WEATHER_SECTION_COPY = {
  it: {
    ariaLabel: "Sezioni meteo",
    changeLocationLabel: "Cambia",
    items: {
      weather: "Previsioni",
      bulletin: "Bollettino",
      live: "Tempo reale",
    },
  },
  fur: {
    ariaLabel: "Sezions meteo",
    changeLocationLabel: "Cambie",
    items: {
      weather: "Previsions",
      bulletin: "Boletin",
      live: "Timp reâl",
    },
  },
};

export const WEATHER_SECTION_IDS = ["weather", "bulletin", "live"];

export function getWeatherSectionNavCopy(language) {
  return WEATHER_SECTION_COPY[language === "fur" ? "fur" : "it"];
}
