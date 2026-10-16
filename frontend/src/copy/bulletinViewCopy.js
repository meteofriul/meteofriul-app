export const BULLETIN_VIEW_COPY = {
  it: {
    title: "Bollettino FVG",
    subtitle: "Previsioni ufficiali OSMER ARPA FVG",
    forecastTabsLabel: "Previsioni",
    officialTitle: "Bollettino ufficiale FVG",
    officialExternalLabel: "Apri il bollettino ufficiale ARPA FVG OSMER",
    metaLabel: "Metadati bollettino OSMER",
    issued: "Emesso",
    reliability: "Attendibilità",
    detailLabel: "Dettaglio bollettino",
    officialTextPendingNote: "Testo ufficiale in italiano - FUR in revisione",
    translationCredit: "",
    unpublished: "Bollettino non pubblicato",
    headingPrefix: "Previsioni per ",
    emissionTimeConnector: "alle",
    areaLabels: {
      general: "Generale giornata",
      mountain: "Montagna",
      highPlain: "Alta pianura",
      lowPlain: "Bassa pianura",
      coast: "Costa",
    },
  },
  fur: {
    title: "Boletin FVG",
    subtitle: "Previsions uficiâls OSMER ARPA FVG",
    forecastTabsLabel: "Previsions",
    officialTitle: "Boletin uficiâl FVG",
    officialExternalLabel: "Vierç il boletin uficiâl ARPA FVG OSMER",
    metaLabel: "Metadâts boletin OSMER",
    issued: "Metût fûr",
    reliability: "Afidabilitât",
    detailLabel: "Detai boletin",
    officialTextPendingNote: "Test uficiâl in talian - FUR in revision",
    unpublished: "Boletin no publicât",
    translationCredit: "Traduzione a cura di Meteo Friul",
    headingPrefix: "Previsions par ",
    emissionTimeConnector: "aes",
    areaLabels: {
      general: "Gjenerâl de zornade",
      mountain: "Mont",
      highPlain: "Alte planure",
      lowPlain: "Basse planure",
      coast: "Cueste",
    },
  },
};

export function getBulletinViewCopy(language) {
  return BULLETIN_VIEW_COPY[language === "fur" ? "fur" : "it"];
}

export function formatBulletinEmission(emission = "", language = "it") {
  const match = String(emission || "").match(/^(\d{2})-(\d{2})-(\d{4})\s+(\d{2}:\d{2})/);

  if (!match) return String(emission || "").trim();

  const [, day, month, year, time] = match;
  const copy = getBulletinViewCopy(language);
  return `${day}/${month}/${year} ${copy.emissionTimeConnector} ${time}`;
}

export function getBulletinHeading(dateLabel, isTrend, language = "it") {
  if (isTrend) return dateLabel;
  return `${getBulletinViewCopy(language).headingPrefix}${dateLabel}`;
}
