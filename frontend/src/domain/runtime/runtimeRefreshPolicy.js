export const RUNTIME_REFRESH_STATE = Object.freeze({
  idle: "idle",
  hydrated: "hydrated",
  refreshing: "refreshing",
  fresh: "fresh",
  unchanged: "unchanged",
  staleVisible: "stale_visible",
  unreachableEmpty: "unreachable_empty",
  ignoredStaleLocation: "ignored_stale_location",
});

export const RUNTIME_REFRESH_ACTION = Object.freeze({
  none: "none",
  hydrateFromCache: "hydrate_from_cache",
  refreshCurrentLocation: "refresh_current_location",
  refreshRegionalBulletin: "refresh_regional_bulletin",
  retryEventsIfPending: "retry_events_if_pending",
  showPassiveFeedback: "show_passive_feedback",
  showUnreachableState: "show_unreachable_state",
  ignoreResponse: "ignore_response",
});

export const RUNTIME_FOREGROUND_REFRESH_MIN_INTERVAL_MS = 2 * 60 * 1000;
export const RUNTIME_WEATHER_VERIFY_INTERVAL_MS = 5 * 60 * 1000;
export const RUNTIME_REFRESH_COMPLETION_TIMEOUT_MS = 8000;
export const RUNTIME_EVENTS_MAX_PENDING_RETRIES = 20;

const AUTHORITATIVE_OFFICIAL_ALERT_STATES = new Set([
  "active",
  "inactive_confirmed",
]);

function toBoolean(value) {
  return value === true;
}

function normalizeToken(value) {
  return String(value || "").trim().toLowerCase();
}

export function hasVisibleRuntimeData(value) {
  if (!value) return false;

  if (Array.isArray(value)) return value.length > 0;
  if (Array.isArray(value.items)) return value.items.length > 0;
  if (Array.isArray(value.events)) return value.events.length > 0;

  return Boolean(value.current || hasVisibleForecast(value.forecast) || value.summary || value.text || value.updatedAt);
}

function hasVisibleForecast(forecast) {
  if (!forecast || typeof forecast !== "object") return false;

  if (Array.isArray(forecast.days)) return forecast.days.length > 0;

  const officialForecasts = [
    ...(forecast?.official?.it?.forecasts || []),
    ...(forecast?.official?.fur?.forecasts || []),
  ];

  if (officialForecasts.some((item) => String(item?.text || item?.title || "").trim())) {
    return true;
  }

  const structuredDays = forecast?.osmer_structured?.days || forecast?.osmerStructured?.days || [];
  if (Array.isArray(structuredDays) && structuredDays.length > 0) return true;

  return false;
}

export function hasVisibleRuntimeDataTree(value, visited = new Set()) {
  if (!value || typeof value !== "object" || visited.has(value)) return false;
  visited.add(value);
  if (hasVisibleRuntimeData(value)) return true;

  return [
    "weather",
    "events",
    "bulletin",
    "data",
    "payload",
    "community",
    "webcams",
  ].some((key) => (
    Object.prototype.hasOwnProperty.call(value, key) &&
    value[key] !== value &&
    hasVisibleRuntimeDataTree(value[key], visited)
  ));
}

function hasUncommittedWeatherCandidate(value, visited = new Set()) {
  if (!value || typeof value !== "object" || visited.has(value)) return false;
  visited.add(value);
  const caches = [value.cache, value.current?.cache, value.rawCurrent?.cache];
  if (caches.some(cache => cache?.runtime_fallback_source === "candidate_not_committed"
    && cache?.runtime_fallback_code === "CACHE_PERSIST_FAILED")) return true;
  return ["weather", "data", "raw"].some(key => (
    value[key] !== value && hasUncommittedWeatherCandidate(value[key], visited)
  ));
}

const RUNTIME_COMPONENT_PROBLEM_STATES = new Set([
  "failed",
  "partial",
  "pending",
  "retained",
  "unavailable",
]);

const RUNTIME_COMPONENT_USABLE_STATES = new Set([
  "partial",
  "retained",
  "settled",
]);

function hasExplicitRuntimePayload(value) {
  return value?.payload !== null && value?.payload !== undefined;
}

