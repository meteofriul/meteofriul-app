import {
  createLoadingEventsDataState,
  loadEventsData,
  readInitialEventsData,
} from "../features/events/eventsDataController";
import { getLocationCacheKey } from "../domain/geo/locationCacheKey";
import { FULL_EVENTS_LIMIT } from "../services/eventsApi";
import {
  buildEventRecord,
  getContextualEventsSummary,
  rankEventsForLocation,
} from "../features/events/eventsViewModel";
import { getCommunityActiveCount } from "../features/live/communitySocialPresentation";
import { createCommunityUnreadSnapshot } from "../features/live/communityUnreadState";

export const DEFAULT_EVENTS_RADIUS_KM = 20;
const EDITORIAL_ROUTE_IDS = new Set(["almanac", "discover"]);

export function createEventsNavigationSnapshot(location, dataState) {
  const locationKey = getLocationCacheKey(location);
  const total = Number(dataState?.total);
  const loadedLimit = Number(dataState?.loadedLimit);
  const keepsVerifiedCache = Boolean(dataState?.fromCache);
  const pendingWithoutCache = Boolean(dataState?.isPartial || dataState?.isRefreshing)
    && !keepsVerifiedCache;
  const failedWithoutCache = dataState?.status === "error" && !keepsVerifiedCache;
  const sourceUnavailable = dataState?.cacheStatus === "source_unavailable";

  if (
    !locationKey
    || !Array.isArray(dataState?.items)
    || !Number.isInteger(total)
    || total < 0
    || !Number.isFinite(loadedLimit)
    || loadedLimit < FULL_EVENTS_LIMIT
    || dataState.items.length !== total
    || sourceUnavailable
    || pendingWithoutCache
    || failedWithoutCache
  ) return null;

  const eventRecords = rankEventsForLocation(
    dataState.items.map((event) => buildEventRecord(event, { location })),
    { location },
  );
  const contextualCount = getContextualEventsSummary(eventRecords);

  return {
    catalogTotal: total,
    locationKey,
    period: contextualCount.period,
    total: contextualCount.count,
  };
}

export function reconcileEventsNavigationSnapshot(
  current,
  activeLocation,
  sourceLocation,
  dataState,
) {
  const candidate = createEventsNavigationSnapshot(sourceLocation, dataState);
  if (!candidate || candidate.locationKey !== getLocationCacheKey(activeLocation)) return current;
  if (
    current?.locationKey === candidate.locationKey
    && current?.total === candidate.total
    && current?.period === candidate.period
    && current?.catalogTotal === candidate.catalogTotal
  ) return current;
  return candidate;
}

export function getEventsNavigationTotal(snapshot, location) {
  if (snapshot?.locationKey !== getLocationCacheKey(location)) return null;
  return Number.isInteger(snapshot?.total) && snapshot.total >= 0 ? snapshot.total : null;
}

export function getEventsNavigationPeriod(snapshot, location) {
  if (snapshot?.locationKey !== getLocationCacheKey(location)) return null;
  return ["today", "next"].includes(snapshot?.period) ? snapshot.period : null;
}

export function readEventsNavigationSnapshot(
  location,
  { readInitialState = readInitialEventsData } = {},
) {
  return createEventsNavigationSnapshot(location, readInitialState(location));
}

export function createCommunityNavigationSnapshot(location, communityModel, options) {
  const locationKey = getLocationCacheKey(location);

  if (
    !locationKey
    || communityModel?.enabled !== true
    || !Array.isArray(communityModel?.items)
  ) return null;

  return {
    locationKey,
    total: getCommunityActiveCount(communityModel.items),
    unread: createCommunityUnreadSnapshot(location, communityModel, options),
  };
}

export function reconcileCommunityNavigationSnapshot(
  current,
  activeLocation,
  sourceLocation,
  communityModel,
  options,
) {
  const candidate = createCommunityNavigationSnapshot(sourceLocation, communityModel, options);
  if (!candidate || candidate.locationKey !== getLocationCacheKey(activeLocation)) return current;
  // A cached/offline render is not evidence that news has been viewed or has
  // disappeared. Retain the last verified IDs until a fresh response arrives;
  // getCommunityUnreadCount independently drops their expired observations.
  if (current?.locationKey === candidate.locationKey
    && current?.unread?.ready === true && candidate.unread?.ready !== true) return current;
  if (
    current?.locationKey === candidate.locationKey
    && current?.total === candidate.total
    && JSON.stringify(current?.unread) === JSON.stringify(candidate.unread)
  ) return current;
  return candidate;
}

export function getCommunityNavigationTotal(snapshot, location) {
  if (snapshot?.locationKey !== getLocationCacheKey(location)) return null;
  return Number.isInteger(snapshot?.total) && snapshot.total >= 0 ? snapshot.total : null;
}

export function getAppRouteViewKey(activeTab, weatherLocation, editorialLocation = weatherLocation) {
  if (activeTab === "events") {
    return `${activeTab}:${getLocationCacheKey(weatherLocation)}:${getLocationCacheKey(editorialLocation)}`;
  }
  const location = EDITORIAL_ROUTE_IDS.has(activeTab) ? editorialLocation : weatherLocation;
  return `${activeTab}:${getLocationCacheKey(location)}`;
}

export function getPilotWhyRequestId(activeTab, options = {}) {
  if (activeTab !== "discover") return "";
  return typeof options?.whyId === "string" ? options.whyId.trim() : "";
}

export function readEventsRouteInitialState(
  location,
  {
    createLoadingState = createLoadingEventsDataState,
    readInitialState = readInitialEventsData,
  } = {},
) {
  return readInitialState(location) || createLoadingState();
}

export async function loadAndCommitEventsRouteData(
  location,
  {
    isCurrent = () => true,
    loadData = loadEventsData,
    onCommit = () => {},
  } = {},
) {
  const nextState = await loadData(location);
  if (isCurrent()) onCommit(nextState);
  return nextState;
}
