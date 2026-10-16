const COPY = {
  it: {
    body: "Meteo Friûl raccoglie dati sulla posizione per aggiornare il Comune degli Avvisi meteo locali e preparare il meteo della località anche quando l’app è chiusa o non è in uso. Le coordinate precise servono a riconoscere la località, ma non vengono conservate nel profilo sul server né usate per pubblicità. La rilevazione è periodica, non un tracciamento continuo.",
    cancel: "Non ora",
    continueSettings: "Continua nelle impostazioni",
    continueStartup: "Continua",
    eyebrow: "Posizione in background",
    title: "Posizione per gli Avvisi meteo",
  },
  fur: {
    body: "Meteo Friûl al dopre i dâts de tô posizion par inzornâ il Comun dai Avîs meteo locâi e preparâ il meteo de localitât ancje cuant che la app e je sierade o no je in ûs. Lis coordenadis precisês a coventin par ricognossi la localitât, ma no vegnin conservadis tal profîl sul server e no son dopradis pe publicitât. La rilevazion e je periodiche, no un control continui.",
    cancel: "No cumò",
    continueSettings: "Continue tes impostazions",
    continueStartup: "Continue",
    eyebrow: "Posizion in sotfont",
    title: "Posizion pai Avîs meteo",
  },
};

export function getBackgroundLocationDisclosureCopy(
  language = "it",
  { context = "settings" } = {},
) {
  const copy = COPY[language] || COPY.it;

  return {
    ...copy,
    continue: context === "startup" ? copy.continueStartup : copy.continueSettings,
  };
}
