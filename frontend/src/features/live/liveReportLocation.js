import { FIXED_FVG_PLACES } from "../../data/fvgPlaces";
import { isLocalCommunityPilot } from "../../services/localCommunityPilot";
import {
  getCommunityVote,
  getOwnCommunityReport,
} from "./communityPersonalState";

export const LIVE_REPORT_MAX_DISTANCE_KM = 5;
export const LIVE_REPORT_LOCATION_OPTION_LIMIT = 2;
export const LIVE_REPORT_MAX_ACCURACY_M = 1000;
export const LIVE_REPORT_MAX_AGE_MS = 2 * 60 * 1000;

export const LIVE_REPORT_LOCATIONS = Object.freeze(
  Object.values(FIXED_FVG_PLACES)
    .map((place) => ({
      lat: Number(place.latitude),
      lon: Number(place.longitude),
      place: place.name,
    }))
    .filter((place) => Number.isFinite(place.lat) && Number.isFinite(place.lon))
    .sort((first, second) => first.place.localeCompare(second.place, "it")),
);

const FVG_REPORT_BOUNDS = Object.freeze({
  latMax: 46.72,
  latMin: 45.52,
  lonMax: 14.08,
  lonMin: 12.24,
});

export function getLiveReportDistanceKm(first, second) {
  const toRadians = (value) => (value * Math.PI) / 180;
  const latDelta = toRadians(second.lat - first.lat);
  const lonDelta = toRadians(second.lon - first.lon);
  const firstLat = toRadians(first.lat);
  const secondLat = toRadians(second.lat);
  const value = Math.sin(latDelta / 2) ** 2
    + Math.cos(firstLat) * Math.cos(secondLat) * Math.sin(lonDelta / 2) ** 2;
  const clamped = Math.min(1, Math.max(0, value));

  return 6371 * 2 * Math.atan2(Math.sqrt(clamped), Math.sqrt(1 - clamped));
}

export function findNearbyMatchingCommunityGroups(
  groups,
  {
    coords,
    maxDistanceKm = LIVE_REPORT_MAX_DISTANCE_KM,
    now = Date.now(),
    typeId,
  } = {},
) {
  const normalizedTypeId = String(typeId || "").trim();
  if (!normalizedTypeId || !(isLocalCommunityPilot()
    ? coords?.lat != null && coords?.lon != null && Number.isFinite(Number(coords.lat)) && Number.isFinite(Number(coords.lon))
    : isWithinLiveReportBounds(coords))) return [];

  const numericNow = Number(now);
  const effectiveMaxDistanceKm = Math.min(
    LIVE_REPORT_MAX_DISTANCE_KM,
    Math.max(0, Number(maxDistanceKm) || LIVE_REPORT_MAX_DISTANCE_KM),
  );

  return (Array.isArray(groups) ? groups : [])
    .map((group) => {
      const lat = Number(group?.lat);
      const lon = Number(group?.lon);
      const expiresAt = Number(group?.expiresAt);
      const groupId = String(group?.groupId || "").trim();
      if (
        !groupId
        || String(group?.typeId || "").trim() !== normalizedTypeId
        || !Number.isFinite(lat)
        || !Number.isFinite(lon)
        || !Number.isFinite(expiresAt)
        || expiresAt <= numericNow + 15_000
      ) return null;

      const resolvedDistanceKm = getLiveReportDistanceKm(coords, { lat, lon });
      if (resolvedDistanceKm > effectiveMaxDistanceKm) return null;

      return {
        ...group,
        matchDistanceKm: resolvedDistanceKm,
      };
    })
    .filter(Boolean)
    .sort((first, second) => (
      first.matchDistanceKm - second.matchDistanceKm
      || Number(second.createdAt || 0) - Number(first.createdAt || 0)
      || String(first.groupId).localeCompare(String(second.groupId), "it")
    ));
}

export function selectCommunityNearbyMatch(
  matches,
  personalState,
  selfMatchGroupIds = [],
) {
  const candidates = Array.isArray(matches) ? matches : [];
  const ownMatch = candidates.find(
    (match) => getOwnCommunityReport(personalState, match.groupId)
      || selfMatchGroupIds.includes(match.groupId),
  );
  const votedMatch = candidates.find(
    (match) => getCommunityVote(personalState, match.groupId) === "yes",
  );
  const match = ownMatch || votedMatch || candidates[0] || null;

  return {
    match,
    state: ownMatch
      ? "own"
      : votedMatch
        ? "voted"
        : match
          ? "confirmable"
          : "none",
  };
}

export function isWithinLiveReportBounds(coords) {
  const lat = Number(coords?.lat);
  const lon = Number(coords?.lon);

  return Number.isFinite(lat)
    && Number.isFinite(lon)
    && lat >= FVG_REPORT_BOUNDS.latMin
    && lat <= FVG_REPORT_BOUNDS.latMax
    && lon >= FVG_REPORT_BOUNDS.lonMin
    && lon <= FVG_REPORT_BOUNDS.lonMax;
}

export function getLiveReportLocationDecision(
  coords,
  {
    locations = LIVE_REPORT_LOCATIONS,
    maxDistanceKm = LIVE_REPORT_MAX_DISTANCE_KM,
  } = {},
) {
  if (!isWithinLiveReportBounds(coords)) {
    return { ok: false, reason: "out_of_area" };
  }

  const ranked = locations
    .map((location) => ({
      ...location,
      distanceKm: getLiveReportDistanceKm(coords, location),
    }))
    .sort((first, second) => (
      first.distanceKm - second.distanceKm
      || String(first.place || "").localeCompare(String(second.place || ""), "it")
    ));
  const nearbyPlaces = ranked
    .filter((location) => location.distanceKm <= maxDistanceKm)
    .slice(0, LIVE_REPORT_LOCATION_OPTION_LIMIT);

  if (!nearbyPlaces.length) {
    return { ok: false, reason: "out_of_area" };
  }

  return {
    detectedPlace: nearbyPlaces[0].place,
    maxDistanceKm,
    nearbyPlaces,
    ok: true,
  };
}
