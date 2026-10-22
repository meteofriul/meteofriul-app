import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { App as CapacitorApp } from "@capacitor/app";

import { APP_ROUTE_IDS, APP_TABS, getPrimaryTabId } from "./appConfig";
import {
  isNativeAndroidRuntime,
  readAndroidStartupPromptStorage,
  shouldPersistAndroidStartupNotificationPatch,
  writeAndroidStartupNotificationStoragePatch,
} from "./androidStartupRuntime";
import {
  DEFAULT_APP_LOCATION,
  readInitialAppLocation,
  readStoredAutoLocationEnabled,
  readStoredAppLocation,
  writeStoredAppLocation,
  writeStoredAutoLocationEnabled,
} from "./appLocation";
import {
  readInitialEditorialContext,
  writeStoredEditorialContext,
} from "./editorialContext";
import {
  createLatestLocationRequestGuard,
  getAutomaticLocationBootstrapState,
  getAutomaticLocationQualityDecision,
  getDisabledAutomaticLocationStatus,
  startAutomaticLocationRuntime,
} from "./autoLocationRuntime";
import {
  changeAutomaticLocationMode,
  runManualLocationChange,
} from "./locationActions";
import { readUiV3LabFlag } from "./labFlags";
import {
  getNativeReleaseIdentity,
  isNativeReleaseIdentityKnown,
} from "./nativeReleaseIdentity";
import {
  DEFAULT_THEME_PREFERENCE,
  normalizeThemePreference,
  readUiThemePreference,
  resolveThemePreference,
  THEME_STORAGE_KEY,
} from "./themePreference";
import {
  readUiLanguagePreference,
  syncDocumentLanguage,
  writeUiLanguagePreference,
} from "./languagePreference";
import {
  readNotificationPreferences,
  writeNotificationPreferences,
} from "./notificationPreferences";
import { getUiShellCopy } from "./uiShellCopy";
import { AppRoutes } from "./AppRoutes";
import {
  createCommunityNavigationSnapshot,
  getCommunityNavigationTotal,
  getEventsNavigationPeriod,
  getEventsNavigationTotal,
  getPilotWhyRequestId,
  readEventsNavigationSnapshot,
  reconcileCommunityNavigationSnapshot,
  reconcileEventsNavigationSnapshot,
} from "./appRouteRuntime";
import { createPilotRouteHistory } from "./pilotRouteHistory";
import { useBrowserDialogBack } from "./useBrowserDialogBack";
import { setPilotBackPageHandler } from "../services/pilotBackNavigation";
import {
  shouldReplaceResolvedPlace,
  shouldKeepAutoLocationEnabledAfterFailure,
  shouldRunForegroundAutoLocationCheck,
} from "../domain/geo/autoLocationPolicy";
import { getLocationPrimaryName } from "../domain/geo/locationIdentity";
import { getNextOfficialAlertExpiryAt } from "../domain/alerts/officialAlerts";
import { resolveProductScope } from "../domain/scope/productScope";
import { runAndroidStartupPromptFlow } from "../domain/startup/androidStartupPromptFlow";
import {
  getRuntimeRefreshGateOutcome,
  getRuntimeRefreshTimeoutOutcome,
  RUNTIME_FOREGROUND_REFRESH_MIN_INTERVAL_MS,
  RUNTIME_REFRESH_COMPLETION_TIMEOUT_MS,
  RUNTIME_WEATHER_VERIFY_INTERVAL_MS,
  shouldRunRuntimeRefresh,
} from "../domain/runtime/runtimeRefreshPolicy";
import { LocationSearchSheet } from "../features/location/LocationSearchSheet";
import { loadHomeWeather } from "../features/home/homeDataController";
import {
  isDefinitiveAppExperience,
  isLocalWeatherNationalPilot,
  isLocalWeatherPilot,
  isOfficialAppRelease,
} from "../services/localWeatherPilot";
import { buildOfficialAlertPresentation } from "../features/bulletin/bulletinViewModel";
import { WebPushForegroundBanner } from "../features/notifications/WebPushForegroundBanner";
import { PilotLanguageOnboarding } from "../features/startup/PilotLanguageOnboarding";
import { WebStartupOnboarding } from "../features/startup/WebStartupOnboarding";
import { BackgroundLocationDisclosure } from "../features/settings/BackgroundLocationDisclosure";
import { getBackgroundLocationDisclosureCopy } from "../features/settings/backgroundLocationDisclosureCopy";
import {
  buildPublicCommunityIdentitySnapshot,
  persistCommunityIdentity,
  readCommunityIdentity,
} from "../features/community/communityIdentity";
import {
  hasAcceptedBackgroundLocationDisclosure,
  markBackgroundLocationDisclosureAccepted,
  markBackgroundLocationDisclosureShown,
  shouldOpenBackgroundLocationDisclosure,
} from "../features/settings/backgroundLocationDisclosureState";
import {
  readWebStartupOnboardingState,
  writeWebStartupOnboardingState,
} from "../features/startup/webStartupOnboardingState";
import {
  readPilotLanguageOnboardingState,
  shouldShowPilotLanguageOnboarding,
  writePilotLanguageOnboardingState,
} from "../features/startup/pilotLanguageOnboardingState";
import {
  locateLiveCommunityReport,
  submitLiveCommunityReport,
  undoLiveCommunityReport,
  updateLiveCommunityReport,
  withdrawLiveCommunityReport,
} from "../features/live/liveReportController";
import { rememberCommunityGuidelinesConsent } from "../features/live/communityGuidelinesConsent";
import { performPilotReportOperation } from "../features/live/pilotReportOperations";
import {
  expireCommunityReport,
  forgetCommunityReport,
  readCommunityPersonalState,
  releaseCommunityReportReceipt,
  refreshCommunityReportReceipt,
  rememberCommunityReport,
  withdrawCommunityReport,
} from "../features/live/communityPersonalState";
import { runPersistentLiveReportSubmission } from "../features/live/liveReportSubmission";
import {
  LIVE_AUTO_REFRESH_INTERVAL_MS,
  loadLiveData,
  readInitialLiveData,
} from "../features/live/liveDataController";
import {
  createCommunityReportPreviewMemoryStorage,
  getLocalCommunityReportPreviewMode,
} from "../features/live/communityReportPreview";
import {
  getCommunityUnreadCount,
  markCommunitySnapshotSeen,
  readCommunitySeenState,
  writeCommunitySeenState,
} from "../features/live/communityUnreadState";
import { isLocalCommunityPilot } from "../services/localCommunityPilot";
import { buildLiveViewModel } from "../features/live/liveViewModel";
import {
  clearLiveReportUndoState,
  readLiveReportUndoState,
  writeLiveReportUndoState,
} from "../features/live/liveReportUndoState";
import {
  buildReliableDeviceAppLocation,
  getDeviceAppLocationUpdatePlan,
  requestDeviceCoordinates,
} from "../services/deviceLocation";
import { resolveReverseLocation } from "../services/reverseLocation";
import { clearRuntimeDeviceCaches } from "../services/runtimeDeviceCache";
import { applyNativeSystemBarsTheme } from "../services/nativeSystemBars";
import { syncWebThemeColor } from "../services/webThemeColor";
import {
  NATIVE_PUSH_PERMISSION,
  addNativePushListeners,
  checkNativePushPermission,
  createNativePushRuntime,
  ensureNativePushAndroidChannels,
  getNativePushNotificationsPlugin,
  openNativeNotificationSettings,
  registerNativePush,
  requestNativePushPermission,
} from "../services/nativePushAdapter";
import {
  readOrCreatePushInstallationId,
  readPushInstallationId,
  registerPushDevice,
  unregisterPushDevice,
} from "../services/pushDeviceRegistration";
import {
  configureBackgroundLocation,
  DEFAULT_BACKGROUND_LOCATION_STATUS,
  openBackgroundLocationSettings,
  readBackgroundLocationStatus,
} from "../services/backgroundLocationAdapter";
import {
  addWebPushListeners,
  createWebPushRuntime,
  getWebPushForegroundContent,
  getWebPushErrorDiagnostic,
  getWebPushRegistrationRetryDelayMs,
  readWebPushPermission,
  registerWebPush,
  requestWebPushPermission,
  shouldRetryWebPushRegistration,
  unregisterWebPush,
} from "../services/firebaseWebMessaging";
import { getPushNavigationTarget } from "../services/pushDeepLink";
import { getNationalOfficialAlertsIstat } from "../services/nationalOfficialAlertsApi";
import {
  CAPACITOR_AUTO_LOCATION_RESUME_INTERVAL_MS,
  createRateLimitedAppResumeHandler,
  runCapacitorResumeSequence,
  startCapacitorAppResumeRuntime,
} from "../services/capacitorAppResume";
import {
  getConfiguredSupportUrl,
  openSupportUrl,
} from "../services/supportLink";
import { readWeatherBootstrapCache } from "../services/weatherApi";
import {
  createOfficialAlertsRuntimeState,
  loadOfficialAlertsRuntime,
  readInitialOfficialAlertsRuntime,
} from "../services/officialAlertsRuntime";
import { AppShell } from "../ui/layout/AppShell";
import frontendPackage from "../../package.json";

function readInitialTabId() {
  const tabId = new URLSearchParams(globalThis.window?.location?.search || "").get("tab");

  return APP_ROUTE_IDS.includes(tabId) ? tabId : "home";
}

function readInitialThemePreference() {
  return readUiThemePreference();
}

function readSystemDarkPreference() {
  return Boolean(globalThis.window?.matchMedia?.("(prefers-color-scheme: dark)")?.matches);
}

function areNotificationPreferencesEnabled(preferences) {
  return preferences?.officialAlerts !== false
    || preferences?.nationalOfficialAlerts === true
    || preferences?.weatherNotices !== false;
}

