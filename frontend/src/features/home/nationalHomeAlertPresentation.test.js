import { describe, expect, it } from "vitest";

import { buildNationalHomeAlertPresentation } from "./nationalHomeAlertPresentation";

const now = Date.parse("2026-09-26T12:00:00Z");
const location = {
  city: "Urbino",
  countryCode: "IT",
  municipality: { istatCode: "041067", name: "Urbino" },
  regionCode: "IT-57",
  source: "manual",
};
const payload = {
  active: true,
  complete: true,
  conservative_multi_zone_display: true,
  contract: "meteofriul.official_alerts.location.v1",
  expires_at: "2026-09-27T23:59:59+02:00",
  municipality: { istat: "041067", name: "Urbino" },
  records: [
    {
      forecast_day: "2026-09-26",
      level: "green",
      risk: "hydraulic",
      transmission_status: "transmitted",
      valid_to: "2026-09-26T23:59:59+02:00",
    },
    {
      forecast_day: "2026-09-26",
      level: "yellow",
      risk: "thunderstorm",
      transmission_status: "transmitted",
      valid_to: "2026-09-26T23:59:59+02:00",
    },
    {
      forecast_day: "2026-09-27",
      level: "green",
      risk: "hydrogeological",
      transmission_status: "transmitted",
      valid_to: "2026-09-27T23:59:59+02:00",
    },
  ],
  schema_version: 1,
  standalone_display_allowed: true,
  zones: ["DPC:Marc-1", "DPC:Marc-2"],
};

function present(overrides = {}, selectedLocation = location, stateOverrides = {}) {
  return buildNationalHomeAlertPresentation({
    data: { ...payload, ...overrides },
    ...stateOverrides,
  }, selectedLocation, { now });
}

describe("national Home alert presentation", () => {
  it("shows only a verified active alert for the exact municipality, with source and forecast day", () => {
    const alert = present();

    expect(alert).toMatchObject({
      action: { tab: "bulletin", type: "tab-anchor" },
      label: "Allerta gialla",
      meta: "Dipartimento della Protezione Civile",
      source: "national-official-alerts",
      tone: "yellow",
    });
    expect(alert.text).toContain("Urbino: temporali");
    expect(alert.text).toContain("più zone");
    expect(alert.validityLabel).toContain("26 settembre");
    expect(alert.text).not.toContain("rischio idraulico");
  });

  it("uses the highest severity and corresponding day without masking a later orange alert", () => {
    const alert = present({
      records: [
        ...payload.records,
        {
          forecast_day: "2026-09-27",
          level: "orange",
          risk: "hydraulic",
          transmission_status: "transmitted",
          valid_to: "2026-09-27T23:59:59+02:00",
        },
      ],
    });

    expect(alert.label).toBe("Allerta arancione");
    expect(alert.text).toContain("rischio idraulico");
    expect(alert.validityLabel).toContain("27 settembre");
  });

  it("uses Friulian interface copy without changing the municipality", () => {
    const alert = buildNationalHomeAlertPresentation({ data: payload }, location, {
      language: "fur",
      now,
    });

    expect(alert.label).toBe("Alerte zale");
    expect(alert.text).toContain("Urbino");
  });

  it.each([
    ["wrong ISTAT", { municipality: { istat: "058091", name: "Roma" } }, location],
    ["wrong name", { municipality: { istat: "041067", name: "Pesaro" } }, location],
    ["FVG-only projection", { standalone_display_allowed: false }, location],
    ["partial projection", { complete: false }, location],
    ["no active alert", { active: false }, location],
    ["green records", { records: payload.records.filter(record => record.level === "green") }, location],
    ["untransmitted risk", { records: [{ ...payload.records[1], transmission_status: "not_transmitted" }] }, location],
    ["expired snapshot", { expires_at: "2026-09-26T11:00:00Z" }, location],
  ])("does not advertise an unverified %s", (_reason, overrides, selectedLocation) => {
    expect(present(overrides, selectedLocation)).toBeNull();
  });

  it("does not advertise stale or failed data", () => {
    expect(present({}, location, { isStale: true })).toBeNull();
    expect(present({}, location, { error: "offline" })).toBeNull();
  });
});
