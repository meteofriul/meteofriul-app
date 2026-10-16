import { describe, expect, it, vi } from "vitest";

import { ANDROID_PERMISSION_STORAGE_KEYS } from "../domain/startup/androidPermissionGate";
import {
  isNativeAndroidRuntime,
  readAndroidStartupPromptStorage,
  shouldPersistAndroidStartupNotificationPatch,
  writeAndroidStartupNotificationStoragePatch,
} from "./androidStartupRuntime";

function createStorage(initial = {}) {
  const items = new Map(Object.entries(initial));

  return {
    getItem: vi.fn((key) => (items.has(key) ? items.get(key) : null)),
    setItem: vi.fn((key, value) => {
      items.set(key, value);
    }),
  };
}

describe("android startup runtime", () => {
  it("does not treat a normal browser as native Android", () => {
    expect(isNativeAndroidRuntime({ windowLike: {} })).toBe(false);
    expect(isNativeAndroidRuntime({
      windowLike: {
        Capacitor: {
          getPlatform: () => "web",
          isNativePlatform: () => false,
        },
      },
    })).toBe(false);
  });

  it("detects Capacitor Android and the legacy MeteoAndroid bridge", () => {
    expect(isNativeAndroidRuntime({
      windowLike: {
        Capacitor: {
          getPlatform: () => "android",
          isNativePlatform: () => true,
        },
      },
    })).toBe(true);

    expect(isNativeAndroidRuntime({
      windowLike: {
        MeteoAndroid: {
          requestFastLocation: () => {},
        },
      },
    })).toBe(true);
  });

  it("reads startup defaults without disabling the first GPS request", () => {
    expect(readAndroidStartupPromptStorage({ storage: createStorage() })).toEqual({
      autoLocationEnabled: true,
      startupNotificationsAsked: false,
      weatherAlertsEnabled: false,
    });
  });

  it("reads persisted startup permission state", () => {
    const storage = createStorage({
      [ANDROID_PERMISSION_STORAGE_KEYS.autoLocationEnabled]: "false",
      [ANDROID_PERMISSION_STORAGE_KEYS.startupNotificationsAsked]: "true",
      [ANDROID_PERMISSION_STORAGE_KEYS.weatherAlertsEnabled]: "true",
    });

    expect(readAndroidStartupPromptStorage({ storage })).toEqual({
      autoLocationEnabled: false,
      startupNotificationsAsked: true,
      weatherAlertsEnabled: true,
    });
  });

  it("does not persist notification patches for unsupported dry-run handlers", () => {
    expect(shouldPersistAndroidStartupNotificationPatch({
      notificationResult: {
        receive: "unsupported",
        requested: false,
      },
      storagePatch: {
        startupNotificationsAsked: false,
        weatherAlertsEnabled: false,
      },
    })).toBe(false);
  });

  it("persists a real notification decision when the native handler returns one", () => {
    const storage = createStorage();
    const patch = {
      startupNotificationsAsked: true,
      weatherAlertsEnabled: true,
    };

    expect(shouldPersistAndroidStartupNotificationPatch({
      notificationResult: {
        receive: "granted",
        requested: true,
      },
      storagePatch: patch,
    })).toBe(true);

    expect(writeAndroidStartupNotificationStoragePatch(patch, { storage })).toBe(true);
    expect(storage.setItem).toHaveBeenCalledWith(
      ANDROID_PERMISSION_STORAGE_KEYS.startupNotificationsAsked,
      "true",
    );
    expect(storage.setItem).toHaveBeenCalledWith(
      ANDROID_PERMISSION_STORAGE_KEYS.weatherAlertsEnabled,
      "true",
    );
  });
});
