import { readFile } from "node:fs/promises";
import { webcrypto } from "node:crypto";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import vm from "node:vm";

const configuredBuildDirectory = String(process.argv[2] || "").trim();
const serviceWorkerPath = configuredBuildDirectory
  ? resolve(configuredBuildDirectory, "firebase-messaging-sw.js")
  : fileURLToPath(new URL("../dist/firebase-messaging-sw.js", import.meta.url));
const source = await readFile(serviceWorkerPath, "utf8");

if (/^\s*import(?:\s|["'{*])/mu.test(source)) {
  throw new Error("firebase-messaging-sw.js contiene ancora import statici di chunk condivisi.");
}

const listeners = new Map();
const contextObject = {
  atob,
  btoa,
  clearTimeout,
  console,
  crypto: webcrypto,
  fetch,
  Headers,
  Notification: function Notification() {},
  navigator: { onLine: true },
  Promise,
  PushSubscription: function PushSubscription() {},
  queueMicrotask,
  Request,
  Response,
  ServiceWorkerRegistration: function ServiceWorkerRegistration() {},
  setTimeout,
  TextDecoder,
  TextEncoder,
  URL,
};

contextObject.PushSubscription.prototype.getKey = () => new ArrayBuffer(0);
contextObject.ServiceWorkerRegistration.prototype.showNotification = () => Promise.resolve();
contextObject.addEventListener = (type, listener) => {
  listeners.set(type, listener);
};
contextObject.clients = {
  matchAll: async () => [],
  openWindow: async () => null,
};
contextObject.location = new URL("https://example.test/firebase-messaging-sw.js");
contextObject.registration = {
  getNotifications: async () => [],
  showNotification: async () => {},
};
contextObject.self = contextObject;

const context = vm.createContext(contextObject, {
  name: "meteo-friul-service-worker-build-check",
});
const unexpectedRejections = [];
const handleUnhandledRejection = (reason) => {
  if (reason?.code !== "messaging/unsupported-browser") {
    unexpectedRejections.push(reason);
  }
};

process.on("unhandledRejection", handleUnhandledRejection);
try {
  new vm.Script(source, { filename: serviceWorkerPath }).runInContext(context);
  await new Promise((resolve) => setImmediate(resolve));
  await new Promise((resolve) => setImmediate(resolve));
} finally {
  process.off("unhandledRejection", handleUnhandledRejection);
}

if (unexpectedRejections.length > 0) {
  throw new Error("firebase-messaging-sw.js ha prodotto un errore asincrono nel contesto worker.");
}

const webPushEnrollmentEnabled = contextObject.__MF_WEB_PUSH_ENROLLMENT_ENABLED__ === true;
const messagingEventTypes = ["notificationclick", "push", "pushsubscriptionchange"];
if (webPushEnrollmentEnabled) {
  for (const eventType of messagingEventTypes) {
    if (typeof listeners.get(eventType) !== "function") {
      throw new Error(`firebase-messaging-sw.js non ha registrato l'evento ${eventType}.`);
    }
  }
} else if (messagingEventTypes.some((eventType) => listeners.has(eventType))) {
  throw new Error("firebase-messaging-sw.js ha attivato Firebase con enrollment Web disabilitato.");
}

console.log(
  `firebase-messaging-sw.js: standalone; enrollment Web ${webPushEnrollmentEnabled ? "attivo" : "disabilitato"}.`,
);
