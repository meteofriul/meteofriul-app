import { describe, expect, it } from "vitest";

import {
  BACKGROUND_LOCATION_DISCLOSURE_CONSENT_STORAGE_KEY,
  BACKGROUND_LOCATION_DISCLOSURE_STORAGE_KEY,
  hasAcceptedBackgroundLocationDisclosure,
  hasShownBackgroundLocationDisclosure,
  markBackgroundLocationDisclosureAccepted,
  markBackgroundLocationDisclosureShown,
  shouldOpenBackgroundLocationDisclosure,
} from "./backgroundLocationDisclosureState";

function createStorage() {
  const values = new Map();
  return {
    getItem: (key) => values.get(key) ?? null,
    setItem: (key, value) => values.set(key, String(value)),
  };
}

describe("backgroundLocationDisclosureState", () => {
  it("keeps the seen marker separate from recorded consent", () => {
    const storage = createStorage();

    expect(hasShownBackgroundLocationDisclosure({ storage })).toBe(false);
    expect(hasAcceptedBackgroundLocationDisclosure({ storage })).toBe(false);
    expect(markBackgroundLocationDisclosureShown({ storage })).toBe(true);

    expect(hasShownBackgroundLocationDisclosure({ storage })).toBe(true);
    expect(hasAcceptedBackgroundLocationDisclosure({ storage })).toBe(false);
    expect(storage.getItem(BACKGROUND_LOCATION_DISCLOSURE_STORAGE_KEY)).toBe("shown");
    expect(storage.getItem(BACKGROUND_LOCATION_DISCLOSURE_CONSENT_STORAGE_KEY)).toBeNull();

    expect(markBackgroundLocationDisclosureAccepted({ storage })).toBe(true);
    expect(hasAcceptedBackgroundLocationDisclosure({ storage })).toBe(true);
    expect(storage.getItem(BACKGROUND_LOCATION_DISCLOSURE_CONSENT_STORAGE_KEY)).toBe("accepted");
  });

  it("fails closed to collection when consent storage is unavailable", () => {
    const storage = {
      getItem: () => { throw new Error("blocked"); },
      setItem: () => { throw new Error("blocked"); },
    };

    expect(hasShownBackgroundLocationDisclosure({ storage })).toBe(false);
    expect(hasAcceptedBackgroundLocationDisclosure({ storage })).toBe(false);
    expect(markBackgroundLocationDisclosureShown({ storage })).toBe(false);
    expect(markBackgroundLocationDisclosureAccepted({ storage })).toBe(false);
  });

  it("opens immediately before Android automatic location until consent is recorded", () => {
    const startup = {
      autoLocationEnabled: true,
      hasAccepted: false,
      isNativeAndroid: true,
      // These later-stage values must never gate the prominent disclosure.
      backgroundLocationRuntime: {
        available: true,
        backgroundPermission: true,
        configured: false,
        precisePermission: false,
      },
      notificationPreferences: { weatherNotices: false },
      notificationRuntime: {
        connected: false,
        permission: "prompt",
        platform: "android",
      },
    };

    expect(shouldOpenBackgroundLocationDisclosure(startup)).toBe(true);
    expect(shouldOpenBackgroundLocationDisclosure({ ...startup, hasAccepted: true })).toBe(false);
  });

  it("does not open outside the native Android automatic-location path", () => {
    expect(shouldOpenBackgroundLocationDisclosure({
      autoLocationEnabled: true,
      hasAccepted: false,
      isNativeAndroid: false,
    })).toBe(false);
    expect(shouldOpenBackgroundLocationDisclosure({
      autoLocationEnabled: false,
      hasAccepted: false,
      isNativeAndroid: true,
    })).toBe(false);
  });
});
