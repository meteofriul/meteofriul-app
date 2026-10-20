import { describe, expect, it } from "vitest";
import { getLiveViewCopy } from "./liveViewCopy";

describe("liveViewCopy", () => {
  const segnala11Keys = [
    "communityActiveSummary",
    "communityActiveSummaryOne",
    "communityActiveSummaryMany",
    "communityRecentSummary",
    "communityRecentSummaryOne",
    "communityRecentSummaryMany",
    "communityUpdatedNow",
    "communityUpdatedMinutesAgo",
    "communityUpdatedUnknown",
    "reportObserveCta",
    "reportLocationRadius",
    "reportTermsRead",
    "communityNearbyTitle",
    "confirmationRecentOne",
    "confirmationRecentMany",
    "denialCountOne",
    "denialCountMany",
    "denialDone",
    "denialExplanation",
    "denialMapRemoved",
    "confirmationAction",
    "confirmationActions",
    "confirmationEndedAction",
    "confirmationDone",
    "confirmationDoneFeedback",
    "confirmationTermsPrompt",
    "confirmationTermsAccept",
    "confirmationConsentSubmit",
    "ownReportLabel",
    "ownReportExpiresIn",
    "reportUpdate",
    "reportUpdateDone",
    "reportUpdateRetryHint",
    "reportUpdateLocationHint",
    "reportUpdateLocationError",
    "reportUpdatePendingTitle",
    "reportUpdatePendingBody",
    "reportUpdatePendingAction",
    "reportUpdateRejected",
    "reportUpdateExpiredTitle",
    "reportUpdateExpiredBody",
    "reportUpdateExpiredClose",
    "reportUpdateExpiredNew",
    "reportSuccessTitle",
    "reportSuccessBody",
    "reportSuccessReceipt",
    "reportSuccessIdentityLabel",
    "reportSuccessConfirmation",
    "reportSuccessMap",
    "communityDailyAlias",
    "communityContributionToday",
    "communityMatchOne",
    "communityMatchMany",
    "communityMatchOwn",
    "communityMatchVoted",
    "communityStateNew",
    "communityStateAging",
    "communityStateMixed",
    "communityLoadingTitle",
    "communityLoadingBody",
    "communityErrorTitle",
    "communityErrorBody",
    "communityStaleTitle",
    "communityStaleBody",
    "reportManageContent",
    "reportHideSourceBody",
    "reportHideSources",
    "reportHideSourcesBody",
    "reportHideSourcesDone",
  ];

  it("returns IT copy for the Territorio tab", () => {
    const copy = getLiveViewCopy("it");

    expect(copy.viewTitle).toBe("Territorio");
    expect(copy.liveMapTitle).toBe("Segnalazioni");
    expect(copy.viewSubtitle).toBe("Webcam, mappa e segnalazioni");
    expect(copy.webcamGroupNearby).toBe("Vicino");
    expect(copy.webcamAreaLabel).toBe("Scegli una zona");
    expect(copy.webcamDistanceOrigin).toBe("Distanze da {place}");
    expect(copy.webcamOpenSourceNewTab).toContain("nuova scheda");
    expect(copy.webcamUpdated).toBe("Fonte esterna");
    expect(copy.webcamPendingTitle).not.toContain("OSMER");
    expect(copy.webcamOpenExternal).toBe("Guarda la webcam");
    expect(copy.webcamOpenExternalCompact).toBe("Guarda");
    expect(copy.webcamOpenExternalNewTab).toContain("nuova scheda");
    expect(copy.webcamLiveExternal).toBe("Vai alla webcam originale");
    expect(copy.webcamStaticImage).toBe("Foto statica del territorio");
    expect(copy.webcamTemporaryUnavailable).toBe("Webcam in pausa");
    expect(copy.webcamAutomaticRetry).toContain("automaticamente");
    expect(copy.webcamNext).toBe("Guarda la prossima");
    expect(copy.webcamAreaUnavailableBody).toContain("soltanto in Friuli Venezia Giulia");
    expect(copy.reportTypes.rain).toBe("Pioggia");
    expect(Object.keys(copy.reportFlagReasons)).toEqual(["inaccurate", "duplicate", "misuse"]);
    expect(copy.reportFlagAction).toBe("Segnala contenuto");
    expect(copy.reportHideSource).toBe("Nascondi questa fonte");
    expect(copy.reportAnonymousSource).toBe("Fonte anonima · {alias}");
    expect(copy.reportTermsBody).toContain("circa 60 minuti");
    expect(copy.reportTermsBody).toContain("anonime");
    expect(copy.reportTermsBody).toContain("indicare che il fenomeno è terminato");
    expect(copy.reportPreciseLocationNotice).toBe(
      "Le coordinate precise vengono usate temporaneamente per verificare il Comune; sulla mappa compare solo una posizione approssimata.",
    );
    expect(copy.reportGpsDenied).toContain("browser o del dispositivo");
    expect(copy.reportGpsServicesDisabled).toContain("Servizi di posizione disattivati");
    expect(copy.reportGpsApproximate).toContain("posizione precisa");
    expect(copy.reportLocationRadius).toContain("{distance} km");
    expect(copy.liveMapInfoBody).toContain("non costituiscono un bollettino");
    expect(copy.languageLabel).toBe("Cambia lingua IT/FUR");
  });

  it("returns FUR copy for the Teritori tab", () => {
    const copy = getLiveViewCopy("fur");

    expect(copy.viewTitle).toBe("Teritori");
    expect(copy.liveMapTitle).toBe("Segnalazions");
    expect(copy.viewSubtitle).toBe("Webcam, mape e segnalazions");
    expect(copy.reportGpsTimeout).toContain("Il GPS nol è rivât");
    expect(copy.webcamGroupNearby).toBe("Dongje");
    expect(copy.webcamAreaLabel).toBe("Sielç une zone");
    expect(copy.webcamDistanceOrigin).toBe("Distancis di {place}");
    expect(copy.webcamUpdated).toBe("Font esterne");
    expect(copy.webcamOpenExternal).toBe("Cjale la webcam");
    expect(copy.webcamOpenExternalCompact).toBe("Cjale");
    expect(copy.webcamOpenExternalNewTab).toContain("gnove schede");
    expect(copy.webcamLiveExternal).toBe("Va ae webcam origjinâl");
    expect(copy.webcamTemporaryUnavailable).toBe("Webcam in pause");
    expect(copy.webcamAutomaticRetry).toContain("in automatic");
    expect(copy.webcamNext).toBe("Cjale chê sucessive");
    expect(copy.webcamAreaUnavailableBody).toContain("dome in Friûl Vignesie Julie");
    expect(copy.reportTypes.rain).toBe("Pluie");
    expect(Object.keys(copy.reportFlagReasons)).toEqual(["inaccurate", "duplicate", "misuse"]);
    expect(copy.reportFlagAction).toBe("Segnale il contignût");
    expect(copy.reportAnonymousSource).toBe("Font anonime · {alias}");
    expect(copy.reportTermsBody).toContain("cirche 60 minûts");
    expect(copy.reportTermsBody).toContain("anonimis");
    expect(copy.reportTermsBody).toContain("indicâ che il fenomen nol è plui");
    expect(copy.reportPreciseLocationNotice).toContain("coordenadis precisis");
    expect(copy.reportPreciseLocationNotice).toContain("posizion aproximative");
    expect(copy.reportGpsDenied).toContain("browser o dal dispositîf");
    expect(copy.reportGpsServicesDisabled).toContain("Servizis di posizion distudâts");
    expect(copy.reportGpsApproximate).toContain("posizion precise");
    expect(copy.reportLocationRadius).toContain("{distance} km");
    expect(copy.languageLabel).toBe("Cjambie lenghe IT/FUR");
  });

  it("exposes the compact Segnala 1.1 contract in IT and FUR", () => {
    const italian = getLiveViewCopy("it");
    const friulian = getLiveViewCopy("fur");

    segnala11Keys.forEach((key) => {
      expect(italian[key], `missing IT copy: ${key}`).toBeTruthy();
      expect(friulian[key], `missing FUR copy: ${key}`).toBeTruthy();
    });

    expect(italian.reportObserveCta).toBe("Segnala cosa vedi");
    expect(italian.communityNearbyTitle).toBe("Vicino a te");
    expect(italian.communityActiveSummary).toContain("{count}");
    expect(italian.communityActiveSummaryOne).toBe("1 osservazione recente");
    expect(italian.communityActiveSummaryMany).toBe("{count} osservazioni recenti");
    expect(italian.communityRecentSummaryOne).toBe("1 segnalazione recente");
    expect(italian.communityRecentSummaryMany).toBe("{count} segnalazioni recenti");
    expect(italian.communityUpdatedMinutesAgo).toContain("{minutes}");
    expect(italian.confirmationRecentMany).toBe("{count} conferme recenti");
    expect(italian.confirmationAction).toBe("Confermo");
    expect(italian.confirmationActions.rain)
      .toEqual({ yes: "Confermo", no: "Non c’è più" });
    expect(Object.keys(italian.confirmationActions)).toEqual([
      "rain",
      "storm",
      "snow",
      "hail",
      "fog",
      "wind",
      "ice",
      "quiet",
      "unknown",
    ]);
    Object.values(italian.confirmationActions).forEach((actions) => {
      expect(actions.yes).toBeTruthy();
      expect(actions.no).toBeTruthy();
    });
    expect(italian.confirmationEndedAction).toBe("Non c’è più");
    expect(italian.confirmationDone).toBe("Hai confermato");
    expect(italian.denialCountOne).toBe("1 voto: non c’è più");
    expect(italian.denialCountMany).toBe("{count} voti: non c’è più");
    expect(italian.denialDone).toBe("Hai indicato che non c’è più");
    expect(italian.denialExplanation)
      .toBe("La nascondi dalla tua mappa. Con 3 voti “Non c’è più” viene rimossa dalla mappa per tutti.");
    expect(italian.denialMapRemoved).toBe("Rimossa dalla mappa");
    expect(italian.confirmationConsentSubmit).toBe("Accetta e invia");
    expect(italian.ownReportExpiresIn).toContain("{minutes}");
    expect(italian.communityDailyAlias).toBe("Sentinella Meteo · {alias}");
    expect(italian.communityContributionToday).toContain("{count}");
    expect(italian.communityMatchMany).toContain("{phenomenon}");
    expect(italian.reportSuccessReceipt).toBe("Grazie per la segnalazione!");
    expect(italian.reportSuccessBody)
      .toBe("Il tuo contributo aiuta la community a rimanere aggiornata.");
    expect(italian.reportSuccessIdentityLabel).toBe("Inviata da:");
    expect(italian.reportSuccessMap).toBe("Vedi sulla mappa");
    expect(italian.reportUpdateDone).toBe("Aggiornato");
    expect(italian.reportUpdateRetryHint).toBe("Esito non confermato");
    expect(italian.reportUpdateLocationHint).toBe("GPS da verificare");
    expect(italian.reportUpdateLocationError)
      .toBe("Non è stato possibile verificare la posizione. Controlla il GPS e riprova.");
    expect(italian.reportUpdateError)
      .toBe("Non abbiamo ricevuto la conferma dell’aggiornamento. Verifica lo stato prima di riprovare.");
    expect(italian.reportUpdatePendingAction).toBe("Verifica aggiornamento");
    expect(italian.reportUpdateExpiredBody).toContain("invia una nuova osservazione");
    expect(italian.communityStateNew).toBe("Nuova");
    expect(italian.communityStateAging).toBe("Da aggiornare");
    expect(italian.communityStateMixed).toBe("Discordanti");
    expect(italian.verifiedBy).toBe("Conferme recenti");
    expect(italian.verifiedBySuffix).toBe("conferme");
    expect(italian.reportManageContent).toBe("Gestisci contenuto");
    expect(italian.reportHideSourceBody).toContain("solo su questo dispositivo");
    expect(italian.reportHideSourceBody).toContain("rinnovo giornaliero");
    expect(italian.reportHideSources).toBe("Nascondi queste fonti");
    expect(italian.reportHideSourcesBody).toContain("solo su questo dispositivo");
    expect(italian.liveMapEmptyTitle).toBe("Tutto tranquillo?");
    expect(italian.liveMapEmptyBody).toBe("Se sei in zona, raccontaci cosa vedi.");

    expect(friulian.reportObserveCta).toBe("Segnale ce che tu viodis");
    expect(friulian.communityNearbyTitle).toBe("Dongje di te");
    expect(friulian.communityActiveSummary).toContain("{count}");
    expect(friulian.communityActiveSummaryOne).toBe("1 osservazion resinte");
    expect(friulian.communityActiveSummaryMany).toBe("{count} osservazions resintis");
    expect(friulian.communityRecentSummaryOne).toBe("1 segnalazion resinte");
    expect(friulian.communityRecentSummaryMany).toBe("{count} segnalazions resintis");
    expect(friulian.communityUpdatedMinutesAgo).toContain("{minutes}");
    expect(friulian.confirmationRecentMany).toContain("{count}");
    expect(friulian.confirmationAction).toBe("O confermi");
    expect(friulian.confirmationActions.rain)
      .toEqual({ yes: "O confermi", no: "Nol è plui" });
    expect(friulian.confirmationActions.unknown)
      .toEqual({ yes: "O confermi", no: "Nol è plui" });
    expect(friulian.confirmationEndedAction).toBe("Nol è plui");
    expect(friulian.confirmationDone).toBe("Tu âs confermât");
    expect(friulian.denialCountOne).toBe("1 vôt: nol è plui");
    expect(friulian.denialCountMany).toBe("{count} vôts: nol è plui");
    expect(friulian.denialDone).toBe("Tu âs indicât che nol è plui");
    expect(friulian.denialExplanation)
      .toBe("Tu le platis de tô mape. Cun 3 vôts “Nol è plui” e ven gjavade de mape par ducj.");
    expect(friulian.denialMapRemoved).toBe("Gjavad de mape");
    expect(friulian.confirmationConsentSubmit).toBe("Acete e invie");
    expect(friulian.ownReportExpiresIn).toContain("{minutes}");
    expect(friulian.communityDailyAlias).toBe("Sentinele Meteo · {alias}");
    expect(friulian.communityContributionToday).toContain("{count}");
    expect(friulian.communityMatchMany).toContain("{phenomenon}");
    expect(friulian.reportSuccessReceipt).toBe("Graciis pe segnalazion!");
    expect(friulian.reportSuccessBody)
      .toBe("Il to contribût al jude la comunitât a restâ inzornade.");
    expect(friulian.reportSuccessIdentityLabel).toBe("Inviade di:");
    expect(friulian.reportSuccessMap).toBe("Viôt su la mape");
    expect(friulian.reportUpdateDone).toBe("Inzornade");
    expect(friulian.reportUpdateRetryHint).toBe("Esit no confermât");
    expect(friulian.reportUpdateLocationHint).toBe("GPS di verificâ");
    expect(friulian.reportUpdateLocationError)
      .toBe("No si à podût verificâ la posizion. Controle il GPS e torne a provâ.");
    expect(friulian.reportUpdateError)
      .toBe("No vin ricevût la conferme dal inzornament. Verifiche il stât prime di tornâ a provâ.");
    expect(friulian.reportUpdatePendingAction).toBe("Verifiche inzornament");
    expect(friulian.verifiedBy).toBe("Confermis resintis");
    expect(friulian.verifiedBySuffix).toBe("confermis");
    expect(friulian.reportManageContent).toBe("Gjestion dal contignût");
    expect(friulian.reportHideSourceBody).toContain("dome su chest dispositîf");
    expect(friulian.reportHideSourceBody).toContain("rinovament zornalîr");
    expect(friulian.reportHideSources).toBe("Plate chestis fonts");
    expect(friulian.reportHideSourcesBody).toContain("dome su chest dispositîf");
    expect(friulian.liveMapEmptyTitle).toBe("Dut cuiet?");
    expect(friulian.liveMapEmptyBody).toContain("conte nus");
  });

  it("keeps the compact territory summary honest and bilingual", () => {
    const italian = getLiveViewCopy("it");
    const friulian = getLiveViewCopy("fur");
    const requiredKeys = [
      "territoryCommunityTitle",
      "territoryCommunityBody",
      "communityNoRecentTitle",
      "communityNoRecentBody",
      "communityNoRecentCaution",
      "territorySourcesTitle",
      "territorySourcesBody",
      "territorySourceAlerts",
      "territorySourceSnow",
      "territorySourceWaterways",
      "territorySourceRadar",
      "territorySourcesNote",
      "territoryRecentReportsTitle",
      "territoryWebcamsTitle",
      "territoryViewAll",
      "territoryShowLess",
    ];

    requiredKeys.forEach((key) => {
      expect(italian[key], `missing IT copy: ${key}`).toBeTruthy();
      expect(friulian[key], `missing FUR copy: ${key}`).toBeTruthy();
    });
    expect(italian.communityNoRecentTitle).toBe("Nessuna segnalazione recente");
    expect(italian.communityNoRecentBody).toContain("contributi recenti");
    expect(italian.communityNoRecentCaution).toContain("Non equivale all’assenza");
    expect(italian.communityNoRecentCaution).not.toContain("Nessun fenomeno grave");
    expect(italian.territorySourcesNote).toContain("servizi separati");
    expect(italian.territoryRecentReportsTitle).toBe("Segnalazioni recenti");
    expect(italian.territoryWebcamsTitle).toBe("Webcam sul territorio");
    expect(italian.territoryViewAll).toBe("Vedi tutte");
    expect(italian.territoryShowLess).toBe("Mostra meno");
    expect(friulian.territorySourcesNote).toContain("servizis separâts");
    expect(friulian.communityNoRecentBody).toContain("contribûts resints");
    expect(friulian.territoryRecentReportsTitle).toBe("Segnalazions resintis");
    expect(friulian.territoryWebcamsTitle).toBe("Webcam sul teritori");
    expect(friulian.territoryViewAll).toBe("Mostre dutis");
    expect(friulian.territoryShowLess).toBe("Mostre mancul");
  });

  it("falls back to IT copy for unknown languages", () => {
    const copy = getLiveViewCopy("unknown");

    expect(copy.viewTitle).toBe("Territorio");
    expect(copy.webcamDistanceOrigin).toBe("Distanze da {place}");
  });
});
