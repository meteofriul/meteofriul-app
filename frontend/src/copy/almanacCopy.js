const ALMANAC_COPY = {
  it: {
    backHomeLabel: "Torna alla Home",
    languageLabel: "Cambia lingua IT/FUR",
    title: "L'Almanacco del giorno",
    cardTitle: "L'almanacco del giorno",
    intro: "Santi, luna, proverbi e lavori della terra per iniziare la giornata.",
    saintTitle: "Il santo del giorno",
    saintSource: "Santorale Meteo Friul",
    nameDayPrefix: "Onomastico",
    otherSaintsCollapseLabel: "Mostra meno",
    otherSaintsLabel: "Altri santi del giorno",
    traditionTitle: "Tradizione del giorno",
    moonTitle: "Luna",
    moonDetailsLabel: "Dettagli lunari",
    moonIllumination: "Illuminazione",
    moonCycle: "Ciclo lunare",
    proverbTitle: "Il proverbio del giorno",
    farmingTitle: "Consiglio della terra",
    discoverCta: "Continua in Scopri",
    openCta: "Apri almanacco",
    saintPendingReview: "Nome del santo in italiano - FUR in revisione",
    textPendingReview: "Testo in italiano - FUR in revisione",
    sourceFallback: "Selezione editoriale Meteo Friul.",
    sourceOstermann: "Da Ostermann 1894, con selezione editoriale Meteo Friul.",
    moonNextPrefix: "Prossima",
    lessThanOneDay: "meno di un giorno",
    dayUnit: "giorni",
    lunarAgeLabel: "Età lunare",
  },
  fur: {
    backHomeLabel: "Torne ae Cjase",
    languageLabel: "Cjambie lenghe IT/FUR",
    title: "L'Almanac dal dì",
    cardTitle: "L'Almanac dal dì",
    intro: "Sants, lune, proverbis e lavôrs de tiere par tacâ la zornade.",
    saintTitle: "Il Sant dal dì",
    saintSource: "Santorâl Meteo Friul",
    nameDayPrefix: "Nons dal dì",
    otherSaintsCollapseLabel: "Mostre mancul",
    otherSaintsLabel: "Altris sants dal dì",
    traditionTitle: "Tradizion dal dì",
    moonTitle: "Lune",
    moonDetailsLabel: "Detais de lune",
    moonIllumination: "Iluminazion",
    moonCycle: "Cicli de lune",
    proverbTitle: "Il proverbi dal dì",
    farmingTitle: "Il consei de tiere",
    discoverCta: "Va a Scuvierç",
    openCta: "Vierç Almanac",
    saintPendingReview: "Nom dal sant in talian - FUR in revision",
    textPendingReview: "Test in talian - FUR in revision",
    sourceFallback: "Selezion editoriâl Meteo Friul.",
    sourceOstermann: "Di Ostermann 1894, cun selezion editoriâl Meteo Friul.",
    moonNextPrefix: "Prossime",
    lessThanOneDay: "mancul di un dì",
    dayUnit: "dîs",
    lunarAgeLabel: "Etât lunâr",
  },
};

const MOON_NEXT_PHASES = {
  new: { age: 1.84566, it: "luna crescente", fur: "lune cressint" },
  waxing_crescent: { age: 5.53699, it: "primo quarto", fur: "prin cuart" },
  first_quarter: { age: 9.22831, it: "gibbosa crescente", fur: "lune cressint plene" },
  waxing_gibbous: { age: 12.91963, it: "luna piena", fur: "lune plene" },
  full: { age: 16.61096, it: "gibbosa calante", fur: "lune calant plene" },
  waning_gibbous: { age: 20.30228, it: "ultimo quarto", fur: "ultin cuart" },
  last_quarter: { age: 23.9936, it: "luna calante", fur: "lune calant" },
  waning_crescent: { age: 29.53059, it: "luna nuova", fur: "lune gnove" },
};

function getShortSource(source) {
  if (!source) return "";

  const pageMatch = source.match(/Ostermann\s+(?:1876|1894)[^,]*(?:,\s*p\.?\s*\d+)?/i);
  if (pageMatch) {
    return pageMatch[0]
      .replace(/\s+/g, " ")
      .replace(/Ostermann\s+1876/i, "Ostermann 1894")
      .replace(/p\.\s*/i, "p. ")
      .trim();
  }

  return source;
}
export function getAlmanacCopy(language) {
  return ALMANAC_COPY[language] || ALMANAC_COPY.it;
}

export function getAlmanacSourceLabel(source, language) {
  const shortSource = getShortSource(source);
  if (!shortSource) return "";

  const copy = getAlmanacCopy(language);
  return /Ostermann/i.test(shortSource) ? copy.sourceOstermann : copy.sourceFallback;
}

export function getAlmanacCulturalSourceLabel(source, language) {
  if (!source) return "";
  return getAlmanacCopy(language).sourceOstermann;
}

export function getAlmanacHiddenOtherSaintsLabel(count, language) {
  return language === "fur" ? `e altris ${count}` : `e altri ${count}`;
}

export function getAlmanacLunarAgeLabel(age, language) {
  const copy = getAlmanacCopy(language);
  return `${copy.lunarAgeLabel}: ${age.toFixed(1)} ${copy.dayUnit}`;
}

export function getMoonNextHint(moon, language) {
  const copy = getAlmanacCopy(language);
  const next = MOON_NEXT_PHASES[moon.id] || MOON_NEXT_PHASES.new;
  const days = Math.max(0.1, next.age - moon.age);
  const dayLabel = days < 1 ? copy.lessThanOneDay : `${days.toFixed(1)} ${copy.dayUnit}`;

  return `${copy.moonNextPrefix}: ${next[language] || next.it} · ${dayLabel}`;
}
