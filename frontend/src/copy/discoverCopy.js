export const DISCOVER_SEASON_LABELS = {
  it: {
    inverno: "Inverno",
    primavera: "Primavera",
    estate: "Estate",
    autunno: "Autunno",
    all: "Tutto l'anno",
  },
  fur: {
    inverno: "Invier",
    primavera: "Primevere",
    estate: "Istât",
    autunno: "Autun",
    all: "Dut l'an",
  },
};

export const DISCOVER_TYPE_LABELS = {
  it: {
    agricoltura: "Raccolti",
    animale: "Segni naturali",
    archivio: "Archivio",
    arcobaleno: "Cielo",
    astronomia: "Luna e stelle",
    calendario: "Calendario",
    contesto: "Almanacco",
    credenza: "Credenza",
    grandine: "Grandine",
    meteo_popolare: "Meteo popolare",
    neve: "Neve",
    pianta: "Piante",
    rito: "Rito",
    storia_locale: "Storia locale",
    vita_quotidiana: "Vita quotidiana",
    vento: "Vento",
  },
  fur: {
    agricoltura: "Racolts",
    animale: "Segns naturâi",
    archivio: "Archivi",
    arcobaleno: "Cîl",
    astronomia: "Lune e stelis",
    calendario: "Calendari",
    contesto: "Almanac",
    credenza: "Crodince",
    grandine: "Tampiere",
    meteo_popolare: "Meteo popolâr",
    neve: "Nêf",
    pianta: "Plantis",
    rito: "Rît",
    storia_locale: "Storie locâl",
    vita_quotidiana: "Vite di ogni dì",
    vento: "Vint",
  },
};

export const DISCOVER_COPY = {
  it: {
    change: "Cambia",
    changeLocationLabel: "Cambia localita",
    languageLabel: "Cambia lingua IT/FUR",
    focus: "In evidenza",
    municipalitySectionTitle: "Comune del giorno",
    detectedMunicipalitySectionTitle: "Comune individuato",
    selectedMunicipalitySectionTitle: "Comune selezionato",
    municipalityKicker: "Storia e territorio",
    municipalityMilestonesTitle: "Tappe storiche",
    locationFocusTitle: "Dal territorio",
    exactMemoryTitle: "Memoria del giorno",
    localMemoryTitle: "Memoria del giorno",
    localMemoryFallbackTitle: "Storie del territorio",
    secondaryMemoryTitle: "Altre memorie",
    traditionalSayingsTitle: "Si diceva che...",
    relatedTitle: "In risonanza oggi",
    ritualsTitle: "Riti e credenze popolari",
    sourceLine: "Da Ostermann 1894, con selezione editoriale Meteo Friul.",
    editorialSourceLine: "Selezione editoriale Meteo Friul.",
    contextLabel: "Contesto della card",
    furPending: "Testo in italiano - FUR in revisione",
  },
  fur: {
    change: "Cambie",
    changeLocationLabel: "Cambie localitat",
    languageLabel: "Cjambie lenghe IT/FUR",
    focus: "In evidencie",
    municipalitySectionTitle: "Comun dal dì",
    detectedMunicipalitySectionTitle: "Comun individuât",
    selectedMunicipalitySectionTitle: "Comun selezionât",
    municipalityKicker: "Storie e teritori",
    municipalityMilestonesTitle: "Tapis storichis",
    locationFocusTitle: "Dal teritori",
    exactMemoryTitle: "Memorie dal dì",
    localMemoryTitle: "Memorie dal dì",
    localMemoryFallbackTitle: "Storiis dal teritori",
    secondaryMemoryTitle: "Altris memoriis",
    traditionalSayingsTitle: "Si diseve che...",
    relatedTitle: "In risonance vuê",
    ritualsTitle: "Rîts e crodincis popolârs",
    sourceLine: "Di Ostermann 1894, cun selezion editoriâl Meteo Friul.",
    editorialSourceLine: "Selezion editoriâl Meteo Friul.",
    contextLabel: "Contest de schede",
    furPending: "Test in talian - FUR in revision",
  },
};

export function getDiscoverCopy(language) {
  return DISCOVER_COPY[language] || DISCOVER_COPY.it;
}

export function getDiscoverSeasonLabel(season, language) {
  const labels = DISCOVER_SEASON_LABELS[language] || DISCOVER_SEASON_LABELS.it;
  return labels[season] || labels.all;
}

export function getDiscoverTypeLabel(type, language) {
  const labels = DISCOVER_TYPE_LABELS[language] || DISCOVER_TYPE_LABELS.it;
  return labels[type] || labels.contesto;
}

export function getDiscoverTitle(language) {
  return language === "fur" ? "Scuvierç" : "Scopri";
}
