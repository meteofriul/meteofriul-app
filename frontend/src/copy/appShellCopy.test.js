import { describe, expect, it } from "vitest";

import { getAppShellCopy } from "./appShellCopy";

describe("appShellCopy", () => {
  it("returns IT copy for the app shell and Home teaser", () => {
    const copy = getAppShellCopy("it");

    expect(copy.brandTagline).toBe("Meteo, eventi e territorio");
    expect(copy.navigationLabel).toBe("Navigazione principale");
    expect(copy.brandLocalTagline).toBe("Meteo, events e teritori");
    expect(copy.openSettingsLabel).toBe("Apri impostazioni");
    expect(copy.locationSearchLabel).toBe("Cerca località");
    expect(copy.officialAlertNavigationLabel).toBe("Apri nel bollettino");
    expect(copy.homeEventsNoLocation).toBe("Scegli una località per vedere gli eventi vicini");
    expect(copy.loadingEvents).toBe("Caricamento eventi...");
    expect(copy.navLabels.weather).toBe("Meteo");
    expect(copy.navLabels.map).toBe("Bollettino");
    expect(copy.navLabels.live).toBe("Territorio");
    expect(copy.navLabels.discover).toBe("Scopri");
  });

  it("returns FUR copy for the app shell and Home teaser", () => {
    const copy = getAppShellCopy("fur");

    expect(copy.brandTagline).toBe("Meteo, events e teritori");
    expect(copy.navigationLabel).toBe("Navigazion principâl");
    expect(copy.brandLocalTagline).toBe("Meteo, events e teritori");
    expect(copy.openSettingsLabel).toBe("Vierç impostazions");
    expect(copy.locationSearchLabel).toBe("Cîr localitât");
    expect(copy.officialAlertNavigationLabel).toBe("Vierç tal boletin");
    expect(copy.officialTextPendingNote).toBe("Test uficiâl in talian - FUR in revision");
    expect(copy.loadingDiscover).toBe("Cjariament Scuvierç...");
    expect(copy.navLabels.weather).toBe("Timp");
    expect(copy.navLabels.map).toBe("Boletin");
    expect(copy.navLabels.live).toBe("Teritori");
    expect(copy.navLabels.discover).toBe("Scuvierç");
  });

  it("falls back to IT for unknown languages", () => {
    expect(getAppShellCopy("unknown").settingsTitle).toBe("Impostazioni");
  });
});
