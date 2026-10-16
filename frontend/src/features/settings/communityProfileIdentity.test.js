import { describe, expect, it, vi } from "vitest";

import { COMMUNITY_PERSONAL_STATE_KEY } from "../live/communityPersonalState";
import { LIVE_REPORT_CLIENT_ID_KEY } from "../../services/liveApi";
import {
  COMMUNITY_PROFILE_ALIAS_INDEX_KEY,
  formatCommunityProfileAlias,
  readCommunityProfileAliasIndex,
  regenerateCommunityProfileAliasIndex,
} from "./communityProfileIdentity";

function createStorage(initial = {}) {
  const values = new Map(Object.entries(initial));

  return {
    getItem: vi.fn((key) => values.get(key) ?? null),
    setItem: vi.fn((key, value) => values.set(key, value)),
    values,
  };
}

describe("local anonymous community profile alias", () => {
  it("persists one cosmetic alias index without exposing a raw identifier", () => {
    const storage = createStorage();

    expect(readCommunityProfileAliasIndex({ random: () => 0.5, storage })).toBe(13);
    expect(readCommunityProfileAliasIndex({ random: () => 0.1, storage })).toBe(13);
    expect(storage.values.get(COMMUNITY_PROFILE_ALIAS_INDEX_KEY)).toBe("13");
    expect(formatCommunityProfileAlias(13, "Pordenon")).not.toContain("Pordenon");
  });

  it("changes only the cosmetic alias and preserves community ownership state", () => {
    const storage = createStorage({
      [COMMUNITY_PERSONAL_STATE_KEY]: "personal-state",
      [COMMUNITY_PROFILE_ALIAS_INDEX_KEY]: "4",
      [LIVE_REPORT_CLIENT_ID_KEY]: "owner-client-id",
    });

    const next = regenerateCommunityProfileAliasIndex(4, { random: () => 0, storage });

    expect(next).toBe(5);
    expect(formatCommunityProfileAlias(next, "Pordenon"))
      .not.toBe(formatCommunityProfileAlias(4, "Pordenon"));
    expect(storage.values.get(LIVE_REPORT_CLIENT_ID_KEY)).toBe("owner-client-id");
    expect(storage.values.get(COMMUNITY_PERSONAL_STATE_KEY)).toBe("personal-state");
  });

  it("keeps working as a session-only alias when storage is blocked", () => {
    const storage = {
      getItem: vi.fn(() => { throw new Error("blocked"); }),
      setItem: vi.fn(() => { throw new Error("blocked"); }),
    };

    const index = readCommunityProfileAliasIndex({ random: () => 0, storage });

    expect(index).toBe(0);
    expect(formatCommunityProfileAlias(index, "")).not.toContain("Friûl");
  });
});
