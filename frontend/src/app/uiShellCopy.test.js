import { describe, expect, it } from "vitest";

import { getUiShellCopy } from "./uiShellCopy";

describe("UI shell copy adapter", () => {
  it("provides the four primary Italian navigation labels", () => {
    const copy = getUiShellCopy("it");

    expect(copy.tabs).toEqual({
      home: "Home",
      weather: "Meteo",
      events: "Eventi",
      discover: "Scopri",
    });
    expect(copy.locationSearchLabel).toBe("Cerca localit\u00e0");
    expect(copy.navigationLabel).toBe("Navigazione principale");
    expect(copy.officialAlertNavigationLabel).toBe("Apri nel bollettino");
    expect(copy.eventCountLabel).toBe("eventi");
    expect(copy.placeholders.weatherTitle).toBe("Meteo");
    expect(copy.pullRefresh.loading).toBe("Aggiornamento...");
    expect(copy.pullRefresh.success).toBe("Aggiornato");
    expect(copy.pullRefresh).not.toHaveProperty("partial");
    expect(copy.pullRefresh.failed).toBe("Controlla la rete");
    expect(copy.pullRefresh).not.toHaveProperty("componentLabels");
    expect(copy.pullRefresh).not.toHaveProperty("componentStatusLabels");
    expect(copy.pullRefresh.release).toBe("Rilascia per aggiornare");
    expect(copy.tabs).not.toHaveProperty("map");
  });

  it("keeps Friulian tab labels available without changing primary tab ids", () => {
    const copy = getUiShellCopy("fur");

    expect(copy.tabs.home).toBe("Cjase");
    expect(copy.tabs.weather).toBe("Timp");
    expect(copy.tabs.events).toBe("Evenis");
    expect(copy.tabs.discover).toBe("Scuvier\u00e7");
    expect(copy.navigationLabel).toBe("Navigazion principâl");
    expect(copy.officialAlertNavigationLabel).toBe("Vierç tal boletin");
    expect(copy.eventCountLabel).toBe("evenis");
    expect(copy.placeholders.weatherTitle).toBe("Timp");
    expect(copy.pullRefresh.loading).toBe("Da\u00fbr a inzorn\u00e2...");
    expect(copy.pullRefresh.success).toBe("Inzorn\u00e2t");
    expect(copy.pullRefresh).not.toHaveProperty("partial");
    expect(copy.pullRefresh.failed).toBe("Controle la r\u00eat");
    expect(copy.pullRefresh).not.toHaveProperty("componentLabels");
    expect(copy.pullRefresh).not.toHaveProperty("componentStatusLabels");
  });
});
