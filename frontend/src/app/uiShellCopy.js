import { getAppShellCopy } from "../copy/appShellCopy";

const BRAND_COPY = {
  first: "Meteo",
  second: "Fri\u00fbl",
};

const LAB_COPY = {
  it: {
    placeholders: {
      homeTitle: "Home",
      homeBody: "Dati meteo non collegati in questa tranche.",
      weatherTitle: "Meteo",
      bulletinTitle: "Bollettino",
      bulletinBody: "Adapter OSMER da importare dopo audit.",
      liveTitle: "Territorio",
      liveBody: "Webcam e segnalazioni restano da separare in servizi dedicati.",
      eventsTitle: "Eventi",
      eventsBody: "La vista resta senza fetch diretto.",
      discoverTitle: "Scopri",
      discoverBody: "Contenuti e ranking saranno importati con test.",
      almanacTitle: "Almanacco",
      almanacBody: "Santi, luna, proverbi e lavori della terra.",
      settingsTitle: "Impostazioni",
      settingsBody: "Preferenze e stato servizi principali.",
    },
  },
  fur: {
    placeholders: {
      homeTitle: "Cjase",
      homeBody: "D\u00e2ts meteo no coleg\u00e2ts in cheste tranche.",
      weatherTitle: "Timp",
      bulletinTitle: "Boletin",
      bulletinBody: "Adapter OSMER di impuart\u00e2 dopo audit.",
      liveTitle: "Teritori",
      liveBody: "Webcam e segnalazions di separ\u00e2 in servizis dedic\u00e2ts.",
      eventsTitle: "Evenis",
      eventsBody: "La viste e reste cence fetch diret.",
      discoverTitle: "Scuvier\u00e7",
      discoverBody: "Contign\u00fbts e ranking cun test dedic\u00e2ts.",
      almanacTitle: "Almanac",
      almanacBody: "Sants, lune, proverbis e lav\u00f4rs de tiere.",
      settingsTitle: "Impostazions",
      settingsBody: "Preferencis e st\u00e2t dai servizis princip\u00e2i.",
    },
  },
};

function getLanguageKey(language) {
  return language === "fur" ? "fur" : "it";
}

export function getUiShellCopy(language) {
  const languageKey = getLanguageKey(language);
  const shellCopy = getAppShellCopy(languageKey);
  const labCopy = LAB_COPY[languageKey];

  return {
    brand: BRAND_COPY,
    brandTagline: shellCopy.brandTagline,
    communityReportCountLabel: shellCopy.communityReportCountLabel,
    communityReportCountOneLabel: shellCopy.communityReportCountOneLabel,
    communityReportUnreadCountLabel: shellCopy.communityReportUnreadCountLabel,
    communityReportUnreadCountOneLabel: shellCopy.communityReportUnreadCountOneLabel,
    eventCountLabel: shellCopy.eventCountLabel,
    eventCountNextOneLabel: shellCopy.eventCountNextOneLabel,
    eventCountNextLabel: shellCopy.eventCountNextLabel,
    eventCountTodayOneLabel: shellCopy.eventCountTodayOneLabel,
    eventCountTodayLabel: shellCopy.eventCountTodayLabel,
    languageLabel: shellCopy.languageLabel,
    locationSearchLabel: shellCopy.locationSearchLabel,
    navigationLabel: shellCopy.navigationLabel,
    officialAlertNavigationLabel: shellCopy.officialAlertNavigationLabel,
    pullRefresh: languageKey === "fur"
      ? {
          pull: "Tire ju par inzorn\u00e2",
          loading: "Da\u00fbr a inzorn\u00e2...",
          success: "Inzorn\u00e2t",
          failed: "Controle la r\u00eat",
          release: "Mole par inzorn\u00e2",
        }
      : {
          pull: "Trascina per aggiornare",
          loading: "Aggiornamento...",
          success: "Aggiornato",
          failed: "Controlla la rete",
          release: "Rilascia per aggiornare",
        },
    settingsLabel: shellCopy.openSettingsLabel,
    tabs: {
      home: shellCopy.navLabels.home,
      weather: shellCopy.navLabels.weather,
      events: shellCopy.navLabels.events,
      discover: shellCopy.navLabels.discover,
    },
    placeholders: labCopy.placeholders,
  };
}