function classifyRuntimeComponent(
  value,
  {
    ignoreUncommittedWeatherCandidate = false,
    unavailableOnEmptyError = false,
  } = {},
) {
  if (!value) return unavailableOnEmptyError ? "unavailable" : "failed";

  // A verified active keeps the screen usable, but failure to commit the
  // verified replacement means the explicit refresh itself did not finish.
  if (!ignoreUncommittedWeatherCandidate && hasUncommittedWeatherCandidate(value)) {
    return "failed";
  }

  const status = normalizeToken(value.status);
  const visible = hasVisibleRuntimeDataTree(value) || hasExplicitRuntimePayload(value);
  const pending = value.isRefreshing === true || status === "loading" ||
    status === "pending" || status === "refreshing";
  const partial = value.isPartial === true || status === "partial";
  const hasError = value.ok === false || Boolean(value.error) ||
    status === "error" || status === "unavailable";
  const retained = value.fromCache === true || value.isStale === true || status === "stale";

  if (partial) return "partial";
  if (pending) return visible ? "partial" : "pending";
  if (hasError) {
    if (visible) return "retained";
    return unavailableOnEmptyError ? "unavailable" : "failed";
  }
  if (retained) return visible ? "retained" : "unavailable";
  return "settled";
}

function hasCamsRuntimeContract(weather) {
  const rawCurrent = weather?.rawCurrent || weather?.current;
  return Boolean(
    rawCurrent && (
      Object.prototype.hasOwnProperty.call(rawCurrent?.data_quality || {}, "cams_status") ||
      Object.prototype.hasOwnProperty.call(rawCurrent?.source || {}, "cams") ||
      Object.prototype.hasOwnProperty.call(rawCurrent, "air_quality_data") ||
      Object.prototype.hasOwnProperty.call(rawCurrent, "pollen_data")
    ),
  );
}

function classifyWeatherComponents(weather) {
  if (!weather) return { icon: "failed" };

  const rawCurrent = weather.rawCurrent || weather.current;
  const iconCandidateUncommitted = hasUncommittedWeatherCandidate(weather);
  const baseState = classifyRuntimeComponent(weather);
  const camsBaseState = classifyRuntimeComponent(weather, {
    ignoreUncommittedWeatherCandidate: true,
  });
  const hasWeather = Boolean(weather.current || rawCurrent || hasVisibleForecast(weather.forecast));
  const iconSourceStatus = normalizeToken(rawCurrent?.source?.icon?.status);
  let icon = iconCandidateUncommitted ? "failed" : baseState;

  if (!iconCandidateUncommitted && hasWeather && baseState === "settled") {
    icon = ["degraded", "error", "unavailable"].includes(iconSourceStatus)
      ? "unavailable"
      : "settled";
  } else if (!iconCandidateUncommitted && hasWeather && baseState === "failed") {
    icon = "retained";
  }

  const components = { icon };
  if (!hasCamsRuntimeContract(weather)) return components;

  const camsStatus = normalizeToken(
    rawCurrent?.data_quality?.cams_status || rawCurrent?.source?.cams?.status,
  );
  const camsSampleStatus = normalizeToken(rawCurrent?.data_quality?.cams_sample_status);
  const camsRefreshPending = Array.isArray(weather.runtimeRefreshPendingComponents) &&
    weather.runtimeRefreshPendingComponents.includes("cams");
  let cams;

  if (camsRefreshPending || ["pending", "loading", "refreshing"].includes(camsStatus)) {
    cams = "pending";
  } else if (["unavailable", "degraded", "error"].includes(camsStatus)) {
    cams = "unavailable";
  } else if (
    ["stale", "last_known"].includes(camsStatus) ||
    camsSampleStatus === "last_known" ||
    ["retained", "stale"].includes(camsBaseState)
  ) {
    cams = "retained";
  } else if (camsBaseState === "failed") {
    cams = "failed";
  } else if (camsBaseState === "partial") {
    cams = "partial";
  } else {
    cams = "settled";
  }

  return { ...components, cams };
}

function expandNamedRuntimeComponent(name, value) {
  if (name === "home") {
    return {
      ...classifyWeatherComponents(value?.weather),
      events: classifyRuntimeComponent(value?.events, { unavailableOnEmptyError: true }),
    };
  }
  if (name === "weather") return classifyWeatherComponents(value);
  if (name === "cams") {
    const weatherState = classifyWeatherComponents(value).cams;
    return {
      cams: weatherState || classifyRuntimeComponent(value, { unavailableOnEmptyError: true }),
    };
  }
  if (name === "live") {
    return {
      webcams: classifyRuntimeComponent(value?.webcams, { unavailableOnEmptyError: true }),
      community: classifyRuntimeComponent(value?.community, { unavailableOnEmptyError: true }),
    };
  }

  return {
    [name]: classifyRuntimeComponent(value, {
      unavailableOnEmptyError: ["events", "osmer", "radar"].includes(name),
    }),
  };
}

function expandPendingRuntimeComponent(name) {
  if (name === "home") return { icon: "pending", events: "pending" };
  if (name === "weather") return { icon: "pending" };
  if (name === "live") return { webcams: "pending", community: "pending" };
  return { [name]: "pending" };
}

function getRouteComponentMap(route, routeStatus) {
  if (route?.components && Object.keys(route.components).length > 0) {
    return route.components;
  }
  return { route: routeStatus };
}

