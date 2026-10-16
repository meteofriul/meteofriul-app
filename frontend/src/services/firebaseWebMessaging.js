import { NATIVE_PUSH_PERMISSION } from "./nativePushAdapter";
import { getFirebaseWebApp } from "./firebaseWebApp";
import { readFirebaseWebConfig } from "./firebaseWebConfig";

export const FIREBASE_MESSAGING_SERVICE_WORKER_PATH = "/firebase-messaging-sw.js";
export const WEB_PUSH_SERVICE_WORKER_ACTIVATION_TIMEOUT_MS = 10_000;
export const WEB_PUSH_REGISTRATION_RETRY_DELAYS_MS = Object.freeze([
  5_000,
  15_000,
  60_000,
  300_000,
]);

const WEB_PUSH_ERROR_CATEGORY_BY_CODE = Object.freeze({
  "firebase_app_check_token_failed": "app_check",
  "firebase_app_check_token_missing": "app_check",
  "installations/app-offline": "network",
  "installations/installation-not-found": "fcm",
  "installations/missing-app-config-values": "client",
  "installations/not-registered": "fcm",
  "installations/request-failed": "fcm",
  "messaging/failed-service-worker-registration": "service_worker",
  "messaging/fid-registration-failed": "fcm",
  "messaging/fid-registration-idb-schema-unavailable": "storage",
  "messaging/indexed-db-unsupported": "storage",
  "messaging/invalid-on-registered-handler": "client",
  "messaging/invalid-sw-registration": "service_worker",
  "messaging/invalid-vapid-key": "vapid",
  "messaging/permission-blocked": "permission",
  "messaging/permission-default": "permission",
  "messaging/unsupported-browser": "browser",
  "push_device_http_400": "backend",
  "push_device_http_401": "app_check",
  "push_device_http_403": "backend",
  "push_device_http_409": "backend",
  "push_device_http_429": "backend",
  "push_device_http_500": "backend",
  "push_device_http_502": "backend",
  "push_device_http_503": "backend",
  "push_device_http_504": "backend",
  "push_device_network_failed": "network",
  "push_device_registration_failed": "backend",
  "push_fetch_unavailable": "browser",
  "push_installation_id_invalid": "client",
  "push_installation_storage_failed": "storage",
  "push_installation_storage_unavailable": "storage",
  "push_registration_invalid": "client",
  "web_push_service_worker_activation_timeout": "service_worker",
  "web_push_service_worker_missing": "service_worker",
  "web_push_service_worker_redundant": "service_worker",
});

const WEB_PUSH_ERROR_CATEGORY_BY_NAME = Object.freeze({
  AbortError: "network",
  InvalidAccessError: "vapid",
  InvalidStateError: "service_worker",
  NetworkError: "network",
  NotAllowedError: "permission",
  NotSupportedError: "browser",
  QuotaExceededError: "storage",
  SecurityError: "permission",
});

const WEB_PUSH_ERROR_PHASES = new Set([
  "device_sync",
  "firebase_registration",
  "initialization",
]);

const WEB_PUSH_POLICY_SERVER_CODES = new Set([
  "push_platform_not_allowed",
  "push_installation_not_allowed",
  "push_app_version_not_allowed",
]);

export class WebPushRuntimeError extends Error {
  constructor(code, options = {}) {
    super(code, options);
    this.name = "WebPushRuntimeError";
    this.code = code;
  }
}

function normalizeFid(value) {
  return String(value || "").trim();
}

function normalizeMessageText(value) {
  return String(value || "").replace(/\s+/g, " ").trim();
}

export function sanitizeWebPushErrorCode(value) {
  const code = String(value || "").trim().toLowerCase();
  return Object.hasOwn(WEB_PUSH_ERROR_CATEGORY_BY_CODE, code) ? code : "";
}

export function getWebPushErrorDiagnostic(error, { phase = "firebase_registration" } = {}) {
  const errorCode = sanitizeWebPushErrorCode(error?.code);
  const serverCode = String(error?.serverCode || "").trim().toLowerCase();
  const errorName = String(error?.name || "").trim();
  let errorCategory = errorCode
    ? WEB_PUSH_ERROR_CATEGORY_BY_CODE[errorCode]
    : WEB_PUSH_ERROR_CATEGORY_BY_NAME[errorName] || "unknown";
  const errorPhase = WEB_PUSH_ERROR_PHASES.has(phase) ? phase : "firebase_registration";

  if (errorCode === "push_device_http_403") {
    if (WEB_PUSH_POLICY_SERVER_CODES.has(serverCode)) {
      errorCategory = "policy";
    } else if (serverCode === "app_check_app_not_allowed") {
      errorCategory = "app_check";
    }
  }

  if (errorCode === "push_device_http_403" && errorCategory === "policy") {
    return {
      errorCategory,
      errorCode,
      errorPhase,
      reason: "web_push_enrollment_disabled",
      retryable: false,
    };
  }

  const diagnostic = {
    errorCategory,
    errorCode: errorCode || null,
    errorPhase,
    reason: errorCategory === "unknown"
      ? "web_push_registration_failed"
      : `web_push_${errorCategory}_failed`,
  };
  if (errorCode === "push_device_http_403") diagnostic.retryable = false;
  return diagnostic;
}

