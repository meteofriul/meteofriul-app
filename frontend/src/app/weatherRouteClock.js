export function resolveWeatherRouteNow(deviceNow, pilotTestNow = null) {
  const pilotTimestamp = Date.parse(String(pilotTestNow || ""));

  return Number.isFinite(pilotTimestamp) ? new Date(pilotTimestamp) : deviceNow;
}
