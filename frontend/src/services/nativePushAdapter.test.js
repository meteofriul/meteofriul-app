import { describe, expect, it, vi } from "vitest";

import {
  DEFAULT_NATIVE_PUSH_ANDROID_CHANNEL,
  DEFAULT_NATIVE_PUSH_ANDROID_CHANNELS,
  DEFAULT_NATIVE_PUSH_NATIONAL_ANDROID_CHANNEL,
  NATIVE_PUSH_NATIONAL_CHANNEL_ID,
  NATIVE_PUSH_CHANNEL_ID,
  NATIVE_PUSH_PERMISSION,
  NATIVE_PUSH_PLUGIN_NAME,
  addNativePushListeners,
  checkNativePushPermission,
  createNativePushRuntime,
  ensureNativePushAndroidChannel,
  getNativePushNotificationsPlugin,
  normalizeNativePushPermission,
  openNativeNotificationSettings,
  registerNativePush,
  requestNativePushPermission,
  unregisterNativePush,
} from "./nativePushAdapter";

describe("nativePushAdapter", () => {
  it("keeps Firebase push disabled in the Android local pilot", () => {
    const pushNotifications = { register: vi.fn() };
    const capacitor = {
      getPlatform: vi.fn(() => "android"),
      isNativePlatform: vi.fn(() => true),
      isPluginAvailable: vi.fn(() => true),
    };

    expect(getNativePushNotificationsPlugin({
      capacitor,
      localPilot: true,
      pushNotifications,
    })).toBeNull();
    expect(capacitor.isPluginAvailable).not.toHaveBeenCalled();
    expect(pushNotifications.register).not.toHaveBeenCalled();
  });

  it("keeps the production Android push plugin available", () => {
    const pushNotifications = { register: vi.fn() };
    const capacitor = {
      getPlatform: vi.fn(() => "android"),
      isNativePlatform: vi.fn(() => true),
      isPluginAvailable: vi.fn(() => true),
    };

    expect(getNativePushNotificationsPlugin({
      capacitor,
      localPilot: false,
      pushNotifications,
    })).toBe(pushNotifications);
    expect(capacitor.isPluginAvailable).toHaveBeenCalledWith(NATIVE_PUSH_PLUGIN_NAME);
  });

  it("wraps the Capacitor proxy so Promise resolution never calls plugin then()", async () => {
    const pushNotifications = {
      then: vi.fn(() => {
        throw new Error("native then must not run");
      }),
    };

    const runtime = await Promise.resolve(createNativePushRuntime(pushNotifications));

    expect(runtime.pushNotifications).toBe(pushNotifications);
    expect(pushNotifications.then).not.toHaveBeenCalled();
  });

  it("normalizes Capacitor permission payloads", () => {
    expect(normalizeNativePushPermission({ receive: "granted" })).toEqual({
      receive: NATIVE_PUSH_PERMISSION.granted,
    });
    expect(normalizeNativePushPermission({ receive: "default" })).toEqual({
      receive: NATIVE_PUSH_PERMISSION.prompt,
    });
    expect(normalizeNativePushPermission({ receive: "prompt-with-rationale" })).toEqual({
      receive: NATIVE_PUSH_PERMISSION.prompt,
    });
    expect(normalizeNativePushPermission("denied")).toEqual({
      receive: NATIVE_PUSH_PERMISSION.denied,
    });
  });

  it("reports unsupported when the native push plugin is missing", async () => {
    await expect(checkNativePushPermission()).resolves.toEqual({
      available: false,
      receive: NATIVE_PUSH_PERMISSION.unsupported,
    });

    await expect(requestNativePushPermission()).resolves.toEqual({
      available: false,
      receive: NATIVE_PUSH_PERMISSION.unsupported,
      requested: false,
    });
  });

  it("does not re-request permission when already granted", async () => {
    const pushNotifications = {
      checkPermissions: vi.fn(async () => ({ receive: "granted" })),
      requestPermissions: vi.fn(),
    };

    await expect(requestNativePushPermission({ pushNotifications })).resolves.toEqual({
      available: true,
      receive: NATIVE_PUSH_PERMISSION.granted,
      requested: false,
    });

    expect(pushNotifications.requestPermissions).not.toHaveBeenCalled();
  });

  it("requests native permission only when Capacitor reports prompt", async () => {
    const pushNotifications = {
      checkPermissions: vi.fn(async () => ({ receive: "prompt" })),
      requestPermissions: vi.fn(async () => ({ receive: "denied" })),
    };

    await expect(requestNativePushPermission({ pushNotifications })).resolves.toEqual({
      available: true,
      receive: NATIVE_PUSH_PERMISSION.denied,
      requested: true,
    });

    expect(pushNotifications.checkPermissions).toHaveBeenCalledTimes(1);
    expect(pushNotifications.requestPermissions).toHaveBeenCalledTimes(1);
  });

  it("requests native permission when Android asks for a rationale", async () => {
    const pushNotifications = {
      checkPermissions: vi.fn(async () => ({ receive: "prompt-with-rationale" })),
      requestPermissions: vi.fn(async () => ({ receive: "granted" })),
    };

    await expect(requestNativePushPermission({ pushNotifications })).resolves.toEqual({
      available: true,
      receive: NATIVE_PUSH_PERMISSION.granted,
      requested: true,
    });
    expect(pushNotifications.requestPermissions).toHaveBeenCalledTimes(1);
  });

  it("opens the Android app notification settings through the native plugin", async () => {
    const notificationSettings = {
      openSettings: vi.fn(async () => undefined),
    };
    const capacitor = {
      getPlatform: vi.fn(() => "android"),
      isNativePlatform: vi.fn(() => true),
      isPluginAvailable: vi.fn(() => true),
    };

    await expect(openNativeNotificationSettings({
      capacitor,
      notificationSettings,
    })).resolves.toEqual({ ok: true });
    expect(notificationSettings.openSettings).toHaveBeenCalledTimes(1);
  });

  it("does not open notification settings outside Android", async () => {
    const notificationSettings = {
      openSettings: vi.fn(async () => undefined),
    };
    const capacitor = {
      getPlatform: vi.fn(() => "web"),
      isNativePlatform: vi.fn(() => false),
      isPluginAvailable: vi.fn(() => true),
    };

    await expect(openNativeNotificationSettings({
      capacitor,
      notificationSettings,
    })).resolves.toEqual({ ok: false, reason: "not_android" });
    expect(notificationSettings.openSettings).not.toHaveBeenCalled();
  });

  it("creates the Android notification channel only on Android", async () => {
    const pushNotifications = {
      createChannel: vi.fn(async () => undefined),
    };

    await expect(ensureNativePushAndroidChannel({
      platform: "ios",
      pushNotifications,
    })).resolves.toEqual({
      ok: true,
      skipped: true,
      reason: "not_android",
    });

    await expect(ensureNativePushAndroidChannel({
      platform: "android",
      pushNotifications,
    })).resolves.toEqual({
      ok: true,
      channelId: NATIVE_PUSH_CHANNEL_ID,
    });

    expect(pushNotifications.createChannel).toHaveBeenCalledWith(DEFAULT_NATIVE_PUSH_ANDROID_CHANNEL);
  });

  it("keeps national alerts on a distinct, municipality-scoped Android channel", () => {
    expect(DEFAULT_NATIVE_PUSH_NATIONAL_ANDROID_CHANNEL).toMatchObject({
      id: NATIVE_PUSH_NATIONAL_CHANNEL_ID,
      importance: 4,
    });
    expect(DEFAULT_NATIVE_PUSH_NATIONAL_ANDROID_CHANNEL.description).toContain("Comune italiano selezionato");
    expect(DEFAULT_NATIVE_PUSH_ANDROID_CHANNELS).toContain(DEFAULT_NATIVE_PUSH_NATIONAL_ANDROID_CHANNEL);
    expect(NATIVE_PUSH_NATIONAL_CHANNEL_ID).not.toBe(NATIVE_PUSH_CHANNEL_ID);
  });

  it("registers and unregisters through the native plugin without backend side effects", async () => {
    const pushNotifications = {
      register: vi.fn(async () => undefined),
      unregister: vi.fn(async () => undefined),
    };

    await expect(registerNativePush({ pushNotifications })).resolves.toEqual({ ok: true });
    await expect(unregisterNativePush({ pushNotifications })).resolves.toEqual({ ok: true });

    expect(pushNotifications.register).toHaveBeenCalledTimes(1);
    expect(pushNotifications.unregister).toHaveBeenCalledTimes(1);
  });

  it("forwards registration tokens only to the provided callback", async () => {
    const removeRegistration = vi.fn(async () => undefined);
    const removeError = vi.fn(async () => undefined);
    const listeners = {};
    const pushNotifications = {
      addListener: vi.fn(async (eventName, callback) => {
        listeners[eventName] = callback;
        return {
          remove: eventName === "registration" ? removeRegistration : removeError,
        };
      }),
    };
    const onRegistration = vi.fn();
    const onRegistrationError = vi.fn();

    const listenerHandle = await addNativePushListeners({
      onRegistration,
      onRegistrationError,
      pushNotifications,
    });

    expect(listenerHandle.ok).toBe(true);
    listeners.registration({ value: "token-123" });
    listeners.registrationError({ error: "boom" });

    expect(onRegistration).toHaveBeenCalledWith({
      token: "token-123",
    });
    expect(onRegistrationError).toHaveBeenCalledWith({ error: "boom" });

    await listenerHandle.remove();
    expect(removeRegistration).toHaveBeenCalledTimes(1);
    expect(removeError).toHaveBeenCalledTimes(1);
  });

  it("forwards foreground notifications and tap actions without displaying a second banner", async () => {
    const listeners = {};
    const pushNotifications = {
      addListener: vi.fn(async (eventName, callback) => {
        listeners[eventName] = callback;
        return { remove: vi.fn(async () => undefined) };
      }),
    };
    const onNotificationReceived = vi.fn();
    const onNotificationAction = vi.fn();

    await addNativePushListeners({
      onNotificationAction,
      onNotificationReceived,
      pushNotifications,
    });
    listeners.pushNotificationReceived({ id: "foreground-1" });
    listeners.pushNotificationActionPerformed({ notification: { data: { tab: "bulletin" } } });

    expect(onNotificationReceived).toHaveBeenCalledWith({ id: "foreground-1" });
    expect(onNotificationAction).toHaveBeenCalledWith({
      notification: { data: { tab: "bulletin" } },
    });
  });
});
