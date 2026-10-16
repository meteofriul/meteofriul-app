import { initializeApp } from "firebase/app";
import { getMessaging } from "firebase/messaging/sw";

import { readFirebaseWebConfig } from "./services/firebaseWebConfig";

const config = readFirebaseWebConfig();
globalThis.__MF_WEB_PUSH_ENROLLMENT_ENABLED__ = config.webPushEnrollmentEnabled === true;

if (config.messagingConfigured) {
  const app = initializeApp(config.firebaseConfig, "meteo-friul-messaging-worker");
  getMessaging(app);
}
