import { describe, expect, it, vi } from "vitest";

import {
  addWebPushListeners,
  createWebPushRuntime,
  getWebPushErrorDiagnostic,
  getWebPushForegroundContent,
  getWebPushCapability,
  getWebPushRegistrationRetryDelayMs,
  readWebPushPermission,
  registerWebPush,
  requestWebPushPermission,
  shouldRetryWebPushRegistration,
  unregisterWebPush,
  waitForWebPushServiceWorkerActive,
} from "./firebaseWebMessaging";

function configuredMessaging() {
  return {
    appCheckConfigured: true,
    appConfigured: true,
    firebaseConfig: {},
    messagingConfigured: true,
    vapidKey: "public-vapid-key",
    webPushEnrollmentEnabled: true,
  };
}

describe("Firebase Web Messaging", () => {
  it("fails closed when the build or secure browser capability is missing", () => {
    expect(getWebPushCapability({
      config: {
        appCheckConfigured: true,
        messagingConfigured: false,
        webPushEnrollmentEnabled: false,
      },
    })).toMatchObject({
      enrollmentEnabled: false,
      reason: "web_enrollment_disabled",
      supported: false,
    });
    expect(getWebPushCapability({
      config: { appCheckConfigured: true, messagingConfigured: false },
    })).toMatchObject({ reason: "not_configured", supported: false });
    expect(getWebPushCapability({
      config: configuredMessaging(),
      globalObject: { Notification: {}, isSecureContext: false, location: { hostname: "example.test" } },
      navigatorLike: { serviceWorker: {} },
    })).toMatchObject({ reason: "insecure_context", supported: false });
  });

  it("registers the stable local module service worker and creates messaging", async () => {
    const serviceWorkerRegistration = { active: { state: "activated" }, scope: "/" };
    const navigatorLike = {
      serviceWorker: {
        register: vi.fn(async () => serviceWorkerRegistration),
      },
    };
    const messaging = { type: "messaging" };
    const messagingModule = {
      getMessaging: vi.fn(() => messaging),
      isSupported: vi.fn(async () => true),
    };

    const runtime = await createWebPushRuntime({
      config: configuredMessaging(),
      firebaseApp: { name: "web" },
      globalObject: { Notification: {}, isSecureContext: true },
      messagingModule,
      navigatorLike,
    });

    expect(runtime.ok).toBe(true);
    expect(navigatorLike.serviceWorker.register).toHaveBeenCalledWith(
      "/firebase-messaging-sw.js",
      { scope: "/", type: "module", updateViaCache: "none" },
    );
    expect(runtime.serviceWorkerRegistration).toBe(serviceWorkerRegistration);
  });

  it.each(["installing", "waiting"])(
    "waits for a custom %s service worker before creating Firebase messaging",
    async (workerSlot) => {
      let stateChangeHandler;
      const incomingWorker = {
        addEventListener: vi.fn((_, handler) => { stateChangeHandler = handler; }),
        removeEventListener: vi.fn(),
        state: "installing",
      };
      const serviceWorkerRegistration = {
        active: null,
        [workerSlot]: incomingWorker,
        scope: "/",
      };
      const messagingModule = {
        getMessaging: vi.fn(() => ({ type: "messaging" })),
        isSupported: vi.fn(async () => true),
      };
      const runtimePromise = createWebPushRuntime({
        config: configuredMessaging(),
        firebaseApp: { name: "web" },
        globalObject: { Notification: {}, isSecureContext: true },
        messagingModule,
        navigatorLike: {
          serviceWorker: { register: vi.fn(async () => serviceWorkerRegistration) },
        },
      });

      await vi.waitFor(() => {
        expect(incomingWorker.addEventListener).toHaveBeenCalledWith(
          "statechange",
          expect.any(Function),
        );
      });
      expect(messagingModule.getMessaging).not.toHaveBeenCalled();

      incomingWorker.state = "activated";
      stateChangeHandler();

      await expect(runtimePromise).resolves.toMatchObject({ ok: true });
      expect(messagingModule.getMessaging).toHaveBeenCalledTimes(1);
      expect(incomingWorker.removeEventListener).toHaveBeenCalledWith(
        "statechange",
        stateChangeHandler,
      );
    },
  );

  it("fails closed when custom service worker activation times out or becomes redundant", async () => {
    const activeRegistration = { active: { state: "activated" } };
    await expect(waitForWebPushServiceWorkerActive(activeRegistration))
      .resolves.toBe(activeRegistration);
    await expect(waitForWebPushServiceWorkerActive({ active: null })).rejects.toMatchObject({
      code: "web_push_service_worker_missing",
    });

    let timeoutHandler;
    let stateChangeHandler;
    const timerApi = {
      clearTimeout: vi.fn(),
      setTimeout: vi.fn((handler) => { timeoutHandler = handler; return 42; }),
    };
    const incomingWorker = {
      addEventListener: vi.fn((_, handler) => { stateChangeHandler = handler; }),
      removeEventListener: vi.fn(),
      state: "installing",
    };
    const registration = { active: null, installing: incomingWorker };
    const timeoutPromise = waitForWebPushServiceWorkerActive(registration, { timerApi });
    const timeoutAssertion = expect(timeoutPromise).rejects.toMatchObject({
      code: "web_push_service_worker_activation_timeout",
    });

    timeoutHandler();
    await timeoutAssertion;

    const redundantPromise = waitForWebPushServiceWorkerActive(registration, { timerApi });
    const redundantAssertion = expect(redundantPromise).rejects.toMatchObject({
      code: "web_push_service_worker_redundant",
    });
    incomingWorker.state = "redundant";
    stateChangeHandler();
    await redundantAssertion;
  });

  it("sanitizes Web Push errors into an allowlisted code and category", () => {
    expect(getWebPushErrorDiagnostic({
      code: "messaging/fid-registration-failed",
      message: "secret FID and endpoint",
    })).toEqual({
      errorCategory: "fcm",
      errorCode: "messaging/fid-registration-failed",
      errorPhase: "firebase_registration",
      reason: "web_push_fcm_failed",
    });
    expect(getWebPushErrorDiagnostic({
      code: "messaging/unexpected-secret-code",
      message: "must not escape",
    }, { phase: "not-a-real-phase" })).toEqual({
      errorCategory: "unknown",
      errorCode: null,
      errorPhase: "firebase_registration",
      reason: "web_push_registration_failed",
    });
    expect(getWebPushErrorDiagnostic({ name: "InvalidAccessError" })).toMatchObject({
      errorCategory: "vapid",
      errorCode: null,
    });
    expect(getWebPushErrorDiagnostic({
      code: "push_device_http_403",
      serverCode: "push_platform_not_allowed",
    }, { phase: "device_sync" })).toEqual({
      errorCategory: "policy",
      errorCode: "push_device_http_403",
      errorPhase: "device_sync",
      reason: "web_push_enrollment_disabled",
      retryable: false,
    });
    expect(getWebPushErrorDiagnostic({
      code: "push_device_http_403",
      serverCode: "app_check_app_not_allowed",
    }, { phase: "device_sync" })).toMatchObject({
      errorCategory: "app_check",
      reason: "web_push_app_check_failed",
      retryable: false,
    });
  });

  it("uses the FID register/onRegistered contract and can unregister", async () => {
    const callbacks = {};
    const unsubscribe = vi.fn();
    const serviceWorkerContainer = {
      addEventListener: vi.fn((_, callback) => { callbacks.serviceWorkerMessage = callback; }),
      removeEventListener: vi.fn(),
    };
    const messagingModule = {
      onMessage: vi.fn((_, callback) => { callbacks.message = callback; return unsubscribe; }),
      onRegistered: vi.fn((_, callback) => { callbacks.registered = callback; return unsubscribe; }),
      onUnregistered: vi.fn((_, callback) => { callbacks.unregistered = callback; return unsubscribe; }),
      register: vi.fn(async () => {}),
      unregister: vi.fn(async () => {}),
    };
    const runtime = {
      messaging: {},
      messagingModule,
      ok: true,
      serviceWorkerRegistration: { scope: "/" },
      serviceWorkerContainer,
      vapidKey: "public-vapid-key",
    };
    const onNotificationAction = vi.fn();
    const onRegistered = vi.fn();
    const onUnregistered = vi.fn();
    const listeners = addWebPushListeners({
      onNotificationAction,
      onRegistered,
      onUnregistered,
      runtime,
    });

    callbacks.registered(" firebase-installation-id ");
    callbacks.unregistered("firebase-installation-id");
    callbacks.serviceWorkerMessage({
      data: {
        data: { type: "official_alert" },
        isFirebaseMessaging: true,
        messageType: "notification-clicked",
      },
    });
    callbacks.serviceWorkerMessage({
      data: { isFirebaseMessaging: true, messageType: "push-received" },
    });
    await registerWebPush({ runtime });
    await unregisterWebPush({ runtime });
    listeners.remove();

    expect(onRegistered).toHaveBeenCalledWith({ fid: "firebase-installation-id" });
    expect(onUnregistered).toHaveBeenCalledWith({ fid: "firebase-installation-id" });
    expect(onNotificationAction).toHaveBeenCalledTimes(1);
    expect(onNotificationAction).toHaveBeenCalledWith(expect.objectContaining({
      messageType: "notification-clicked",
    }));
    expect(messagingModule.register).toHaveBeenCalledWith(runtime.messaging, {
      serviceWorkerRegistration: runtime.serviceWorkerRegistration,
      vapidKey: "public-vapid-key",
    });
    expect(messagingModule.unregister).toHaveBeenCalledWith(runtime.messaging);
    expect(unsubscribe).toHaveBeenCalledTimes(3);
    expect(serviceWorkerContainer.removeEventListener).toHaveBeenCalledWith(
      "message",
      callbacks.serviceWorkerMessage,
    );
  });

  it("normalizes foreground copy and caps registration retry backoff", () => {
    expect(getWebPushForegroundContent({
      data: { body: "  Nuova   allerta  ", title: " Meteo Friûl " },
    })).toEqual({ body: "Nuova allerta", title: "Meteo Friûl" });
    expect(getWebPushForegroundContent({}, { defaultBody: "Aggiornamento disponibile" }))
      .toEqual({ body: "Aggiornamento disponibile", title: "Meteo Friûl" });
    expect(getWebPushRegistrationRetryDelayMs(1)).toBe(5_000);
    expect(getWebPushRegistrationRetryDelayMs(2)).toBe(15_000);
    expect(getWebPushRegistrationRetryDelayMs(99)).toBe(300_000);
    expect(shouldRetryWebPushRegistration({
      failedAttempts: 1,
      hasRegistration: false,
      notificationsEnabled: true,
      permission: "granted",
      runtimeOk: true,
    })).toBe(true);
    expect(shouldRetryWebPushRegistration({
      failedAttempts: 1,
      hasRegistration: false,
      notificationsEnabled: false,
      permission: "granted",
      runtimeOk: true,
    })).toBe(false);
  });

  it("requests browser permission only through an explicit adapter call", async () => {
    const notificationApi = {
      permission: "default",
      requestPermission: vi.fn(async () => "granted"),
    };

    expect(readWebPushPermission(notificationApi)).toBe("prompt");
    await expect(requestWebPushPermission({ notificationApi })).resolves.toMatchObject({
      receive: "granted",
      requested: true,
    });
    expect(notificationApi.requestPermission).toHaveBeenCalledTimes(1);
  });
});
