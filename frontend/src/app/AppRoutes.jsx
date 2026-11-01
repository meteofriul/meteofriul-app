import { lazy, Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  getLocalWeatherPilotTestNow,
  isDefinitiveAppExperience,
  isLocalWeatherNationalPilot,
} from "../services/localWeatherPilot";

import { buildAlmanacViewModel } from "../features/almanac/almanacViewModel";
import { BulletinView } from "../features/bulletin/BulletinView";
import { NationalOfficialAlertsView } from "../features/bulletin/NationalOfficialAlertsView";
import {
  createEmptyBulletinDataState,
  loadBulletinData,
  readInitialBulletinData,
} from "../features/bulletin/bulletinDataController";
import {
  createNationalOfficialAlertsState,
  loadNationalOfficialAlerts,
  readInitialNationalOfficialAlerts,
} from "../features/bulletin/nationalOfficialAlertsDataController";
import { buildBulletinLocalViewModel } from "../features/bulletin/bulletinLocalViewModel";
import {
  BULLETIN_RADAR_AUTO_REFRESH_INTERVAL_MS,
  createEmptyBulletinRadarDataState,
  loadBulletinRadarData,
  readInitialBulletinRadarData,
} from "../features/bulletin/bulletinRadarDataController";
import { buildBulletinRadarViewModel } from "../features/bulletin/bulletinRadarViewModel";
import { buildBulletinViewModel } from "../features/bulletin/bulletinViewModel";
import { EventsView } from "../features/events/EventsView";
import { loadEventsData } from "../features/events/eventsDataController";
import { buildEventsViewModel } from "../features/events/eventsViewModel";
import { getEventsViewCopy } from "../copy/eventsViewCopy";
import { HomeView } from "../features/home/HomeView";
import { buildNationalHomeAlertPresentation } from "../features/home/nationalHomeAlertPresentation";
import { subscribeToHomeSolarClock } from "../features/home/homeDayPhase";
import {
  loadHomeEvents,
  loadHomeWeather,
  hydrateHomeWeatherFromBackgroundPrefetch,
  mergeHomeDataState,
  readInitialHomeData,
} from "../features/home/homeDataController";
import {
  buildHomeAlmanacStateFromModel,
  buildHomeViewModel,
} from "../features/home/homeViewModel";
import { buildHomeBulletinPresentation } from "../features/home/homeBulletinPresentation";
import { selectHomeDiscoverPreview } from "../features/home/homeDiscoverPreview";
import { DiscoverView } from "../features/discover/DiscoverView";
import { MarketsExplorer } from "../features/markets/MarketsExplorer";
import { marketDay, mergeMarketEvents } from "../features/markets/marketsCatalog";
import { subscribeToMarketsDayClock } from "../features/markets/marketsDayClock";
import { useMarketsCatalogue } from "../features/markets/useMarketsCatalogue";
import { getPilotMunicipalityContext } from "../features/discover/pilotMunicipalityContext";
import { buildDiscoverViewModel } from "../features/discover/discoverViewModel";
import { HomeLabView } from "../features/lab/HomeLabView";
import {
  LIVE_AUTO_REFRESH_INTERVAL_MS,
  createEmptyLiveDataState,
  loadLiveData,
  readInitialLiveData,
} from "../features/live/liveDataController";
import {
  confirmLiveCommunityReport,
  locateLiveCommunityReport,
  readPendingLiveCommunityReportUpdates,
  reconcilePendingLiveCommunityReportUpdate,
} from "../features/live/liveReportController";
import {
  applyCommunityReportSimulationConfirmation,
  applyCommunityReportSimulationOverlay,
  applyCommunityReportSimulationSubmission,
  applyCommunityReportSimulationUndo,
  applyPilotReportSimulation,
  applyPilotReportSimulationSubmission,
  COMMUNITY_REPORT_PREVIEW_MODE_ACTIVE,
  COMMUNITY_REPORT_PREVIEW_MODE_INTERACTIVE,
  createCommunityReportActivePreviewState,
  createCommunityReportPreviewMemoryStorage,
  createCommunityReportSimulationOverlay,
  getLocalCommunityReportPreviewMode,
} from "../features/live/communityReportPreview";
import {
  forgetCommunityReport,
  readCommunityPersonalState,
  refreshCommunityReportReceipt,
  rememberCommunityReport,
  withdrawCommunityReport,
} from "../features/live/communityPersonalState";
import { LiveView } from "../features/live/LiveView";
import { buildLiveViewModel } from "../features/live/liveViewModel";
import { readCommunityReportShareTarget } from "../features/live/communityShare";
import {
  createWebcamPlayerPreviewState,
  getLocalWebcamPlayerPreviewMode,
} from "../features/live/webcamPlayerPreview";
import { SettingsView } from "../features/settings/SettingsView";
import { normalizeEventsRadius } from "./eventsRadiusPreference";
import { buildPublicCommunityIdentitySnapshot } from "../features/community/communityIdentity";
import { WeatherForecastView } from "../features/weather/WeatherForecastView";
import { WeatherSectionNav } from "../features/weather/WeatherSectionNav";
import { WeatherSwipeShell } from "../features/weather/WeatherSwipeShell";
import { buildWeatherForecastViewModel } from "../features/weather/weatherForecastViewModel";
import { DEFAULT_APP_LOCATION } from "./appLocation";
import { getLocationCacheKey } from "../domain/geo/locationCacheKey";
import { getLocationDisplayName } from "../domain/geo/locationDisplayName";
import { getNationalOfficialAlertsIstat } from "../services/nationalOfficialAlertsApi";
import { resolveProductScope } from "../domain/scope/productScope";
import { isLocalCommunityPilot } from "../services/localCommunityPilot";
import { getRuntimeRefreshCompletionOutcome } from "../domain/runtime/runtimeRefreshPolicy";
import { EmptyState } from "../ui/components/EmptyState";
import { LocationContext } from "../ui/components/LocationContext";
import { TabPage } from "../ui/layout/TabPage";
import { resolveWeatherRouteNow } from "./weatherRouteClock";
import {
  DEFAULT_EVENTS_RADIUS_KM,
  getAppRouteViewKey,
  loadAndCommitEventsRouteData,
  readEventsRouteInitialState,
} from "./appRouteRuntime";

const AlmanacPageView = lazy(() => (
  import("../features/almanac/AlmanacView").then((module) => ({ default: module.AlmanacView }))
));
const FORECAST_PRESENTATION_MEMORY_LIMIT = 8;
const forecastPresentationMemory = new Map();

function useRouteRuntimeRefreshToken(routeKey, token) {
  const [request, setRequest] = useState(() => ({ routeKey, seenToken: token, token }));
  if (request.routeKey !== routeKey || request.seenToken !== token) {
    // A refresh belongs to the view that received it. Keep that view subscribed
    // to late data after the UI deadline, but never replay the same request when
    // another view mounts (or when the user later returns to this one).
    const nextRequest = {
      routeKey,
      seenToken: token,
      token: request.seenToken !== token ? token : 0,
    };
    setRequest(nextRequest);
    return nextRequest.token;
  }
  return request.token;
}

function rememberForecastPresentation(key, model) {
  if (!model) return;
  forecastPresentationMemory.delete(key);
  if (model?.hourly?.items?.length) forecastPresentationMemory.set(key, model);
  while (forecastPresentationMemory.size > FORECAST_PRESENTATION_MEMORY_LIMIT) {
    forecastPresentationMemory.delete(forecastPresentationMemory.keys().next().value);
  }
}

function buildHomeBulletinFromData(dataState, {
  advicePending = false,
  language,
  location,
  now = null,
  weatherState = null,
}) {
  const bulletinModel = buildBulletinViewModel(dataState, { language });

  return {
    bulletin: buildHomeBulletinPresentation(bulletinModel, {
      advicePending,
      language,
      location,
      now,
      weatherState,
    }),
    officialAlert: bulletinModel.alert,
  };
}

function observeRuntimeRefresh(
  onRuntimeRefreshSettled,
  runtimeRefreshToken,
  promises,
  componentNames,
  isCurrent = () => true,
) {
  const results = promises.map(() => ({ status: "pending" }));
  let remaining = promises.length;

  promises.forEach((promise, index) => {
    Promise.resolve(promise).then(
      (value) => ({ status: "fulfilled", value }),
      (reason) => ({ status: "rejected", reason }),
    ).then((result) => {
      results[index] = result;
      remaining -= 1;
      if (!isCurrent()) return;

      onRuntimeRefreshSettled?.(runtimeRefreshToken, {
        ...getRuntimeRefreshCompletionOutcome(results, componentNames),
        complete: remaining === 0,
      });
    });
  });
}

function createRuntimeComponentCompletion() {
  let completed = false;
  let complete;
  const promise = new Promise((resolve) => {
    complete = (value) => {
      if (completed) return;
      completed = true;
      resolve(value);
    };
  });

  return { complete, promise };
}

