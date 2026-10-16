import { describe, expect, it, vi } from "vitest";

import {
  buildNationalOfficialAlertsUrl,
  fetchNationalOfficialAlertsPayload,
  getNationalOfficialAlertsIstat,
} from "./nationalOfficialAlertsApi";

describe("national official alerts api", () => {
  const urbino = {
    city: "Urbino",
    municipality: { istatCode: "041067", name: "Urbino" },
  };

  it("requires an exact six-digit municipality identity", () => {
    expect(getNationalOfficialAlertsIstat(urbino)).toBe("041067");
    expect(() => buildNationalOfficialAlertsUrl({ city: "Urbino" }, { apiBase: "/api" }))
      .toThrow("Codice ISTAT");
  });

  it("builds the national URL without a municipality-name fallback", () => {
    expect(buildNationalOfficialAlertsUrl(urbino, { apiBase: "/api/" })).toBe(
      "/api/weather/official-alerts/national?municipality_istat=041067",
    );
    expect(buildNationalOfficialAlertsUrl(urbino, {
      apiBase: "/api",
      force: true,
      now: () => 123,
    })).toBe(
      "/api/weather/official-alerts/national?municipality_istat=041067&_=123",
    );
  });

  it("loads the location-aware contract", async () => {
    const payload = { contract: "meteofriul.official_alerts.location.v1" };
    const fetchImpl = vi.fn().mockResolvedValue({
      ok: true,
      json: vi.fn().mockResolvedValue(payload),
    });

    await expect(fetchNationalOfficialAlertsPayload(urbino, {
      apiBase: "/api",
      fetchImpl,
    })).resolves.toEqual(payload);
    expect(fetchImpl).toHaveBeenCalledWith(
      "/api/weather/official-alerts/national?municipality_istat=041067",
      { cache: "default" },
    );
  });
});
