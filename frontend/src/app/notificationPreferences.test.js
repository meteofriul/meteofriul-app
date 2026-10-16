import { describe, expect, it, vi } from "vitest";

import {
  DEFAULT_NOTIFICATION_PREFERENCES,
  NOTIFICATION_PREFERENCES_STORAGE_KEY,
  readNotificationPreferences,
  toPushNotificationPreferences,
  writeNotificationPreferences,
} from "./notificationPreferences";

function createStorage(initialValue = null) {
  let value = initialValue;

  return {
    getItem: vi.fn(() => value),
    setItem: vi.fn((key, nextValue) => {
      if (key === NOTIFICATION_PREFERENCES_STORAGE_KEY) value = nextValue;
    }),
  };
}

describe("notificationPreferences", () => {
  it("keeps FVG alerts and weather notices but not national alerts on by default", () => {
    expect(readNotificationPreferences(createStorage())).toEqual(DEFAULT_NOTIFICATION_PREFERENCES);
    expect(DEFAULT_NOTIFICATION_PREFERENCES).toEqual({
      officialAlerts: true,
      nationalOfficialAlerts: false,
      weatherNotices: true,
    });
  });

  it("enables local weather notices when an older stored record omits the field", () => {
    const storage = createStorage(JSON.stringify({ officialAlerts: true }));

    expect(readNotificationPreferences(storage)).toEqual({
      officialAlerts: true,
      nationalOfficialAlerts: false,
      weatherNotices: true,
    });
  });

  it("persists a separate, explicit national alert choice", () => {
    const storage = createStorage();

    expect(writeNotificationPreferences({
      officialAlerts: false,
      nationalOfficialAlerts: true,
      weatherNotices: true,
    }, storage)).toEqual({
      officialAlerts: false,
      nationalOfficialAlerts: true,
      weatherNotices: true,
    });

    expect(readNotificationPreferences(storage)).toEqual({
      officialAlerts: false,
      nationalOfficialAlerts: true,
      weatherNotices: true,
    });
  });

  it("maps Avvisi to every local weather category used by the existing backend", () => {
    expect(toPushNotificationPreferences({
      officialAlerts: true,
      weatherNotices: false,
    })).toEqual({
      official_alerts: true,
      rain: false,
      storms: false,
      wind: false,
      snow: false,
      heat: false,
    });
  });
});
