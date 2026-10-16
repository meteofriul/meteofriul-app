import { APP_ROUTE_IDS } from "../app/appConfig";

const BULLETIN_NOTIFICATION_TYPES = new Set([
  "official_alert",
  "official_alerts",
  "national_official_alert",
  "local_weather_notice",
  "local_weather_notices",
  "weather_notice",
  "weather_notices",
]);

function normalizeToken(value) {
  return String(value || "").trim().toLowerCase();
}

function routeFromCandidate(value) {
  const candidate = normalizeToken(value);
  if (!candidate) return "";

  if (APP_ROUTE_IDS.includes(candidate)) return candidate;

  try {
    const url = new URL(candidate, "https://app.meteofriul.invalid");
    const queryTab = normalizeToken(url.searchParams.get("tab"));
    if (APP_ROUTE_IDS.includes(queryTab)) return queryTab;

    const pathTab = normalizeToken(url.pathname.split("/").filter(Boolean).at(-1));
    return APP_ROUTE_IDS.includes(pathTab) ? pathTab : "";
  } catch {
    return "";
  }
}

export function getPushNavigationTarget(action, { currentMunicipalityIstat = "" } = {}) {
  const notification = action?.notification || action || {};
  const data = notification?.data && typeof notification.data === "object"
    ? notification.data
    : {};
  const notificationType = normalizeToken(
    data.notification_type || data.type || data.category || data.kind,
  );
  if (notificationType === "national_official_alert") {
    const notifiedIstat = String(data.municipality_istat || "").trim();
    if (!/^\d{6}$/u.test(notifiedIstat)
      || notifiedIstat !== String(currentMunicipalityIstat || "").trim()) {
      // A retained notification must never open another Comune's bulletin.
      return null;
    }
  }
  const explicitRoute = [data.tab, data.route, data.screen, data.deep_link, data.deeplink]
    .map(routeFromCandidate)
    .find(Boolean);

  if (explicitRoute) return { tab: explicitRoute };

  if (BULLETIN_NOTIFICATION_TYPES.has(notificationType)) {
    return { tab: "bulletin" };
  }

  return null;
}