function buildRuntimeCompletionOutcome(componentStates, components = null) {
  const states = [...componentStates];
  const hasUsableComponent = states.some((state) => RUNTIME_COMPONENT_USABLE_STATES.has(state));
  const ok = states.length === 0 || hasUsableComponent;
  const partial = ok && states.some((state) => RUNTIME_COMPONENT_PROBLEM_STATES.has(state));
  const outcome = { ok };

  if (components) outcome.components = components;
  if (partial) outcome.partial = true;
  return outcome;
}

export function getRuntimeRefreshCompletionOutcome(results = [], componentNames = []) {
  const named = componentNames.length > 0 || results.some((result) => result?.component);
  const components = named ? {} : null;
  const componentStates = [];

  results.forEach((result, index) => {
    const name = result?.component || componentNames[index] || null;
    if (result?.status === "pending") {
      if (!name) {
        componentStates.push("pending");
        return;
      }
      const expanded = expandPendingRuntimeComponent(name);
      Object.entries(expanded).forEach(([component, state]) => {
        components[component] = state;
        componentStates.push(state);
      });
      return;
    }
    if (result?.status === "rejected") {
      const state = "failed";
      componentStates.push(state);
      if (components && name) components[name] = state;
      return;
    }

    if (!name) {
      componentStates.push(classifyRuntimeComponent(result?.value));
      return;
    }

    const expanded = expandNamedRuntimeComponent(name, result?.value);
    Object.entries(expanded).forEach(([component, state]) => {
      components[component] = state;
      componentStates.push(state);
    });
  });

  return buildRuntimeCompletionOutcome(componentStates, components);
}

export function isFreshAuthoritativeOfficialAlertsRuntime(runtime) {
  return Boolean(
    runtime?.status === "fresh" &&
    AUTHORITATIVE_OFFICIAL_ALERT_STATES.has(runtime?.alertState) &&
    !runtime?.error &&
    !runtime?.fromCache &&
    !runtime?.retained,
  );
}

function getOfficialAlertsComponentStatus(officialAlerts) {
  if (officialAlerts === undefined) return "pending";
  if (isFreshAuthoritativeOfficialAlertsRuntime(officialAlerts)) return "settled";
  if (officialAlerts?.retained === true || officialAlerts?.fromCache === true) return "retained";
  return "unavailable";
}

export function getRuntimeRefreshGateOutcome({
  officialAlerts,
  officialAlertsRequired = true,
  route,
} = {}) {
  if (route === undefined || (officialAlertsRequired && officialAlerts === undefined)) return null;

  const routeOk = route?.ok !== false;
  const routeStatus = routeOk
    ? route?.partial === true ? "partial" : "settled"
    : "failed";
  const officialAlertsStatus = officialAlertsRequired
    ? getOfficialAlertsComponentStatus(officialAlerts)
    : "not_applicable";
  const routeComponents = getRouteComponentMap(route, routeStatus);
  const routeHasProblem = Object.values(routeComponents)
    .some((status) => RUNTIME_COMPONENT_PROBLEM_STATES.has(status));

  return {
    components: {
      ...routeComponents,
      ...(officialAlertsRequired ? { officialAlerts: officialAlertsStatus } : {}),
    },
    ok: routeOk,
    partial: routeOk && (
      routeStatus === "partial"
      || routeHasProblem
      || (officialAlertsRequired && officialAlertsStatus !== "settled")
    ),
  };
}

export function getRuntimeRefreshTimeoutOutcome({
  officialAlerts,
  officialAlertsRequired = true,
  route,
} = {}) {
  const officialAlertsStatus = officialAlertsRequired
    ? getOfficialAlertsComponentStatus(officialAlerts)
    : "not_applicable";
  if (route === undefined) {
    return {
      components: {
        route: "pending",
        ...(officialAlertsRequired ? { officialAlerts: officialAlertsStatus } : {}),
      },
      ok: false,
      partial: false,
    };
  }

  const routeOk = route?.ok !== false;
  const routeStatus = routeOk
    ? route?.partial === true ? "partial" : "settled"
    : "failed";

  return {
    components: {
      ...getRouteComponentMap(route, routeStatus),
      ...(officialAlertsRequired ? { officialAlerts: officialAlertsStatus } : {}),
    },
    ok: routeOk,
    partial: routeOk,
  };
}

export function shouldIgnoreStaleLocationResponse({ activeLocationKey, responseLocationKey } = {}) {
  const activeKey = normalizeToken(activeLocationKey);
  const responseKey = normalizeToken(responseLocationKey);

  return Boolean(activeKey && responseKey && activeKey !== responseKey);
}

