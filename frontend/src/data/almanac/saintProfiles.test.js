import { describe, expect, it } from "vitest";
import profiles from "./saintProfiles.json";
import saints from "./saints.json";

const DAY_KEY_PATTERN = /^\d{2}-\d{2}$/;
const calendarKeys = Object.keys(saints).filter((key) => DAY_KEY_PATTERN.test(key)).sort();
const profileKeys = Object.keys(profiles).sort();

describe("saint profiles catalog", () => {
  it("covers every calendar day exactly once", () => {
    expect(calendarKeys).toHaveLength(366);
    expect(profileKeys).toEqual(calendarKeys);
  });

  it("keeps Italian copy concise and tied to the CEI source", () => {
    for (const dayKey of calendarKeys) {
      const profile = profiles[dayKey];

      expect(profile.profile_source, dayKey).toBe("CEI - Martirologio Romano");
      expect(profile.profile_source_url, dayKey).toMatch(
        new RegExp(`^https://www\\.chiesacattolica\\.it/santo-del-giorno/\\?data-liturgia=\\d{4}${dayKey.replace("-", "")}$`),
      );

      if (profile.description_it_status === "curated") {
        expect(profile.description_it.trim().length, dayKey).toBeGreaterThan(0);
        expect(profile.description_it.length, dayKey).toBeLessThanOrEqual(260);
        expect(profile.description_it, dayKey).not.toMatch(/[\r\n]/);
        expect(profile.profile_review_status, dayKey).toBe("approved_it");
      } else {
        expect(profile.description_it_status, dayKey).toBe("pending_source");
        expect(profile.description_it, dayKey).toBe("");
        expect(profile.profile_review_status, dayKey).toBe("pending_source");
      }
    }
  });

  it("keeps every sourced profile curated in Friulian without Italian fallback", () => {
    for (const dayKey of calendarKeys) {
      const profile = profiles[dayKey];

      if (profile.description_it_status === "curated") {
        expect(profile.description_fur_status, dayKey).toBe("curated");
        expect(profile.description_fur.trim().length, dayKey).toBeGreaterThan(0);
        expect(profile.description_fur.length, dayKey).toBeLessThanOrEqual(300);
        expect(profile.description_fur, dayKey).not.toMatch(/[\r\n]/);
        expect(profile.description_fur.localeCompare(
          profile.description_it,
          "it",
          { sensitivity: "base" },
        ), dayKey).not.toBe(0);
      } else {
        expect(profile.description_fur_status, dayKey).toBe("pending_review");
        expect(profile.description_fur, dayKey).toBe("");
      }
    }
  });

  it("documents the two 2026 movable celebrations without invented copy", () => {
    const pendingSourceDates = Object.entries(profiles)
      .filter(([, profile]) => profile.description_it_status === "pending_source")
      .map(([dayKey]) => dayKey);

    expect(pendingSourceDates).toEqual(["03-30", "04-12"]);
  });

});
