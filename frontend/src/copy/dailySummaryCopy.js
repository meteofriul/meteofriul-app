export const DAILY_SUMMARY_COPY = {
  it: {
    bulletinCtaLabel: "Apri bollettino OSMER",
    currentSummaryFallback: "Sintesi meteo in aggiornamento.",
    locationLabel: "Località",
    regionalBulletinAvailable: "Bollettino regionale OSMER disponibile.",
    officialTextPendingLabel: "",
  },
  fur: {
    bulletinCtaLabel: "Vierç boletin OSMER",
    currentSummaryFallback: "Sintesi meteo in inzornament.",
    locationLabel: "Localitât",
    regionalBulletinAvailable: "Boletin regjonâl OSMER disponibil.",
    officialTextPendingLabel: "Test uficiâl in talian - FUR in revision",
  },
};

export function getDailySummaryCopy(language) {
  return DAILY_SUMMARY_COPY[language === "fur" ? "fur" : "it"];
}
