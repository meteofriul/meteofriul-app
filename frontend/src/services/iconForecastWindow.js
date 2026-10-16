// Pilot usage policy, separate from the immutable weather-v1 wire contract.
// Count actual hourly timestamps, not padded/interpolated duration estimates.
export const ICON_FORECAST_WINDOW_POLICY = Object.freeze({
  minimumFutureHours: 12,
  maximumFutureHours: 48,
  currentSampleMaxLagMs: 60 * 60 * 1000,
});

const HOUR_MS = 60 * 60 * 1000;

export function countIconFutureHours(validTo, nowMilliseconds) {
  const end = typeof validTo === "number" ? validTo : Date.parse(validTo);
  if (!Number.isFinite(end) || !Number.isFinite(nowMilliseconds)) return 0;
  const firstFutureHour = Math.ceil(nowMilliseconds / HOUR_MS) * HOUR_MS;
  return Math.max(0, Math.floor((end - firstFutureHour) / HOUR_MS) + 1);
}

export function selectIconFutureRows(rows, nowMilliseconds, timeKey = "valid_at") {
  if (!Array.isArray(rows) || !Number.isFinite(nowMilliseconds)) return [];
  let previous = null;
  const future = [];
  for (const row of rows) {
    const time = Date.parse(row?.[timeKey]);
    // A verified ICON series is hourly, ordered and gap-free. Never repair it.
    if (!Number.isFinite(time) || time % HOUR_MS !== 0
      || (previous !== null && time - previous !== HOUR_MS)) return [];
    previous = time;
    if (time >= nowMilliseconds && future.length < ICON_FORECAST_WINDOW_POLICY.maximumFutureHours) {
      future.push(row);
    }
  }
  return future;
}
