import { describe, expect, it } from "vitest";

import {
  CAMS_AIR_FIELDS,
  CAMS_POLLEN_FIELDS,
  decodeVerifiedCamsHourlyCache,
  encodeCamsHourlyCacheV2,
} from "./camsHourlyCache";
import { sha256Hex } from "./weatherV1Client";

const HOUR_MS = 60 * 60 * 1000;
const RUN_AT = "2026-09-03T00:00:00Z";
const ISTAT = "093033";
const CATALOG_SHA256 = "d5cb6f9efdf10151caa0508b07ed910488db01dc29de45b293ac9eb05652eca4";

function fixture() {
  const run = Date.parse(RUN_AT);
  const pollenVariables = CAMS_POLLEN_FIELDS.map(([id, uiKey]) => ({
    id,
    ui_key: uiKey,
    category: "pollen",
    unit: "grains/m3",
    validation_status: "experimental_unvalidated_by_provider",
  }));
  const samples = Array.from({ length: 97 }, (_, sample) => ({
    valid_at_utc: new Date(run + sample * HOUR_MS).toISOString().replace(".000Z", "Z"),
    pollen_values: Object.fromEntries(CAMS_POLLEN_FIELDS
      .map(([, uiKey], field) => [
        uiKey,
        sample === 42 && field === 2 ? null : sample + field / 100,
      ])),
    pollen_quality_flags: Object.fromEntries(CAMS_POLLEN_FIELDS
      .map(([id], field) => [id, field === 0 && sample % 2 ? ["interpolated"] : []])),
    air_values: Object.fromEntries(CAMS_AIR_FIELDS
      .map((id, field) => [
        id,
        sample === 42 && field === 1 ? null : sample + 100 + field / 100,
      ])),
  }));
  return {
    input: {
      municipality_istat: ISTAT,
      catalog_sha256: CATALOG_SHA256,
      run_utc: RUN_AT,
      generated_at_utc: "2026-09-03T02:00:00Z",
      fresh_until_utc: "2026-09-04T00:00:00Z",
      usable_until_utc: "2026-09-07T00:00:00Z",
      pollen_variables: pollenVariables,
      samples,
    },
    samples,
  };
}

function decode(cache) {
  return decodeVerifiedCamsHourlyCache(cache, {
    municipalityIstat: ISTAT,
    catalogSha256: CATALOG_SHA256,
    runUtc: RUN_AT,
  });
}

function rehash(cache) {
  const { sha256: _oldHash, ...payload } = cache;
  return { ...payload, sha256: sha256Hex(JSON.stringify(payload)) };
}

function mutateBase64(value, mutate) {
  const bytes = Uint8Array.from(globalThis.atob(value), character => character.charCodeAt(0));
  mutate(new DataView(bytes.buffer));
  return globalThis.btoa(String.fromCharCode(...bytes));
}

