import { describe, expect, it } from "vitest";

import {
  getOfficialBulletinDates,
  hasCurrentOfficialBulletinDay,
  hasOfficialBulletinText,
  hasUsableOsmerStructuredMap,
  isUsableOfficialBulletin,
} from "./officialBulletin";

const NOW = new Date("2026-08-02T10:00:00.000Z");

function buildTextPayload(date = "2026-08-02") {
  return {
    forecast: {
      official: {
        it: {
          forecasts: [{ date, text: "Tempo stabile" }],
        },
      },
    },
  };
}

function buildStructuredPayload({ stale = false } = {}) {
  const areas9 = Object.fromEntries(
    Array.from({ length: 9 }, (_, index) => [
      `A${index + 1}`,
      { source_kind: "structured_xml" },
    ]),
  );

  return {
    forecast: {
      osmer_structured: {
        days: [{ areas9, source_kind: "structured_xml", valid_date: "2026-08-02" }],
        is_stale: stale,
        source_kind: "structured_xml",
        source_status: stale ? "source_unavailable" : "reachable_xml",
      },
    },
  };
}

describe("official bulletin validity", () => {
  it("accepts official text with a current forecast date", () => {
    const payload = buildTextPayload();

    expect(hasOfficialBulletinText(payload)).toBe(true);
    expect(getOfficialBulletinDates(payload)).toEqual(["2026-08-02"]);
    expect(hasCurrentOfficialBulletinDay(payload, { now: NOW })).toBe(true);
    expect(isUsableOfficialBulletin(payload, { now: NOW })).toBe(true);
  });

  it("accepts a complete current structured OSMER map without text", () => {
    const payload = buildStructuredPayload();

    expect(hasUsableOsmerStructuredMap(payload)).toBe(true);
    expect(isUsableOfficialBulletin(payload, { now: NOW })).toBe(true);
  });

  it("rejects Open-Meteo-only model data", () => {
    const payload = {
      forecast: {
        forecast: [{ date: "2026-08-02", condition: "Sole", min_temp: 20, max_temp: 31 }],
        primary_source: "open_meteo",
      },
    };

    expect(hasOfficialBulletinText(payload)).toBe(false);
    expect(hasUsableOsmerStructuredMap(payload)).toBe(false);
    expect(isUsableOfficialBulletin(payload, { now: NOW })).toBe(false);
  });

  it("rejects official data whose forecast dates have all passed", () => {
    const payload = buildTextPayload("2026-08-01");

    expect(hasOfficialBulletinText(payload)).toBe(true);
    expect(hasCurrentOfficialBulletinDay(payload, { now: NOW })).toBe(false);
    expect(isUsableOfficialBulletin(payload, { now: NOW })).toBe(false);
  });

  it("rejects stale structured data when no official text remains", () => {
    const payload = buildStructuredPayload({ stale: true });

    expect(hasUsableOsmerStructuredMap(payload)).toBe(false);
    expect(isUsableOfficialBulletin(payload, { now: NOW })).toBe(false);
  });

  it("accepts official Friulian text when Italian text is absent", () => {
    const payload = {
      forecast: {
        official: {
          fur: {
            forecasts: [{ date: "2026-08-03", text: "Timp stabil" }],
          },
        },
      },
    };

    expect(isUsableOfficialBulletin(payload, { now: NOW })).toBe(true);
  });
});