function getOfficialAlertsRuntimePayload(runtime) {
  if (runtime === undefined) return undefined;
  if (runtime?.active && runtime?.payload) return runtime.payload;
  if (runtime?.error && !runtime?.active) return { state: "unavailable" };
  if (["error", "unavailable"].includes(runtime?.status)) {
    return { state: "unavailable" };
  }
  if (runtime?.payload) return runtime.payload;

  return null;
}

function getUsableAlmanacWeather(weatherState) {
  if (!weatherState?.current || weatherState.isStale) return null;
  if (["empty", "error", "stale"].includes(weatherState.status)) return null;

  return weatherState.current;
}

function createUnavailableWeatherState(location, availability) {
  return {
    city: getLocationDisplayName(location, "it"),
    current: null,
    error: null,
    forecast: null,
    fromCache: false,
    isStale: false,
    officialAlerts: null,
    osmerAudit: null,
    status: availability,
    unavailableReason: availability === "planned"
      ? "national_icon2i_planned"
      : "weather_territory_unsupported",
    updatedAt: null,
  };
}

function createUnavailableEventsState() {
  return {
    error: null,
    fromCache: false,
    isPartial: false,
    isRefreshing: false,
    items: [],
    loadedLimit: 0,
    retry: 0,
    shouldRetry: false,
    status: "unsupported",
    total: 0,
    unavailableReason: "events_fvg_only",
  };
}

function withoutUnavailableWeather(initialState, location, eventsLocation, availability) {
  return {
    ...(initialState || {}),
    editorialLocation: eventsLocation,
    events: initialState?.events,
    location,
    ok: !initialState?.events?.error,
    weather: createUnavailableWeatherState(location, availability),
  };
}