export function waitForWebPushServiceWorkerActive(registration, {
  timeoutMs = WEB_PUSH_SERVICE_WORKER_ACTIVATION_TIMEOUT_MS,
  timerApi = globalThis,
} = {}) {
  if (registration?.active) return Promise.resolve(registration);

  const incomingWorker = registration?.installing || registration?.waiting;
  if (registration?.active) return Promise.resolve(registration);
  if (!incomingWorker || typeof incomingWorker.addEventListener !== "function") {
    return Promise.reject(new WebPushRuntimeError("web_push_service_worker_missing"));
  }
  if (typeof timerApi?.setTimeout !== "function") {
    return Promise.reject(
      new WebPushRuntimeError("web_push_service_worker_activation_timeout"),
    );
  }

  return new Promise((resolve, reject) => {
    let settled = false;
    let timeoutId = null;
    const finish = (error) => {
      if (settled) return;
      settled = true;
      if (timeoutId != null) timerApi.clearTimeout?.(timeoutId);
      incomingWorker.removeEventListener?.("statechange", handleStateChange);
      if (error) {
        reject(error);
      } else {
        resolve(registration);
      }
    };
    const handleStateChange = () => {
      if (registration.active || incomingWorker.state === "activated") {
        finish();
      } else if (incomingWorker.state === "redundant") {
        finish(new WebPushRuntimeError("web_push_service_worker_redundant"));
      }
    };

    incomingWorker.addEventListener("statechange", handleStateChange);
    timeoutId = timerApi.setTimeout?.(
      () => finish(new WebPushRuntimeError("web_push_service_worker_activation_timeout")),
      Math.max(1, Number(timeoutMs) || WEB_PUSH_SERVICE_WORKER_ACTIVATION_TIMEOUT_MS),
    );
    handleStateChange();
  });
}

export function getWebPushRegistrationRetryDelayMs(failedAttempts) {
  const attemptIndex = Math.max(0, Math.trunc(Number(failedAttempts) || 1) - 1);
  return WEB_PUSH_REGISTRATION_RETRY_DELAYS_MS[
    Math.min(attemptIndex, WEB_PUSH_REGISTRATION_RETRY_DELAYS_MS.length - 1)
  ];
}

export function shouldRetryWebPushRegistration({
  failedAttempts,
  hasRegistration,
  notificationsEnabled,
  permission,
  runtimeOk,
} = {}) {
  return Number(failedAttempts) > 0 &&
    !hasRegistration &&
    notificationsEnabled === true &&
    permission === NATIVE_PUSH_PERMISSION.granted &&
    runtimeOk === true;
}

export function getWebPushForegroundContent(payload, {
  defaultBody = "",
  defaultTitle = "Meteo Friûl",
} = {}) {
  const notification = payload?.notification && typeof payload.notification === "object"
    ? payload.notification
    : {};
  const data = payload?.data && typeof payload.data === "object" ? payload.data : {};

  return {
    body: normalizeMessageText(notification.body || data.body || defaultBody),
    title: normalizeMessageText(notification.title || data.title || defaultTitle),
  };
}

function isLocalDevelopmentOrigin(locationLike) {
  const hostname = String(locationLike?.hostname || "").trim().toLowerCase();
  return hostname === "localhost" || hostname === "127.0.0.1" || hostname === "[::1]";
}

export function getWebPushCapability({
  config = readFirebaseWebConfig(),
  globalObject = globalThis,
  navigatorLike = globalThis.navigator,
} = {}) {
  if (config.webPushEnrollmentEnabled === false) {
    return {
      configured: true,
      enrollmentEnabled: false,
      reason: "web_enrollment_disabled",
      supported: false,
    };
  }
  if (!config.messagingConfigured || !config.appCheckConfigured) {
    return { configured: false, reason: "not_configured", supported: false };
  }
  if (!globalObject?.Notification || !navigatorLike?.serviceWorker) {
    return { configured: true, reason: "browser_unsupported", supported: false };
  }
  if (!globalObject.isSecureContext && !isLocalDevelopmentOrigin(globalObject.location)) {
    return { configured: true, reason: "insecure_context", supported: false };
  }

  return { configured: true, reason: null, supported: true };
}

