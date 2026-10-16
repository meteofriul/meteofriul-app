import { createHash } from "node:crypto";
import { describe, expect, it } from "vitest";

import originalRecords from "../../data/ostermannCulturalDiscover.json";
import weatherContextReview from "../../data/discover/weatherContextReview.json";
import { getDiscoverCulturalRecords, getOstermannCulturalRecords } from "./discoverCulturalRecords";
import { applyDiscoverWeatherEditorialPolicy } from "./discoverWeatherEditorialPolicy";
import { getDiscoverTemporalRank, pickDiscoverTemporalRecord } from "./discoverTemporalSelection";

const OVERRIDES = {
  "ost-0005-lessico-venti": "always",
  "ost-0009-luna-lavori-agricoli": "always",
  "ost-0021-segni-animali-vento": "always",
  "ost-0024-monti-col-cappello": "seasonal",
  "ost-0026-pioggia-grandine-streghe": "seasonal",
  "ost-0042-vespe-neve-inverno": "seasonal",
  "ost-0048-palle-neve-slitte": "seasonal",
  "ost-0058-demoni-aria-tempeste": "always",
};
const transformed = applyDiscoverWeatherEditorialPolicy(originalRecords);
const byId = new Map(transformed.map((record) => [record.id, record]));

function deepFreeze(value) {
  if (value && typeof value === "object") {
    Object.values(value).forEach(deepFreeze);
    Object.freeze(value);
  }
  return value;
}