function HomeRouteView({
  runtimeRefreshForce = true,
  activeLocation,
  eventsRadius = DEFAULT_EVENTS_RADIUS_KM,
  editorialContext,
  copy,
  deviceNow,
  language,
  officialAlert,
  productScope,
  onLocationSearchOpen,
  onEventsNavigationState,
  onNavigate,
  onRuntimeRefreshSettled,
  runtimeRefreshToken = 0,
  weatherNow,
  marketsCatalogue,
}) {
  const location = activeLocation || DEFAULT_APP_LOCATION;
  const editorialLocation = editorialContext?.focusLocation || DEFAULT_APP_LOCATION;
  const eventsLocation = useMemo(() => ({
    ...location,
    eventsRadius: normalizeEventsRadius(eventsRadius) ?? DEFAULT_EVENTS_RADIUS_KM,
  }), [location, eventsRadius]);
  const weatherMatchesEditorialLocation = getLocationCacheKey(location)
    === getLocationCacheKey(editorialLocation);
  const forecastAvailability = productScope?.sources?.forecast?.status || "enabled";
  const weatherEnabled = forecastAvailability === "enabled";
  const osmerEnabled = productScope?.sources?.osmer?.status === "enabled";
  const nationalAlertsEnabled = !osmerEnabled
    && productScope?.sources?.nationalAlerts?.status === "enabled";
  const nationalAlertsIstat = nationalAlertsEnabled
    ? getNationalOfficialAlertsIstat(location)
    : "";
  const eventsEnabled = productScope?.sources?.events?.status !== "unsupported";
  const weatherHour = isDefinitiveAppExperience() ? Math.floor(new Date(weatherNow).getTime() / 3600000) : 0;
  const weatherLocationKey = getLocationCacheKey(location);
  const initialAdviceWeatherRequestKey = [weatherLocationKey, weatherHour].join(":");
  const [homeData, setHomeData] = useState(() => {
    const initialState = readInitialHomeData(location, {
      eventsLocation,
      manageOfficialAlerts: false,
      ...(weatherEnabled ? {} : {
        bootstrapCacheReader: () => null,
        weatherCacheReader: () => null,
      }),
    });
    const weatherScopedState = weatherEnabled
      ? initialState
      : withoutUnavailableWeather(
          initialState,
          location,
          eventsLocation,
          forecastAvailability,
        );
    return eventsEnabled
      ? weatherScopedState
      : {
          ...(weatherScopedState || {}),
          editorialLocation: eventsLocation,
          events: createUnavailableEventsState(),
          location,
          ok: weatherScopedState?.ok ?? true,
        };
  });
  const [bulletinData, setBulletinData] = useState(() => (
    osmerEnabled
      ? readInitialBulletinData(location, { includeAlerts: false })
      : null
  ));
  const [nationalAlertsData, setNationalAlertsData] = useState(() => ({
    istat: nationalAlertsIstat,
    state: nationalAlertsIstat
      ? readInitialNationalOfficialAlerts(location)
      : createNationalOfficialAlertsState(),
  }));
  const nationalAlertsRequestRef = useRef(0);
  const [adviceWeatherLifecycle, setAdviceWeatherLifecycle] = useState(() => ({
    initialRequestKey: null,
    runtimeRefreshToken: 0,
  }));
  const advicePending = weatherEnabled && (
    adviceWeatherLifecycle.initialRequestKey !== initialAdviceWeatherRequestKey
    || (
      runtimeRefreshToken > 0
      && adviceWeatherLifecycle.runtimeRefreshToken !== runtimeRefreshToken
    )
  );
  const homeEventsShouldRetry = Boolean(homeData?.events?.shouldRetry);
  const homeEventsRetry = Number(homeData?.events?.retry || 0);

  useEffect(() => {
    if (eventsEnabled) onEventsNavigationState?.(eventsLocation, homeData?.events);
  }, [eventsEnabled, eventsLocation, homeData?.events, onEventsNavigationState]);

  useEffect(() => {
    let cancelled = false;
    if (!nationalAlertsIstat) return undefined;
    const requestId = ++nationalAlertsRequestRef.current;
    loadNationalOfficialAlerts(location).then((state) => {
      if (!cancelled && nationalAlertsRequestRef.current === requestId) {
        setNationalAlertsData({ istat: nationalAlertsIstat, state });
      }
    });
    return () => { cancelled = true; };
  }, [location, nationalAlertsIstat]);

  useEffect(() => {
    let cancelled = false;

    const hydrateAndLoadWeather = async () => {
      try {
        const prefetchedWeather = await hydrateHomeWeatherFromBackgroundPrefetch(location, {
          manageOfficialAlerts: false,
        });
        if (!cancelled && prefetchedWeather) {
          setHomeData((current) => mergeHomeDataState(current, location, { weather: prefetchedWeather }));
        }

        const weather = await loadHomeWeather(location, {
          deferCams: true,
          manageOfficialAlerts: false,
          onCamsUpdate: (enrichedWeather) => {
            if (!cancelled) {
              setHomeData((current) => mergeHomeDataState(current, location, {
                weather: enrichedWeather,
              }));
            }
          },
        });
        if (!cancelled) {
          setHomeData((current) => mergeHomeDataState(current, location, { weather }));
        }
      } finally {
        if (!cancelled) {
          setAdviceWeatherLifecycle((current) => ({
            ...current,
            initialRequestKey: initialAdviceWeatherRequestKey,
          }));
        }
      }
    };

    if (weatherEnabled) void hydrateAndLoadWeather();
    if (eventsEnabled) {
      loadHomeEvents(eventsLocation).then((events) => {
        if (!cancelled) {
          setHomeData((current) => mergeHomeDataState(current, location, {
            editorialLocation: eventsLocation,
            events,
          }));
        }
      });
    }
    if (osmerEnabled) {
      loadBulletinData(location, { includeAlerts: false }).then((nextState) => {
        if (!cancelled) setBulletinData(nextState);
      });
    }

    return () => {
      cancelled = true;
    };
  }, [eventsEnabled, eventsLocation, forecastAvailability, initialAdviceWeatherRequestKey, location, osmerEnabled, weatherEnabled, weatherHour]);

  useEffect(() => {
    if (!eventsEnabled || !homeEventsShouldRetry) return undefined;

    let cancelled = false;
    const retry = homeEventsRetry + 1;
    const timer = window.setTimeout(() => {
      loadHomeEvents(eventsLocation, { retry }).then((events) => {
        if (!cancelled) {
          setHomeData((current) => mergeHomeDataState(current, location, {
            editorialLocation: eventsLocation,
            events,
          }));
        }
      });
    }, 2500);

    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [eventsEnabled, eventsLocation, homeEventsRetry, homeEventsShouldRetry, location]);

  useEffect(() => {
    if (!runtimeRefreshToken) return undefined;

    let cancelled = false;
    let enrichedWeather = null;
    let camsSettled = false;
    const trackDeferredCams = weatherEnabled && isDefinitiveAppExperience()
      && !isLocalWeatherNationalPilot();
    const camsCompletion = createRuntimeComponentCompletion();

    const weatherRefresh = weatherEnabled
      ? loadHomeWeather(location, {
          force: runtimeRefreshForce,
          deferCams: true,
          manageOfficialAlerts: false,
          onCamsFailure: () => {
            camsSettled = true;
            camsCompletion.complete({ status: "unavailable" });
          },
          onCamsUpdate: (nextWeather, lifecycle) => {
            const isTerminal = lifecycle?.lifecycle !== "intermediate";
            if (isTerminal) {
              camsSettled = true;
              camsCompletion.complete(nextWeather);
            }
            enrichedWeather = nextWeather;
            if (!cancelled) {
              setHomeData((current) => mergeHomeDataState(current, location, {
                weather: nextWeather,
              }));
            }
          },
        }).then((nextWeather) => {
          if (!cancelled) {
            setHomeData((current) => mergeHomeDataState(current, location, {
              weather: enrichedWeather || nextWeather,
            }));
          }

          return trackDeferredCams && !camsSettled
            ? { ...nextWeather, runtimeRefreshPendingComponents: ["cams"] }
            : nextWeather;
        }).finally(() => {
          if (!cancelled) {
            setAdviceWeatherLifecycle((current) => ({
              ...current,
              runtimeRefreshToken,
            }));
          }
        })
      : Promise.resolve({ status: forecastAvailability });
    const eventsRefresh = eventsEnabled
      ? loadHomeEvents(eventsLocation).then((events) => {
          if (!cancelled) {
            setHomeData((current) => mergeHomeDataState(current, location, {
              editorialLocation: eventsLocation,
              events,
            }));
          }

          return events;
        })
      : Promise.resolve(createUnavailableEventsState());
    const bulletinRefresh = osmerEnabled
      ? loadBulletinData(location, {
          force: true,
          includeAlerts: false,
        }).then((nextState) => {
          if (!cancelled) setBulletinData(nextState);
          return nextState;
        })
      : null;
    const nationalAlertsRefreshRequestId = nationalAlertsIstat
      ? ++nationalAlertsRequestRef.current
      : 0;
    const nationalAlertsRefresh = nationalAlertsIstat
      ? loadNationalOfficialAlerts(location, { force: true }).then((state) => {
          if (!cancelled && nationalAlertsRequestRef.current === nationalAlertsRefreshRequestId) {
            setNationalAlertsData({ istat: nationalAlertsIstat, state });
          }
          return state;
        })
      : null;

    observeRuntimeRefresh(
      onRuntimeRefreshSettled,
      runtimeRefreshToken,
      [
        weatherRefresh,
        ...(trackDeferredCams ? [camsCompletion.promise] : []),
        eventsRefresh,
        ...(bulletinRefresh ? [bulletinRefresh] : []),
        ...(nationalAlertsRefresh ? [nationalAlertsRefresh] : []),
      ],
      [
        "weather",
        ...(trackDeferredCams ? ["cams"] : []),
        "events",
        ...(bulletinRefresh ? ["osmer"] : []),
        ...(nationalAlertsRefresh ? ["national-alerts"] : []),
      ],
      () => !cancelled,
    );

    return () => {
      cancelled = true;
    };
  }, [eventsEnabled, eventsLocation, forecastAvailability, location, nationalAlertsIstat, onRuntimeRefreshSettled, osmerEnabled, runtimeRefreshToken, runtimeRefreshForce, weatherEnabled]);

  const almanacWeather = weatherMatchesEditorialLocation ? homeData?.weather?.current || null : null;
  const almanac = useMemo(() => (
    buildHomeAlmanacStateFromModel(
      buildAlmanacViewModel({
        date: deviceNow,
        language,
        location: editorialLocation,
        now: deviceNow,
        weather: almanacWeather,
      }),
      { language },
    )
  ), [almanacWeather, deviceNow, editorialLocation, language]);
  const territory = useMemo(() => {
    const discoverModel = buildDiscoverViewModel({
      language,
      location: editorialLocation,
      today: deviceNow,
    });
    return selectHomeDiscoverPreview(discoverModel);
  }, [deviceNow, editorialLocation, language]);

  const homeModel = useMemo(() => {
    const nationalHomeAlert = nationalAlertsIstat
      && nationalAlertsData.istat === nationalAlertsIstat
      ? buildNationalHomeAlertPresentation(nationalAlertsData.state, location, {
          language,
          now: weatherNow.getTime(),
        })
      : null;
    const bulletinContent = bulletinData
      ? buildHomeBulletinFromData(bulletinData, {
        advicePending,
        language,
        location,
        now: weatherNow,
        weatherState: homeData?.weather,
      })
      : { bulletin: null, officialAlert: null };
    const localWeather = homeData?.weather
      ? buildBulletinLocalViewModel(homeData.weather, { language, location, now: weatherNow, hourlyHours: 48 })
      : null;
    const mergedData = {
      ...(homeData || {}),
      ...(marketsCatalogue?.schemaVersion === 2 && eventsEnabled ? { events: {
        ...homeData?.events,
        items: mergeMarketEvents(homeData?.events?.items, { location: eventsLocation,
          radius: eventsLocation.eventsRadius || DEFAULT_EVENTS_RADIUS_KM, now: deviceNow, catalogue: marketsCatalogue }),
      } } : {}),
      editorialLocation: eventsLocation,
      location,
      sourceAvailability: productScope?.sources,
      weather: homeData?.weather
        ? {
          ...homeData.weather,
          officialAlerts: officialAlert === undefined
            ? bulletinData?.officialAlerts
              ?? homeData.weather.officialAlerts
              ?? null
            : null,
        }
        : homeData?.weather,
      bulletin: bulletinContent.bulletin,
      officialAlert: nationalAlertsEnabled
        ? nationalHomeAlert
        : officialAlert === undefined
          ? bulletinContent.officialAlert
          : officialAlert,
      almanac,
      territory,
      localWeather,
      hourly: localWeather
        ? {
            items: localWeather.hourly,
            sourceLabel: localWeather.hourlySourceLabel,
            title: localWeather.evolutionLabel,
          }
        : null,
    };

    return buildHomeViewModel(mergedData, {
      language,
      maxEvents: 3,
      now: deviceNow,
    });
  }, [
    almanac,
    advicePending,
    bulletinData,
    deviceNow,
    eventsLocation,
    eventsEnabled,
    marketsCatalogue,
    homeData,
    language,
    location,
    nationalAlertsData,
    nationalAlertsEnabled,
    nationalAlertsIstat,
    officialAlert,
    productScope,
    territory,
    weatherNow,
  ]);
  return (
    <TabPage className="mf-tab-page--home" language={language} title={copy.placeholders.homeTitle} titleMode="hidden">
      <HomeView
        language={language}
        model={homeModel}
        onChangeLocation={onLocationSearchOpen}
        onNavigate={onNavigate}
        weatherNow={weatherNow}
      />
    </TabPage>
  );
}

function ForecastRouteView({
  runtimeRefreshForce = true,
  activeLocation,
  copy,
  language,
  officialAlert,
  onLocationSearchOpen,
  onNavigate,
  onRuntimeRefreshSettled,
  runtimeRefreshToken = 0,
  showEmbeddedWeatherLocation = true,
  weatherNow,
}) {
  const location = activeLocation || DEFAULT_APP_LOCATION;
  const weatherHour = isDefinitiveAppExperience() ? Math.floor(new Date(weatherNow).getTime() / 3600000) : 0;
  const presentationKey = getLocationCacheKey(location);
  const previousForecastModel = forecastPresentationMemory.get(presentationKey) || null;
  const [weatherLoading, setWeatherLoading] = useState(true);
  const [presentedRefreshToken, setPresentedRefreshToken] = useState(0);
  const trackDeferredCams = isDefinitiveAppExperience() && !isLocalWeatherNationalPilot();
  const startingCamsRefresh = trackDeferredCams && Boolean(runtimeRefreshToken)
    && runtimeRefreshToken !== presentedRefreshToken;
  const [weatherState, setWeatherState] = useState(() => readInitialHomeData(location, {
    manageOfficialAlerts: false,
  })?.weather || null);

  useEffect(() => {
    let cancelled = false;

    const hydrateAndLoadWeather = async () => {
      setWeatherLoading(true);
      const prefetchedWeather = await hydrateHomeWeatherFromBackgroundPrefetch(location, {
        manageOfficialAlerts: false,
      });
      if (!cancelled && prefetchedWeather) setWeatherState(prefetchedWeather);

      const weather = await loadHomeWeather(location, {
        deferCams: true,
        manageOfficialAlerts: false,
        onCamsUpdate: (enrichedWeather) => {
          if (!cancelled) setWeatherState(enrichedWeather);
        },
      });
      if (!cancelled) {
        setWeatherState(weather);
        setWeatherLoading(false);
      }
    };

    void hydrateAndLoadWeather();
    return () => {
      cancelled = true;
    };
  }, [location, weatherHour]);

  useEffect(() => {
    if (!runtimeRefreshToken) return undefined;

    let cancelled = false;
    let enrichedWeather = null;
    let camsSettled = false;
    const camsCompletion = createRuntimeComponentCompletion();
    const refresh = loadHomeWeather(location, {
      force: runtimeRefreshForce,
      manageOfficialAlerts: false,
      deferCams: true,
      onCamsFailure: () => {
        camsSettled = true;
        camsCompletion.complete({ status: "unavailable" });
        if (!cancelled) {
          setPresentedRefreshToken(runtimeRefreshToken);
          setWeatherState(previous => previous
            ? { ...previous, runtimeRefreshPendingComponents: [] } : previous);
        }
      },
      onCamsUpdate: (nextWeather, lifecycle) => {
        const isTerminal = lifecycle?.lifecycle !== "intermediate";
        if (isTerminal) {
          camsSettled = true;
          camsCompletion.complete(nextWeather);
        }
        enrichedWeather = nextWeather;
        if (!cancelled) {
          setPresentedRefreshToken(runtimeRefreshToken);
          setWeatherState(isTerminal ? nextWeather
            : { ...nextWeather, runtimeRefreshPendingComponents: ["cams"] });
        }
      },
    }).then((nextWeather) => {
      // A whole-request failure can finish without a deferred CAMS callback.
      const requestFailed = nextWeather.error
        || nextWeather.rawCurrent?.cache?.runtime_fallback === true
        || nextWeather.rawCurrent?.data_quality?.flags?.includes("runtime_refresh_failed_bundle_retained");
      if (requestFailed && trackDeferredCams && !camsSettled) {
        camsSettled = true;
        camsCompletion.complete({ status: "unavailable" });
      }
      const presentedWeather = trackDeferredCams && !camsSettled
        ? { ...nextWeather, runtimeRefreshPendingComponents: ["cams"] }
        : nextWeather;
      if (!cancelled) {
        setPresentedRefreshToken(runtimeRefreshToken);
        if (!enrichedWeather) setWeatherState(presentedWeather);
      }
      return presentedWeather;
    });

    observeRuntimeRefresh(
      onRuntimeRefreshSettled,
      runtimeRefreshToken,
      [refresh, ...(trackDeferredCams ? [camsCompletion.promise] : [])],
      ["weather", ...(trackDeferredCams ? ["cams"] : [])],
      () => !cancelled,
    );

    return () => {
      cancelled = true;
    };
  }, [location, onRuntimeRefreshSettled, runtimeRefreshToken, runtimeRefreshForce, trackDeferredCams]);

  const model = useMemo(() => {
    if (!weatherState) return null;
    // The new token is visible in the first render, before any provider reply.
    // Keep this request state out of the cached weather snapshot.
    const presentation = startingCamsRefresh
      ? { ...weatherState, runtimeRefreshPendingComponents: ["cams"] }
      : weatherState;
    return buildWeatherForecastViewModel(presentation, {
      language,
      location,
      now: weatherNow,
      previousModel: previousForecastModel,
      loading: weatherLoading,
    });
  }, [language, location, previousForecastModel, startingCamsRefresh, weatherLoading, weatherNow, weatherState]);

  useEffect(() => {
    rememberForecastPresentation(presentationKey, model);
  }, [model, presentationKey]);

  return (
    <TabPage className="mf-tab-page--weather" language={language} title={copy.placeholders.weatherTitle} titleMode="hidden">
      <WeatherForecastView
        location={location}
        language={language}
        model={model}
        onChangeLocation={onLocationSearchOpen}
        officialAlert={officialAlert}
        onOfficialAlertOpen={() => onNavigate?.("bulletin", { anchor: "official-alerts" })}
        showLocationHeader={showEmbeddedWeatherLocation}
        weatherNow={weatherNow}
      />
    </TabPage>
  );
}

function AlmanacRouteView({
  activeLocation,
  copy,
  language,
  onNavigate,
  onRuntimeRefreshSettled,
  runtimeRefreshToken = 0,
}) {
  const location = activeLocation || DEFAULT_APP_LOCATION;
  const [weatherState, setWeatherState] = useState(() => (
    readInitialHomeData(location, { manageOfficialAlerts: false })?.weather || null
  ));

  useEffect(() => {
    let cancelled = false;

    loadHomeWeather(location, { manageOfficialAlerts: false }).then((nextState) => {
      if (!cancelled) {
        setWeatherState(nextState);
      }
    });

    return () => {
      cancelled = true;
    };
  }, [location]);

  useEffect(() => {
    if (!runtimeRefreshToken) return undefined;

    let cancelled = false;
    const weatherRefresh = loadHomeWeather(location, {
      force: true,
      manageOfficialAlerts: false,
    }).then((nextState) => {
      if (!cancelled) {
        setWeatherState(nextState);
      }

      return nextState;
    });

    observeRuntimeRefresh(
      onRuntimeRefreshSettled,
      runtimeRefreshToken,
      [weatherRefresh],
      ["weather"],
      () => !cancelled,
    );

    return () => {
      cancelled = true;
    };
  }, [location, onRuntimeRefreshSettled, runtimeRefreshToken]);

  return (
    <AlmanacPageView
      copy={copy}
      language={language}
      location={location}
      onNavigate={onNavigate}
      weather={getUsableAlmanacWeather(weatherState)}
    />
  );
}

function BulletinRouteView({
  activeLocation,
  copy,
  language,
  officialAlert,
  officialAlertsRuntime,
  onRuntimeRefreshSettled,
  runtimeRefreshToken = 0,
}) {
  const location = activeLocation || DEFAULT_APP_LOCATION;
  const [dataState, setDataState] = useState(() => (
    readInitialBulletinData(location, { includeAlerts: false })
      || createEmptyBulletinDataState()
  ));

  useEffect(() => {
    let cancelled = false;

    loadBulletinData(location, { includeAlerts: false }).then((nextState) => {
      if (!cancelled) {
        setDataState(nextState);
      }
    });
    return () => {
      cancelled = true;
    };
  }, [location]);

  useEffect(() => {
    if (!runtimeRefreshToken) return undefined;

    let cancelled = false;

    const bulletinRefresh = loadBulletinData(location, {
      force: true,
      includeAlerts: false,
    }).then((nextState) => {
      if (!cancelled) {
        setDataState(nextState);
      }

      return nextState;
    });

    observeRuntimeRefresh(
      onRuntimeRefreshSettled,
      runtimeRefreshToken,
      [bulletinRefresh],
      ["osmer"],
      () => !cancelled,
    );

    return () => {
      cancelled = true;
    };
  }, [location, onRuntimeRefreshSettled, runtimeRefreshToken]);

  const model = useMemo(() => {
    const officialAlerts = getOfficialAlertsRuntimePayload(officialAlertsRuntime);
    const modelData = officialAlerts === undefined
      ? dataState
      : { ...dataState, officialAlerts };
    const bulletinModel = buildBulletinViewModel(modelData, { language });

    if (officialAlerts !== undefined || officialAlert === undefined) return bulletinModel;

    return {
      ...bulletinModel,
      alert: officialAlert,
    };
  }, [dataState, language, officialAlert, officialAlertsRuntime]);

  return (
    <BulletinView
      copy={copy}
      language={language}
      model={model}
      storyLayout={isDefinitiveAppExperience()}
    />
  );
}

function EventsRouteView({
  activeLocation,
  eventsRadius = DEFAULT_EVENTS_RADIUS_KM,
  language,
  onMarketsOpen,
  marketEventRequest,
  marketsCatalogue,
  onEventsNavigationState,
  onRuntimeRefreshSettled,
  runtimeRefreshToken = 0,
}) {
  const activeEventsLocation = marketEventRequest?.location || activeLocation || DEFAULT_APP_LOCATION;
  const location = useMemo(() => ({
    ...activeEventsLocation,
    eventsRadius: normalizeEventsRadius(eventsRadius) ?? DEFAULT_EVENTS_RADIUS_KM,
  }), [activeEventsLocation, eventsRadius]);
  const [marketNow, setMarketNow] = useState(() => new Date());
  useEffect(() => subscribeToMarketsDayClock(setMarketNow), []);
  const [dataState, setDataState] = useState(() => (
    readEventsRouteInitialState(location)
  ));

  useEffect(() => {
    onEventsNavigationState?.(location, dataState);
  }, [dataState, location, onEventsNavigationState]);

  useEffect(() => {
    let cancelled = false;

    loadAndCommitEventsRouteData(location, {
      isCurrent: () => !cancelled,
      onCommit: setDataState,
    });

    return () => {
      cancelled = true;
    };
  }, [location]);

  useEffect(() => {
    if (!runtimeRefreshToken) return undefined;

    let cancelled = false;

    const eventsRefresh = loadEventsData(location, { force: true }).then((nextState) => {
        if (!cancelled) {
          setDataState(nextState);
        }

        return nextState;
    });
    observeRuntimeRefresh(
      onRuntimeRefreshSettled,
      runtimeRefreshToken,
      [eventsRefresh],
      ["events"],
      () => !cancelled,
    );

    return () => {
      cancelled = true;
    };
  }, [location, onRuntimeRefreshSettled, runtimeRefreshToken]);

  useEffect(() => {
    if (!dataState.shouldRetry) return undefined;

    let cancelled = false;
    const retry = Number(dataState.retry || 0) + 1;
    const timer = window.setTimeout(() => {
      loadEventsData(location, { force: true, retry }).then((nextState) => {
        if (!cancelled) {
          setDataState(nextState);
        }
      });
    }, 2500);

    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [dataState.retry, dataState.shouldRetry, location]);

  const model = useMemo(
    () => buildEventsViewModel({ ...dataState, items: mergeMarketEvents(dataState.items, {
      location, radius: location.eventsRadius || DEFAULT_EVENTS_RADIUS_KM, now: marketNow, catalogue: marketsCatalogue,
    }) }, { language, location, now: new Date(marketDay(marketNow) + 'T12:00:00') }),
    [dataState, language, location, marketNow, marketsCatalogue],
  );

  return (
    <EventsView
      key={marketEventRequest?.key || 'events'}
      marketEventRequest={marketEventRequest}
      catalogue={marketsCatalogue}
      onMarketsOpen={onMarketsOpen}
      language={language}
      model={model}
      radius={location.eventsRadius}
      onChangeLocation={undefined}
      showCardSource={!isDefinitiveAppExperience()}
      titleMode={isDefinitiveAppExperience() ? "hidden" : "visible"}
    />
  );
}

function EventsAvailabilityRouteView({
  language,
  municipalityLocation,
  onRuntimeRefreshSettled,
  runtimeRefreshToken = 0,
}) {
  const eventsCopy = getEventsViewCopy(language);
  const locationLabel = getLocationDisplayName(municipalityLocation, language)
    || (language === "fur" ? "cheste localitât" : "questa località");
  const body = eventsCopy.fvgOnlyBody.replace("{location}", locationLabel);

  useEffect(() => {
    if (runtimeRefreshToken) onRuntimeRefreshSettled?.(runtimeRefreshToken, {
      complete: true,
      components: ["events"],
      ok: true,
      partial: false,
    });
  }, [onRuntimeRefreshSettled, runtimeRefreshToken]);

  return (
    <TabPage
      className="mf-tab-page--events"
      language={language}
      title={eventsCopy.viewTitle}
      titleMode="hidden"
    >
      <EmptyState body={body} title={eventsCopy.fvgOnlyTitle} />
    </TabPage>
  );
}

function ForecastAvailabilityRouteView({
  copy,
  language,
  onRuntimeRefreshSettled,
  productScope,
  runtimeRefreshToken = 0,
}) {
  const planned = productScope?.sources?.forecast?.status === "planned";

  useEffect(() => {
    if (runtimeRefreshToken) onRuntimeRefreshSettled?.(runtimeRefreshToken, {
      complete: true,
      components: ["weather"],
      ok: true,
      partial: false,
    });
  }, [onRuntimeRefreshSettled, runtimeRefreshToken]);

  return (
    <TabPage className="mf-tab-page--weather" language={language} title={copy.placeholders.weatherTitle} titleMode="hidden">
      <EmptyState
        body={planned
          ? language === "fur"
            ? "Lis previsions ICON-2I nazionâls no son inmò disponibilis par cheste localitât. No doprin Open-Meteo come sostitut: il meteo al restarà no disponibil fintremai che il dât autonom nol sarà pront."
            : "Le previsioni ICON-2I nazionali non sono ancora disponibili per questa località. Non usiamo Open-Meteo come ripiego: il meteo resterà non disponibile finché il dato autonomo non sarà pronto."
          : language === "fur"
            ? "Meteo Friûl al supuarte pal moment localitâts talianis. Nissun dât meteo al ven domandât par cheste localitât."
            : "Meteo Friûl supporta al momento località italiane. Nessun dato meteo viene richiesto per questa località."}
        title={planned
          ? language === "fur" ? "Previsions nazionâls in preparazion" : "Previsioni nazionali in preparazione"
          : language === "fur" ? "Localitât fûr de cuvierture" : "Località fuori copertura"}
      />
    </TabPage>
  );
}

function NationalAlertsRouteView({
  activeLocation,
  copy,
  language,
  onRuntimeRefreshSettled,
  runtimeRefreshToken = 0,
}) {
  const location = activeLocation || DEFAULT_APP_LOCATION;
  const [state, setState] = useState(() => (
    readInitialNationalOfficialAlerts(location) || createNationalOfficialAlertsState()
  ));

  useEffect(() => {
    let cancelled = false;
    loadNationalOfficialAlerts(location).then((nextState) => {
      if (!cancelled) setState(nextState);
    });
    return () => { cancelled = true; };
  }, [location]);

  useEffect(() => {
    if (!runtimeRefreshToken) return undefined;
    let cancelled = false;
    const refresh = loadNationalOfficialAlerts(location, { force: true }).then((nextState) => {
      if (!cancelled) setState(nextState);
      return nextState;
    });
    observeRuntimeRefresh(
      onRuntimeRefreshSettled,
      runtimeRefreshToken,
      [refresh],
      ["national-alerts"],
      () => !cancelled,
    );
    return () => { cancelled = true; };
  }, [location, onRuntimeRefreshSettled, runtimeRefreshToken]);

  return <NationalOfficialAlertsView copy={copy} language={language} state={state} />;
}

function NationalAlertsAvailabilityRouteView({
  copy,
  language,
  onRuntimeRefreshSettled,
  runtimeRefreshToken = 0,
}) {
  useEffect(() => {
    if (runtimeRefreshToken) onRuntimeRefreshSettled?.(runtimeRefreshToken, {
      complete: true,
      components: ["national-alerts"],
      ok: true,
      partial: false,
    });
  }, [onRuntimeRefreshSettled, runtimeRefreshToken]);

  return (
    <TabPage className="mf-tab-page--bulletin" language={language} title={copy.placeholders.bulletinTitle} titleMode="hidden">
      <EmptyState
        body={language === "fur"
          ? "Lis alertis talianis no vegnin domandadis par cheste localitât."
          : "Le allerte italiane non vengono richieste per questa località."}
        title={language === "fur" ? "Localitât fûr de cuvierture" : "Località fuori copertura"}
      />
    </TabPage>
  );
}

function LiveRouteView({
  activeLocation,
  communityIdentity,
  language,
  officialAlert,
  productScope,
  onCommunityNavigationState,
  onCommunityReportsViewed,
  onLocationSearchOpen,
  onNavigate,
  onReportSubmit,
  onReportUndo,
  onReportUpdate,
  onReportWithdraw,
  onRuntimeRefreshSettled,
  pendingReportUndo,
  reportSubmissionLocked = false,
  runtimeRefreshToken = 0,
  showEmbeddedWeatherLocation = true,
  theme = "light",
}) {
  const location = activeLocation || DEFAULT_APP_LOCATION;
  const [sharedReportTarget] = useState(readCommunityReportShareTarget);
  const communityLocation = useMemo(() => (
    sharedReportTarget?.istatCode
      ? { istatCode: sharedReportTarget.istatCode }
      : location
  ), [location, sharedReportTarget]);
  const communityReadable = productScope?.community?.read !== false;
  const radarEnabled = productScope?.sources?.radar?.status === "enabled";
  const communityReportPreviewMode = getLocalCommunityReportPreviewMode();
  const communityReportInteractive = communityReadable
    && communityReportPreviewMode === COMMUNITY_REPORT_PREVIEW_MODE_INTERACTIVE;
  const communityReportQa = communityReadable && Boolean(communityReportPreviewMode);
  const communityReportPreview = communityReportQa && !communityReportInteractive;
  const communityEnabled = communityReadable && !communityReportInteractive;
  const webcamsEnabled = productScope?.sources?.webcams?.status === "enabled";
  const webcamPlayerPreview = Boolean(getLocalWebcamPlayerPreviewMode());
  const [communityPreviewStorage] = useState(createCommunityReportPreviewMemoryStorage);
  const communityPersonalStorage = communityReportInteractive
    ? communityPreviewStorage
    : undefined;
  const [pendingReportUpdates, setPendingReportUpdates] = useState(() => (
    isLocalCommunityPilot() ? readPendingLiveCommunityReportUpdates() : []
  ));
  const [dataState, setDataState] = useState(() => (
    readInitialLiveData({ communityLocation, communityEnabled, webcamsEnabled }) || createEmptyLiveDataState()
  ));
  const [radarDataState, setRadarDataState] = useState(() => (
    radarEnabled
      ? readInitialBulletinRadarData(location, { enabled: radarEnabled }) || createEmptyBulletinRadarDataState()
      : createEmptyBulletinRadarDataState()
  ));
  const [communitySimulationOverlay, setCommunitySimulationOverlay] = useState(() => (
    createCommunityReportSimulationOverlay(createEmptyLiveDataState())
  ));
  const communitySimulationOverlayRef = useRef(communitySimulationOverlay);
  useEffect(() => { communitySimulationOverlayRef.current = communitySimulationOverlay; }, [communitySimulationOverlay]);
  const liveLoadSequenceRef = useRef(0);
  const liveRouteMountedRef = useRef(false);
  const loadAndCommitLiveData = useCallback(async (options) => {
    const sequence = liveLoadSequenceRef.current + 1;
    liveLoadSequenceRef.current = sequence;
    const nextState = await loadLiveData({
      ...options,
      communityLocation,
      communityEnabled,
      webcamsEnabled,
      onUpdate: (partialState) => {
        if (liveRouteMountedRef.current && liveLoadSequenceRef.current === sequence) {
          setDataState(partialState);
        }
      },
    });

    if (liveRouteMountedRef.current && liveLoadSequenceRef.current === sequence) {
      setDataState(nextState);
    }

    return nextState;
  }, [communityEnabled, communityLocation, webcamsEnabled]);

  useEffect(() => {
    liveRouteMountedRef.current = true;

    loadAndCommitLiveData({ forceCommunity: true });
    if (radarEnabled) {
      loadBulletinRadarData(location, { enabled: radarEnabled }).then((nextState) => {
        if (liveRouteMountedRef.current) setRadarDataState(nextState);
      });
    }

    return () => {
      liveRouteMountedRef.current = false;
      liveLoadSequenceRef.current += 1;
    };
  }, [communityEnabled, loadAndCommitLiveData, location, radarEnabled, webcamsEnabled]);

  useEffect(() => {
    if (!runtimeRefreshToken) return undefined;

    let cancelled = false;
    const liveRefresh = loadAndCommitLiveData({ force: true });
    const radarRefresh = radarEnabled
      ? loadBulletinRadarData(location, { enabled: radarEnabled, force: true }).then((nextState) => {
          if (!cancelled) setRadarDataState(nextState);
          return nextState;
        })
      : Promise.resolve({ status: "unsupported" });

    observeRuntimeRefresh(
      onRuntimeRefreshSettled,
      runtimeRefreshToken,
      [liveRefresh, radarRefresh],
      ["live", "radar"],
      () => !cancelled,
    );

    return () => {
      cancelled = true;
    };
  }, [loadAndCommitLiveData, location, onRuntimeRefreshSettled, radarEnabled, runtimeRefreshToken]);

  useEffect(() => {
    if (!radarEnabled) return undefined;

    let cancelled = false;
    const documentRef = globalThis.document;
    const windowRef = globalThis.window;
    const refreshRadar = () => {
      loadBulletinRadarData(location, { enabled: radarEnabled }).then((nextState) => {
        if (!cancelled) setRadarDataState(nextState);
      });
    };
    const intervalId = windowRef?.setInterval(
      refreshRadar,
      BULLETIN_RADAR_AUTO_REFRESH_INTERVAL_MS,
    );
    const handleVisibilityChange = () => {
      if (documentRef?.visibilityState === "visible") refreshRadar();
    };

    documentRef?.addEventListener("visibilitychange", handleVisibilityChange);
    return () => {
      cancelled = true;
      documentRef?.removeEventListener("visibilitychange", handleVisibilityChange);
      if (intervalId !== undefined) windowRef?.clearInterval(intervalId);
    };
  }, [location, radarEnabled]);

  useEffect(() => {
    const documentRef = globalThis.document;
    const windowRef = globalThis.window;

    const refreshCommunity = () => {
      loadAndCommitLiveData({ forceCommunity: true });
    };

    const intervalId = windowRef?.setInterval(
      refreshCommunity,
      LIVE_AUTO_REFRESH_INTERVAL_MS,
    );
    const handleVisibilityChange = () => {
      if (documentRef?.visibilityState === "visible") refreshCommunity();
    };

    documentRef?.addEventListener("visibilitychange", handleVisibilityChange);

    return () => {
      documentRef?.removeEventListener("visibilitychange", handleVisibilityChange);
      if (intervalId !== undefined) windowRef?.clearInterval(intervalId);
    };
  }, [communityEnabled, loadAndCommitLiveData]);

  const model = useMemo(
    () => {
      const communityPreviewState = communityReportInteractive
        ? applyCommunityReportSimulationOverlay(dataState, communitySimulationOverlay)
        : communityReadable && communityReportPreviewMode === COMMUNITY_REPORT_PREVIEW_MODE_ACTIVE
          ? createCommunityReportActivePreviewState(dataState)
          : dataState;
      const previewState = webcamPlayerPreview && webcamsEnabled
        ? createWebcamPlayerPreviewState(communityPreviewState)
        : communityPreviewState;

      return buildLiveViewModel(previewState, {
        language,
        location,
        webcamsEnabled,
      });
    },
    [
      communityReportInteractive,
      communityReportPreviewMode,
      communityReadable,
      communitySimulationOverlay,
      dataState,
      language,
      location,
      webcamPlayerPreview,
      webcamsEnabled,
    ],
  );
  const radarModel = useMemo(
    () => radarEnabled
      ? buildBulletinRadarViewModel(radarDataState, { language, location })
      : null,
    [language, location, radarDataState, radarEnabled],
  );

  useEffect(() => {
    if (!isLocalCommunityPilot()) return;
    const timeoutId = globalThis.setTimeout?.(() => {
      if (dataState.community?.status === "fresh") {
        const reports = Array.isArray(dataState.community?.payload?.reports)
          ? dataState.community.payload.reports
          : [];
        const knownReports = readCommunityPersonalState().reports;
        reports.forEach((report) => {
          if (knownReports.some((receipt) => receipt.reportId === report.id)) {
            refreshCommunityReportReceipt(readCommunityPersonalState(), report);
          }
          const result = reconcilePendingLiveCommunityReportUpdate(report);
          if (!result.ok) return;
          refreshCommunityReportReceipt(
            readCommunityPersonalState(),
            result.report,
          );
        });
      }
      setPendingReportUpdates(readPendingLiveCommunityReportUpdates());
    }, 0);
    return () => {
      if (timeoutId !== undefined) globalThis.clearTimeout?.(timeoutId);
    };
  }, [dataState.community]);

  useEffect(() => {
    onCommunityNavigationState?.(location, model.community, {
      personalState: readCommunityPersonalState({ storage: communityPersonalStorage }),
    });
  }, [communityPersonalStorage, location, model.community, onCommunityNavigationState]);

  const handleReportsViewed = useCallback((communityModel, personalState) => {
    onCommunityReportsViewed?.(location, communityModel, { personalState });
  }, [location, onCommunityReportsViewed]);

  const handleReportConfirm = async (groupId, vote, consent) => {
    const result = await confirmLiveCommunityReport(groupId, vote, consent);

    if (result.ok) {
      void loadAndCommitLiveData({ forceCommunity: true }).catch(() => undefined);
    }

    return result;
  };

  const handleReportWithdraw = async (reportId, options) => {
    if (!onReportWithdraw) return { ok: false, reason: "unavailable" };
    const result = await onReportWithdraw(reportId, options);
    if (result?.ok) {
      void loadAndCommitLiveData({ forceCommunity: true }).catch(() => undefined);
    }
    return result;
  };

  const handleReportUpdate = async (report) => {
    if (!onReportUpdate) return { ok: false, reason: "unavailable" };
    const result = await onReportUpdate(report);
    if (
      result?.ok
      || result?.reason === "observation_expired"
      || result?.reason === "observation_conflict"
      || result?.reason === "observation_rejected"
    ) {
      await loadAndCommitLiveData({ forceCommunity: true }).catch(() => undefined);
    }
    setPendingReportUpdates(readPendingLiveCommunityReportUpdates());
    return result;
  };

  const handleSimulationReportSubmit = async (typeId, reportLocation, consent) => {
    const mutation = isLocalCommunityPilot() ? applyPilotReportSimulationSubmission(
      communitySimulationOverlayRef.current,
      typeId,
      reportLocation,
      {
        ...consent,
        identity: buildPublicCommunityIdentitySnapshot(communityIdentity),
      },
    ) : applyCommunityReportSimulationSubmission(
      communitySimulationOverlayRef.current,
      typeId,
      reportLocation,
      {
        identity: buildPublicCommunityIdentitySnapshot(communityIdentity),
      },
    );
    const { result } = mutation;
    // Commit even when phase two fails: the accepted retirement and its grant
    // must survive on the QA map and on a retry from the same render callback.
    communitySimulationOverlayRef.current = mutation.overlay;
    setCommunitySimulationOverlay(mutation.overlay);
    if (result.replacementWithdrawn && result.replacedReportId) withdrawCommunityReport(
      readCommunityPersonalState({ storage: communityPersonalStorage }),
      result.replacedReportId, { storage: communityPersonalStorage },
    );
    if (result.ok) {
      (consent?.correctionReport ? refreshCommunityReportReceipt : rememberCommunityReport)(
        readCommunityPersonalState({ storage: communityPersonalStorage }),
        result.report,
        { storage: communityPersonalStorage },
      );
    }
    return result;
  };

  const handleSimulationReportAction = async (kind, report) => {
    const mutation = applyPilotReportSimulation(communitySimulationOverlay, kind, { report });
    if (mutation.result.ok) {
      setCommunitySimulationOverlay(mutation.overlay);
      if (mutation.result.report) refreshCommunityReportReceipt(
        readCommunityPersonalState({ storage: communityPersonalStorage }),
        mutation.result.report, { storage: communityPersonalStorage },
      );
      else withdrawCommunityReport(
        readCommunityPersonalState({ storage: communityPersonalStorage }),
        report.reportId, { storage: communityPersonalStorage },
      );
    }
    return mutation.result;
  };

  const handleSimulationReportConfirm = async (groupId, vote) => {
    const mutation = applyCommunityReportSimulationConfirmation(
      communitySimulationOverlay,
      groupId,
      vote,
    );
    if (mutation.result.ok) setCommunitySimulationOverlay(mutation.overlay);
    return mutation.result;
  };

  const handleSimulationReportUndo = async (reportId) => {
    const mutation = applyCommunityReportSimulationUndo(
      communitySimulationOverlay,
      reportId,
    );
    const { result } = mutation;
    if (result.ok) {
      setCommunitySimulationOverlay(mutation.overlay);
      forgetCommunityReport(
        readCommunityPersonalState({ storage: communityPersonalStorage }),
        reportId,
        { storage: communityPersonalStorage },
      );
    }
    return result;
  };

  return (
    <LiveView
      compactLayout={isDefinitiveAppExperience()}
      language={language}
      model={model}
      onChangeLocation={onLocationSearchOpen}
      officialAlert={officialAlert}
      onOfficialAlertOpen={() => onNavigate?.("bulletin", { anchor: "official-alerts" })}
      onReportConfirm={communityReportInteractive
        ? handleSimulationReportConfirm
        : communityReportPreview
          ? undefined
          : handleReportConfirm}
      onReportLocate={communityReportQa ? undefined : locateLiveCommunityReport}
      onReportRefresh={isLocalCommunityPilot() && !communityReportQa ? () => loadAndCommitLiveData({ forceCommunity: true }) : undefined}
      onReportsViewed={isDefinitiveAppExperience() && onCommunityReportsViewed ? handleReportsViewed : undefined}
      onReportSubmit={communityReportInteractive
        ? handleSimulationReportSubmit
        : communityReportPreview
          ? undefined
          : onReportSubmit}
      onReportUndo={isLocalCommunityPilot() ? undefined : communityReportInteractive
        ? handleSimulationReportUndo
        : communityReportPreview
          ? undefined
          : onReportUndo}
      onReportUpdate={
        communityReportInteractive
          ? (report) => handleSimulationReportAction("update", report)
          : !communityReportQa && isLocalCommunityPilot() && onReportUpdate
          ? handleReportUpdate
          : undefined
      }
      pendingReportUpdates={communityReportQa ? [] : pendingReportUpdates}
      onReportWithdraw={
        communityReportInteractive
          ? (reportId, options = {}) => handleSimulationReportAction(options.replace ? "replace" : "withdraw", { reportId })
          : !communityReportQa && isLocalCommunityPilot() && onReportWithdraw
          ? handleReportWithdraw
          : undefined
      }
      pendingReportUndo={communityReportQa ? null : pendingReportUndo}
      personalStorage={communityPersonalStorage}
      radarModel={radarModel}
      reportingEnabled={productScope?.community?.write ? undefined : false}
      reportingUnavailableText={productScope?.community?.unavailableMessage || ""}
      reportingPreview={communityReportPreview}
      reportingSimulation={communityReportInteractive}
      sharedReportId={sharedReportTarget?.groupId || ""}
      sharedReportLoadSettled={dataState.community?.status === "fresh"}
      showLocationContext={showEmbeddedWeatherLocation}
      submissionLocked={reportSubmissionLocked}
      theme={theme}
    />
  );
}

const ROUTES = {
  home: HomeRouteView,
  weather: ForecastRouteView,
  almanac: AlmanacRouteView,
  bulletin: BulletinRouteView,
  live: LiveRouteView,
  events: EventsRouteView,
  discover: DiscoverView,
  settings: SettingsView,
};

const WEATHER_ROUTE_IDS = new Set(["weather", "bulletin", "live"]);
const ROUTES_WITH_RUNTIME_REFRESH = new Set(["home", "weather", "almanac", "bulletin", "events", "live"]);

export function AppRoutes({
  runtimeRefreshForce = true,
  activeTab,
  activeLocation = DEFAULT_APP_LOCATION,
  eventsRadius = DEFAULT_EVENTS_RADIUS_KM,
  onEventsRadiusChange,
  appVersion,
  autoLocationEnabled = false,
  backgroundLocationRuntime,
  communityIdentity = null,
  copy,
  deviceLocationStatus,
  editorialContext,
  labEnabled = false,
  language,
  notificationPreferences,
  notificationRuntime,
  officialAlert,
  officialAlertsRuntime,
  productScope,
  onAutomaticLocationChange,
  onBackgroundLocationSettingsOpen,
  onCommunityIdentityChange,
  onCommunityNavigationState,
  onCommunityReportsViewed,
  onLanguageSelect,
  onEventsNavigationState,
  onLocationSearchOpen,
  onNavigate,
  onNotificationPermissionRequest,
  onNotificationPreferenceChange,
  onNotificationSettingsOpen,
  onReportSubmit,
  onReportUndo,
  onReportUpdate,
  onReportWithdraw,
  onRuntimeCacheReset,
  onSupportOpen,
  onRuntimeRefreshSettled,
  onSettingsBack,
  onThemePreferenceChange,
  pendingReportUndo,
  pilotWhyId = "",
  reportSubmissionLocked = false,
  routeAnchorRequest,
  runtimeRefreshToken = 0,
  theme = "light",
  themePreference,
  supportUrl,
}) {
  const localWeatherPilot = isDefinitiveAppExperience();
  const editorialLocation = editorialContext?.focusLocation || DEFAULT_APP_LOCATION;
  const routeKey = getAppRouteViewKey(activeTab, activeLocation, editorialLocation);
  const marketLocation = localWeatherPilot
    ? getPilotMunicipalityContext({ activeLocation, autoLocationEnabled, deviceLocationStatus })?.location || null
    : activeLocation;
  const marketLocationKey = getLocationCacheKey(marketLocation);
  const [marketCatalogueRequest, setMarketCatalogueRequest] = useState(null);
  const [marketEventRequest, setMarketEventRequest] = useState(null);
  const marketsState = useMarketsCatalogue({ enabled: ["home", "events"].includes(activeTab) || Boolean(marketCatalogueRequest),
    refreshToken: `${activeTab}:${runtimeRefreshToken}:${marketCatalogueRequest?.key || 0}` });
  const marketVisit = useRef(0);
  const [marketContext, setMarketContext] = useState({ tab: activeTab, locationKey: marketLocationKey });
  if (marketContext.tab !== activeTab || marketContext.locationKey !== marketLocationKey) {
    setMarketContext({ tab: activeTab, locationKey: marketLocationKey });
    // An edition link belongs to this visit; normal navigation must not reopen it.
    if ((marketContext.tab === "events" && activeTab !== "events") || marketContext.locationKey !== marketLocationKey) {
      setMarketEventRequest(null);
    }
    setMarketCatalogueRequest(null);
  }
  const openMarkets = useCallback((marketId = null) => {
    if (reportSubmissionLocked) return;
    setMarketCatalogueRequest({ marketId, key: ++marketVisit.current, locationKey: marketLocationKey });
  }, [marketLocationKey, reportSubmissionLocked]);
  const openMarketEvent = useCallback((request) => {
    if (reportSubmissionLocked) return;
    setMarketEventRequest({ ...request, location: marketLocation, key: ++marketVisit.current, locationKey: marketLocationKey });
    setMarketCatalogueRequest(null);
    onNavigate?.("events");
  }, [marketLocation, marketLocationKey, onNavigate, reportSubmissionLocked]);
  const routeRuntimeRefreshToken = useRouteRuntimeRefreshToken(routeKey, runtimeRefreshToken);
  const previousRouteRefreshRef = useRef({ routeKey, token: routeRuntimeRefreshToken });
  useEffect(() => {
    const previous = previousRouteRefreshRef.current;
    previousRouteRefreshRef.current = { routeKey, token: routeRuntimeRefreshToken };
    if (previous.routeKey !== routeKey && previous.token) {
      onRuntimeRefreshSettled?.(previous.token, { complete: true, status: "superseded" });
    }
  }, [onRuntimeRefreshSettled, routeKey, routeRuntimeRefreshToken]);
  const effectiveProductScope = productScope || resolveProductScope(
    activeLocation || DEFAULT_APP_LOCATION,
    { language, nationalForecastEnabled: isLocalWeatherNationalPilot(), nationalCommunityEnabled: isLocalCommunityPilot() },
  );
  const pendingRouteAnchorRef = useRef(null);
  const [deviceNow, setDeviceNow] = useState(() => new Date());
  useEffect(() => subscribeToHomeSolarClock(setDeviceNow), []);
  const weatherNow = resolveWeatherRouteNow(deviceNow, getLocalWeatherPilotTestNow());
  const handleRouteNavigation = useCallback((nextTab, options = {}) => {
    if (reportSubmissionLocked) return;

    const anchor = typeof options?.anchor === "string" ? options.anchor.trim() : "";
    const whyId = typeof options?.whyId === "string" ? options.whyId.trim() : "";
    pendingRouteAnchorRef.current = anchor ? { anchor, tab: nextTab } : null;
    if (whyId) {
      onNavigate?.(nextTab, { whyId });
    } else {
      onNavigate?.(nextTab);
    }
  }, [onNavigate, reportSubmissionLocked]);

  useEffect(() => {
    const anchor = typeof routeAnchorRequest?.anchor === "string"
      ? routeAnchorRequest.anchor.trim()
      : "";
    const tab = typeof routeAnchorRequest?.tab === "string"
      ? routeAnchorRequest.tab.trim()
      : "";
    if (!anchor || !tab) return;

    pendingRouteAnchorRef.current = { anchor, tab };
  }, [routeAnchorRequest]);

  useEffect(() => {
    const routeRefreshesData = ROUTES_WITH_RUNTIME_REFRESH.has(activeTab) && !(activeTab === "home" && labEnabled);
    if (!routeRuntimeRefreshToken || routeRefreshesData) return;

    onRuntimeRefreshSettled?.(routeRuntimeRefreshToken);
  }, [activeTab, labEnabled, onRuntimeRefreshSettled, routeRuntimeRefreshToken]);

  useEffect(() => {
    const pendingRouteAnchor = pendingRouteAnchorRef.current;
    if (!pendingRouteAnchor || activeTab !== pendingRouteAnchor.tab) return undefined;

    let attempt = 0;
    let cancelled = false;
    let timer = null;
    const revealTarget = () => {
      if (cancelled) return;

      const target = document.getElementById(pendingRouteAnchor.anchor);
      if (target) {
        const navigation = target.closest(".mf-weather-route-shell")
          ?.querySelector(".mf-section-navigation--sticky");
        if (navigation) {
          const gap = Number.parseFloat(getComputedStyle(navigation.parentElement).rowGap) || 0;
          target.style.scrollMarginTop = String(navigation.getBoundingClientRect().height + gap) + "px";
        }
        target.scrollIntoView({ block: "start", behavior: "auto" });
        target.focus?.({ preventScroll: true });
        pendingRouteAnchorRef.current = null;
        return;
      }

      attempt += 1;
      if (attempt < 6) {
        timer = window.setTimeout(revealTarget, 16);
      } else {
        pendingRouteAnchorRef.current = null;
      }
    };

    timer = window.setTimeout(revealTarget, 0);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [activeTab, routeAnchorRequest]);

  if (activeTab === "home" && labEnabled) {
    return <HomeLabView copy={copy} language={language} onNavigate={handleRouteNavigation} />;
  }

  const routeId = localWeatherPilot && activeTab === "almanac" ? "discover" : activeTab;
  const View = activeTab === "weather"
    && effectiveProductScope.sources.forecast.status !== "enabled"
    ? ForecastAvailabilityRouteView
    : activeTab === "bulletin"
      && effectiveProductScope.sources.osmer.status !== "enabled"
      ? effectiveProductScope.sources.nationalAlerts.status === "enabled"
        ? NationalAlertsRouteView
        : NationalAlertsAvailabilityRouteView
      : activeTab === "events"
        && !marketEventRequest
        && effectiveProductScope.sources.events?.status === "unsupported"
        ? EventsAvailabilityRouteView
        : ROUTES[routeId] || ROUTES.home;
  const viewLocation = ["almanac", "discover"].includes(activeTab)
    ? editorialLocation
    : activeLocation;
  const routeView = (
    <View
      key={activeTab === "events" || activeTab === "home" ? `${routeKey}:radius-${eventsRadius}` : activeTab === "live" && isLocalCommunityPilot() ? `${routeKey}:${getLocationCacheKey(activeLocation)}` : routeKey}
      copy={copy}
      activeLocation={viewLocation}
      eventsRadius={eventsRadius}
      onEventsRadiusChange={onEventsRadiusChange}
      municipalityLocation={activeLocation || null}
      appVersion={appVersion}
      autoLocationEnabled={autoLocationEnabled}
      backgroundLocationRuntime={backgroundLocationRuntime}
      communityIdentity={communityIdentity}
      deviceLocationStatus={deviceLocationStatus}
      editorialContext={editorialContext}
      deviceNow={deviceNow}
      language={language}
      notificationPreferences={notificationPreferences}
      notificationRuntime={notificationRuntime}
      officialAlert={officialAlert}
      officialAlertsRuntime={officialAlertsRuntime}
      productScope={effectiveProductScope}
      onAutomaticLocationChange={onAutomaticLocationChange}
      onBackgroundLocationSettingsOpen={onBackgroundLocationSettingsOpen}
      onCommunityIdentityChange={onCommunityIdentityChange}
      onCommunityNavigationState={onCommunityNavigationState}
      onCommunityReportsViewed={onCommunityReportsViewed}
      onLanguageSelect={onLanguageSelect}
      onEventsNavigationState={onEventsNavigationState}
      onLocationSearchOpen={activeTab === "settings" ? onLocationSearchOpen : undefined}
      onNavigate={handleRouteNavigation}
      onNotificationPermissionRequest={onNotificationPermissionRequest}
      onNotificationPreferenceChange={onNotificationPreferenceChange}
      onNotificationSettingsOpen={onNotificationSettingsOpen}
      onReportSubmit={onReportSubmit}
      onReportUndo={onReportUndo}
      onReportUpdate={onReportUpdate}
      onReportWithdraw={onReportWithdraw}
      onRuntimeCacheReset={onRuntimeCacheReset}
      onSupportOpen={onSupportOpen}
      onRuntimeRefreshSettled={onRuntimeRefreshSettled}
      onSettingsBack={onSettingsBack}
      onThemePreferenceChange={onThemePreferenceChange}
      pendingReportUndo={pendingReportUndo}
      pilotWhyId={pilotWhyId}
      onMarketsOpen={openMarkets}
      marketEventRequest={marketEventRequest?.locationKey === marketLocationKey ? marketEventRequest : null}
      marketsCatalogue={marketsState.catalogue}
      reportSubmissionLocked={reportSubmissionLocked}
      runtimeRefreshToken={routeRuntimeRefreshToken}
      runtimeRefreshForce={runtimeRefreshForce}
      showEmbeddedWeatherLocation={!localWeatherPilot}
      themePreference={themePreference}
      supportUrl={supportUrl}
      theme={theme}
      weatherNow={weatherNow}
    />
  );

  return (
    <Suspense
      fallback={(
        <TabPage
          language={language}
          title={copy.placeholders[`${activeTab}Title`] || copy.placeholders.homeTitle}
          titleMode={localWeatherPilot ? "hidden" : "visible"}
        >
          <EmptyState body={copy.placeholders.almanacBody} title={copy.placeholders.almanacTitle} />
        </TabPage>
      )}
    >
      {WEATHER_ROUTE_IDS.has(activeTab) ? (
        <WeatherSwipeShell activeId={activeTab} disabled={localWeatherPilot || reportSubmissionLocked} onNavigate={handleRouteNavigation}>
          <div className={"mf-section-navigation" + (localWeatherPilot && activeTab === "bulletin" ? " mf-section-navigation--sticky" : "")}>
            {localWeatherPilot ? (
              <LocationContext
                city={getLocationDisplayName(activeLocation || DEFAULT_APP_LOCATION, language)}
                className="mf-route-location-context mf-weather-route-context"
              />
            ) : (
              <h1 className="mf-weather-route-title">{language === "fur" ? "Timp" : "Meteo"}</h1>
            )}
            <WeatherSectionNav
              activeId={activeTab}
              compact={localWeatherPilot}
              disabled={reportSubmissionLocked}
              language={language}
              onNavigate={handleRouteNavigation}
            />
          </div>
          {routeView}
        </WeatherSwipeShell>
      ) : routeView}
      <MarketsExplorer
        key={marketLocationKey}
        request={marketCatalogueRequest?.locationKey === marketLocationKey ? marketCatalogueRequest : null}
        location={marketLocation}
        radius={normalizeEventsRadius(eventsRadius) ?? DEFAULT_EVENTS_RADIUS_KM}
        language={language}
        onClose={() => setMarketCatalogueRequest(null)}
        onViewEvent={openMarketEvent}
        catalogue={marketsState.catalogue}
        catalogueStatus={marketsState.status}
      />
    </Suspense>
  );
}
