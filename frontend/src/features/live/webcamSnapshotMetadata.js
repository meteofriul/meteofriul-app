export const WEBCAM_SNAPSHOT_METADATA_TIMEOUT_MS = 8000;
export const WEBCAM_SNAPSHOT_RECENT_MAX_AGE_MS = 30 * 60 * 1000;
const WEBCAM_SNAPSHOT_FUTURE_TOLERANCE_MS = 2 * 60 * 1000;
const WEBCAM_SNAPSHOT_TIME_ZONE = "Europe/Rome";

function getCalendarKey(date) {
  return new Intl.DateTimeFormat("en-CA", {
    day: "2-digit",
    month: "2-digit",
    timeZone: WEBCAM_SNAPSHOT_TIME_ZONE,
    year: "numeric",
  }).format(date);
}

function normalizeSnapshotUrl(imageUrl) {
  if (typeof imageUrl !== "string" || !/^https:\/\//i.test(imageUrl.trim())) return "";

  try {
    const url = new URL(imageUrl.trim());
    if (url.protocol !== "https:" || !url.hostname || url.username || url.password) return "";
    return url.href;
  } catch {
    return "";
  }
}

function normalizeLastModified(lastModified) {
  if (typeof lastModified !== "string" || !lastModified.trim()) return "";

  const timestamp = Date.parse(lastModified);
  if (!Number.isFinite(timestamp)) return "";

  try {
    return new Date(timestamp).toISOString();
  } catch {
    return "";
  }
}

export function getWebcamSnapshotBadgeLabel({
  copy,
  language = "it",
  now = new Date(),
  updatedAt,
}) {
  const updatedDate = new Date(updatedAt || "");
  const currentDate = now instanceof Date ? now : new Date(now);
  if (Number.isNaN(updatedDate.getTime())) return copy.webcamSnapshotLatest;

  const locale = language === "fur" ? "fur-IT" : "it-IT";
  const time = new Intl.DateTimeFormat(locale, {
    hour: "2-digit",
    hour12: false,
    minute: "2-digit",
    timeZone: WEBCAM_SNAPSHOT_TIME_ZONE,
  }).format(updatedDate);
  const sameDay = !Number.isNaN(currentDate.getTime())
    && getCalendarKey(updatedDate) === getCalendarKey(currentDate);

  if (sameDay) return copy.webcamSnapshotUpdatedAt.replace("{time}", time);

  const date = new Intl.DateTimeFormat(locale, {
    day: "2-digit",
    month: "2-digit",
    timeZone: WEBCAM_SNAPSHOT_TIME_ZONE,
  }).format(updatedDate);
  return copy.webcamSnapshotUpdatedOn
    .replace("{date}", date)
    .replace("{time}", time);
}

export function isWebcamSnapshotRecent({
  maxAgeMs = WEBCAM_SNAPSHOT_RECENT_MAX_AGE_MS,
  now = new Date(),
  updatedAt,
} = {}) {
  const updatedTime = new Date(updatedAt || "").getTime();
  const currentTime = (now instanceof Date ? now : new Date(now)).getTime();
  const safeMaxAgeMs = Number.isFinite(maxAgeMs) && maxAgeMs >= 0
    ? maxAgeMs
    : WEBCAM_SNAPSHOT_RECENT_MAX_AGE_MS;
  if (!Number.isFinite(updatedTime) || !Number.isFinite(currentTime)) return false;

  const ageMs = currentTime - updatedTime;
  return ageMs >= -WEBCAM_SNAPSHOT_FUTURE_TOLERANCE_MS && ageMs <= safeMaxAgeMs;
}

export async function fetchWebcamSnapshotUpdatedAt(imageUrl, {
  fetchImpl = globalThis.fetch,
  timeoutMs = WEBCAM_SNAPSHOT_METADATA_TIMEOUT_MS,
  AbortControllerClass = globalThis.AbortController,
} = {}) {
  const snapshotUrl = normalizeSnapshotUrl(imageUrl);
  if (!snapshotUrl || typeof fetchImpl !== "function") return "";

  const safeTimeoutMs = Number.isFinite(timeoutMs) && timeoutMs > 0
    ? timeoutMs
    : WEBCAM_SNAPSHOT_METADATA_TIMEOUT_MS;
  let controller = null;
  let timeoutId = null;

  try {
    controller = typeof AbortControllerClass === "function"
      ? new AbortControllerClass()
      : null;
    if (controller) {
      timeoutId = globalThis.setTimeout(() => controller.abort(), safeTimeoutMs);
    }

    const response = await fetchImpl(snapshotUrl, {
      method: "HEAD",
      mode: "cors",
      credentials: "omit",
      referrerPolicy: "no-referrer",
      cache: "no-store",
      ...(controller ? { signal: controller.signal } : {}),
    });

    if (!response?.ok || typeof response.headers?.get !== "function") return "";
    return normalizeLastModified(response.headers.get("last-modified"));
  } catch {
    return "";
  } finally {
    if (timeoutId !== null) globalThis.clearTimeout(timeoutId);
  }
}
