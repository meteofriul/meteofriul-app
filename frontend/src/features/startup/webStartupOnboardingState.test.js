import { describe, expect, it, vi } from "vitest";

import {
  readWebStartupOnboardingState,
  WEB_STARTUP_ONBOARDING_STORAGE_KEY,
  writeWebStartupOnboardingState,
} from "./webStartupOnboardingState";

describe("web startup onboarding storage", () => {
  it("shows a new visitor once and persists an explicit terminal choice", () => {
    const values = new Map();
    const storage = {
      getItem: vi.fn((key) => values.get(key) || null),
      setItem: vi.fn((key, value) => values.set(key, value)),
    };

    expect(readWebStartupOnboardingState({ storage })).toBe("pending");
    expect(writeWebStartupOnboardingState("completed", { storage })).toBe("completed");
    expect(storage.setItem).toHaveBeenCalledWith(
      WEB_STARTUP_ONBOARDING_STORAGE_KEY,
      "completed",
    );
    expect(readWebStartupOnboardingState({ storage })).toBe("completed");
  });
});
