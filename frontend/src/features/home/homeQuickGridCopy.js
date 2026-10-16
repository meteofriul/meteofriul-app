const COPY = {
  it: {
    sectionLabel: "In breve",
    forecastFallback: "Evoluzione oraria",
    forecastAction: "Apri le previsioni",
    forecastUnavailable: "Previsioni in aggiornamento",
    eventsFallback: "Eventi vicino a te",
    eventsAction: "Apri gli eventi",
    eventsCountCaption: "eventi in programma",
    eventsFeaturedHeading: "Evento in evidenza",
    territoryHeading: "Dal territorio",
    territoryAction: "Apri in Scopri",
    territoryRead: "Leggi",
    territoryInvitation: "Scopri luoghi, storie e curiosità del Friuli.",
    almanacFallback: "Almanacco",
    almanacAction: "Apri l'almanacco",
    almanacSaintLabel: "Santo del giorno",
  },
  fur: {
    sectionLabel: "In curt",
    forecastFallback: "Evoluzion orarie",
    forecastAction: "Vierç lis previsions",
    forecastUnavailable: "Previsions in inzornament",
    eventsFallback: "Evenis dongje di te",
    eventsAction: "Vierç i evenis",
    eventsCountCaption: "evenis in program",
    eventsFeaturedHeading: "Event in evidence",
    territoryHeading: "Dal teritori",
    territoryAction: "Vierç in Scuvierç",
    territoryRead: "Lei",
    territoryInvitation: "Scuvierç lûcs, storiis e curiositâts dal Friûl.",
    almanacFallback: "Almanac",
    almanacAction: "Vierç l'almanac",
    almanacSaintLabel: "Sant dal dì",
  },
};

export function getHomeQuickGridCopy(language = "it") {
  return COPY[language === "fur" ? "fur" : "it"];
}