export function readWebPushPermission(notificationApi = globalThis.Notification) {
  const permission = String(notificationApi?.permission || "").trim().toLowerCase();
  if (permission === "granted") return NATIVE_PUSH_PERMISSION.granted;
  if (permission === "denied") return NATIVE_PUSH_PERMISSION.denied;
  if (permission === "default") return NATIVE_PUSH_PERMISSION.prompt;
  return NATIVE_PUSH_PERMISSION.unsupported;
}

export async function createWebPushRuntime({
  config = readFirebaseWebConfig(),
  firebaseApp,
  globalObject = globalThis,
  messagingModule,
  navigatorLike = globalThis.navigator,
} = {}) {
  const capability = getWebPushCapability({ config, globalObject, navigatorLike });
  if (!capability.supported) return { ...capability, ok: false };

  const module = messagingModule || await import("firebase/messaging");
  const supported = await module.isSupported();
  if (!supported) {
    return { configured: true, ok: false, reason: "browser_unsupported", supported: false };
  }

  const serviceWorkerRegistration = await navigatorLike.serviceWorker.register(
    FIREBASE_MESSAGING_SERVICE_WORKER_PATH,
    {
      scope: "/",
      type: "module",
      updateViaCache: "none",
    },
  );
  await waitForWebPushServiceWorkerActive(serviceWorkerRegistration);
  const app = firebaseApp || await getFirebaseWebApp({ config });

  return {
    configured: true,
    messaging: module.getMessaging(app),
    messagingModule: module,
    ok: true,
    reason: null,
    serviceWorkerRegistration,
    serviceWorkerContainer: navigatorLike.serviceWorker,
    supported: true,
    vapidKey: config.vapidKey,
  };
}

export async function requestWebPushPermission({
  notificationApi = globalThis.Notification,
} = {}) {
  if (typeof notificationApi?.requestPermission !== "function") {
    return {
      reason: "browser_unsupported",
      receive: NATIVE_PUSH_PERMISSION.unsupported,
      requested: false,
    };
  }

  const permission = await notificationApi.requestPermission();
  return {
    reason: null,
    receive: readWebPushPermission({ permission }),
    requested: true,
  };
}

export function addWebPushListeners({
  onMessage,
  onNotificationAction,
  onRegistered,
  onUnregistered,
  runtime,
} = {}) {
  if (!runtime?.ok || !runtime.messaging || !runtime.messagingModule) {
    return { ok: false, reason: "web_push_runtime_unavailable", remove: () => {} };
  }

  const remove = [
    runtime.messagingModule.onRegistered(runtime.messaging, (fid) => {
      const normalized = normalizeFid(fid);
      if (normalized) onRegistered?.({ fid: normalized });
    }),
    runtime.messagingModule.onUnregistered(runtime.messaging, (fid) => {
      onUnregistered?.({ fid: normalizeFid(fid) });
    }),
    runtime.messagingModule.onMessage(runtime.messaging, (payload) => {
      onMessage?.(payload);
    }),
  ];
  const serviceWorkerContainer = runtime.serviceWorkerContainer || globalThis.navigator?.serviceWorker;
  const handleServiceWorkerMessage = (event) => {
    const message = event?.data;
    if (
      message?.isFirebaseMessaging === true &&
      message?.messageType === "notification-clicked"
    ) {
      onNotificationAction?.(message);
    }
  };
  serviceWorkerContainer?.addEventListener?.("message", handleServiceWorkerMessage);

  return {
    ok: true,
    remove: () => {
      remove.forEach((unsubscribe) => unsubscribe?.());
      serviceWorkerContainer?.removeEventListener?.("message", handleServiceWorkerMessage);
    },
  };
}

export async function registerWebPush({ runtime } = {}) {
  if (!runtime?.ok || typeof runtime.messagingModule?.register !== "function") {
    return { ok: false, reason: "web_push_runtime_unavailable" };
  }

  await runtime.messagingModule.register(runtime.messaging, {
    serviceWorkerRegistration: runtime.serviceWorkerRegistration,
    vapidKey: runtime.vapidKey,
  });
  return { ok: true };
}

export async function unregisterWebPush({ runtime } = {}) {
  if (!runtime?.ok || typeof runtime.messagingModule?.unregister !== "function") {
    return { ok: false, reason: "web_push_runtime_unavailable" };
  }

  await runtime.messagingModule.unregister(runtime.messaging);
  return { ok: true };
}
