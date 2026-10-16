import { describe, expect, it, vi } from "vitest";

import { COMMUNITY_SOURCE_ALIASES } from "../live/communitySourceAlias";
import {
  COMMUNITY_IDENTITY_ANGLES,
  COMMUNITY_IDENTITY_EPITHETS,
  COMMUNITY_IDENTITY_LEGACY_ALIAS_INDEX_KEY,
  COMMUNITY_IDENTITY_PALETTES,
  COMMUNITY_IDENTITY_PATTERN_IDS,
  COMMUNITY_IDENTITY_STORAGE_KEY,
  COMMUNITY_IDENTITY_SUBJECTS,
  buildCommunityIdentity,
  buildPublicCommunityIdentitySnapshot,
  createFallbackCommunityIdentitySnapshot,
  formatCommunityIdentityForPlace,
  generateCommunityIdentity,
  getCommunityIdentityPreview,
  normalizePublicCommunityIdentitySnapshot,
  parsePublicCommunityIdentitySnapshot,
  readCommunityIdentity,
  regenerateCommunityIdentity,
  serializePublicCommunityIdentitySnapshot,
  toPublicCommunityIdentityWire,
} from "./communityIdentity";

function createStorage(initial = {}) {
  const values = new Map(Object.entries(initial));

  return {
    getItem: vi.fn((key) => values.get(key) ?? null),
    setItem: vi.fn((key, value) => values.set(key, value)),
    values,
  };
}

