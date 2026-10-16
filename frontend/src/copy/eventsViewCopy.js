export const EVENTS_VIEW_COPY = {
  it: {
    viewTitle: "Eventi",
    locationLabel: "Località",
    change: "Cambia",
    languageLabel: "Cambia lingua IT/FUR",
    externalLinkLabel: "apri link esterno",
    previewOpenLabel: "apri dettagli evento",
    previewCloseLabel: "Chiudi dettagli evento",
    previewDialogLabel: "Dettagli evento",
    previewDescriptionLoading: "Caricamento descrizione…",
    previewDescriptionFallback: "Descrizione non disponibile per questo evento.",
    previewSourceLabel: "Fonte",
    previewPageLabel: "Pagina dell'evento",
    previewProgrammeLabel: "Programma",
    previewProgrammeCountLabel: "appuntamenti",
    previewProgrammeScrollLabel: "Scorri gli appuntamenti del programma",
    previewMainFestivalDatesLabel: "Festival",
    previewDirectionsLabel: "Indicazioni",
    eventCountLabel: "eventi",
    multiLocationSuffix: "e altre localit\u00e0",
    dateFallbackToday: "Oggi",
    loadingTitle: "Ricerca eventi in corso",
    loadingBody: "Resto in attesa delle fonti verificate.",
    emptyTodayTitle: "Nessun evento verificato in zona",
    emptyTitle: "Nessun evento verificato",
    emptyBody: "Mostriamo solo eventi con fonte e data affidabili.",
    fvgOnlyTitle: "Eventi disponibili solo in FVG",
    fvgOnlyBody: "La località attiva è {location}. Gli eventi coprono soltanto il Friuli Venezia Giulia e non vengono associati a località fuori regione.",
  },
  fur: {
    viewTitle: "Evenis",
    locationLabel: "Localitât",
    change: "Cambie",
    languageLabel: "Cjambie lenghe IT/FUR",
    externalLinkLabel: "vierç leam esterni",
    previewOpenLabel: "vierç i detais dal eveniment",
    previewCloseLabel: "Siere i detais dal eveniment",
    previewDialogLabel: "Detais dal eveniment",
    previewDescriptionLoading: "Daûr a cjariâ la descrizion…",
    previewDescriptionFallback: "Nissune descrizion disponibile par chest eveniment.",
    previewSourceLabel: "Font",
    previewPageLabel: "Pagjine dal eveniment",
    previewProgrammeLabel: "Program",
    previewProgrammeCountLabel: "apontaments",
    previewProgrammeScrollLabel: "Scor i apontaments dal program",
    previewMainFestivalDatesLabel: "Festival",
    previewDirectionsLabel: "Indicazions",
    eventCountLabel: "evenis",
    multiLocationSuffix: "e altris localit\u00e2ts",
    dateFallbackToday: "Vuê",
    loadingTitle: "O sin daûr a cirî evenis",
    loadingBody: "O spieti lis fonts verificadis.",
    emptyTodayTitle: "Nissun eveni verificât in zone",
    emptyTitle: "Nissun eveni verificât",
    emptyBody: "Mostrin dome evenis cun font e date afidabils.",
    fvgOnlyTitle: "Evenis disponibii dome in FVG",
    fvgOnlyBody: "La localitât ative e je {location}. I evenis a cuvierzin dome il Friûl Vignesie Julie e no vegnin associâts a localitâts fûr regjon.",
  },
};

export const EVENTS_TIME_TABS = [
  { id: "today" },
  { id: "weekend" },
  { id: "next" },
];

export const EVENTS_TIME_TAB_IDS = EVENTS_TIME_TABS.map(tab => tab.id);

const EVENTS_TIME_TAB_LABELS = {
  it: {
    today: "Oggi",
    weekend: "Weekend",
    next: "Prossimi giorni",
  },
  fur: {
    today: "Vu\u00ea",
    weekend: "Fin setemane",
    next: "Prossims d\u00ees",
  },
};

const EVENTS_TIME_TAB_SHORT_LABELS = {
  it: {
    today: "Oggi",
    weekend: "Weekend",
    next: "Prossimi",
  },
  fur: {
    today: "Vu\u00ea",
    weekend: "Fin set.",
    next: "Prossims",
  },
};

