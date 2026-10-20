import { describe, expect, it } from "vitest";
import { LOCATION_SELECTOR_COPY, getLocationSelectorCopy } from "./locationSelectorCopy";

describe("locationSelectorCopy", () => {
  it("keeps IT and FUR copy keys aligned", () => {
    expect(Object.keys(LOCATION_SELECTOR_COPY.fur).sort()).toEqual(
      Object.keys(LOCATION_SELECTOR_COPY.it).sort(),
    );
  });

  it("returns IT copy for location settings", () => {
    const copy = getLocationSelectorCopy("it");

    expect(copy.settings).toBe("Impostazioni");
    expect(copy.location).toBe("Località");
    expect(copy.searchLoading).toBe("Ricerca delle località in corso...");
    expect(copy.deviceName).toBe("Nome dispositivo");
    expect(copy.infoValue).toBe("Trasparenza");
    expect(copy.infoText).toContain("riferimento meteo ufficiale");
  });

  it("returns FUR copy for location settings", () => {
    const copy = getLocationSelectorCopy("fur");

    expect(copy.settings).toBe("Impostazions");
    expect(copy.location).toBe("Localitât");
    expect(copy.searchLoading).toBe("O stoi cirint lis localitâts...");
    expect(copy.deviceName).toBe("Non dispositîf");
    expect(copy.infoWarningTitle).toBe("Avîs");
    expect(copy.infoValue).toBe("Trasparence");
    expect(copy.infoText).toContain("fonts esternis");
  });

  it("falls back to IT for unknown languages", () => {
    expect(getLocationSelectorCopy("unknown").settings).toBe("Impostazioni");
  });
});
