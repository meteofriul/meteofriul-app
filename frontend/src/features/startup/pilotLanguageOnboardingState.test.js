import { describe, expect, it, vi } from "vitest";

import {
  PILOT_LANGUAGE_ONBOARDING_STORAGE_KEY,
  readPilotLanguageOnboardingState,
  shouldShowPilotLanguageOnboarding,
  writePilotLanguageOnboardingState,
} from "./pilotLanguageOnboardingState";

describe("pilot language onboarding state", () => {
  it("persists the one-time welcome independently from the language preference", () => {
    const values = new Map();
    const storage = {
      getItem: vi.fn((key) => values.get(key) || null),
      setItem: vi.fn((key, value) => values.set(key, value)),
    };

    expect(readPilotLanguageOnboardingState({ storage })).toBe("pending");
    expect(writePilotLanguageOnboardingState({ storage })).toBe("completed");
    expect(storage.setItem).toHaveBeenCalledWith(
      PILOT_LANGUAGE_ONBOARDING_STORAGE_KEY,
      "completed",
    );
    expect(readPilotLanguageOnboardingState({ storage })).toBe("completed");
  });

  it.each([
    [false, "pending", false],
    [false, "completed", false],
    [true, "pending", true],
    [true, "completed", false],
  ])("gates the welcome for pilot=%s and state=%s", (pilot, state, expected) => {
    expect(shouldShowPilotLanguageOnboarding({ pilot, state })).toBe(expected);
  });
});