describe("Scopri weather editorial policy", () => {
  it("records exactly one explicit decision for each of the original 26 weather records", () => {
    const weatherRecords = originalRecords.filter((record) => record.recurrence === "weather");
    expect(weatherContextReview).toMatchObject({
      scope: "discover_only", readyForUi: false, copyChanged: false, newSourceChecksPerformed: false,
      sharedSourceSnapshot: {
        records: 63,
        sha256Json: createHash("sha256").update(JSON.stringify(originalRecords)).digest("hex"),
      },
    });
    expect(weatherContextReview.records.map((review) => review.recordId)).toEqual(weatherRecords.map((record) => record.id));
    expect(new Set(weatherContextReview.records.map((review) => review.recordId)).size).toBe(26);
    expect(weatherContextReview.editorialDecision.recordIds).toEqual(Object.keys(OVERRIDES));
    weatherContextReview.records.forEach((review) => {
      const original = weatherRecords.find((record) => record.id === review.recordId);
      expect(review.original).toEqual({ section: original.section, recurrence: original.recurrence, seasons: original.seasons });
      expect(review.reason).toBeTruthy();
      expect(review.nextStep).toBeTruthy();
      expect(review.contextRequirements.length).toBeGreaterThan(0);
      expect(review).not.toHaveProperty("text");
      if (OVERRIDES[review.recordId]) {
        expect(review.disposition).toBe("archive_rotation");
        expect(review.override).toEqual({ section: "archivio_tradizioni", recurrence: OVERRIDES[review.recordId] });
      } else {
        expect(review.disposition).toBe("excluded");
        expect(review).not.toHaveProperty("override");
      }
    });
  });

  it("exposes the overlay only in Scopri while preserving the raw source accessor", () => {
    expect(getOstermannCulturalRecords()).toEqual(originalRecords);
    const runtime = new Map(getDiscoverCulturalRecords().map((record) => [record.id, record]));
    Object.entries(OVERRIDES).forEach(([id, recurrence]) => {
      expect(runtime.get(id)).toEqual(byId.get(id));
      expect(runtime.get(id).recurrence).toBe(recurrence);
      expect(originalRecords.find((record) => record.id === id).recurrence).toBe("weather");
    });
  });

  it("preserves the shared Ostermann source and applies only eight scoped overrides", () => {
    expect(createHash("sha256").update(JSON.stringify(originalRecords)).digest("hex"))
      .toBe("f4a8864f7d16765c3e4091573e4fe66e48b24bd0669d05a63db8ba7c9c0bfc05");
    expect(transformed.map((record) => record.id)).toEqual(originalRecords.map((record) => record.id));
    expect(new Set(transformed.map((record) => record.id)).size).toBe(transformed.length);
    originalRecords.forEach((original) => {
      const actual = byId.get(original.id);
      if (!OVERRIDES[original.id]) {
        expect(actual).toEqual(original);
        return;
      }
      expect(actual).toMatchObject({
        ...original,
        section: "archivio_tradizioni",
        recurrence: OVERRIDES[original.id],
      });
      expect(original.recurrence).toBe("weather");
      ["title", "text", "appShort", "source", "candidateId", "seasons", "weatherTags", "languageStatus"]
        .forEach((field) => expect(actual[field]).toEqual(original[field]));
    });
  });

  it("does not mutate even deeply frozen source records", () => {
    const source = deepFreeze(structuredClone(originalRecords));
    expect(() => applyDiscoverWeatherEditorialPolicy(source)).not.toThrow();
    expect(source).toEqual(originalRecords);
  });

  it("fails closed for missing approval, excluded reviews, changed originals and unready copy", () => {
    const original = originalRecords.find((record) => record.id === "ost-0005-lessico-venti");
    const policy = {
      editorialDecision: {
        approvalBasis: "user_delegated_assisted_editorial_review",
        independentHumanReview: false,
        recordIds: [original.id],
      },
      records: [{
        recordId: original.id,
        disposition: "archive_rotation",
        original: { section: original.section, recurrence: original.recurrence, seasons: original.seasons },
        override: { section: "archivio_tradizioni", recurrence: "always" },
      }],
    };
    const invalidPolicies = [
      {},
      { ...policy, editorialDecision: { ...policy.editorialDecision, recordIds: [] } },
      { ...policy, editorialDecision: { ...policy.editorialDecision, approvalBasis: "unreviewed" } },
      { ...policy, records: [{ ...policy.records[0], disposition: "excluded" }] },
      { ...policy, records: [{ ...policy.records[0], original: { ...policy.records[0].original, seasons: ["inverno"] } }] },
      { ...policy, records: [{ ...policy.records[0], override: { section: "riti_credenze_popolari", recurrence: "always" } }] },
    ];
    invalidPolicies.forEach((invalid) => {
      expect(applyDiscoverWeatherEditorialPolicy([original], invalid)).toEqual([original]);
    });
    [
      { ...original, readyForUi: false },
      { ...original, languageStatus: { ...original.languageStatus, fur: "pending_human_review" } },
      { ...original, dateAnchors: ["01-01"] },
      { ...original, nthWeekdayDates: [{ month: 10, weekday: 0, ordinal: 1 }] },
      { ...original, nthWeekdayDates: [] },
      { ...original, nthWeekdayDates: null },
    ].forEach((invalid) => {
      expect(applyDiscoverWeatherEditorialPolicy([invalid], policy)).toEqual([invalid]);
    });
    expect(applyDiscoverWeatherEditorialPolicy([original], policy)[0].recurrence).toBe("always");
    const unsafeOverride = {
      ...policy,
      records: [{ ...policy.records[0], override: {
        ...policy.records[0].override,
        text: { it: "unexpected rewrite", fur: "unexpected rewrite" },
        source: { label: "unexpected source" },
        candidateId: "unexpected-identity",
        readyForUi: true,
      } }],
    };
    expect(applyDiscoverWeatherEditorialPolicy([original], unsafeOverride)[0]).toEqual({
      ...original, section: "archivio_tradizioni", recurrence: "always",
    });
  });

  it("keeps the other eighteen weather records excluded rather than treating tags as observations", () => {
    const stillWeather = transformed.filter((record) => record.recurrence === "weather");
    expect(stillWeather).toHaveLength(18);
    stillWeather.forEach((record) => {
      ["2028-01-15", "2028-04-15", "2028-07-15", "2028-10-15"].forEach((date) => {
        expect(getDiscoverTemporalRank(record, date)).toBeNull();
      });
    });
    expect(getDiscoverTemporalRank({ recurrence: "weather", seasons: ["all"] }, "2028-07-15"))
      .toBeNull();
  });

  it("moves only the two approved undated beliefs out of Rituals", () => {
    const moved = originalRecords.filter((record) => (
      record.section === "riti_credenze_popolari" && byId.get(record.id).section !== record.section
    ));
    expect(moved.map((record) => record.id)).toEqual([
      "ost-0026-pioggia-grandine-streghe", "ost-0058-demoni-aria-tempeste",
    ]);
    const weatherRituals = transformed.filter((record) => (
      record.section === "riti_credenze_popolari" && record.recurrence === "weather"
    ));
    expect(weatherRituals.map((record) => record.id)).toEqual([
      "ost-0037-grandine-campane-scongiuri", "ost-0047-lin-di-strie-igroscopio",
    ]);
    expect(pickDiscoverTemporalRecord(weatherRituals, "2028-07-15")).toBeNull();
  });

  it.each([
    ["ost-0024-monti-col-cappello", ["03-01", "11-30"], ["02-29", "12-01"]],
    ["ost-0026-pioggia-grandine-streghe", ["03-01", "08-31"], ["02-29", "09-01"]],
    ["ost-0042-vespe-neve-inverno", ["02-29", "06-01", "08-31", "12-01"], ["03-01", "05-31", "09-01", "11-30"]],
    ["ost-0048-palle-neve-slitte", ["02-29", "12-01"], ["03-01", "11-30"]],
  ])("preserves the existing seasonal boundaries for %s", (id, inside, outside) => {
    inside.forEach((date) => expect(getDiscoverTemporalRank(byId.get(id), `2028-${date}`)).toBe(3));
    outside.forEach((date) => expect(getDiscoverTemporalRank(byId.get(id), `2028-${date}`)).toBeNull());
  });

  it("uses evergreen stories as history without inventing exact or lunar dates", () => {
    Object.entries(OVERRIDES).filter(([, recurrence]) => recurrence === "always").forEach(([id]) => {
      ["2028-01-15", "2028-04-15", "2028-07-15", "2028-10-15"].forEach((date) => {
        expect(getDiscoverTemporalRank(byId.get(id), date)).toBe(4);
      });
    });
    const exact = { id: "fixture-exact", recurrence: "fixed_date", dateAnchors: ["07-15"] };
    expect(pickDiscoverTemporalRecord([...transformed, exact], "2028-07-15", { blendBroader: true }))
      .toBe(exact);
  });
});
