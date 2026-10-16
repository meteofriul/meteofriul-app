import { describe, expect, it } from "vitest";

import {
  COMMUNITY_GUIDELINES_CONSENT_KEY,
  clearCommunityGuidelinesConsent,
  hasCommunityGuidelinesConsent,
  rememberCommunityGuidelinesConsent,
} from "./communityGuidelinesConsent";

function createStorage() {
  const values = new Map();
  return {
    getItem: (key) => values.get(key) ?? null,
    removeItem: (key) => values.delete(key),
    setItem: (key, value) => values.set(key, value),
    values,
  };
}

describe("communityGuidelinesConsent", () => {
  it("remembers consent only for the current policy version", () => {
    const storage = createStorage();

    expect(hasCommunityGuidelinesConsent("community-guidelines-v2", { storage })).toBe(false);
    expect(rememberCommunityGuidelinesConsent("community-guidelines-v2", { storage })).toBe(true);
    expect(hasCommunityGuidelinesConsent("community-guidelines-v2", { storage })).toBe(true);
    expect(hasCommunityGuidelinesConsent("community-guidelines-v3", { storage })).toBe(false);
    expect(storage.values.get(COMMUNITY_GUIDELINES_CONSENT_KEY)).toBe("community-guidelines-v2");
  });

  it("can clear consent without failing when storage is unavailable", () => {
    const storage = createStorage();
    rememberCommunityGuidelinesConsent("community-guidelines-v2", { storage });

    clearCommunityGuidelinesConsent({ storage });

    expect(hasCommunityGuidelinesConsent("community-guidelines-v2", { storage })).toBe(false);
    expect(() => clearCommunityGuidelinesConsent({
      storage: { removeItem: () => { throw new Error("blocked"); } },
    })).not.toThrow();
  });
});
