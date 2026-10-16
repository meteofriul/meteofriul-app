import { isIconLocalPilotWeather } from "./normalizedWeather";

const HOUR_MS = 60 * 60 * 1000;

function firstBoolean(...values) {
  return values.find((value) => typeof value === "boolean") ?? null;
}

function firstText(...values) {
  const value = values.find((entry) => typeof entry === "string" && entry.trim());
  return value ? value.trim() : null;
}

function getProviderDelivery(provider = {}) {
  const evidence = provider.evidence || {};
  const delivery = provider.delivery || evidence.delivery || {};
  const fromCache = firstBoolean(
    delivery.from_cache,
    delivery.fromCache,
    evidence.from_cache,
    evidence.fromCache,
  );
  const networkFallback = firstBoolean(
    delivery.network_fallback,
    delivery.networkFallback,
    evidence.network_fallback,
    evidence.networkFallback,
  );
  const notModified = firstBoolean(
    delivery.not_modified,
    delivery.notModified,
    evidence.not_modified,
    evidence.notModified,
  );
  const cachePersisted = firstBoolean(
    delivery.cache_persisted,
    delivery.cachePersisted,
    evidence.cache_persisted,
    evidence.cachePersisted,
  );
  const fallbackReason = firstText(
    delivery.fallback_reason,
    delivery.fallbackReason,
    evidence.fallback_reason,
    evidence.fallbackReason,
  );
  const provenance = networkFallback
    ? fallbackReason === "transport_failure" ? "offline_cache" : "network_fallback_cache"
    : fromCache ? notModified === true || networkFallback === false ? "validated_cache" : "cache"
      : fromCache === false ? "network" : "unknown";
  return {
    provenance,
    from_cache: fromCache,
    network_fallback: networkFallback,
    fallback_reason: fallbackReason,
    not_modified: notModified,
    cache_persisted: cachePersisted,
  };
}

function getProviderFreshness(provider = {}) {
  const freshness = provider.evidence?.freshness || provider.freshness || {};
  return freshness && typeof freshness === "object" ? { ...freshness } : {};
}

export function getLocalPilotFreshness(metadata, now = Date.now()) {
  const runTime = metadata?.run_utc ? Date.parse(metadata.run_utc) : NaN;
  const startTime = metadata?.first_forecast_at_utc ? Date.parse(metadata.first_forecast_at_utc) : NaN;
  const endTime = metadata?.last_forecast_at_utc ? Date.parse(metadata.last_forecast_at_utc) : NaN;
  const nowTime = Number(new Date(now));
  const ageHours = Number.isFinite(runTime) ? (nowTime - runTime) / HOUR_MS : null;
  const coverageHours = Number.isFinite(endTime) ? Math.max(0, (endTime - nowTime) / HOUR_MS) : null;
  const declaredPointCount = Number(metadata?.forecast_point_count);
  const pointCount = Number.isSafeInteger(declaredPointCount) && declaredPointCount >= 0
    ? declaredPointCount : null;
  const currentHour = Number.isFinite(nowTime) ? Math.floor(nowTime / HOUR_MS) * HOUR_MS : NaN;
  const remainingTimelinePoints = Number.isFinite(startTime) && Number.isFinite(endTime)
    && Number.isFinite(currentHour) && endTime >= Math.max(startTime, currentHour)
    ? Math.floor((endTime - Math.max(startTime, currentHour)) / HOUR_MS) + 1
    : null;
  const forecastPointCount = pointCount === null
    ? remainingTimelinePoints
    : remainingTimelinePoints === null ? pointCount : Math.min(pointCount, remainingTimelinePoints);
  const expired = ageHours !== null && ageHours > 30 || coverageHours !== null && coverageHours <= 0;
  return {
    ageHours,
    coverageHours,
    forecastPointCount,
    forecastIntervalCount: forecastPointCount === null ? null : Math.max(0, forecastPointCount - 1),
    label: !metadata ? "In attesa dello snapshot locale"
      : expired ? "Snapshot ICON scaduto"
        : metadata.status === "stale" || ageHours !== null && ageHours > 18
          ? "Snapshot ICON datato" : "Snapshot ICON di prova",
  };
}

export function buildLocalWeatherPilotMetadata(current) {
  if (!isIconLocalPilotWeather(current)) return null;
  const raw = current.raw || current;
  const quality = raw.data_quality || current.dataQuality || {};
  const hourly = raw.hourly_forecast || current.hourlyForecast || [];
  const pollen = raw.pollen_data || current.pollenData || {};
  const iconSource = raw.source?.icon || current.source?.icon || {};
  const camsSource = raw.source?.cams || current.source?.cams || {};
  const pollenStatus = String(pollen.status || "").trim().toLowerCase();
  const qualityStatus = String(quality.cams_status || "").trim().toLowerCase();
  const sourceStatus = String(camsSource.status || "").trim().toLowerCase();
  const camsStatuses = [pollenStatus, qualityStatus, sourceStatus];
  const camsUnavailable = camsStatuses
    .some((status) => ["error", "missing", "unavailable"].includes(status));
  const camsPending = !camsUnavailable && camsStatuses.includes("pending");
  const camsAvailable = !camsUnavailable && !camsPending && (
    pollenStatus === "experimental_model_snapshot" || sourceStatus === "available"
  );
  const timestamps = [...new Set(hourly
    .filter((slot) => slot?.temperature !== null && slot?.temperature !== undefined)
    .map((slot) => Date.parse(slot?.time))
    .filter(Number.isFinite))].sort((left, right) => left - right);
  const iconFreshness = getProviderFreshness(iconSource);
  const camsFreshness = getProviderFreshness(camsSource);
  const camsFreshnessStatus = firstText(
    qualityStatus === "unavailable" ? null : qualityStatus,
    pollen.freshness,
    camsFreshness.status,
  );
  return {
    ...quality,
    first_forecast_at_utc: timestamps.length ? new Date(timestamps[0]).toISOString() : null,
    last_forecast_at_utc: timestamps.length ? new Date(Math.max(...timestamps)).toISOString() : null,
    forecast_point_count: timestamps.length,
    forecast_interval_count: Math.max(0, timestamps.length - 1),
    icon_delivery: getProviderDelivery(iconSource),
    icon_freshness: iconFreshness,
    cams_available: camsAvailable,
    cams_pending: camsPending,
    cams_status: camsUnavailable ? "unavailable" : camsPending ? "pending" : camsFreshnessStatus,
    cams_product_status: pollen.status || null,
    cams_delivery: getProviderDelivery(camsSource),
    cams_freshness: {
      ...camsFreshness,
      status: camsUnavailable || camsPending ? null : camsFreshnessStatus,
    },
    cams_diagnostic: pollen.diagnostic || quality.cams_diagnostic || camsSource.diagnostic || null,
  };
}
