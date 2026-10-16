import { FIXED_FVG_PLACES } from "../../data/fvgPlaces";
import { normalizeLocationDataPoint } from "../../domain/geo/locationIdentity";
import { isFvgLocation } from "../../domain/scope/productScope";
import {
  DEVICE_LOCATION_BOUNDARY_MARGIN_M,
  DEVICE_LOCATION_MAX_ACCURACY_M,
} from "../../services/deviceLocation";

const SUPPORTED_MUNICIPALITIES = new Set(
  Object.values(FIXED_FVG_PLACES).map((place) => place.istatCode),
);
const RESOLVED_STATUSES = new Set(["resolved", "municipality_only"]);

function finiteEvidenceNumber(value) {
  if (value == null || value === "" || typeof value === "boolean") return null;
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}

/**
 * Use the session's successful device-resolution result, never the selected,
 * saved or editorial location. Acquisition already checks fix freshness; this
 * presentation gate must not invent a shorter expiry than the GPS runtime.
 */
export function getPilotDetectedMunicipality({
  autoLocationEnabled = false,
  deviceLocationStatus,
} = {}) {
  if (autoLocationEnabled !== true || deviceLocationStatus?.status !== "success") return null;

  const location = deviceLocationStatus.location;
  if (!location || !isFvgLocation(location)) return null;
  const source = String(location.source || "").trim().toLowerCase();
  const isDeviceSource = source === "browser_geolocation"
    || source === "capacitor_geolocation"
    || source.startsWith("android_");
  const municipality = location.municipality;
  const istatCode = String(municipality?.istatCode || "").trim();
  const resolution = location.resolution;
  const dataPoint = normalizeLocationDataPoint(location.dataPoint);
  const accuracyM = finiteEvidenceNumber(location.positionAccuracyM);
  const boundaryDistanceM = finiteEvidenceNumber(resolution?.boundaryDistanceM);
  const countryCode = String(location.countryCode || "").trim().toUpperCase();

  if (
    !isDeviceSource
    || (countryCode && countryCode !== "IT")
    || municipality?.source !== "istat_boundaries"
    || !SUPPORTED_MUNICIPALITIES.has(istatCode)
    || (location.istatCode != null && String(location.istatCode).trim() !== istatCode)
    || resolution?.municipalityResolved !== true
    || !RESOLVED_STATUSES.has(resolution?.status)
    || !dataPoint
    || !["municipality_catalog", "rafvg_irdat_5000"].includes(dataPoint.source)
    || accuracyM === null || accuracyM < 0 || accuracyM > DEVICE_LOCATION_MAX_ACCURACY_M
    || boundaryDistanceM === null
    || accuracyM + DEVICE_LOCATION_BOUNDARY_MARGIN_M >= boundaryDistanceM
    || typeof location.positionCapturedAt !== "string"
    || !Number.isFinite(Date.parse(location.positionCapturedAt))
  ) return null;

  // `nearest` may describe locality selection inside an ISTAT-resolved
  // municipality; municipal containment is established by the checks above.
  return location.istatCode === istatCode ? location : { ...location, istatCode };
}