describe("compact CAMS hourly cache", () => {
  it("round-trips all 97 samples exactly with deduplicated quality sets", () => {
    const { input, samples } = fixture();
    const cache = encodeCamsHourlyCacheV2(input);
    const decoded = decode(cache);

    expect(cache).toMatchObject({ version: 2, sample_count: 97, step_seconds: 3600 });
    expect(cache.quality_flag_sets).toEqual([[], ["interpolated"]]);
    expect(JSON.stringify(cache).length).toBeLessThan(18_000);
    expect(decoded.samples).toEqual(samples);
    expect(decoded.samples[42].pollen_values.graminacee).toBeNull();
    expect(decoded.samples[42].air_values["particulate_matter_10um"]).toBeNull();
    expect(decoded.stored).toBe(cache);
  });

  it("rejects v2 sample counts and starts that are not the complete run series", () => {
    const { input } = fixture();
    expect(() => encodeCamsHourlyCacheV2({
      ...input,
      samples: input.samples.slice(0, 96),
    })).toThrow("invalid CAMS hourly cache input");
    expect(() => encodeCamsHourlyCacheV2({
      ...input,
      samples: input.samples.map(sample => ({
        ...sample,
        valid_at_utc: new Date(Date.parse(sample.valid_at_utc) + HOUR_MS)
          .toISOString().replace(".000Z", "Z"),
      })),
    })).toThrow("invalid CAMS hourly cache timestamps");

    const cache = encodeCamsHourlyCacheV2(input);
    expect(decode(rehash({ ...cache, sample_count: 96 }))).toBeNull();
    expect(decode(rehash({
      ...cache,
      first_valid_at_utc: "2026-09-03T01:00:00Z",
    }))).toBeNull();
  });

  it.each([
    ["not ordered", ["zeta", "alfa"]],
    ["duplicated", ["alfa", "alfa"]],
    ["empty", [""]],
    ["not trimmed", [" alfa"]],
  ])("rejects %s quality flags during encoding and decoding", (_label, flags) => {
    const { input } = fixture();
    const invalidSamples = input.samples.map((sample, index) => index ? sample : ({
      ...sample,
      pollen_quality_flags: {
        ...sample.pollen_quality_flags,
        alder_pollen: flags,
      },
    }));
    expect(() => encodeCamsHourlyCacheV2({ ...input, samples: invalidSamples }))
      .toThrow("invalid CAMS hourly cache quality flags");

    const cache = encodeCamsHourlyCacheV2(input);
    expect(decode(rehash({
      ...cache,
      quality_flag_sets: [...cache.quality_flag_sets, flags],
    }))).toBeNull();
  });

  it("rejects a tampered binary payload through its whole-payload hash", () => {
    const { input } = fixture();
    const cache = encodeCamsHourlyCacheV2(input);
    const replacement = cache.values_f64_b64[0] === "A" ? "B" : "A";
    expect(decode({
      ...cache,
      values_f64_b64: `${replacement}${cache.values_f64_b64.slice(1)}`,
    })).toBeNull();
  });

  it("rejects a false hash and a rehashed non-exact schema", () => {
    const { input } = fixture();
    const cache = encodeCamsHourlyCacheV2(input);
    expect(decode({ ...cache, sha256: "0".repeat(64) })).toBeNull();
    expect(decode(rehash({ ...cache, unexpected: true }))).toBeNull();
    expect(decode(rehash({ ...cache, version: 3 }))).toBeNull();
  });

  it("rejects rehashed binary values and quality references outside the schema", () => {
    const { input } = fixture();
    const cache = encodeCamsHourlyCacheV2(input);
    expect(decode(rehash({
      ...cache,
      values_f64_b64: mutateBase64(cache.values_f64_b64, view => {
        view.setFloat64(0, Number.POSITIVE_INFINITY, true);
      }),
    }))).toBeNull();
    expect(decode(rehash({
      ...cache,
      pollen_quality_refs_u16_b64: mutateBase64(cache.pollen_quality_refs_u16_b64, view => {
        view.setUint16(0, 0xffff, true);
      }),
    }))).toBeNull();
  });

  it("continues to read the expanded v1 schema", () => {
    const { input, samples } = fixture();
    const payload = {
      version: 1,
      municipality_istat: input.municipality_istat,
      catalog_sha256: input.catalog_sha256,
      run_utc: input.run_utc,
      generated_at_utc: input.generated_at_utc,
      fresh_until_utc: input.fresh_until_utc,
      usable_until_utc: input.usable_until_utc,
      pollen_variables: input.pollen_variables,
      samples,
    };
    const cache = { ...payload, sha256: sha256Hex(JSON.stringify(payload)) };
    expect(decode(cache)?.samples).toEqual(samples);
    const duplicatedVariables = {
      ...payload,
      pollen_variables: [...payload.pollen_variables, payload.pollen_variables[0]],
    };
    expect(decode({
      ...duplicatedVariables,
      sha256: sha256Hex(JSON.stringify(duplicatedVariables)),
    })).toBeNull();
  });
});