export const EVENTS_CATEGORY_FILTERS = [
  { id: "all" },
  { id: "sagra" },
  { id: "food_wine" },
  { id: "mercato" },
  { id: "cultura" },
  { id: "convegni" },
  { id: "musica" },
  { id: "sport" },
  { id: "natura" },
  { id: "famiglia" },
  { id: "other" },
];

const EVENTS_CATEGORY_FILTER_LABELS = {
  it: {
    all: "Tutti",
    sagra: "Feste e sagre",
    food_wine: "Gusto",
    mercato: "Mercati",
    cultura: "Cultura",
    convegni: "Convegni",
    musica: "Musica",
    sport: "Sport",
    natura: "Natura",
    famiglia: "Famiglia",
    other: "Altro",
  },
  fur: {
    all: "Ducj",
    sagra: "Sagris",
    food_wine: "Gust",
    mercato: "Marcjats",
    cultura: "Culture",
    convegni: "Convegnis",
    musica: "Musiche",
    sport: "Sport",
    natura: "Nature",
    famiglia: "Famee",
    other: "Altri",
  },
};

const EVENTS_DATE_CHIP_MONTHS = {
  it: ["GEN", "FEB", "MAR", "APR", "MAG", "GIU", "LUG", "AGO", "SET", "OTT", "NOV", "DIC"],
  fur: ["ZEN", "FEV", "MAR", "AVR", "MAI", "JUG", "LUI", "AVO", "SET", "OTU", "NOV", "DIC"],
};

const EVENTS_BADGE_CATEGORY_LABELS = {
  it: {
    sagra: "Sagra / festa locale",
    food_wine: "Gusto",
    mercato: "Mercato",
    cultura: "Cultura",
    convegni: "Convegni",
    musica: "Musica",
    sport: "Sport",
    natura: "Natura",
    famiglia: "Famiglia",
    other: "Evento",
  },
  fur: {
    sagra: "Sagris / fiestis loc\u00e2ls",
    food_wine: "Gust",
    mercato: "Marcj\u00e2t",
    cultura: "Culture",
    convegni: "Convegnis",
    musica: "Musiche",
    sport: "Sport",
    natura: "Nature",
    famiglia: "Famee",
    other: "Eveni",
  },
};

function getEventsLanguageKey(language) {
  return language === "fur" ? "fur" : "it";
}

export function getEventsViewCopy(language) {
  return EVENTS_VIEW_COPY[language] || EVENTS_VIEW_COPY.it;
}

export function getEventsDateFallbackLabel(language) {
  return getEventsViewCopy(language).dateFallbackToday;
}

export function getEventsTimeTabLabel(tabId, language, options = {}) {
  const languageKey = getEventsLanguageKey(language);
  const labels = options.short ? EVENTS_TIME_TAB_SHORT_LABELS : EVENTS_TIME_TAB_LABELS;
  return labels[languageKey]?.[tabId] || labels.it[tabId] || tabId;
}

export function getEventsCategoryFilterLabel(categoryId, language) {
  const languageKey = getEventsLanguageKey(language);
  return EVENTS_CATEGORY_FILTER_LABELS[languageKey]?.[categoryId] || EVENTS_CATEGORY_FILTER_LABELS.it[categoryId] || categoryId;
}

export function getEventsDateChipMonthLabel(monthIndex, language) {
  const languageKey = getEventsLanguageKey(language);
  return EVENTS_DATE_CHIP_MONTHS[languageKey]?.[monthIndex] || EVENTS_DATE_CHIP_MONTHS.it[monthIndex] || "";
}

export function getEventsBadgeCategoryLabel(categoryId, language, options = {}) {
  const languageKey = getEventsLanguageKey(language);
  const label = EVENTS_BADGE_CATEGORY_LABELS[languageKey]?.[categoryId] || EVENTS_BADGE_CATEGORY_LABELS.it[categoryId];
  if (label || options.fallback === false) return label;
  return EVENTS_BADGE_CATEGORY_LABELS[languageKey]?.other || EVENTS_BADGE_CATEGORY_LABELS.it.other;
}
