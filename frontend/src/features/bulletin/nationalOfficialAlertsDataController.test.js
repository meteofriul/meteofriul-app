import { describe, expect, it, vi } from "vitest";

import {
  isUsableNationalOfficialAlerts,
  loadNationalOfficialAlerts,
} from "./nationalOfficialAlertsDataController";

const location = {
  city: "Urbino",
  municipality: { istatCode: "041067", name: "Urbino" },
};
const now = Date.parse("2026-09-26T12:00:00Z");
const payload = {
  contract: "meteofriul.official_alerts.location.v1",
  schema_version: 1,
  municipality: { istat: "041067", name: "Urbino", region_iso: "IT-57" },
  zones: ["DPC:Marc-1", "DPC:Marc-2"],
  records: [{ risk: "hydraulic" }],
  standalone_display_allowed: true,
  expires_at: "2026-09-27T23:59:59+02:00",
};

describe("national official alerts data controller", () => {
  it("fails closed on the wrong municipality or the FVG non-replacement guard", () => {
    expect(isUsableNationalOfficialAlerts(payload, location, { now: () => now })).toBe(true);
    expect(isUsableNationalOfficialAlerts({
      ...payload,
      municipality: { ...payload.municipality, istat: "058091" },
    }, location, { now: () => now })).toBe(false);
    expect(isUsableNationalOfficialAlerts({
      ...payload,
      standalone_display_allowed: false,
    }, location, { now: () => now })).toBe(false);
  });

  it("keeps a still-valid cached state when refresh fails", async () => {
    const cacheReader = vi.fn().mockReturnValue(payload);
    const result = await loadNationalOfficialAlerts(location, {
      cacheReader,
      fetcher: vi.fn().mockRejectedValue(new Error("offline")),
      force: true,
      now: () => now,
    });

    expect(result).toMatchObject({ fromCache: true, status: "stale", data: payload });
  });

  it("never requests by municipality name when ISTAT is missing", async () => {
    const fetcher = vi.fn();
    const result = await loadNationalOfficialAlerts({ city: "Urbino" }, { fetcher });

    expect(result.status).toBe("error");
    expect(fetcher).not.toHaveBeenCalled();
  });
});