export default function App() {
  const localWeatherPilot = isLocalWeatherPilot();
  const definitiveAppExperience = isDefinitiveAppExperience();
  const officialAppRelease = isOfficialAppRelease();
  const communityReportPreviewMode = localWeatherPilot
    ? getLocalCommunityReportPreviewMode()
    : "";
  const supportUrl = getConfiguredSupportUrl();
  const [activeTab, setActiveTab] = useState(readInitialTabId);
  const [pilotWhyId, setPilotWhyId] = useState("");
  const pilotRouteHistoryRef = useRef(null);
  if (pilotRouteHistoryRef.current === null) {
    pilotRouteHistoryRef.current = createPilotRouteHistory(activeTab);
  }
  const [settingsReturnTab, setSettingsReturnTab] = useState(() => {
    const initialTab = readInitialTabId();

    return initialTab === "settings" ? "home" : initialTab;
  });
  const [activeLocation, setActiveLocation] = useState(readInitialAppLocation);
  const [editorialContext] = useState(() => readInitialEditorialContext({
    weatherLocation: activeLocation,
  }));
  const [communityIdentity, setCommunityIdentity] = useState(readCommunityIdentity);
  const [communityNavigationSnapshot, setCommunityNavigationSnapshot] = useState(null);
  const [communitySeenStorage] = useState(() => communityReportPreviewMode
    ? createCommunityReportPreviewMemoryStorage()
    : undefined);
  const [communitySeenState, setCommunitySeenState] = useState(() => readCommunitySeenState({
    storage: definitiveAppExperience ? communitySeenStorage : null,
  }));
  const [communityNavigationRefreshTick, setCommunityNavigationRefreshTick] = useState(0);
  const [eventsNavigationSnapshot, setEventsNavigationSnapshot] = useState(null);
  const [autoLocationEnabled, setAutoLocationEnabled] = useState(() => {
    const enabled = readStoredAutoLocationEnabled();
    const location = readInitialAppLocation();
    const bootstrapState = getAutomaticLocationBootstrapState({ enabled, location });

    if (bootstrapState.requiresStorageRepair) {
      writeStoredAutoLocationEnabled(false);
    }

    return bootstrapState.autoLocationEnabled;
  });
  const [deviceLocationStatus, setDeviceLocationStatus] = useState({ status: "idle" });
  const [language, setLanguage] = useState(readUiLanguagePreference);
  const [isLocationSearchOpen, setLocationSearchOpen] = useState(false);
  const [runtimeRefreshToken, setRuntimeRefreshToken] = useState(0);
  const [runtimeRefreshForce, setRuntimeRefreshForce] = useState(true);
  const [routeAnchorRequest, setRouteAnchorRequest] = useState(null);
  const [notificationPreferences, setNotificationPreferences] = useState(readNotificationPreferences);
  const [officialAlertsRuntime, setOfficialAlertsRuntime] = useState(
    readInitialOfficialAlertsRuntime,
  );
  const [officialAlertsEvaluationAt, setOfficialAlertsEvaluationAt] = useState(Date.now);
  const [notificationRuntime, setNotificationRuntime] = useState(() => {
    const nativeAndroid = isNativeAndroidRuntime();

    return {
      connected: false,
      permission: NATIVE_PUSH_PERMISSION.unknown,
      platform: nativeAndroid ? "android" : "web",
      readOnly: !nativeAndroid,
      status: nativeAndroid ? "connecting" : "checking",
    };
  });
  const [backgroundLocationRuntime, setBackgroundLocationRuntime] = useState(() => ({
    ...DEFAULT_BACKGROUND_LOCATION_STATUS,
    available: isNativeAndroidRuntime(),
  }));
  const [backgroundLocationDisclosureAccepted, setBackgroundLocationDisclosureAccepted] = useState(
    hasAcceptedBackgroundLocationDisclosure,
  );
  const [backgroundLocationDisclosureContext, setBackgroundLocationDisclosureContext] = useState(null);
  const [nativeAppVersion, setNativeAppVersion] = useState("unknown");
  const [pushRegistrationRevision, setPushRegistrationRevision] = useState(0);
  const [pushToken, setPushToken] = useState("");
  const [webRegistrationFid, setWebRegistrationFid] = useState("");
  const [webPushActivationFailures, setWebPushActivationFailures] = useState(0);
  const [webPushForegroundMessage, setWebPushForegroundMessage] = useState(null);
  const [pilotLanguageOnboardingVisible, setPilotLanguageOnboardingVisible] = useState(() => (
    shouldShowPilotLanguageOnboarding({
      pilot: definitiveAppExperience,
      state: definitiveAppExperience ? readPilotLanguageOnboardingState() : "completed",
    })
  ));
  const [webStartupOnboarding, setWebStartupOnboarding] = useState(() => ({
    busy: false,
    locationResult: null,
    manualLocationPending: false,
    step: "location",
    visible: !isNativeAndroidRuntime() && readWebStartupOnboardingState() === "pending",
  }));
  const [isReportSubmissionLocked, setReportSubmissionLocked] = useState(false);
  const [pendingReportUndo, setPendingReportUndo] = useState(readLiveReportUndoState);
  const [themePreference, setThemePreference] = useState(readInitialThemePreference);
  const [systemDark, setSystemDark] = useState(readSystemDarkPreference);
  const foregroundRefreshAtRef = useRef(0);
  const activeLocationRef = useRef(activeLocation);
  const autoLocationEnabledRef = useRef(autoLocationEnabled);
  const autoLocationLastCheckedAtRef = useRef(0);
  const automaticLocationRefreshPromiseRef = useRef(null);
  const backgroundLocationConfigurationQueueRef = useRef(Promise.resolve());
  const backgroundLocationDisclosureAcceptedRef = useRef(backgroundLocationDisclosureAccepted);
  const backgroundLocationDisclosurePromiseRef = useRef(null);
  const backgroundLocationDisclosureResolverRef = useRef(null);
  const locationRequestAbortRef = useRef(null);
  const locationRequestGuardRef = useRef(null);
  const communityNavigationRefreshCycleRef = useRef({ runtime: 0, tick: 0 });
  const runtimeRefreshResolversRef = useRef(new Map());
  const runtimeRefreshSequenceRef = useRef(0);
  const reportSubmissionLockedRef = useRef(false);
  const reportSubmissionPromiseRef = useRef(null);
  const startupPromptFlowStartedRef = useRef(false);
  const pushRuntimeInitializationRef = useRef(
    Promise.resolve(createNativePushRuntime()),
  );
  const pushActivationRef = useRef({ complete: false, promise: null });
  const pushDeviceSyncQueueRef = useRef(Promise.resolve());
  const nativePushPermissionRef = useRef(NATIVE_PUSH_PERMISSION.unknown);
  const webPushPermissionRef = useRef(NATIVE_PUSH_PERMISSION.unknown);
  const webPushRuntimeRef = useRef(null);
  const webPushRuntimeInitializationRef = useRef(Promise.resolve(null));
  const webPushActivationRef = useRef({ promise: null, registrationRequested: false });
  const webPushUnregisteredRef = useRef(false);
  const webPushPreferencesRef = useRef(notificationPreferences);
  const labEnabled = readUiV3LabFlag();
  const theme = resolveThemePreference(themePreference, systemDark);
  const copy = useMemo(() => getUiShellCopy(language), [language]);
  const navActiveTab = getPrimaryTabId(activeTab);
  const productScope = useMemo(
    () => resolveProductScope(activeLocation, {
      language,
      nationalForecastEnabled: officialAppRelease || isLocalWeatherNationalPilot(),
      nationalCommunityEnabled: isLocalCommunityPilot(),
    }),
    [activeLocation, language, officialAppRelease],
  );
  const officialAlertsEnabled = productScope.sources.osmer.status === "enabled";
  const officialAlert = useMemo(
    () => officialAlertsEnabled
      ? buildOfficialAlertPresentation(officialAlertsRuntime.payload, {
          language,
          now: officialAlertsEvaluationAt,
        })
      : null,
    [language, officialAlertsEnabled, officialAlertsEvaluationAt, officialAlertsRuntime.payload],
  );
  const eventsEnabled = productScope.sources.events?.status !== "unsupported";
  const cachedEventsNavigationSnapshot = useMemo(() => (
    definitiveAppExperience && eventsEnabled
      ? readEventsNavigationSnapshot(activeLocation)
      : null
  ), [activeLocation, definitiveAppExperience, eventsEnabled]);
  const liveEventsNavigationTotal = definitiveAppExperience && eventsEnabled
    ? getEventsNavigationTotal(eventsNavigationSnapshot, activeLocation)
    : null;
  const resolvedEventsNavigationSnapshot = liveEventsNavigationTotal !== null
    ? eventsNavigationSnapshot
    : cachedEventsNavigationSnapshot;
  const eventsNavigationTotal = definitiveAppExperience && eventsEnabled
    ? getEventsNavigationTotal(resolvedEventsNavigationSnapshot, activeLocation)
    : null;
  const eventsNavigationPeriod = definitiveAppExperience && eventsEnabled
    ? getEventsNavigationPeriod(resolvedEventsNavigationSnapshot, activeLocation)
    : null;
  const cachedCommunityNavigationSnapshot = useMemo(() => {
    if (
      !definitiveAppExperience
      || communityReportPreviewMode
      || productScope.community.read === false
    ) return null;
    const cachedLiveData = readInitialLiveData({
      communityLocation: activeLocation,
      communityEnabled: true,
      webcamsEnabled: false,
    });
    if (!cachedLiveData) return null;
    const cachedCommunityModel = buildLiveViewModel(cachedLiveData, {
      language,
      location: activeLocation,
      webcamsEnabled: false,
    }).community;
    return createCommunityNavigationSnapshot(activeLocation, cachedCommunityModel, {
      personalState: readCommunityPersonalState(),
    });
  }, [
    activeLocation,
    communityReportPreviewMode,
    language,
    definitiveAppExperience,
    productScope.community.read,
  ]);
  const liveCommunityNavigationTotal = definitiveAppExperience
    ? getCommunityNavigationTotal(communityNavigationSnapshot, activeLocation)
    : null;
  const resolvedCommunityNavigationSnapshot = liveCommunityNavigationTotal !== null
    ? communityNavigationSnapshot
    : cachedCommunityNavigationSnapshot;
  const communityReportsTotal = definitiveAppExperience && productScope.community.read !== false
    && getCommunityNavigationTotal(resolvedCommunityNavigationSnapshot, activeLocation) !== null
    ? getCommunityUnreadCount(resolvedCommunityNavigationSnapshot?.unread, communitySeenState)
    : null;

  useEffect(() => {
    if (!definitiveAppExperience) return;
    writeCommunitySeenState(communitySeenState, { storage: communitySeenStorage });
  }, [communitySeenState, communitySeenStorage, definitiveAppExperience]);

  if (locationRequestGuardRef.current == null) {
    locationRequestGuardRef.current = createLatestLocationRequestGuard();
  }

  const settleRuntimeRefreshPart = useCallback((token, part, outcome = {}) => {
    const entry = runtimeRefreshResolversRef.current.get(token);
    if (!entry) return;

    if (part === "route" && outcome.status === "superseded") {
      window.clearTimeout(entry.timeout);
      runtimeRefreshResolversRef.current.delete(token);
      entry.resolve({ status: "superseded", token });
      return;
    }

    entry[part] = outcome;
    if (entry.route?.complete === false) return;
    const completion = getRuntimeRefreshGateOutcome({
      officialAlerts: entry.officialAlerts,
      officialAlertsRequired: entry.officialAlertsRequired,
      route: entry.route,
    });
    if (!completion) return;

    window.clearTimeout(entry.timeout);
    runtimeRefreshResolversRef.current.delete(token);
    entry.resolve({
      components: completion.components,
      status: completion.ok
        ? completion.partial ? "partial" : "settled"
        : "failed",
      token,
    });
  }, []);

  useEffect(() => {
    webPushPreferencesRef.current = notificationPreferences;
  }, [notificationPreferences]);

  useEffect(() => {
    if (!officialAlertsEnabled) return undefined;
    let cancelled = false;

    loadOfficialAlertsRuntime({ force: Boolean(runtimeRefreshToken) }).then((nextState) => {
      if (cancelled) return;

      setOfficialAlertsRuntime(nextState);
      setOfficialAlertsEvaluationAt(Date.now());
      if (runtimeRefreshToken) {
        settleRuntimeRefreshPart(runtimeRefreshToken, "officialAlerts", nextState);
      }
    }).catch((error) => {
      if (cancelled) return;

      const failedState = createOfficialAlertsRuntimeState(null, {
        error,
        now: Date.now,
        status: "error",
      });
      if (runtimeRefreshToken) {
        settleRuntimeRefreshPart(runtimeRefreshToken, "officialAlerts", failedState);
      }
    });

    return () => {
      cancelled = true;
    };
  }, [officialAlertsEnabled, runtimeRefreshToken, settleRuntimeRefreshPart]);

  useEffect(() => {
    if (!officialAlertsEnabled) return undefined;
    const nextExpiryAt = getNextOfficialAlertExpiryAt(officialAlertsRuntime.payload, {
      now: officialAlertsEvaluationAt,
    });
    if (nextExpiryAt === null) return undefined;

    const delay = Math.max(0, nextExpiryAt - Date.now());
    const timeout = window.setTimeout(() => {
      const evaluatedAt = Math.max(Date.now(), nextExpiryAt);
      setOfficialAlertsEvaluationAt(evaluatedAt);
      setOfficialAlertsRuntime((current) => createOfficialAlertsRuntimeState(current.payload, {
        error: current.error,
        fromCache: current.fromCache,
        now: evaluatedAt,
        retained: current.retained,
        status: current.status,
      }));
    }, delay);

    return () => window.clearTimeout(timeout);
  }, [officialAlertsEnabled, officialAlertsEvaluationAt, officialAlertsRuntime.payload]);

  useEffect(() => {
    if (
      !definitiveAppExperience
      || communityReportPreviewMode
      || productScope.community.read === false
    ) return undefined;

    const intervalId = globalThis.setInterval?.(() => {
      setCommunityNavigationRefreshTick((current) => current + 1);
    }, LIVE_AUTO_REFRESH_INTERVAL_MS);

    return () => globalThis.clearInterval?.(intervalId);
  }, [communityReportPreviewMode, definitiveAppExperience, productScope.community.read]);

  useEffect(() => {
    const refreshCycle = {
      runtime: runtimeRefreshToken,
      tick: communityNavigationRefreshTick,
    };
    const previousRefreshCycle = communityNavigationRefreshCycleRef.current;
    const runtimeChanged = refreshCycle.runtime !== previousRefreshCycle.runtime;
    const tickChanged = refreshCycle.tick !== previousRefreshCycle.tick;
    const refreshRequested = runtimeChanged || tickChanged;
    const currentTotal = getCommunityNavigationTotal(
      communityNavigationSnapshot,
      activeLocation,
    );

    if (
      !definitiveAppExperience
      || productScope.community.read === false
      || activeTab === "live"
      || Boolean(communityReportPreviewMode)
      || (currentTotal !== null && !refreshRequested)
    ) return undefined;

    let cancelled = false;
    loadLiveData({
      communityLocation: activeLocation,
      communityEnabled: true,
      forceCommunity: tickChanged || (runtimeChanged && runtimeRefreshForce)
        || currentTotal === null || !communityNavigationSnapshot?.unread?.ready,
      webcamsEnabled: false,
    }).then((nextState) => {
      if (cancelled) return;
      const communityModel = buildLiveViewModel(nextState, {
        language,
        location: activeLocation,
        webcamsEnabled: false,
      }).community;
      communityNavigationRefreshCycleRef.current = refreshCycle;
      setCommunityNavigationSnapshot((current) => reconcileCommunityNavigationSnapshot(
        current,
        activeLocation,
        activeLocation,
        communityModel,
        { personalState: readCommunityPersonalState() },
      ));
    }).catch(() => undefined);

    return () => {
      cancelled = true;
    };
  }, [
    activeLocation,
    activeTab,
    communityNavigationSnapshot,
    communityReportPreviewMode,
    communityNavigationRefreshTick,
    language,
    definitiveAppExperience,
    productScope.community.read,
    runtimeRefreshForce,
    runtimeRefreshToken,
  ]);

  const requestBackgroundLocationDisclosure = useCallback(({
    autoLocationEnabled: requestedAutoLocationEnabled = autoLocationEnabledRef.current,
    context = "startup",
  } = {}) => {
    if (!isNativeAndroidRuntime()) return Promise.resolve(true);
    if (!shouldOpenBackgroundLocationDisclosure({
      autoLocationEnabled: requestedAutoLocationEnabled,
      hasAccepted: backgroundLocationDisclosureAcceptedRef.current,
      isNativeAndroid: true,
    })) {
      return Promise.resolve(true);
    }
    if (backgroundLocationDisclosurePromiseRef.current) {
      return backgroundLocationDisclosurePromiseRef.current;
    }

    let resolveDisclosure;
    const disclosurePromise = new Promise((resolve) => {
      resolveDisclosure = resolve;
    });
    backgroundLocationDisclosurePromiseRef.current = disclosurePromise;
    backgroundLocationDisclosureResolverRef.current = resolveDisclosure;
    setBackgroundLocationDisclosureContext(context === "settings" ? "settings" : "startup");
    return disclosurePromise;
  }, []);

  const settleBackgroundLocationDisclosure = useCallback((accepted) => {
    markBackgroundLocationDisclosureShown();
    const consentRecorded = Boolean(
      accepted && markBackgroundLocationDisclosureAccepted(),
    );

    if (consentRecorded) {
      backgroundLocationDisclosureAcceptedRef.current = true;
      setBackgroundLocationDisclosureAccepted(true);
      setPushRegistrationRevision((revision) => revision + 1);
    }

    const resolveDisclosure = backgroundLocationDisclosureResolverRef.current;
    backgroundLocationDisclosureResolverRef.current = null;
    backgroundLocationDisclosurePromiseRef.current = null;
    setBackgroundLocationDisclosureContext(null);
    resolveDisclosure?.(consentRecorded);
    return consentRecorded;
  }, []);

  useEffect(() => () => {
    backgroundLocationDisclosureResolverRef.current?.(false);
    backgroundLocationDisclosureResolverRef.current = null;
    backgroundLocationDisclosurePromiseRef.current = null;
  }, []);

  const nextLanguage = language === "it" ? "fur" : "it";

  const syncBackgroundLocationConfiguration = useCallback(async ({
    enabled,
    installationId = "",
  }) => {
    const disclosureAccepted = backgroundLocationDisclosureAcceptedRef.current;
    const configure = async () => {
      try {
        const status = await configureBackgroundLocation({
          disclosureAccepted,
          enabled: Boolean(enabled),
          installationId,
        });
        setBackgroundLocationRuntime(status);
        return status;
      } catch {
        setBackgroundLocationRuntime((current) => ({
          ...current,
          available: isNativeAndroidRuntime(),
          lastStatus: "configure_failed",
          trackingActive: false,
        }));
        return null;
      }
    };
    const pendingConfiguration = backgroundLocationConfigurationQueueRef.current
      .catch(() => {})
      .then(configure);
    backgroundLocationConfigurationQueueRef.current = pendingConfiguration;
    return pendingConfiguration;
  }, []);

  const refreshBackgroundLocationRuntime = useCallback(async () => {
    if (!backgroundLocationDisclosureAcceptedRef.current) {
      return syncBackgroundLocationConfiguration({ enabled: false });
    }

    try {
      const status = await readBackgroundLocationStatus();
      setBackgroundLocationRuntime(status);
      return status;
    } catch {
      setBackgroundLocationRuntime((current) => ({
        ...current,
        lastStatus: "status_failed",
        trackingActive: false,
      }));
      return null;
    }
  }, [syncBackgroundLocationConfiguration]);

  const handleRouteChange = useCallback((nextTab, options = {}) => {
    if (reportSubmissionLockedRef.current) return;

    const normalizedTab = APP_ROUTE_IDS.includes(nextTab) ? nextTab : "home";

    if (isDefinitiveAppExperience()) pilotRouteHistoryRef.current.visit(normalizedTab);
    setPilotWhyId(getPilotWhyRequestId(normalizedTab, options));
    setActiveTab(normalizedTab);

    if (normalizedTab !== "settings") {
      setSettingsReturnTab(normalizedTab);
    }
  }, []);

  const handleSettingsOpen = useCallback(() => {
    if (reportSubmissionLockedRef.current) return;

    setSettingsReturnTab((currentTab) => (activeTab !== "settings" ? activeTab : currentTab || "home"));
    if (isDefinitiveAppExperience()) pilotRouteHistoryRef.current.visit("settings");
    setPilotWhyId("");
    setActiveTab("settings");
  }, [activeTab]);

  const handleSettingsBack = useCallback(() => {
    if (reportSubmissionLockedRef.current) return;

    const nextTab = isDefinitiveAppExperience()
      ? pilotRouteHistoryRef.current.back()
      : APP_ROUTE_IDS.includes(settingsReturnTab) && settingsReturnTab !== "settings"
        ? settingsReturnTab
        : "home";

    setPilotWhyId("");
    setActiveTab(nextTab);
  }, [settingsReturnTab]);

  useBrowserDialogBack(handleSettingsBack, activeTab === "settings");

  useEffect(() => {
    if (!isDefinitiveAppExperience()) return undefined;
    return setPilotBackPageHandler(() => {
      if (reportSubmissionLockedRef.current) return;
      const nextTab = pilotRouteHistoryRef.current.back();
      setPilotWhyId("");
      setActiveTab(nextTab);
      if (nextTab !== "settings") setSettingsReturnTab(nextTab);
    }, {
      atRoot: activeTab === "home",
      canExit: () => !reportSubmissionLockedRef.current,
    });
  }, [activeTab]);

  const handleReportSubmissionStateChange = useCallback((isLocked) => {
    const locked = Boolean(isLocked);
    reportSubmissionLockedRef.current = locked;
    setReportSubmissionLocked(locked);
  }, []);

  const requestRuntimeRefresh = useCallback(({ force = false } = {}) => {
    const now = Date.now();
    if (isDefinitiveAppExperience() && runtimeRefreshResolversRef.current.size) {
      return Promise.resolve({ status: "skipped" });
    }
    const shouldRefresh = shouldRunRuntimeRefresh({
      force,
      lastRefreshAt: foregroundRefreshAtRef.current,
      minIntervalMs: isDefinitiveAppExperience() ? 10 * 60 * 1000 : RUNTIME_FOREGROUND_REFRESH_MIN_INTERVAL_MS,
      now,
      visibilityState: document.visibilityState,
    });

    if (!shouldRefresh) {
      return Promise.resolve({ status: "skipped" });
    }

    foregroundRefreshAtRef.current = now;
    if (isDefinitiveAppExperience()) {
      // Keep the selected municipality warm even while Events/Discover is open.
      // The weather runtime coalesces this with any visible route request.
      void loadHomeWeather(activeLocationRef.current || DEFAULT_APP_LOCATION, {
        force, deferCams: true, manageOfficialAlerts: false, retryUnavailableCams: true,
      });
    }

    const nextToken = runtimeRefreshSequenceRef.current + 1;
    runtimeRefreshSequenceRef.current = nextToken;
    setRuntimeRefreshToken(nextToken);
    setRuntimeRefreshForce(isDefinitiveAppExperience() ? force : true);

    return new Promise((resolve) => {
      const timeout = window.setTimeout(() => {
        const entry = runtimeRefreshResolversRef.current.get(nextToken);
        runtimeRefreshResolversRef.current.delete(nextToken);
        const completion = getRuntimeRefreshTimeoutOutcome(entry);
        resolve({
          components: completion.components,
          status: completion.ok ? "partial" : "timeout",
          token: nextToken,
        });
      }, RUNTIME_REFRESH_COMPLETION_TIMEOUT_MS);

      runtimeRefreshResolversRef.current.set(nextToken, {
        officialAlertsRequired: officialAlertsEnabled,
        resolve,
        timeout,
      });
    });
  }, [officialAlertsEnabled]);

  const handleCommunityReportSubmit = useCallback((typeId, reportLocation, consent) => {
    return runPersistentLiveReportSubmission({
      onStateChange: handleReportSubmissionStateChange,
      onSuccess: (result) => {
        rememberCommunityGuidelinesConsent(consent?.policyVersion);
        if (isLocalCommunityPilot() && result.expired) expireCommunityReport(readCommunityPersonalState(), result.reportId);
        else if (consent?.correctionReport) refreshCommunityReportReceipt(readCommunityPersonalState(), result.report);
        else rememberCommunityReport(readCommunityPersonalState(), result.report);
        setPendingReportUndo(writeLiveReportUndoState({
          reportId: result.report?.id,
          undoUntil: result.undoUntil,
        }));
        requestRuntimeRefresh({ force: true });
      },
      operation: () => submitLiveCommunityReport(typeId, reportLocation, {
        ...consent,
        identity: buildPublicCommunityIdentitySnapshot(communityIdentity),
      }),
      promiseRef: reportSubmissionPromiseRef,
    });
  }, [communityIdentity, handleReportSubmissionStateChange, requestRuntimeRefresh]);

  const handleCommunityReportUndo = useCallback(async (reportId) => {
    const result = await undoLiveCommunityReport(reportId);

    if (result.ok) {
      forgetCommunityReport(readCommunityPersonalState(), reportId);
      clearLiveReportUndoState();
      setPendingReportUndo(null);
      requestRuntimeRefresh({ force: true });
    }

    return result;
  }, [requestRuntimeRefresh]);

  const handleCommunityReportWithdraw = useCallback(async (reportId, options = {}) => {
    const report = options.report || readCommunityPersonalState().reports.find((item) => item.reportId === reportId);
    const result = isLocalCommunityPilot()
      ? await performPilotReportOperation(options.replace ? "replace" : "withdraw", {
        reportId, expectedRevision: report?.revision || 1,
      })
      : await withdrawLiveCommunityReport(reportId);

    if (result.ok) {
      withdrawCommunityReport(readCommunityPersonalState(), reportId);
      setPendingReportUndo((current) => {
        if (current?.reportId !== reportId) return current;
        clearLiveReportUndoState();
        return null;
      });
    }

    return result;
  }, []);

  const handleCommunityReportUpdate = useCallback(async (report) => {
    const location = await locateLiveCommunityReport();
    if (!location?.ok) return location;

    const result = await updateLiveCommunityReport(report, location, {
      acceptedTerms: true,
    });
    if (result?.ok && result.report) {
      refreshCommunityReportReceipt(readCommunityPersonalState(), result.report);
    } else if (result?.reason === "observation_expired") {
      expireCommunityReport(readCommunityPersonalState(), result.reportId);
    } else if (result?.reason === "observation_conflict") {
      const personalState = readCommunityPersonalState();
      const receipt = personalState.reports.find((item) => item.reportId === result.reportId);
      const revision = Number(result.serverState?.revision);
      if (receipt && Number.isInteger(revision) && revision > 0) {
        refreshCommunityReportReceipt(personalState, {
          ...receipt,
          expiresAt: Number(result.serverState?.expires_at) || receipt.expiresAt,
          id: receipt.reportId,
          revision,
        });
      }
    } else if (result?.reason === "observation_rejected") {
      const personalState = readCommunityPersonalState();
      if (result.code === "community_observation_not_active") {
        expireCommunityReport(personalState, result.reportId);
      } else {
        releaseCommunityReportReceipt(personalState, result.reportId);
      }
    }
    return result;
  }, []);

  const handleRuntimeRefreshSettled = useCallback((token, outcome = {}) => {
    settleRuntimeRefreshPart(token, "route", outcome);
  }, [settleRuntimeRefreshPart]);

  useEffect(() => () => {
    runtimeRefreshResolversRef.current.forEach((entry) => {
      window.clearTimeout(entry.timeout);
      entry.resolve({ status: "cancelled" });
    });
    runtimeRefreshResolversRef.current.clear();
  }, []);

  useEffect(() => {
    activeLocationRef.current = activeLocation;
  }, [activeLocation]);

  useEffect(() => {
    writeStoredEditorialContext(editorialContext);
  }, [editorialContext]);

  const handleCommunityIdentityChange = useCallback((nextIdentity) => {
    if (!nextIdentity) return;
    persistCommunityIdentity(nextIdentity);
    setCommunityIdentity(nextIdentity);
  }, []);

  const handleEventsNavigationState = useCallback((sourceLocation, dataState) => {
    if (!isDefinitiveAppExperience()) return;

    setEventsNavigationSnapshot((current) => reconcileEventsNavigationSnapshot(
      current,
      activeLocation,
      sourceLocation,
      dataState,
    ));
  }, [activeLocation]);

  const handleCommunityNavigationState = useCallback((sourceLocation, communityModel, options) => {
    if (!isDefinitiveAppExperience()) return;

    const candidate = createCommunityNavigationSnapshot(sourceLocation, communityModel, options);
    if (getCommunityNavigationTotal(candidate, activeLocation) === null) return;

    setCommunityNavigationSnapshot((current) => reconcileCommunityNavigationSnapshot(
      current,
      activeLocation,
      sourceLocation,
      communityModel,
      options,
    ));
  }, [activeLocation]);

  const handleCommunityReportsViewed = useCallback((sourceLocation, communityModel, options) => {
    if (!definitiveAppExperience || activeTab !== "live"
      || globalThis.document?.visibilityState === "hidden") return;
    const candidate = createCommunityNavigationSnapshot(sourceLocation, communityModel, options);
    if (getCommunityNavigationTotal(candidate, activeLocation) === null) return;
    setCommunitySeenState((current) => markCommunitySnapshotSeen(current, candidate.unread));
  }, [activeLocation, activeTab, definitiveAppExperience]);

  const pendingReportId = pendingReportUndo?.reportId || "";
  const pendingReportUndoUntil = Number(pendingReportUndo?.undoUntil) || 0;

  useEffect(() => {
    if (!pendingReportId || !pendingReportUndoUntil) return undefined;

    const timeoutId = globalThis.setTimeout?.(() => {
      clearLiveReportUndoState();
      setPendingReportUndo(null);
    }, Math.max(0, pendingReportUndoUntil - Date.now()));

    return () => {
      if (timeoutId !== undefined) globalThis.clearTimeout?.(timeoutId);
    };
  }, [pendingReportId, pendingReportUndoUntil]);

  useEffect(() => {
    autoLocationEnabledRef.current = autoLocationEnabled;
  }, [autoLocationEnabled]);

  useEffect(() => () => {
    locationRequestGuardRef.current.invalidate();
    locationRequestAbortRef.current?.abort();
  }, []);

  useEffect(() => {
    const query = globalThis.window?.matchMedia?.("(prefers-color-scheme: dark)");
    if (!query) return undefined;

    const handleChange = (event) => {
      setSystemDark(Boolean(event.matches));
    };

    query.addEventListener?.("change", handleChange);
    return () => {
      query.removeEventListener?.("change", handleChange);
    };
  }, []);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    if (isDefinitiveAppExperience() && !isNativeAndroidRuntime()) {
      syncWebThemeColor(theme);
    }
    void applyNativeSystemBarsTheme({ theme });

    return () => {
      delete document.documentElement.dataset.theme;
    };
  }, [theme]);

  useEffect(() => {
    syncDocumentLanguage(language);
  }, [language]);

  useEffect(() => {
    const interval = window.setInterval(() => {
      if (isDefinitiveAppExperience() && document.visibilityState !== "visible") return;
      requestRuntimeRefresh({ force: !isDefinitiveAppExperience() });
    }, isDefinitiveAppExperience() ? 10 * 60 * 1000 : RUNTIME_WEATHER_VERIFY_INTERVAL_MS);

    return () => {
      window.clearInterval(interval);
    };
  }, [requestRuntimeRefresh]);

  useEffect(() => {
    const handleForegroundRefresh = () => {
      if (document.visibilityState === "hidden") return;
      requestRuntimeRefresh();
    };
    const handleVisibilityChange = () => {
      if (document.visibilityState === "visible") {
        requestRuntimeRefresh();
      }
    };

    document.addEventListener("visibilitychange", handleVisibilityChange);
    window.addEventListener("focus", handleForegroundRefresh);
    window.addEventListener("online", handleForegroundRefresh);

    return () => {
      document.removeEventListener("visibilitychange", handleVisibilityChange);
      window.removeEventListener("focus", handleForegroundRefresh);
      window.removeEventListener("online", handleForegroundRefresh);
    };
  }, [requestRuntimeRefresh]);

  const handleThemePreferenceChange = (nextPreference) => {
    const normalized = normalizeThemePreference(nextPreference) || DEFAULT_THEME_PREFERENCE;

    try {
      globalThis.window?.localStorage?.setItem(THEME_STORAGE_KEY, normalized);
    } catch {
      // UI state still updates even if storage is unavailable.
    }

    setThemePreference(normalized);
  };

  const handleLanguagePreferenceChange = (nextLanguagePreference) => {
    setLanguage(writeUiLanguagePreference(nextLanguagePreference));
  };

  const handlePilotLanguageSelect = (nextLanguagePreference) => {
    handleLanguagePreferenceChange(nextLanguagePreference);
    writePilotLanguageOnboardingState();
    setPilotLanguageOnboardingVisible(false);
  };

  const disableAutomaticLocation = useCallback(({ preserveLastResult = true } = {}) => {
    locationRequestGuardRef.current.invalidate();
    locationRequestAbortRef.current?.abort();
    locationRequestAbortRef.current = null;
    autoLocationEnabledRef.current = false;
    writeStoredAutoLocationEnabled(false);
    setAutoLocationEnabled(false);
    setDeviceLocationStatus((currentStatus) => getDisabledAutomaticLocationStatus(
      currentStatus,
      { preserveLastResult },
    ));
  }, []);

  const handleLocationSelect = useCallback(async (nextLocation) => {
    return runManualLocationChange(nextLocation, {
      immediate: isDefinitiveAppExperience(),
      commitLocation: (preparedLocation) => {
        const storedLocation = writeStoredAppLocation(preparedLocation) || preparedLocation;

        activeLocationRef.current = storedLocation;
        setActiveLocation(storedLocation);
        setWebStartupOnboarding((current) => (
          current.manualLocationPending
            ? {
                ...current,
                locationResult: { location: storedLocation, ok: true },
                manualLocationPending: false,
                step: "notifications",
                visible: true,
              }
            : current
        ));
        return storedLocation;
      },
      disableAutomaticLocation,
      loadWeather: loadHomeWeather,
      readWeather: readWeatherBootstrapCache,
    });
  }, [disableAutomaticLocation]);

  const resolveDeviceLocationToAppLocation = useCallback(async ({
    deviceLocationResult,
    keepAutomaticModeOnTemporaryFailure = false,
    markLoading = false,
  } = {}) => {
    const requestToken = locationRequestGuardRef.current.begin();
    locationRequestAbortRef.current?.abort();
    locationRequestAbortRef.current = null;
    const automaticModeWasEnabled = autoLocationEnabledRef.current;

    if (markLoading) {
      setDeviceLocationStatus({ status: "loading" });
    }
    const rawDeviceLocation = deviceLocationResult || await requestDeviceCoordinates();
    const deviceLocation = getAutomaticLocationQualityDecision(rawDeviceLocation);

    if (!deviceLocationResult) {
      autoLocationLastCheckedAtRef.current = Date.now();
    }

    if (!locationRequestGuardRef.current.isCurrent(requestToken)) {
      return { ok: false, reason: "superseded" };
    }

    if (!deviceLocation.ok) {
      const keepAutomaticMode = keepAutomaticModeOnTemporaryFailure &&
        automaticModeWasEnabled &&
        shouldKeepAutoLocationEnabledAfterFailure(deviceLocation.reason);

      if (!keepAutomaticMode) {
        autoLocationEnabledRef.current = false;
        writeStoredAutoLocationEnabled(false);
        setAutoLocationEnabled(false);
      }
      setDeviceLocationStatus({
        status: deviceLocation.reason === "permission_denied" ? "denied" : "error",
        reason: deviceLocation.reason,
      });
      return {
        ok: false,
        reason: deviceLocation.reason,
      };
    }

    const abortController = new AbortController();
    locationRequestAbortRef.current = abortController;
    const reverseResult = await resolveReverseLocation(deviceLocation.coords, {
      cacheEnabled: false,
      signal: abortController.signal,
      source: deviceLocation.source || "browser_geolocation",
    });

    if (locationRequestAbortRef.current === abortController) {
      locationRequestAbortRef.current = null;
    }

    if (!locationRequestGuardRef.current.isCurrent(requestToken)) {
      return { ok: false, reason: "superseded" };
    }

    if (!reverseResult.ok) {
      const failureReason = reverseResult.error;
      const keepAutomaticMode = keepAutomaticModeOnTemporaryFailure && automaticModeWasEnabled;

      if (!keepAutomaticMode) {
        autoLocationEnabledRef.current = false;
        writeStoredAutoLocationEnabled(false);
        setAutoLocationEnabled(false);
      }
      setDeviceLocationStatus({
        status: "error",
        reason: failureReason,
      });
      return {
        ok: false,
        reason: failureReason,
      };
    }

    const currentLocation = activeLocationRef.current;
    const reliableLocationDecision = buildReliableDeviceAppLocation(
      reverseResult.location,
      deviceLocation,
    );
    if (!reliableLocationDecision.ok) {
      setDeviceLocationStatus({
        status: "error",
        reason: reliableLocationDecision.reason,
      });
      return { ok: false, reason: reliableLocationDecision.reason };
    }
    const reliableLocation = reliableLocationDecision.location;
    const placeChanged = shouldReplaceResolvedPlace(
      currentLocation,
      reliableLocation,
    );
    const updatePlan = getDeviceAppLocationUpdatePlan(
      currentLocation,
      reliableLocation,
      { placeChanged },
    );
    const { coordsChanged } = updatePlan;
    const nextLocation = writeStoredAppLocation(reliableLocation) || reliableLocation;

    writeStoredAutoLocationEnabled(true);
    autoLocationEnabledRef.current = true;
    setAutoLocationEnabled(true);
    activeLocationRef.current = nextLocation;
    if (updatePlan.shouldUpdateVisibleLocation) {
      setActiveLocation(nextLocation);
    } else {
      setPushRegistrationRevision((revision) => revision + 1);
    }
    setDeviceLocationStatus({
      status: "success",
      city: nextLocation.city,
      displayName: getLocationPrimaryName(nextLocation),
      locality: nextLocation.locality || null,
      location: nextLocation,
      fromCache: reverseResult.fromCache,
    });
    if (updatePlan.shouldRefreshRuntime) {
      requestRuntimeRefresh({ force: true });
    }

    return {
      ok: true,
      changed: placeChanged || coordsChanged,
      coordsChanged,
      evidenceUpdated: true,
      location: nextLocation,
      placeChanged,
      source: deviceLocation.source || "browser_geolocation",
    };
  }, [requestRuntimeRefresh]);

  const refreshAutomaticDeviceLocation = useCallback((options = {}) => {
    if (automaticLocationRefreshPromiseRef.current) {
      return automaticLocationRefreshPromiseRef.current;
    }

    let trackedPromise;
    trackedPromise = requestDeviceCoordinates()
      .then((deviceLocationResult) => resolveDeviceLocationToAppLocation({
        ...options,
        deviceLocationResult,
      }))
      .finally(() => {
        if (automaticLocationRefreshPromiseRef.current === trackedPromise) {
          automaticLocationRefreshPromiseRef.current = null;
        }
      });
    automaticLocationRefreshPromiseRef.current = trackedPromise;
    return trackedPromise;
  }, [resolveDeviceLocationToAppLocation]);

  const handleAutomaticLocationChange = useCallback(async (enabled) => {
    if (enabled && isNativeAndroidRuntime()) {
      const disclosureAccepted = await requestBackgroundLocationDisclosure({
        autoLocationEnabled: true,
        context: "startup",
      });
      if (!disclosureAccepted) {
        return { enabled: false, ok: false, reason: "background_location_disclosure_declined" };
      }
    }

    return changeAutomaticLocationMode(enabled, {
      disableAutomaticLocation,
      resolveDeviceLocation: resolveDeviceLocationToAppLocation,
    });
  }, [
    disableAutomaticLocation,
    requestBackgroundLocationDisclosure,
    resolveDeviceLocationToAppLocation,
  ]);

  const handleSupportOpen = useCallback((url) => {
    return openSupportUrl(url || supportUrl);
  }, [supportUrl]);

  const activateNativePush = useCallback(async (pushNotifications) => {
    if (!pushNotifications) return { ok: false, reason: "native_push_unavailable" };
    if (pushActivationRef.current.complete) return { ok: true, skipped: true };
    if (pushActivationRef.current.promise) return pushActivationRef.current.promise;

    const activation = (async () => {
      setNotificationRuntime((current) => ({
        ...current,
        connected: false,
        permission: NATIVE_PUSH_PERMISSION.granted,
        status: "registering",
      }));

      const channelsResult = await ensureNativePushAndroidChannels({ pushNotifications });
      if (!channelsResult.ok) {
        setNotificationRuntime((current) => ({ ...current, connected: false, status: "error" }));
        return channelsResult;
      }

      const registrationResult = await registerNativePush({ pushNotifications });
      if (!registrationResult.ok) {
        setNotificationRuntime((current) => ({ ...current, connected: false, status: "error" }));
        return registrationResult;
      }

      pushActivationRef.current.complete = true;
      return registrationResult;
    })();

    pushActivationRef.current.promise = activation;
    try {
      return await activation;
    } finally {
      pushActivationRef.current.promise = null;
    }
  }, []);

  const requestAndActivateNativePush = useCallback(async () => {
    const pushRuntime = await pushRuntimeInitializationRef.current;
    const pushNotifications = pushRuntime?.pushNotifications || null;
    if (!pushNotifications) {
      const result = {
        reason: "native_push_runtime_not_connected",
        receive: NATIVE_PUSH_PERMISSION.unsupported,
        requested: false,
      };
      setNotificationRuntime((current) => ({
        ...current,
        connected: false,
        permission: result.receive,
        status: "error",
      }));
      return result;
    }

    const result = await requestNativePushPermission({ pushNotifications });
    nativePushPermissionRef.current = result.receive;
    const status = result.receive === NATIVE_PUSH_PERMISSION.granted
      ? "registering"
      : result.receive === NATIVE_PUSH_PERMISSION.denied
        ? "permission_denied"
        : result.receive === NATIVE_PUSH_PERMISSION.prompt
          ? "permission_prompt"
          : "error";
    setNotificationRuntime((current) => ({
      ...current,
      connected: false,
      permission: result.receive,
      status,
    }));
    if (result.receive === NATIVE_PUSH_PERMISSION.granted) {
      await activateNativePush(pushNotifications);
      setPushRegistrationRevision((revision) => revision + 1);
    }

    return result;
  }, [activateNativePush]);

  const activateWebPush = useCallback(async (runtime = webPushRuntimeRef.current) => {
    if (!runtime?.ok) return { ok: false, reason: "web_push_runtime_unavailable" };
    if (!areNotificationPreferencesEnabled(webPushPreferencesRef.current)) {
      return { ok: false, reason: "web_push_preferences_disabled" };
    }
    if (webPushActivationRef.current.promise) return webPushActivationRef.current.promise;
    if (webPushActivationRef.current.registrationRequested) {
      return { ok: true, skipped: true };
    }

    const activation = (async () => {
      setNotificationRuntime((current) => ({
        ...current,
        connected: false,
        errorCategory: null,
        errorCode: null,
        errorPhase: null,
        permission: NATIVE_PUSH_PERMISSION.granted,
        reason: null,
        readOnly: false,
        status: "registering",
      }));
      try {
        const result = await registerWebPush({ runtime });
        webPushActivationRef.current.registrationRequested = true;
        setWebPushActivationFailures(0);
        setPushRegistrationRevision((revision) => revision + 1);
        return result;
      } catch (error) {
        const diagnostic = getWebPushErrorDiagnostic(error, {
          phase: "firebase_registration",
        });
        webPushActivationRef.current.registrationRequested = false;
        setWebPushActivationFailures((failedAttempts) => failedAttempts + 1);
        setNotificationRuntime((current) => ({
          ...current,
          connected: false,
          ...diagnostic,
          status: "error",
        }));
        return { ok: false, ...diagnostic };
      }
    })();

    webPushActivationRef.current.promise = activation;
    try {
      return await activation;
    } finally {
      webPushActivationRef.current.promise = null;
    }
  }, []);

  const requestAndActivateWebPush = useCallback(async () => {
    const runtime = await webPushRuntimeInitializationRef.current;
    if (!runtime?.ok) {
      const result = {
        reason: runtime?.reason || "web_push_runtime_unavailable",
        receive: NATIVE_PUSH_PERMISSION.unsupported,
        requested: false,
      };
      setNotificationRuntime((current) => ({
        ...current,
        connected: false,
        permission: result.receive,
        readOnly: true,
        reason: result.reason,
        status: ["not_configured", "web_enrollment_disabled"].includes(result.reason)
          ? "not_configured"
          : "unsupported",
      }));
      return result;
    }

    const currentPermission = readWebPushPermission();
    let result;
    try {
      result = currentPermission === NATIVE_PUSH_PERMISSION.granted
        ? {
            reason: null,
            receive: NATIVE_PUSH_PERMISSION.granted,
            requested: false,
          }
        : await requestWebPushPermission();
    } catch {
      result = {
        reason: "web_push_permission_request_failed",
        receive: currentPermission,
        requested: true,
      };
    }
    webPushPermissionRef.current = result.receive;
    setNotificationRuntime((current) => ({
      ...current,
      connected: false,
      permission: result.receive,
      readOnly: false,
      reason: result.reason,
      status: result.reason
        ? "error"
        : result.receive === NATIVE_PUSH_PERMISSION.granted
        ? "registering"
        : result.receive === NATIVE_PUSH_PERMISSION.denied
          ? "permission_denied"
          : result.receive === NATIVE_PUSH_PERMISSION.prompt
            ? "permission_prompt"
            : "error",
    }));
    if (result.receive === NATIVE_PUSH_PERMISSION.granted) {
      await activateWebPush(runtime);
    }
    return result;
  }, [activateWebPush]);

  useEffect(() => {
    if (!isNativeAndroidRuntime()) return undefined;

    let disposed = false;
    let listenerHandle = null;
    const initialization = (async () => {
      const pushNotifications = getNativePushNotificationsPlugin();
      if (!pushNotifications) {
        if (!disposed) {
          setNotificationRuntime((current) => ({ ...current, connected: false, status: "error" }));
        }
        return createNativePushRuntime();
      }

      listenerHandle = await addNativePushListeners({
        onNotificationAction: (action) => {
          const target = getPushNavigationTarget(action, {
            currentMunicipalityIstat: getNationalOfficialAlertsIstat(activeLocationRef.current),
          });
          if (target?.tab) handleRouteChange(target.tab);
          requestRuntimeRefresh({ force: true });
        },
        onNotificationReceived: () => {
          requestRuntimeRefresh({ force: true });
        },
        onRegistration: ({ token }) => {
          const normalizedToken = String(token || "").trim();
          if (normalizedToken && !disposed) setPushToken(normalizedToken);
        },
        onRegistrationError: () => {
          if (!disposed) {
            setNotificationRuntime((current) => ({ ...current, connected: false, status: "error" }));
          }
        },
        pushNotifications,
      });

      if (!listenerHandle.ok || disposed) {
        await listenerHandle?.remove?.();
        if (!disposed) {
          setNotificationRuntime((current) => ({ ...current, connected: false, status: "error" }));
        }
        return createNativePushRuntime();
      }

      const permission = await checkNativePushPermission({ pushNotifications });
      nativePushPermissionRef.current = permission.receive;
      const permissionStatus = permission.receive === NATIVE_PUSH_PERMISSION.denied
        ? "permission_denied"
        : permission.receive === NATIVE_PUSH_PERMISSION.granted
          ? "connecting"
          : permission.receive === NATIVE_PUSH_PERMISSION.prompt
            ? "permission_prompt"
            : "error";
      if (!disposed) {
        setNotificationRuntime((current) => ({
          ...current,
          connected: false,
          permission: permission.receive,
          status: permissionStatus,
        }));
      }
      if (permission.receive === NATIVE_PUSH_PERMISSION.granted) {
        await activateNativePush(pushNotifications);
      }

      return createNativePushRuntime(pushNotifications);
    })();

    pushRuntimeInitializationRef.current = initialization;

    CapacitorApp.getInfo()
      .then((info) => {
        const releaseIdentity = getNativeReleaseIdentity(info);
        if (!disposed && isNativeReleaseIdentityKnown(releaseIdentity)) {
          setNativeAppVersion(releaseIdentity);
        }
      })
      .catch(() => {});

    return () => {
      disposed = true;
      listenerHandle?.remove?.();
    };
  }, [activateNativePush, handleRouteChange, requestRuntimeRefresh]);

  useEffect(() => {
    if (isNativeAndroidRuntime()) return undefined;

    let disposed = false;
    let listenerHandle = null;
    const initialization = (async () => {
      try {
        const runtime = await createWebPushRuntime();
        if (!runtime?.ok) {
          if (!disposed) {
            setNotificationRuntime((current) => ({
              ...current,
              connected: false,
              permission: NATIVE_PUSH_PERMISSION.unsupported,
              readOnly: true,
              reason: runtime?.reason || "browser_unsupported",
              status: ["not_configured", "web_enrollment_disabled"].includes(runtime?.reason)
                ? "not_configured"
                : "unsupported",
            }));
          }
          return runtime;
        }

        if (disposed) return runtime;

        webPushRuntimeRef.current = runtime;
        listenerHandle = addWebPushListeners({
          onMessage: (payload) => {
            if (disposed) return;
            setWebPushForegroundMessage({
              ...getWebPushForegroundContent(payload),
              id: String(payload?.messageId || Date.now()),
            });
            requestRuntimeRefresh({ force: true });
          },
          onNotificationAction: (action) => {
            if (disposed) return;
            const target = getPushNavigationTarget(action) || { tab: "bulletin" };
            handleRouteChange(target.tab);
            setWebPushForegroundMessage(null);
            requestRuntimeRefresh({ force: true });
          },
          onRegistered: ({ fid }) => {
            if (disposed) return;
            webPushActivationRef.current.registrationRequested = true;
            webPushUnregisteredRef.current = false;
            setWebPushActivationFailures(0);
            setWebRegistrationFid(fid);
            setNotificationRuntime((current) => ({
              ...current,
              connected: false,
              errorCategory: null,
              errorCode: null,
              errorPhase: null,
              permission: NATIVE_PUSH_PERMISSION.granted,
              reason: null,
              readOnly: false,
              status: "registering",
            }));
            setPushRegistrationRevision((revision) => revision + 1);
          },
          onUnregistered: ({ fid }) => {
            if (disposed) return;
            webPushActivationRef.current.registrationRequested = false;
            setWebRegistrationFid((currentFid) => (
              !fid || currentFid === fid ? "" : currentFid
            ));
            setNotificationRuntime((current) => ({ ...current, connected: false }));
          },
          runtime,
        });
        const permission = readWebPushPermission();
        webPushPermissionRef.current = permission;
        if (!disposed) {
          setNotificationRuntime((current) => ({
            ...current,
            connected: false,
            errorCategory: null,
            errorCode: null,
            errorPhase: null,
            permission,
            readOnly: false,
            reason: null,
            status: permission === NATIVE_PUSH_PERMISSION.granted
              ? "connecting"
              : permission === NATIVE_PUSH_PERMISSION.denied
                ? "permission_denied"
                : "permission_prompt",
          }));
        }
        if (permission === NATIVE_PUSH_PERMISSION.granted) {
          await activateWebPush(runtime);
        } else if (permission === NATIVE_PUSH_PERMISSION.denied) {
          setPushRegistrationRevision((revision) => revision + 1);
        }
        return runtime;
      } catch (error) {
        const diagnostic = getWebPushErrorDiagnostic(error, { phase: "initialization" });
        const runtime = {
          configured: true,
          ok: false,
          reason: diagnostic.reason,
          supported: false,
        };
        if (!disposed) {
          setNotificationRuntime((current) => ({
            ...current,
            connected: false,
            ...diagnostic,
            permission: NATIVE_PUSH_PERMISSION.unsupported,
            readOnly: true,
            status: "error",
          }));
        }
        return runtime;
      }
    })();

    webPushRuntimeInitializationRef.current = initialization;
    return () => {
      disposed = true;
      listenerHandle?.remove?.();
    };
  }, [activateWebPush, handleRouteChange, requestRuntimeRefresh]);

  useEffect(() => {
    if (isNativeAndroidRuntime()) return undefined;
    if (!shouldRetryWebPushRegistration({
      failedAttempts: webPushActivationFailures,
      hasRegistration: Boolean(webRegistrationFid),
      notificationsEnabled: areNotificationPreferencesEnabled(notificationPreferences),
      permission: webPushPermissionRef.current,
      runtimeOk: webPushRuntimeRef.current?.ok === true,
    })) return undefined;

    const retryTimerId = globalThis.window?.setTimeout?.(() => {
      if (globalThis.navigator?.onLine === false) return;
      activateWebPush(webPushRuntimeRef.current);
    }, getWebPushRegistrationRetryDelayMs(webPushActivationFailures));

    return () => {
      if (retryTimerId != null) globalThis.window?.clearTimeout?.(retryTimerId);
    };
  }, [
    activateWebPush,
    notificationPreferences,
    webPushActivationFailures,
    webRegistrationFid,
  ]);

  useEffect(() => {
    if (isNativeAndroidRuntime()) return undefined;

    const syncPermission = () => {
      if (!webPushRuntimeRef.current?.ok) return;
      const permission = readWebPushPermission();
      if (permission === webPushPermissionRef.current) return;

      webPushPermissionRef.current = permission;
      setNotificationRuntime((current) => ({
        ...current,
        connected: permission === NATIVE_PUSH_PERMISSION.granted
          ? current.connected
          : false,
        permission,
        readOnly: false,
        status: permission === NATIVE_PUSH_PERMISSION.granted
          ? "connecting"
          : permission === NATIVE_PUSH_PERMISSION.denied
            ? "permission_denied"
            : "permission_prompt",
      }));
      if (permission === NATIVE_PUSH_PERMISSION.granted) {
        webPushActivationRef.current.registrationRequested = false;
        activateWebPush(webPushRuntimeRef.current);
      } else {
        webPushActivationRef.current.registrationRequested = false;
        setPushRegistrationRevision((revision) => revision + 1);
      }
    };
    const retryFailedRegistration = () => {
      if (shouldRetryWebPushRegistration({
        failedAttempts: webPushActivationFailures,
        hasRegistration: Boolean(webRegistrationFid),
        notificationsEnabled: areNotificationPreferencesEnabled(notificationPreferences),
        permission: webPushPermissionRef.current,
        runtimeOk: webPushRuntimeRef.current?.ok === true,
      })) {
        webPushActivationRef.current.registrationRequested = false;
        activateWebPush(webPushRuntimeRef.current);
      }
    };
    const handleFocus = () => {
      syncPermission();
      retryFailedRegistration();
    };
    const handleOnline = () => {
      syncPermission();
      retryFailedRegistration();
    };
    const handleVisibility = () => {
      if (document.visibilityState === "visible") handleFocus();
    };

    window.addEventListener("focus", handleFocus);
    window.addEventListener("online", handleOnline);
    document.addEventListener("visibilitychange", handleVisibility);
    return () => {
      window.removeEventListener("focus", handleFocus);
      window.removeEventListener("online", handleOnline);
      document.removeEventListener("visibilitychange", handleVisibility);
    };
  }, [
    activateWebPush,
    notificationPreferences,
    webPushActivationFailures,
    webRegistrationFid,
  ]);

  useEffect(() => {
    if (!isNativeAndroidRuntime()) return undefined;

    const notificationsEnabled = areNotificationPreferencesEnabled(notificationPreferences);
    if (
      notificationsEnabled &&
      (
        !pushToken
        || !isNativeReleaseIdentityKnown(nativeAppVersion)
        || nativePushPermissionRef.current !== NATIVE_PUSH_PERMISSION.granted
      )
    ) return undefined;

    let cancelled = false;
    let retryTimerId = null;
    const syncDevice = async () => {
      setNotificationRuntime((current) => ({
        ...current,
        connected: false,
        status: notificationsEnabled ? "registering" : "disabled",
      }));

      try {
        const installationId = readOrCreatePushInstallationId();
        if (!notificationsEnabled) {
          try {
            await unregisterPushDevice({ installationId });
          } finally {
            await syncBackgroundLocationConfiguration({ enabled: false });
          }
          if (!cancelled) {
            setNotificationRuntime((current) => ({ ...current, connected: false, status: "disabled" }));
          }
          return;
        }

        const result = await registerPushDevice({
          activeLocation: activeLocationRef.current,
          appVersion: nativeAppVersion,
          installationId,
          language,
          notificationPreferences,
          token: pushToken,
        });
        await syncBackgroundLocationConfiguration({
          enabled: result?.registered !== false
            && autoLocationEnabledRef.current
            && notificationPreferences.weatherNotices !== false,
          installationId,
        });
        if (!cancelled) {
          setNotificationRuntime((current) => ({
            ...current,
            connected: result?.registered !== false,
            localTargetEligible: result?.local_target_eligible === true,
            permission: NATIVE_PUSH_PERMISSION.granted,
            status: result?.registered === false ? "error" : "connected",
          }));
        }
      } catch {
        if (!cancelled) {
          setNotificationRuntime((current) => ({ ...current, connected: false, status: "error" }));
          retryTimerId = globalThis.window?.setTimeout?.(
            () => setPushRegistrationRevision((revision) => revision + 1),
            60_000,
          );
        }
      }
    };

    pushDeviceSyncQueueRef.current = pushDeviceSyncQueueRef.current
      .catch(() => {})
      .then(syncDevice);
    return () => {
      cancelled = true;
      if (retryTimerId != null) globalThis.window?.clearTimeout?.(retryTimerId);
    };
  }, [
    activeLocation,
    autoLocationEnabled,
    language,
    nativeAppVersion,
    notificationPreferences,
    pushRegistrationRevision,
    pushToken,
    syncBackgroundLocationConfiguration,
  ]);

  useEffect(() => {
    if (!isNativeAndroidRuntime()) return undefined;
    const shouldDisable = !backgroundLocationDisclosureAccepted
      || !autoLocationEnabled
      || notificationPreferences.weatherNotices === false
      || notificationRuntime.permission !== NATIVE_PUSH_PERMISSION.granted;
    if (!shouldDisable) return undefined;

    const timerId = globalThis.setTimeout(() => {
      void syncBackgroundLocationConfiguration({ enabled: false });
    }, 0);

    return () => globalThis.clearTimeout(timerId);
  }, [
    autoLocationEnabled,
    backgroundLocationDisclosureAccepted,
    notificationPreferences.weatherNotices,
    notificationRuntime.permission,
    syncBackgroundLocationConfiguration,
  ]);

  useEffect(() => {
    if (isNativeAndroidRuntime()) return undefined;

    const notificationsEnabled = areNotificationPreferencesEnabled(notificationPreferences);
    const permission = webPushPermissionRef.current;
    const shouldUnregister = !notificationsEnabled || permission === NATIVE_PUSH_PERMISSION.denied;

    if (shouldUnregister && webPushUnregisteredRef.current) return undefined;
    if (!shouldUnregister && (
      !webRegistrationFid || permission !== NATIVE_PUSH_PERMISSION.granted
    )) return undefined;

    let cancelled = false;
    let retryTimerId = null;
    const syncDevice = async () => {
      setNotificationRuntime((current) => ({
        ...current,
        connected: false,
        errorCategory: null,
        errorCode: null,
        errorPhase: null,
        reason: null,
        status: shouldUnregister
          ? permission === NATIVE_PUSH_PERMISSION.denied
            ? "permission_denied"
            : "disabled"
          : "registering",
      }));

      try {
        if (shouldUnregister) {
          const installationId = readPushInstallationId();
          try {
            if (installationId) await unregisterPushDevice({ installationId });
          } finally {
            if (webRegistrationFid) {
              await unregisterWebPush({ runtime: webPushRuntimeRef.current });
            }
          }
          webPushActivationRef.current.registrationRequested = false;
          setWebPushActivationFailures(0);
          webPushUnregisteredRef.current = true;
          if (!cancelled) {
            setNotificationRuntime((current) => ({
              ...current,
              connected: false,
              status: permission === NATIVE_PUSH_PERMISSION.denied
                ? "permission_denied"
                : "disabled",
            }));
          }
          return;
        }

        webPushUnregisteredRef.current = false;
        const installationId = readOrCreatePushInstallationId();
        const result = await registerPushDevice({
          activeLocation,
          appVersion: frontendPackage.version,
          installationId,
          language,
          notificationPreferences,
          platform: "web",
          registration: {
            kind: "firebase_installation_id",
            value: webRegistrationFid,
          },
        });
        if (!cancelled) {
          setNotificationRuntime((current) => ({
            ...current,
            connected: result?.registered !== false,
            errorCategory: null,
            errorCode: null,
            errorPhase: null,
            permission: NATIVE_PUSH_PERMISSION.granted,
            reason: null,
            readOnly: false,
            status: result?.registered === false ? "error" : "connected",
          }));
        }
      } catch (error) {
        const diagnostic = getWebPushErrorDiagnostic(error, { phase: "device_sync" });
        if (!cancelled) {
          setNotificationRuntime((current) => ({
            ...current,
            connected: false,
            ...diagnostic,
            status: "error",
          }));
          if (diagnostic.retryable !== false) {
            retryTimerId = globalThis.window?.setTimeout?.(
              () => setPushRegistrationRevision((revision) => revision + 1),
              60_000,
            );
          }
        }
      }
    };

    pushDeviceSyncQueueRef.current = pushDeviceSyncQueueRef.current
      .catch(() => {})
      .then(syncDevice);
    return () => {
      cancelled = true;
      if (retryTimerId != null) globalThis.window?.clearTimeout?.(retryTimerId);
    };
  }, [
    activeLocation,
    language,
    notificationPreferences,
    pushRegistrationRevision,
    webRegistrationFid,
  ]);

  useEffect(() => {
    if (isNativeAndroidRuntime()) return;

    const notificationsEnabled = areNotificationPreferencesEnabled(notificationPreferences);
    if (
      !notificationsEnabled ||
      webRegistrationFid ||
      webPushActivationRef.current.registrationRequested ||
      webPushPermissionRef.current !== NATIVE_PUSH_PERMISSION.granted ||
      !webPushRuntimeRef.current?.ok
    ) return;

    webPushUnregisteredRef.current = false;
    activateWebPush(webPushRuntimeRef.current);
  }, [activateWebPush, notificationPreferences, webRegistrationFid]);

  useEffect(() => {
    if (labEnabled || !isNativeAndroidRuntime()) return undefined;

    const markAutomaticLocationChecked = (checkedAt) => {
      autoLocationLastCheckedAtRef.current = checkedAt;
    };
    const refreshAutomaticLocation = () => (
      backgroundLocationDisclosureAcceptedRef.current
        ? refreshAutomaticDeviceLocation({
            keepAutomaticModeOnTemporaryFailure: true,
          })
        : Promise.resolve({ ok: false, reason: "background_location_disclosure_required" })
    );
    const onResume = createRateLimitedAppResumeHandler({
      isDue: () => (
        backgroundLocationDisclosureAcceptedRef.current
        && autoLocationEnabledRef.current
      ),
      markChecked: markAutomaticLocationChecked,
      onDueResume: refreshAutomaticLocation,
    });
    const onForegroundCheck = createRateLimitedAppResumeHandler({
      isDue: () => shouldRunForegroundAutoLocationCheck({
        autoLocationEnabled: backgroundLocationDisclosureAcceptedRef.current
          && autoLocationEnabledRef.current,
        lastCheckedAt: autoLocationLastCheckedAtRef.current,
        minIntervalMs: CAPACITOR_AUTO_LOCATION_RESUME_INTERVAL_MS,
        now: Date.now(),
      }),
      markChecked: markAutomaticLocationChecked,
      onDueResume: refreshAutomaticLocation,
    });
    const runtime = startCapacitorAppResumeRuntime({
      onForegroundCheck,
      onResume: () => runCapacitorResumeSequence({
        refreshLocation: onResume,
        refreshNotifications: async () => {
          await refreshBackgroundLocationRuntime();
          const pushRuntime = await pushRuntimeInitializationRef.current;
          const pushNotifications = pushRuntime?.pushNotifications || null;
          if (!pushNotifications) return;

          const permission = await checkNativePushPermission({ pushNotifications });
          nativePushPermissionRef.current = permission.receive;
          setNotificationRuntime((current) => ({
            ...current,
            connected: permission.receive === NATIVE_PUSH_PERMISSION.granted
              ? current.connected
              : false,
            permission: permission.receive,
            status: permission.receive === NATIVE_PUSH_PERMISSION.denied
              ? "permission_denied"
              : permission.receive === NATIVE_PUSH_PERMISSION.prompt
                ? "permission_prompt"
                : permission.receive === NATIVE_PUSH_PERMISSION.granted
                  ? current.status
                  : "error",
          }));
          if (permission.receive === NATIVE_PUSH_PERMISSION.granted) {
            await activateNativePush(pushNotifications);
            setPushRegistrationRevision((revision) => revision + 1);
          }
        },
        refreshRuntime: requestRuntimeRefresh,
      }),
    });

    return () => runtime.stop();
  }, [
    activateNativePush,
    labEnabled,
    refreshBackgroundLocationRuntime,
    refreshAutomaticDeviceLocation,
    requestRuntimeRefresh,
  ]);

  useEffect(() => {
    if (!autoLocationEnabled || labEnabled || isNativeAndroidRuntime()) return undefined;

    let disposed = false;
    let runtime = null;
    const startTimerId = globalThis.window?.setTimeout?.(() => {
      if (disposed) return;
      runtime = startAutomaticLocationRuntime({
        initialLastCheckedAt: autoLocationLastCheckedAtRef.current,
        onResult: async (result) => {
          if (!autoLocationEnabledRef.current) return { ok: false, reason: "disabled" };
          return resolveDeviceLocationToAppLocation({
            deviceLocationResult: result,
            keepAutomaticModeOnTemporaryFailure: true,
          });
        },
      });
    }, 0);

    return () => {
      disposed = true;
      if (startTimerId != null) globalThis.window?.clearTimeout?.(startTimerId);
      runtime?.stop();
    };
  }, [autoLocationEnabled, labEnabled, resolveDeviceLocationToAppLocation]);

  useEffect(() => {
    if (startupPromptFlowStartedRef.current) return undefined;
    if (!isNativeAndroidRuntime()) return undefined;
    if (pilotLanguageOnboardingVisible) return undefined;

    startupPromptFlowStartedRef.current = true;
    let cancelled = false;
    const startupStorage = readAndroidStartupPromptStorage();

    runAndroidStartupPromptFlow({
      autoLocationEnabled: startupStorage.autoLocationEnabled,
      backgroundLocationDisclosureAccepted: backgroundLocationDisclosureAcceptedRef.current,
      isNativeAndroid: true,
      requestBackgroundLocationDisclosure: () => (
        cancelled
          ? false
          : requestBackgroundLocationDisclosure({
              autoLocationEnabled: true,
              context: "startup",
            })
      ),
      requestNativeNotifications: async () => {
        if (cancelled) return { receive: NATIVE_PUSH_PERMISSION.unknown, requested: false };
        return requestAndActivateNativePush();
      },
      resolveDeviceLocation: () => refreshAutomaticDeviceLocation({
        // Startup rechecks an existing choice; a temporary failure must not erase it.
        keepAutomaticModeOnTemporaryFailure: true,
        markLoading: true,
      }),
      selectedLocation: readStoredAppLocation(),
      startupNotificationsAsked: startupStorage.startupNotificationsAsked,
      weatherAlertsEnabled: startupStorage.weatherAlertsEnabled,
    })
      .then((result) => {
        if (cancelled) return;
        if (result?.reason === "background_location_disclosure_declined") {
          disableAutomaticLocation();
        }
        if (shouldPersistAndroidStartupNotificationPatch(result)) {
          writeAndroidStartupNotificationStoragePatch(result.storagePatch);
        }
        if (result?.needsManualLocation) setLocationSearchOpen(true);
      })
      .catch(() => {});

    return () => {
      cancelled = true;
    };
  }, [
    disableAutomaticLocation,
    pilotLanguageOnboardingVisible,
    refreshAutomaticDeviceLocation,
    requestAndActivateNativePush,
    requestBackgroundLocationDisclosure,
  ]);

  const handleRuntimeCacheReset = useCallback(() => (
    clearRuntimeDeviceCaches(activeLocation || DEFAULT_APP_LOCATION, {
      eventsLocation: activeLocation || DEFAULT_APP_LOCATION,
    })
  ), [activeLocation]);

  const handleNotificationPreferenceChange = useCallback((preference, enabled) => {
    if (!isNativeAndroidRuntime() && notificationRuntime.readOnly) return;

    setNotificationPreferences((currentPreferences) => writeNotificationPreferences({
      ...currentPreferences,
      [preference]: Boolean(enabled),
    }));
  }, [notificationRuntime.readOnly]);

  const handleNotificationSettingsOpen = useCallback(() => (
    openNativeNotificationSettings()
  ), []);

  const handleBackgroundLocationSettingsOpen = useCallback(async () => {
    const disclosureAccepted = await requestBackgroundLocationDisclosure({
      autoLocationEnabled: true,
      context: "settings",
    });
    if (!disclosureAccepted) return false;

    const installationId = readPushInstallationId();
    await syncBackgroundLocationConfiguration({
      enabled: Boolean(
        installationId
        && autoLocationEnabledRef.current
        && notificationPreferences.weatherNotices !== false
        && notificationRuntime.connected === true
        && notificationRuntime.permission === NATIVE_PUSH_PERMISSION.granted
      ),
      installationId,
    });

    try {
      await openBackgroundLocationSettings();
      return true;
    } catch {
      setBackgroundLocationRuntime((current) => ({
        ...current,
        lastStatus: "settings_unavailable",
      }));
      return false;
    }
  }, [
    notificationPreferences.weatherNotices,
    notificationRuntime.connected,
    notificationRuntime.permission,
    requestBackgroundLocationDisclosure,
    syncBackgroundLocationConfiguration,
  ]);

  const handleWebStartupClose = useCallback((state = "dismissed") => {
    writeWebStartupOnboardingState(state);
    setWebStartupOnboarding((current) => ({
      ...current,
      busy: false,
      manualLocationPending: false,
      visible: false,
    }));
  }, []);

  const handleWebStartupLocationRequest = useCallback(async () => {
    setWebStartupOnboarding((current) => ({ ...current, busy: true }));
    let result;
    try {
      result = await resolveDeviceLocationToAppLocation({ markLoading: true });
    } catch {
      result = { ok: false, reason: "location_failed" };
    }
    setWebStartupOnboarding((current) => ({
      ...current,
      busy: false,
      locationResult: result,
      step: "notifications",
    }));
  }, [resolveDeviceLocationToAppLocation]);

  const handleWebStartupLocationSkip = useCallback(() => {
    setWebStartupOnboarding((current) => ({
      ...current,
      busy: false,
      locationResult: null,
      step: "notifications",
    }));
  }, []);

  const handleWebStartupNotificationRequest = useCallback(async () => {
    setWebStartupOnboarding((current) => ({ ...current, busy: true }));
    try {
      await requestAndActivateWebPush();
    } finally {
      handleWebStartupClose("completed");
    }
  }, [handleWebStartupClose, requestAndActivateWebPush]);

  const handleWebStartupManualLocation = useCallback(() => {
    setWebStartupOnboarding((current) => ({
      ...current,
      manualLocationPending: true,
      visible: false,
    }));
    setLocationSearchOpen(true);
  }, []);

  const handleLocationSearchClose = useCallback(() => {
    setLocationSearchOpen(false);
    setWebStartupOnboarding((current) => (
      current.manualLocationPending
        ? {
            ...current,
            manualLocationPending: false,
            step: "notifications",
            visible: true,
          }
        : current
    ));
  }, []);

  const handleWebPushBannerOpen = useCallback(() => {
    setWebPushForegroundMessage(null);
    handleRouteChange("bulletin");
  }, [handleRouteChange]);

  const handleOfficialAlertOpen = useCallback(() => {
    setRouteAnchorRequest({
      anchor: "official-alerts",
      tab: "bulletin",
    });
    handleRouteChange("bulletin");
  }, [handleRouteChange]);

  return (
    <>
      <AppShell
        activeRoute={activeTab}
        activeTab={navActiveTab}
        autoLocationEnabled={autoLocationEnabled}
        communityIdentity={communityIdentity}
        communityReportsTotal={communityReportsTotal}
        communityReportsUnread={definitiveAppExperience}
        copy={copy}
        definitiveExperience={definitiveAppExperience}
        eventsPeriod={eventsNavigationPeriod}
        eventsTotal={eventsNavigationTotal}
        fitMainViewport={definitiveAppExperience && activeTab === "live"}
        language={language}
        labEnabled={labEnabled}
        nativeAndroid={isNativeAndroidRuntime()}
        onLanguageChange={() => handleLanguagePreferenceChange(nextLanguage)}
        onLocationSearchOpen={() => setLocationSearchOpen(true)}
        officialAlert={officialAlert}
        onOfficialAlertOpen={handleOfficialAlertOpen}
        onRuntimeRefresh={requestRuntimeRefresh}
        onSettingsOpen={handleSettingsOpen}
        onTabChange={handleRouteChange}
        navigationLocked={isReportSubmissionLocked}
        tabs={APP_TABS}
        theme={theme}
      >
        <AppRoutes
          activeTab={activeTab}
          activeLocation={activeLocation}
          appVersion={{
            platform: isNativeAndroidRuntime() ? "android" : "web",
            version: isNativeAndroidRuntime() ? nativeAppVersion : frontendPackage.version,
            development: import.meta.env.DEV,
          }}
          communityIdentity={communityIdentity}
          copy={copy}
          labEnabled={labEnabled}
          language={language}
          autoLocationEnabled={autoLocationEnabled}
          backgroundLocationRuntime={backgroundLocationRuntime}
          deviceLocationStatus={deviceLocationStatus}
          editorialContext={editorialContext}
          onAutomaticLocationChange={handleAutomaticLocationChange}
          onBackgroundLocationSettingsOpen={handleBackgroundLocationSettingsOpen}
          onCommunityIdentityChange={handleCommunityIdentityChange}
          onCommunityNavigationState={handleCommunityNavigationState}
          onCommunityReportsViewed={handleCommunityReportsViewed}
          onLanguageSelect={handleLanguagePreferenceChange}
          onLocationSearchOpen={() => setLocationSearchOpen(true)}
          onEventsNavigationState={handleEventsNavigationState}
          onNavigate={handleRouteChange}
          notificationPreferences={notificationPreferences}
          notificationRuntime={notificationRuntime}
          officialAlert={officialAlert}
          officialAlertsRuntime={officialAlertsRuntime}
          productScope={productScope}
          onNotificationPermissionRequest={isNativeAndroidRuntime()
            ? requestAndActivateNativePush
            : requestAndActivateWebPush}
          onNotificationPreferenceChange={handleNotificationPreferenceChange}
          onNotificationSettingsOpen={handleNotificationSettingsOpen}
          onReportSubmit={handleCommunityReportSubmit}
          onReportUndo={isLocalCommunityPilot() ? undefined : handleCommunityReportUndo}
          onReportUpdate={isLocalCommunityPilot() ? handleCommunityReportUpdate : undefined}
          onReportWithdraw={isLocalCommunityPilot() ? handleCommunityReportWithdraw : undefined}
          pendingReportUndo={pendingReportUndo}
          pilotWhyId={pilotWhyId}
          reportSubmissionLocked={isReportSubmissionLocked}
          routeAnchorRequest={routeAnchorRequest}
          onRuntimeCacheReset={handleRuntimeCacheReset}
          onSupportOpen={handleSupportOpen}
          onRuntimeRefreshSettled={handleRuntimeRefreshSettled}
          onSettingsBack={handleSettingsBack}
          onThemePreferenceChange={handleThemePreferenceChange}
          runtimeRefreshToken={runtimeRefreshToken}
          runtimeRefreshForce={runtimeRefreshForce}
          theme={theme}
          themePreference={themePreference}
          supportUrl={supportUrl}
        />
      </AppShell>
      <LocationSearchSheet
        activeLocation={activeLocation}
        isOpen={isLocationSearchOpen}
        language={language}
        onClose={handleLocationSearchClose}
        onLocationSelect={handleLocationSelect}
      />
      <WebPushForegroundBanner
        language={language}
        message={webPushForegroundMessage}
        onClose={() => setWebPushForegroundMessage(null)}
        onOpenBulletin={handleWebPushBannerOpen}
      />
      {pilotLanguageOnboardingVisible ? (
        <PilotLanguageOnboarding
          language={language}
          onLanguageSelect={handlePilotLanguageSelect}
        />
      ) : null}
      {!pilotLanguageOnboardingVisible
        && !isNativeAndroidRuntime()
        && !labEnabled
        && webStartupOnboarding.visible ? (
        <WebStartupOnboarding
          busy={webStartupOnboarding.busy}
          language={language}
          locationResult={webStartupOnboarding.locationResult}
          notificationRuntime={notificationRuntime}
          onClose={handleWebStartupClose}
          onLocationRequest={handleWebStartupLocationRequest}
          onLocationSkip={handleWebStartupLocationSkip}
          onManualLocation={handleWebStartupManualLocation}
          onNotificationRequest={handleWebStartupNotificationRequest}
          step={webStartupOnboarding.step}
        />
      ) : null}
      {backgroundLocationDisclosureContext ? (
        <BackgroundLocationDisclosure
          context={backgroundLocationDisclosureContext}
          copy={getBackgroundLocationDisclosureCopy(language, {
            context: backgroundLocationDisclosureContext,
          })}
          onCancel={() => settleBackgroundLocationDisclosure(false)}
          onContinue={() => settleBackgroundLocationDisclosure(true)}
        />
      ) : null}
    </>
  );
}
