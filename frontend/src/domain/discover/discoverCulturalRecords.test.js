import { describe, expect, it } from "vitest";

import {
  getDiscoverCulturalRecords,
  getInstitutionalArchiveRecords,
  getInstitutionalRitualRecords,
  getOstermannCulturalRecords,
} from "./discoverCulturalRecords";

describe("discover cultural records", () => {
  it("combines institutional records without changing the Ostermann archive", () => {
    const ostermannRecords = getOstermannCulturalRecords();
    const institutionalRituals = getInstitutionalRitualRecords();
    const institutionalArchive = getInstitutionalArchiveRecords();
    const records = getDiscoverCulturalRecords();

    expect(ostermannRecords).toHaveLength(63);
    expect(institutionalRituals).toHaveLength(17);
    expect(institutionalArchive).toHaveLength(29);
    expect(records).toHaveLength(109);
    expect(new Set(records.map((record) => record.id)).size).toBe(records.length);
    expect(institutionalRituals.every((record) => (
      record.section === "riti_credenze_popolari" &&
      record.source?.label !== "Ostermann 1894"
    ))).toBe(true);
    expect(institutionalArchive.every((record) => (
      record.section === "archivio_tradizioni" &&
      record.source?.url?.startsWith("https://")
    ))).toBe(true);
    expect(new Set(institutionalArchive.map((record) => record.source?.type))).toEqual(new Set([
      "institutional_catalogue",
      "institutional_archive",
      "institutional_museum",
      "institutional_publication",
      "municipal_cultural_portal",
      "institutional_park_portal",
      "local_tourism_consortium",
      "public_transport_operator",
    ]));
  });
});