describe("community identity v2", () => {
  it("offers a broad, stable Friulian subject and avatar vocabulary", () => {
    const ids = COMMUNITY_IDENTITY_SUBJECTS.map(({ id }) => id);
    const animalOrObjectCount = COMMUNITY_IDENTITY_SUBJECTS
      .filter(({ kind }) => kind === "animal" || kind === "object")
      .length;

    expect(new Set(ids).size).toBe(ids.length);
    expect(animalOrObjectCount).toBeGreaterThanOrEqual(20);
    expect(COMMUNITY_IDENTITY_SUBJECTS.slice(0, 26).map(({ label }) => label))
      .toEqual(COMMUNITY_SOURCE_ALIASES);
    expect(ids).toEqual(expect.arrayContaining([
      "acuile",
      "cevron",
      "lof",
      "claf",
      "scarpete",
      "cjalcjut",
    ]));
    expect(COMMUNITY_IDENTITY_PALETTES.map(({ id }) => id)).toEqual([
      "sky",
      "cobalt",
      "lagoon",
      "gold",
      "slate",
      "night",
    ]);
    expect(COMMUNITY_IDENTITY_PATTERN_IDS).toEqual([
      "diagonal",
      "halo",
      "split",
      "orbit",
    ]);
    expect(COMMUNITY_IDENTITY_ANGLES).toEqual([45, 90, 135]);
    expect(COMMUNITY_IDENTITY_EPITHETS.map(({ label }) => label)).toEqual(expect.arrayContaining([
      "di Aur",
      "dal Bosc",
      "dal Fogolâr",
    ]));
  });

  it("derives the same alias and avatar independently from weather or report places", () => {
    const pordenone = buildCommunityIdentity({
      placeName: "Pordenon",
      revision: 7,
      subjectId: "acuile",
    });
    const udine = buildCommunityIdentity({
      placeName: "Udin",
      revision: 7,
      subjectId: "acuile",
    });

    expect(pordenone.alias).toBe(`Acuile ${pordenone.epithetLabel}`);
    expect(udine.alias).toBe(pordenone.alias);
    expect(udine.avatar).toEqual(pordenone.avatar);
    expect(buildCommunityIdentity({
      placeName: "Pordenon",
      revision: 8,
      subjectId: "acuile",
    }).avatar).not.toEqual(pordenone.avatar);
  });

  it("generates, persists and reads a profile without identity or ownership secrets", () => {
    const storage = createStorage();
    const generated = readCommunityIdentity({
      placeName: "Pordenon",
      random: () => 0,
      storage,
    });
    const stored = storage.values.get(COMMUNITY_IDENTITY_STORAGE_KEY);

    expect(generated.subjectId).toBe("crot");
    expect(readCommunityIdentity({ placeName: "Udin", random: () => 0.9, storage }))
      .toEqual(generated);
    expect(stored).not.toMatch(/client|owner|sourceKey|source_key/i);
    expect(JSON.parse(stored)).toEqual({
      alias: generated.alias,
      epithetId: generated.epithetId,
      revision: 0,
      subjectId: "crot",
      version: 2,
    });
  });

  it("migrates the v1 alias index in place without deleting its compatibility value", () => {
    const storage = createStorage({
      [COMMUNITY_IDENTITY_LEGACY_ALIAS_INDEX_KEY]: "20",
    });

    const migrated = readCommunityIdentity({ placeName: "Pordenon", storage });

    expect(migrated).toMatchObject({
      revision: 0,
      subjectId: "claf",
      version: 2,
    });
    expect(migrated.alias).toBe(`Clâf ${migrated.epithetLabel}`);
    expect(storage.values.get(COMMUNITY_IDENTITY_LEGACY_ALIAS_INDEX_KEY)).toBe("20");
    expect(JSON.parse(storage.values.get(COMMUNITY_IDENTITY_STORAGE_KEY)).subjectId).toBe("claf");
  });

  it("upgrades a geographic v2 profile in place without changing its subject or revision", () => {
    const storage = createStorage({
      [COMMUNITY_IDENTITY_STORAGE_KEY]: JSON.stringify({
        alias: "Acuile di Pordenon",
        placeName: "Pordenon",
        revision: 7,
        subjectId: "acuile",
        version: 2,
      }),
    });

    const identity = readCommunityIdentity({ placeName: "Roma", storage });
    const upgraded = JSON.parse(storage.values.get(COMMUNITY_IDENTITY_STORAGE_KEY));

    expect(identity).toMatchObject({ revision: 7, subjectId: "acuile" });
    expect(identity.alias).not.toContain("Pordenon");
    expect(upgraded).toEqual({
      alias: identity.alias,
      epithetId: identity.epithetId,
      revision: 7,
      subjectId: "acuile",
      version: 2,
    });
  });

  it("regenerates only cosmetic identity state and always selects another subject", () => {
    const storage = createStorage({
      "meteoFriul:communityPersonalState:v1": "private-history",
      "meteoFriul:liveReportClientId:v1": "private-owner",
    });
    const current = buildCommunityIdentity({
      placeName: "Pordenon",
      revision: 4,
      subjectId: "ors",
    });
    const next = regenerateCommunityIdentity(current, { random: () => 0, storage });

    expect(next.subjectId).not.toBe(current.subjectId);
    expect(next.revision).toBe(5);
    expect(storage.values.get("meteoFriul:communityPersonalState:v1")).toBe("private-history");
    expect(storage.values.get("meteoFriul:liveReportClientId:v1")).toBe("private-owner");
  });

  it("keeps the same profile when legacy callers request formatting for a place", () => {
    const profile = buildCommunityIdentity({
      placeName: "Friûl",
      revision: 2,
      subjectId: "cevron",
    });
    const reportIdentity = formatCommunityIdentityForPlace(profile, "Pordenon");
    const snapshot = buildPublicCommunityIdentitySnapshot(profile, { placeName: "Pordenon" });

    expect(reportIdentity).toEqual(profile);
    expect(snapshot.alias).toBe(profile.alias);
    expect(snapshot.avatar).toEqual({
      angle: profile.avatar.angle,
      paletteId: profile.avatar.paletteId,
      patternId: profile.avatar.patternId,
      variant: profile.avatar.variant,
    });
    expect(profile.alias).toBe(`Cevron ${profile.epithetLabel}`);
  });

  it("builds a minimal public snapshot and normalizes API snake_case safely", () => {
    const identity = buildCommunityIdentity({
      placeName: "Pordenon",
      revision: 3,
      subjectId: "claf",
    });
    const snapshot = buildPublicCommunityIdentitySnapshot(identity);
    const wire = toPublicCommunityIdentityWire(snapshot);
    const reportWire = toPublicCommunityIdentityWire(identity, { placeName: "Udin" });

    expect(snapshot).toEqual({
      alias: identity.alias,
      avatar: {
        angle: identity.avatar.angle,
        paletteId: identity.avatar.paletteId,
        patternId: identity.avatar.patternId,
        variant: identity.avatar.variant,
      },
      subjectId: "claf",
      version: 1,
    });
    expect(wire).toEqual({
      alias: identity.alias,
      avatar: {
        angle: identity.avatar.angle,
        palette_id: identity.avatar.paletteId,
        pattern_id: identity.avatar.patternId,
        variant: identity.avatar.variant,
      },
      subject_id: "claf",
      version: 1,
    });
    expect(reportWire.alias).toBe(identity.alias);
    expect(reportWire.avatar).toEqual(wire.avatar);
    expect(normalizePublicCommunityIdentitySnapshot({
      identity: wire,
      owner_key: "must-not-pass-through",
    })).toEqual(snapshot);
  });

  it("serializes only whitelisted public fields and rejects forged vocabulary", () => {
    const identity = generateCommunityIdentity({
      placeName: "Pordenon",
      random: () => 0.8,
      revision: 1,
    });
    const serialized = serializePublicCommunityIdentitySnapshot({
      ...identity,
      clientId: "secret-client",
      ownerKey: "secret-owner",
    });
    const parsed = parsePublicCommunityIdentitySnapshot(serialized);

    expect(parsed).toEqual(buildPublicCommunityIdentitySnapshot(identity));
    expect(serialized).not.toMatch(/secret|client|owner/i);
    expect(normalizePublicCommunityIdentitySnapshot({
      ...parsed,
      subjectId: "not-allowed",
    })).toBeNull();
    expect(normalizePublicCommunityIdentitySnapshot({
      ...parsed,
      avatar: { ...parsed.avatar, paletteId: "user-css" },
    })).toBeNull();
  });

  it("creates deterministic legacy fallbacks without echoing the public source key", () => {
    const first = createFallbackCommunityIdentitySnapshot(
      "opaque-public-source-key",
      "Pordenon",
    );
    const second = createFallbackCommunityIdentitySnapshot(
      "opaque-public-source-key",
      "Pordenon",
    );

    expect(second).toEqual(first);
    expect(JSON.stringify(first)).not.toContain("opaque-public-source-key");
    expect(COMMUNITY_IDENTITY_EPITHETS.some(
      ({ label }) => first.alias.endsWith(` ${label}`),
    )).toBe(true);
    expect(createFallbackCommunityIdentitySnapshot(" ", "Pordenon")).toBeNull();
  });

  it("combines stored snapshots and legacy fallbacks without duplicating a source", () => {
    const identity = buildPublicCommunityIdentitySnapshot(buildCommunityIdentity({
      placeName: "Pordenon",
      subjectId: "acuile",
    }));
    const preview = getCommunityIdentityPreview({
      identities: [{ identity, sourceKey: "source-1" }],
      limit: 1,
      placeName: "Pordenon",
      sourceKeys: ["source-1", "source-2"],
    });

    expect(preview.identities).toEqual([identity]);
    expect(preview.totalCount).toBe(2);
    expect(preview.hiddenCount).toBe(1);
  });

  it("degrades to session state when storage access is blocked", () => {
    const storage = {
      getItem: vi.fn(() => { throw new Error("blocked"); }),
      setItem: vi.fn(() => { throw new Error("blocked"); }),
    };

    expect(() => readCommunityIdentity({ random: () => 0, storage })).not.toThrow();
    expect(readCommunityIdentity({ random: () => 0, storage }).alias).toMatch(/^Crot /);
  });

  it("keeps published snapshots immutable when a future alias is regenerated", () => {
    const current = buildCommunityIdentity({ revision: 4, subjectId: "claf" });
    const published = buildPublicCommunityIdentitySnapshot(current, { placeName: "Pordenone" });
    const next = regenerateCommunityIdentity(current, { random: () => 0 });

    expect(next.alias).not.toBe(current.alias);
    expect(published.alias).toBe(current.alias);
    expect(published).toEqual(buildPublicCommunityIdentitySnapshot(current));
  });

  it("accepts historical location aliases while rejecting subject mismatches", () => {
    const identity = buildCommunityIdentity({ subjectId: "claf" });
    const current = buildPublicCommunityIdentitySnapshot(identity);
    const legacy = { ...current, alias: "Clâf di Pordenon" };

    expect(normalizePublicCommunityIdentitySnapshot(current)).toEqual(current);
    expect(normalizePublicCommunityIdentitySnapshot(legacy)?.alias).toBe("Clâf di Pordenon");
    expect(normalizePublicCommunityIdentitySnapshot({
      ...current,
      alias: "Ors dal Bosc",
    })).toBeNull();
  });
});