export function getInitialHydrationDecision({
  hasFreshCache = false,
  hasStaleCache = false,
  hasUsableCache = false,
} = {}) {
  if (toBoolean(hasFreshCache) || toBoolean(hasStaleCache) || toBoolean(hasUsableCache)) {
    return {
      action: RUNTIME_REFRESH_ACTION.hydrateFromCache,
      state: RUNTIME_REFRESH_STATE.hydrated,
      shouldFetchAfterRender: true,
    };
  }

  return {
    action: RUNTIME_REFRESH_ACTION.refreshCurrentLocation,
    state: RUNTIME_REFRESH_STATE.refreshing,
    shouldFetchAfterRender: true,
  };
}

export function getRefreshRequestDecision({
  activeLocationKey,
  hasLocation = true,
  responseLocationKey,
} = {}) {
  if (shouldIgnoreStaleLocationResponse({ activeLocationKey, responseLocationKey })) {
    return {
      action: RUNTIME_REFRESH_ACTION.ignoreResponse,
      state: RUNTIME_REFRESH_STATE.ignoredStaleLocation,
    };
  }

  if (!hasLocation) {
    return {
      action: RUNTIME_REFRESH_ACTION.refreshRegionalBulletin,
      state: RUNTIME_REFRESH_STATE.refreshing,
    };
  }

  return {
    action: RUNTIME_REFRESH_ACTION.refreshCurrentLocation,
    state: RUNTIME_REFRESH_STATE.refreshing,
  };
}

export function getRefreshResultDecision({
  changed = false,
  error = null,
  hasVisibleData = false,
  ok = false,
} = {}) {
  if (ok) {
    return {
      action: RUNTIME_REFRESH_ACTION.showPassiveFeedback,
      state: changed ? RUNTIME_REFRESH_STATE.fresh : RUNTIME_REFRESH_STATE.unchanged,
      shouldKeepVisibleData: true,
    };
  }

  if (hasVisibleData) {
    return {
      action: RUNTIME_REFRESH_ACTION.showPassiveFeedback,
      error: error ? String(error) : null,
      state: RUNTIME_REFRESH_STATE.staleVisible,
      shouldKeepVisibleData: true,
    };
  }

  return {
    action: RUNTIME_REFRESH_ACTION.showUnreachableState,
    error: error ? String(error) : null,
    state: RUNTIME_REFRESH_STATE.unreachableEmpty,
    shouldKeepVisibleData: false,
  };
}

export function shouldWriteEventsCacheForPayload(payload = {}) {
  return !payload?.isRefreshing && !payload?.isPartial;
}

export function getEventsPendingDecision({
  hasCachedEvents = false,
  isPartial = false,
  isRefreshing = false,
  retry = 0,
  maxRetries = RUNTIME_EVENTS_MAX_PENDING_RETRIES,
} = {}) {
  const isPending = Boolean(isRefreshing || isPartial);
  const shouldRetry = isPending && Number(retry) < maxRetries;

  return {
    action: shouldRetry ? RUNTIME_REFRESH_ACTION.retryEventsIfPending : RUNTIME_REFRESH_ACTION.none,
    shouldKeepCachedEvents: Boolean(isPending && hasCachedEvents),
    shouldRetry,
    shouldWriteCache: !isPending,
    state: isPending ? RUNTIME_REFRESH_STATE.refreshing : RUNTIME_REFRESH_STATE.fresh,
  };
}

export function shouldRunForegroundRuntimeRefresh({
  lastRefreshAt = 0,
  minIntervalMs = RUNTIME_FOREGROUND_REFRESH_MIN_INTERVAL_MS,
  now,
  visibilityState = "visible",
} = {}) {
  if (visibilityState === "hidden") return false;

  const numericNow = Number(now);
  const numericLastRefreshAt = Number(lastRefreshAt);
  const numericMinIntervalMs = Number(minIntervalMs);

  if (!Number.isFinite(numericNow)) return false;
  if (!Number.isFinite(numericLastRefreshAt) || numericLastRefreshAt <= 0) return true;
  if (!Number.isFinite(numericMinIntervalMs) || numericMinIntervalMs < 0) return true;

  return numericNow - numericLastRefreshAt >= numericMinIntervalMs;
}

export function shouldRunRuntimeRefresh({
  force = false,
  lastRefreshAt = 0,
  minIntervalMs = RUNTIME_FOREGROUND_REFRESH_MIN_INTERVAL_MS,
  now,
  visibilityState = "visible",
} = {}) {
  const numericNow = Number(now);
  if (!Number.isFinite(numericNow)) return false;

  if (force) return true;

  return shouldRunForegroundRuntimeRefresh({
    lastRefreshAt,
    minIntervalMs,
    now: numericNow,
    visibilityState,
  });
}
