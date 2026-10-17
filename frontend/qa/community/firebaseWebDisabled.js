// This Android-only QA entry must never initialize production Web Firebase.
export const FIREBASE_WEB_PRODUCTION_PUBLIC_CONFIG = Object.freeze({});
export function readFirebaseWebConfig() { return { appConfigured: false, appCheckConfigured: false, messagingConfigured: false, webPushEnrollmentEnabled: false }; }
export function isFirebaseWebAppCheckConfigured() { return false; }
export function isFirebaseWebMessagingConfigured() { return false; }
