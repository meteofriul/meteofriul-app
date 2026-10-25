import {
  Camera,
  Check,
  ChevronLeft,
  ChevronRight,
  ChevronUp,
  LocateFixed,
  MapPin,
  Radio,
  SatelliteDish,
  Send,
  Share2,
  TriangleAlert,
  X,
} from "lucide-react";
import { useCallback, useEffect, useId, useMemo, useRef, useState } from "react";
import { usePilotBackHandler } from "../../app/usePilotBackHandler";
import { isAndroidCapacitorRuntime } from "../../services/apiConfig";
import { isLocalCommunityPilot, isLocalCommunityDevelopmentRuntime } from "../../services/localCommunityPilot";
import { isDefinitiveAppExperience } from "../../services/localWeatherPilot";
import { AppIconButton } from "../../ui/components/AppIconButton";
import { CommunityMapPhenomenon } from "./CommunityMap";
import { CommunityHistory } from "./CommunityHistory";
import { buildCommunityRecentItems } from "./communityRecentReports";
import { useCommunityRecentReports } from "./useCommunityRecentReports";
import { CommunityRecentHistoryRow, CommunityHistoryDetail } from "./CommunityRecentHistoryRow";
import { CommunityRecentPagination } from "./CommunityRecentPagination";
import "./communityRecentReports.css";
import {
  buildCommunitySharePayload,
  consumeCommunityReportShareTarget,
  shareCommunityPayload,
} from "./communityShare";
import { trapCommunityModerationFocus } from "./communityModerationFocus";
import {
  getCommunityVote,
  getOwnCommunityReport,
} from "./communityPersonalState";
import {
  getCommunityDenialLabel,
  getCommunityMapWithdrawalLabel,
} from "./communitySocialPresentation";
import { CommunityAvatar } from "../community/CommunityAvatar";
import { getCommunityIdentityPreview } from "../community/communityIdentity";
import { PILOT_LIVE_REPORT_ICONS } from "./liveReportIcons";
import { TerritoryRadarOverlay } from "./TerritoryRadarOverlay";
import {
  TERRITORY_FVG_BOUNDS,
  TERRITORY_ITALY_BOUNDS,
  getTerritoryInitialCenter,
  getTerritoryBasemapConfig,
} from "./territoryMapConfig";
import { mountTerritoryBasemapLayer } from "./territoryBasemapLayer";
import {
  WEBCAM_CLUSTER_EXPANSION_ZOOM,
  buildColocatedWebcamMarkerOffsets,
  buildWebcamPlaceGroups,
} from "./webcamPlaceGroups";

const TERRITORY_INITIAL_ZOOM_BOOST = 0.5;
const TERRITORY_LOCATION_INITIAL_ZOOM = 8.5;
const TERRITORY_CLUSTER_FAN_MIN_RADIUS = 60;
const TERRITORY_CLUSTER_FAN_MAX_RADIUS = 65;
const SHARE_FEEDBACK_MS = 2_000;
const TERRITORY_CLUSTER_TYPE_ORDER = [
  "rain",
  "storm",
  "snow",
  "hail",
  "fog",
  "wind",
  "ice",
  "quiet",
  "unknown",
];

const COPY = {
  fur: {
    alert: "Alerte uficiâl",
    alertArea: "Aree interessade",
    alertDetails: "Vierç i detais uficiâi",
    alertLevel: "Nivel",
    alertMixedArea: "Nivei diferents a seconde de zone",
    alertRegionalArea: "Teritori regjonâl dal Friûl Vignesie Julie",
    alertRisk: "Risi",
    alertSource: "Font uficiâl",
    alertValidity: "Validitât",
    cameraPositionDeclared: "Posizion declarade",
    cameraPositionIndicative: "Posizion indicative",
    center: "Centre la mape su la localitât selezionade",
    close: "Siere",
    map: "Mape",
    mapAria: "Mape interative dal teritori",
    mapControls: "Controi de mape",
    noApprovedWebcams: "Lis posizions des webcam a son daûr a vignî controladis une par volte.",
    noReports: "Nissune segnalazion resinte su la mape.",
    radar: "Radar",
    radarUnavailable: "Radar pal moment no disponibil",
    reported: "Segnalade",
    reportSentinel: "Sentinele Meteo",
    reportSentinels: "Sentinelis Meteo",
    reportSentinelsHide: "Plate lis sentinelis Meteo",
    reportSentinelsMore: "e altris {count}",
    reportSentinelsMoreOne: "e une altre",
    reportSentinelsShowAll: "Mostre dutis lis sentinelis Meteo",
    reportScope: "Riferît al Comun",
    reports: "Segnalazions",
    reportsLayer: "Segnalazions resintis su la mape",
    share: "Condivît",
    shareCopied: "Link copiât",
    shareDialogTitle: "Condivît la segnalazion Meteo Friûl",
    shareDone: "Condividût",
    shareWorking: "Daûr a condividi…",
    shareUnavailableShort: "No disponibil",
    shareUnavailable: "La condivision no je disponibile.",
    sharedReportUnavailable: "Cheste segnalazion no je plui ative o no je disponibile.",
    webcams: "Webcam",
    webcamClusterLabel: "{place} · {count} webcam",
    webcamNext: "Webcam sucessive",
    webcamPosition: "{current} di {count}",
    webcamPrevious: "Webcam precedente",
    webcamsLayer: "Webcam su la mape",
  },
  it: {
    alert: "Allerta ufficiale",
    alertArea: "Area interessata",
    alertDetails: "Apri i dettagli ufficiali",
    alertLevel: "Livello",
    alertMixedArea: "Livelli differenziati per zona",
    alertRegionalArea: "Territorio regionale del Friuli Venezia Giulia",
    alertRisk: "Rischio",
    alertSource: "Fonte ufficiale",
    alertValidity: "Validità",
    cameraPositionDeclared: "Posizione dichiarata",
    cameraPositionIndicative: "Posizione indicativa",
    center: "Centra la mappa sulla località selezionata",
    close: "Chiudi",
    map: "Mappa",
    mapAria: "Mappa interattiva del territorio",
    mapControls: "Controlli mappa",
    noApprovedWebcams: "Le posizioni delle webcam saranno verificate e abilitate una alla volta.",
    noReports: "Nessuna segnalazione recente sulla mappa.",
    radar: "Radar",
    radarUnavailable: "Radar temporaneamente non disponibile",
    reported: "Segnalata",
    reportSentinel: "Sentinella Meteo",
    reportSentinels: "Sentinelle Meteo",
    reportSentinelsHide: "Nascondi le Sentinelle Meteo",
    reportSentinelsMore: "e altri {count}",
    reportSentinelsMoreOne: "e un’altra",
    reportSentinelsShowAll: "Mostra tutte le Sentinelle Meteo",
    reportScope: "Riferito al Comune",
    reports: "Segnalazioni",
    reportsLayer: "Segnalazioni recenti sulla mappa",
    share: "Condividi",
    shareCopied: "Link copiato",
    shareDialogTitle: "Condividi la segnalazione Meteo Friûl",
    shareDone: "Condiviso",
    shareWorking: "Condivisione…",
    shareUnavailableShort: "Non disponibile",
    shareUnavailable: "Condivisione non disponibile.",
    sharedReportUnavailable: "Questa segnalazione non è più attiva o non è disponibile.",
    webcams: "Webcam",
    webcamClusterLabel: "{place} · {count} webcam",
    webcamNext: "Webcam successiva",
    webcamPosition: "{current} di {count}",
    webcamPrevious: "Webcam precedente",
    webcamsLayer: "Webcam sulla mappa",
  },
};

function getCopy(language) {
  return language === "fur" ? COPY.fur : COPY.it;
}

function buildFallbackPositions(items, offset = 0) {
  return Object.fromEntries(items.map((item, index) => [item.id, {
    left: `${42 + ((index + offset) % 3) * 8}%`,
    top: `${42 + ((index + offset) % 2) * 12}%`,
  }]));
}

function getCommunityMarkerLabel(marker) {
  return [marker.typeLabel, marker.place, marker.timeLabel, marker.countLabel]
    .filter(Boolean)
    .join(" · ");
}

function getClusterFanPosition(index, total) {
  const itemCount = Math.max(1, Number(total) || 1);
  const safeIndex = Math.min(Math.max(0, Number(index) || 0), itemCount - 1);
  const radius = itemCount >= 4
    ? TERRITORY_CLUSTER_FAN_MAX_RADIUS
    : TERRITORY_CLUSTER_FAN_MIN_RADIUS;
  const [startAngle, endAngle] = itemCount === 1
    ? [-90, -90]
    : itemCount === 2
      ? [-135, -45]
      : itemCount === 3
        ? [-150, -30]
        : [-165, -15];
  const angle = itemCount === 1
    ? startAngle
    : startAngle + ((endAngle - startAngle) * safeIndex) / (itemCount - 1);
  const radians = (angle * Math.PI) / 180;

  return {
    angle,
    radius,
    x: Math.round(Math.cos(radians) * radius),
    y: Math.round(Math.sin(radians) * radius),
  };
}

function sortClusterPhenomena(phenomena) {
  return [...(phenomena || [])].sort((first, second) => {
    const firstIndex = TERRITORY_CLUSTER_TYPE_ORDER.indexOf(first?.typeId);
    const secondIndex = TERRITORY_CLUSTER_TYPE_ORDER.indexOf(second?.typeId);
    const normalizedFirstIndex = firstIndex === -1
      ? TERRITORY_CLUSTER_TYPE_ORDER.length
      : firstIndex;
    const normalizedSecondIndex = secondIndex === -1
      ? TERRITORY_CLUSTER_TYPE_ORDER.length
      : secondIndex;
    return normalizedFirstIndex - normalizedSecondIndex;
  });
}

function getRecentCommunityConfirmationLabel(marker, communityCopy) {
  const count = Math.max(1, Number(marker?.count) || 1);
  const template = count === 1
    ? communityCopy?.communityRecentSummaryOne
    : communityCopy?.communityRecentSummaryMany;
  return String(template || marker?.countLabel || "").replace("{count}", String(count));
}

function getCommunityAvailabilityMessage(kind, communityCopy, fallback) {
  const messages = {
    error: [communityCopy?.communityErrorTitle, communityCopy?.communityErrorBody],
    loading: [communityCopy?.communityLoadingTitle, communityCopy?.communityLoadingBody],
    stale: [communityCopy?.communityStaleTitle, communityCopy?.communityStaleBody],
  };
  return (messages[kind] || [fallback]).filter(Boolean).join(". ");
}

function normalizeCameraLabel(value) {
  return String(value || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
}

function getCameraLocation(camera) {
  const cameraName = normalizeCameraLabel(camera?.name);
  return [camera?.locationLabel, camera?.place, camera?.area]
    .map((value) => String(value || "").trim())
    .find((value) => value && normalizeCameraLabel(value) !== cameraName) || "";
}

function getCameraDetailTitle(camera) {
  const name = String(camera?.name || "").trim();
  const locationPrefixes = [camera?.place, camera?.locationLabel, camera?.area]
    .flatMap((value) => String(value || "").split("·"))
    .map((value) => value.trim())
    .filter(Boolean)
    .sort((first, second) => second.length - first.length);

  for (const prefix of locationPrefixes) {
    for (const separator of [" - ", " – ", " — ", " · ", " / "]) {
      const expectedPrefix = `${prefix}${separator}`;
      if (name.slice(0, expectedPrefix.length).localeCompare(expectedPrefix, undefined, {
        sensitivity: "base",
      }) === 0) {
        return name.slice(expectedPrefix.length).trim() || name;
      }
    }
  }

  return name;
}

function isWebcamHealthNotOk(camera) {
  const healthId = String(camera?.health?.id || "").toLowerCase();
  return Boolean(healthId && !["fresh", "ok", "loading", "unknown"].includes(healthId));
}

function getWebcamMarkerLabel(copy, camera) {
  return [
    copy.webcams,
    camera?.name,
    getCameraLocation(camera),
    isWebcamHealthNotOk(camera) ? camera?.health?.label : "",
  ].filter(Boolean).join(" · ");
}

function getWebcamMarkerStyle(basePosition, visualOffset) {
  if (!visualOffset) return basePosition;
  return {
    ...basePosition,
    marginLeft: `${visualOffset.x}px`,
    marginTop: `${visualOffset.y}px`,
  };
}

function dedupeCameras(cameras) {
  const seen = new Set();
  return (cameras || []).filter((camera) => {
    const id = String(camera?.id || "");
    if (!id || seen.has(id)) return false;
    seen.add(id);
    return true;
  });
}

function dedupeReports(reports) {
  const seen = new Set();
  return (reports || []).filter((report) => {
    const id = String(report?.groupId || report?.id || "");
    if (!id || seen.has(id)) return false;
    seen.add(id);
    return true;
  });
}

function WebcamBrowseThumbnail({ camera }) {
  const sources = useMemo(() => [...new Set([
    camera?.imageUrl,
    camera?.fallbackImageUrl,
  ].filter(Boolean))], [camera?.fallbackImageUrl, camera?.imageUrl]);
  const [sourceIndex, setSourceIndex] = useState(0);
  const source = sources[sourceIndex] || "";

  return (
    <span aria-hidden="true" className="mf-territory-map__webcam-thumbnail">
      {source ? (
        <img
          alt=""
          decoding="async"
          loading="lazy"
          onError={() => setSourceIndex((current) => current + 1)}
          referrerPolicy="no-referrer"
          src={source}
        />
      ) : <Camera aria-hidden="true" size={19} strokeWidth={2.35} />}
    </span>
  );
}

function CommunitySentinelCluster({ compact = false, copy, identities = [] }) {
  const aliasAvatarSize = 40;
  const [expanded, setExpanded] = useState(false);
  const generatedListId = useId().replace(/[^a-zA-Z0-9_-]/g, "");
  const listId = `territory-report-sentinels-${generatedListId}`;
  const visibleAvatars = identities.slice(0, 3);
  const firstIdentity = identities[0];
  const additionalCount = Math.max(0, identities.length - 1);
  const additionalLabel = additionalCount === 1
    ? copy.reportSentinelsMoreOne
    : String(copy.reportSentinelsMore || "").replace("{count}", String(additionalCount));
  const summary = [firstIdentity?.alias, additionalCount ? additionalLabel : ""]
    .filter(Boolean)
    .join(" ");
  const toggleLabel = expanded
    ? copy.reportSentinelsHide
    : copy.reportSentinelsShowAll;

  if (!firstIdentity) return null;

  if (compact && identities.length === 1) {
    return (
      <span className="mf-territory-map__report-community-identities mf-territory-map__report-community-identities--single">
        <span className="mf-territory-map__report-community-identities-label">
          {copy.reportSentinel}:
        </span>
        <span className="mf-territory-map__report-community-single">
          <span aria-hidden="true" className="mf-territory-map__report-community-avatar-stack">
            <CommunityAvatar decorative size={aliasAvatarSize} snapshot={firstIdentity} />
          </span>
          <span className="mf-territory-map__report-community-summary">{firstIdentity.alias}</span>
        </span>
      </span>
    );
  }

  return (
    <span className="mf-territory-map__report-community-identities">
      <span className="mf-territory-map__report-community-identities-label">
        {copy.reportSentinels}:
      </span>
      <button
        aria-controls={listId}
        aria-expanded={expanded}
        aria-label={`${toggleLabel}: ${summary}`}
        className="mf-territory-map__report-community-toggle"
        onClick={() => setExpanded((current) => !current)}
        title={toggleLabel}
        type="button"
      >
        <span aria-hidden="true" className="mf-territory-map__report-community-avatar-stack">
          {visibleAvatars.map((identity, index) => (
            <CommunityAvatar
              decorative
              key={`${identity.subjectId}:${identity.alias}:${index}`}
              size={aliasAvatarSize}
              snapshot={identity}
            />
          ))}
        </span>
        <span className="mf-territory-map__report-community-summary">{summary}</span>
        {expanded ? (
          <ChevronUp
            aria-hidden="true"
            className="mf-territory-map__report-community-chevron"
            size={14}
            strokeWidth={2.5}
          />
        ) : (
          <ChevronRight
            aria-hidden="true"
            className="mf-territory-map__report-community-chevron"
            size={14}
            strokeWidth={2.5}
          />
        )}
      </button>
      <span
        className="mf-territory-map__report-community-list"
        hidden={!expanded}
        id={listId}
        role="list"
      >
        {identities.map((identity, index) => (
          <span
            className="mf-territory-map__report-community-list-item"
            key={`${identity.subjectId}:${identity.alias}:${index}`}
            role="listitem"
          >
            {identity.alias}
          </span>
        ))}
      </span>
    </span>
  );
}

export function TerritoryImmersiveMap({
  communityAvailability = "empty",
  communityCopy,
  confirmationCountsByGroup = {},
  confirmationStatuses = {},
  confirmationMessages = {},
  inferredOwnGroupIds = [],
  inline = false,
  language = "it",
  location = null,
  mapWebcams = [],
  markers = [],
  onConfirm,
  onDetailOpenChange,
  onEdit,
  officialAlert = null,
  onOfficialAlertOpen,
  onReportRequest,
  onReportsViewed,
  onUpdate,
  onWithdraw,
  onCorrect,
  onReplace,
  personalState,
  radarModel = null,
  reportUnavailableText = "",
  reportItems = [],
  reportDialogId,
  reportOpen = false,
  renderWebcamDetail,
  sharedReportId = "",
  sharedReportLoadSettled = false,
  theme = "light",
  webcamGroups = [],
  webcamList = [],
  webcamsEnabled = true,
}) {
  const copy = getCopy(language);
  const pilotPresentation = isDefinitiveAppExperience() || isLocalCommunityPilot();
  const recentListEnabled = isLocalCommunityDevelopmentRuntime();
  const basemap = useMemo(
    () => getTerritoryBasemapConfig(undefined, { theme }),
    [theme],
  );
  const mapMaxZoom = basemap.primary.maxZoom;
  const mapMinZoom = basemap.primary.minZoom;
  const containerRef = useRef(null);
  const detailRef = useRef(null);
  const detailSwipeRef = useRef(null);
  const webcamSwipeRef = useRef(null);
  const detailTriggerRef = useRef(null);
  const dockSwipeRef = useRef(null);
  const dockSwipeHandledRef = useRef(false);
  const clusterTriggerRef = useRef(null);
  const pendingWebcamClusterFocusRef = useRef("");
  const regionRef = useRef(null);
  const mapRef = useRef(null);
  const mapViewportKeyRef = useRef("");
  const panelModeRef = useRef("map");
  const selectedLocationRef = useRef(null);
  const generatedBrowseId = useId();
  const browsePanelId = `territory-browse-panel-${generatedBrowseId}`;
  const browseListId = `territory-browse-list-${generatedBrowseId}`;
  const radarOverlayId = `territory-radar-overlay-${generatedBrowseId}`;
  const alertDialogId = `territory-alert-dialog-${generatedBrowseId}`;
  const [leaflet, setLeaflet] = useState(null);
  const [map, setMap] = useState(null);
  const [mapZoom, setMapZoom] = useState(mapMinZoom);
  const [panelMode, setPanelMode] = useState("map");
  const [browseExpanded, setBrowseExpanded] = useState(false);
  const [activeWebcamGroupId, setActiveWebcamGroupId] = useState("nearby");
  const [radarEnabled, setRadarEnabled] = useState(false);
  const [alertOpen, setAlertOpen] = useState(false);
  const [gpsPulse, setGpsPulse] = useState(false);
  const [positions, setPositions] = useState({
    community: {},
    webcam: {},
    webcamGroups: {},
  });
  const [selectedFeature, setSelectedFeature] = useState(null);
  const pendingSharedReportIdRef = useRef(sharedReportId);
  const pendingSharedReportMapPointRef = useRef(null);
  const [highlightedWebcamId, setHighlightedWebcamId] = useState(null);
  const [expandedClusterId, setExpandedClusterId] = useState(null);
  const [shareState, setShareState] = useState("idle");
  const shareAttemptRef = useRef(0);
  const gpsPulseFrameRef = useRef(null);
  const gpsPulseTimeoutRef = useRef(null);
  const officialAlertTone = ["orange", "red"].includes(officialAlert?.tone)
    ? officialAlert.tone
    : "";
  const hasOfficialAlert = Boolean(officialAlertTone && officialAlert?.label);
  const officialAlertArea = String(
    officialAlert?.mixedLevels
      ? copy.alertMixedArea
      : officialAlert?.area
        || (Array.isArray(officialAlert?.zones) ? officialAlert.zones.join(" · ") : "")
        || copy.alertRegionalArea,
  ).trim();
  const officialAlertRisk = (
    Array.isArray(officialAlert?.risks) && officialAlert.risks.length
      ? officialAlert.risks.join(" · ")
      : officialAlert?.text || officialAlert?.paragraphs?.[0] || ""
  ).trim();
  const officialAlertSource = String(
    officialAlert?.sourceLabel || officialAlert?.meta || "Protezione Civile FVG",
  ).trim();
  const [showHistory, setShowHistory] = useState(false);
  const allReports = useMemo(() => {
    const source = reportItems.length
      ? reportItems
      : markers.flatMap((marker) => marker.phenomena || [marker]);
    return dedupeReports(source).sort(
      (first, second) => Number(second.createdAt || 0) - Number(first.createdAt || 0),
    );
  }, [markers, reportItems]);
  const recentHistory = useCommunityRecentReports({
    enabled: recentListEnabled && panelMode === "reports", location,
    refreshKey: JSON.stringify(allReports.map((report) => [report.id, report.reportIds,
      report.createdAt, report.expiresAt, report.confirmations])),
  });
  const recentItems = recentListEnabled
    ? buildCommunityRecentItems(recentHistory.reports, allReports, recentHistory.now) : [];
  const sharedReportUnavailable = Boolean(
    sharedReportId
      && sharedReportLoadSettled
      && !allReports.some((item) => (
        item.groupId === sharedReportId || item.id === sharedReportId
      )),
  );

  useEffect(() => {
    pendingSharedReportIdRef.current = sharedReportId;
    pendingSharedReportMapPointRef.current = null;
  }, [sharedReportId]);

  useEffect(() => {
    const targetId = pendingSharedReportIdRef.current;
    if (!targetId) return;

    const report = allReports.find((item) => (
      item.groupId === targetId || item.id === targetId
    ));
    if (!report) {
      if (!sharedReportLoadSettled) return;
      pendingSharedReportIdRef.current = "";
      consumeCommunityReportShareTarget();
      return;
    }

    const reportMarker = markers.find((marker) => (
      (marker.phenomena || [marker]).some((phenomenon) => (
        phenomenon.groupId === targetId || phenomenon.id === targetId
      ))
    ));
    if (Number.isFinite(reportMarker?.lat) && Number.isFinite(reportMarker?.lon)) {
      pendingSharedReportMapPointRef.current = {
        lat: reportMarker.lat,
        lon: reportMarker.lon,
      };
    }

    pendingSharedReportIdRef.current = "";
    detailTriggerRef.current = null;
    setExpandedClusterId(null);
    setBrowseExpanded(false);
    setPanelMode("map");
    setAlertOpen(false);
    setShareState("idle");
    setSelectedFeature({ id: report.id, kind: "community" });
    consumeCommunityReportShareTarget();
  }, [allReports, markers, sharedReportId, sharedReportLoadSettled]);
  const allWebcams = useMemo(
    () => webcamsEnabled ? dedupeCameras(webcamList) : [],
    [webcamList, webcamsEnabled],
  );
  const availableWebcamGroups = useMemo(() => (
    webcamsEnabled
      ? webcamGroups
        .map((group) => ({
          ...group,
          cameras: dedupeCameras(group?.cameras),
        }))
        .filter((group) => group.id && group.cameras.length)
      : []
  ), [webcamGroups, webcamsEnabled]);
  const activeWebcamGroup = availableWebcamGroups.find(
    (group) => group.id === activeWebcamGroupId,
  ) || availableWebcamGroups[0] || null;
  const activeWebcams = activeWebcamGroup?.cameras || allWebcams;
  const activeWebcamPlaceGroups = useMemo(() => {
    const cameraOrder = new Map(activeWebcams.map((camera, index) => [camera.id, index]));
    return buildWebcamPlaceGroups(activeWebcams).sort((first, second) => {
      const firstIndex = Math.min(...first.cameras.map(
        (camera) => cameraOrder.get(camera.id) ?? Number.MAX_SAFE_INTEGER,
      ));
      const secondIndex = Math.min(...second.cameras.map(
        (camera) => cameraOrder.get(camera.id) ?? Number.MAX_SAFE_INTEGER,
      ));
      return firstIndex - secondIndex;
    });
  }, [activeWebcams]);
  const visibleMapWebcams = useMemo(() => {
    const activeIds = new Set(activeWebcams.map((camera) => camera.id));
    return webcamsEnabled
      ? mapWebcams.filter((camera) => activeIds.has(camera.id))
      : [];
  }, [activeWebcams, mapWebcams, webcamsEnabled]);
  const visibleWebcamPlaceGroups = useMemo(
    () => buildWebcamPlaceGroups(visibleMapWebcams),
    [visibleMapWebcams],
  );
  const webcamClustersExpandedByZoom = mapZoom >= WEBCAM_CLUSTER_EXPANSION_ZOOM;
  const colocatedWebcamOffsets = useMemo(
    () => webcamClustersExpandedByZoom
      ? buildColocatedWebcamMarkerOffsets(visibleMapWebcams)
      : {},
    [visibleMapWebcams, webcamClustersExpandedByZoom],
  );
  const webcamsVisible = webcamsEnabled && panelMode === "webcams";
  const selectedCommunity = selectedFeature?.kind === "community"
    ? allReports.find((report) => report.id === selectedFeature.id) ||
      markers.find((marker) => marker.id === selectedFeature.id) || null
    : null;
  const selectedHistory = selectedFeature?.kind === "history"
    ? recentItems.find((report) => report.recentKind === "history" && report.id === selectedFeature.id) || null
    : null;
  const selectedPhenomena = selectedCommunity?.phenomena || (
    selectedCommunity ? [selectedCommunity] : []
  );
  const selectedPrimaryPhenomenon = selectedPhenomena[0] || null;
  const SelectedCommunityIcon = PILOT_LIVE_REPORT_ICONS[selectedCommunity?.typeId] || Radio;
  const selectedCommunityConfirmationLabel = selectedCommunity
    ? getRecentCommunityConfirmationLabel(selectedCommunity, communityCopy)
    : "";
  const selectedCommunitySourceKeys = selectedPrimaryPhenomenon?.sourceKeys || [];
  const selectedCommunityIdentityPreview = selectedPhenomena.length === 1
    ? getCommunityIdentityPreview({
        identities: selectedPrimaryPhenomenon?.identities,
        limit: Number.MAX_SAFE_INTEGER,
        placeName: selectedPrimaryPhenomenon?.place,
        sourceKeys: selectedCommunitySourceKeys,
      })
    : { hiddenCount: 0, identities: [], totalCount: 0 };
  const selectedCommunityConfirmationStatus = selectedPrimaryPhenomenon
    ? confirmationStatuses[selectedPrimaryPhenomenon.groupId] || "idle"
    : "idle";
  const selectedCommunityVote = selectedPrimaryPhenomenon
    ? getCommunityVote(personalState, selectedPrimaryPhenomenon.groupId, isLocalCommunityPilot() ? selectedPrimaryPhenomenon.reportIds || [] : undefined)
    : "";
  const selectedCommunityStatusLabel = selectedCommunityConfirmationStatus === "error"
    ? confirmationMessages[selectedPrimaryPhenomenon?.groupId] || communityCopy.confirmError
    : selectedCommunityConfirmationStatus === "success"
      ? selectedCommunityVote === "no"
        ? communityCopy.denialDone
        : communityCopy.confirmationDoneFeedback
      : selectedCommunityConfirmationLabel;
  const selectedWebcam = webcamsEnabled && selectedFeature?.kind === "webcam"
    ? allWebcams.find((camera) => camera.id === selectedFeature.id)
      || mapWebcams.find((camera) => camera.id === selectedFeature.id)
      || null
    : null;
  const selectedWebcamPlaceGroup = selectedWebcam
    ? activeWebcamPlaceGroups.find((placeGroup) => (
      placeGroup.cameras.some((camera) => camera.id === selectedWebcam.id)
    )) || null
    : null;
  const selectedWebcamIndex = selectedWebcamPlaceGroup
    ? selectedWebcamPlaceGroup.cameras.findIndex((camera) => camera.id === selectedWebcam.id)
    : -1;

  useEffect(() => {
    const point = pendingSharedReportMapPointRef.current;
    if (!map || !point || !selectedCommunity) return;

    pendingSharedReportMapPointRef.current = null;
    map.setView(
      [point.lat, point.lon],
      Math.max(10, Number(map.getZoom?.()) || 10),
      { animate: false },
    );
  }, [map, selectedCommunity]);
  const hasDetail = Boolean(selectedCommunity || selectedHistory || selectedWebcam || alertOpen);
  const shareAnnouncement = shareState === "copied"
    ? copy.shareCopied
    : shareState === "shared"
      ? copy.shareDone
      : shareState === "unavailable"
        ? copy.shareUnavailable
        : "";
  const shareButtonLabel = shareState === "loading"
    ? copy.shareWorking
    : shareState === "copied"
      ? copy.shareCopied
      : shareState === "shared"
        ? copy.shareDone
        : shareState === "unavailable"
          ? copy.shareUnavailableShort
          : copy.share;
  const shareSucceeded = ["copied", "shared"].includes(shareState);
  const ShareIcon = shareSucceeded ? Check : Share2;
  const browseItems = panelMode === "reports"
    ? recentListEnabled ? recentItems : allReports : activeWebcamPlaceGroups;
  const browsePreviewLimit = 1;
  const compactWebcamBrowse = panelMode === "webcams" && !browseExpanded;
  const visibleBrowseItems = browseExpanded
    ? browseItems
    : compactWebcamBrowse
      ? []
      : browseItems.slice(0, browsePreviewLimit);
  const canExpandBrowse = recentListEnabled && panelMode === "reports"
    ? browseItems.length > browsePreviewLimit || Boolean(recentHistory.next)
    : panelMode === "webcams"
    ? browseItems.length > 0
    : browseItems.length > browsePreviewLimit;
  const dockBrowseHandleEnabled = panelMode !== "map" && (browseExpanded
    || (recentListEnabled && panelMode === "reports" && canExpandBrowse));
  const hasChildSurface = hasDetail || Boolean(expandedClusterId) || panelMode !== "map";
  const fallbackPositions = useMemo(() => ({
    community: buildFallbackPositions(markers),
    webcam: buildFallbackPositions(visibleMapWebcams, markers.length),
    webcamGroups: buildFallbackPositions(visibleWebcamPlaceGroups, markers.length),
  }), [markers, visibleMapWebcams, visibleWebcamPlaceGroups]);
  const validLocation = useMemo(() => {
    const center = getTerritoryInitialCenter(location);
    return center ? { lat: center[0], lon: center[1] } : null;
  }, [location]);
  useEffect(() => {
    selectedLocationRef.current = validLocation;
  }, [validLocation]);

  useEffect(() => {
    panelModeRef.current = panelMode;
  }, [panelMode]);

  useEffect(() => {
    if (!["copied", "shared", "unavailable"].includes(shareState)) return undefined;
    const timeoutId = globalThis.setTimeout?.(() => setShareState("idle"), SHARE_FEEDBACK_MS);
    return () => globalThis.clearTimeout?.(timeoutId);
  }, [shareState]);

  const closeSelectedFeature = useCallback(({ restoreFocus = true } = {}) => {
    setSelectedFeature(null);
    setAlertOpen(false);
    shareAttemptRef.current += 1;
    setShareState("idle");
    detailSwipeRef.current = null;
    if (!restoreFocus) return;

    globalThis.requestAnimationFrame?.(() => {
      const trigger = detailTriggerRef.current;
      if (trigger?.isConnected) trigger.focus?.({ preventScroll: true });
      else regionRef.current?.focus?.({ preventScroll: true });
    });
  }, []);
  const withdrawOwnReport = async (reportId) => {
    if (!onWithdraw) return { ok: false, reason: "unavailable" };
    const result = await onWithdraw(reportId);
    if (result?.ok) closeSelectedFeature();
    return result;
  };
  const updateOwnReport = async (report) => {
    if (!onUpdate) return { ok: false, reason: "unavailable" };
    const result = await onUpdate(report);
    if (result?.reason === "observation_expired") closeSelectedFeature({ restoreFocus: false });
    else if (["observation_conflict", "observation_rejected"].includes(result?.reason)) {
      closeSelectedFeature();
    }
    return result;
  };

  const closeExpandedCluster = useCallback(({ restoreFocus = true } = {}) => {
    const trigger = clusterTriggerRef.current;
    setExpandedClusterId(null);
    if (!restoreFocus) return;

    if (trigger?.isConnected) trigger.focus?.({ preventScroll: true });
    else regionRef.current?.focus?.({ preventScroll: true });
  }, []);

  useEffect(() => () => {
    if (gpsPulseFrameRef.current !== null) {
      globalThis.cancelAnimationFrame?.(gpsPulseFrameRef.current);
    }
    if (gpsPulseTimeoutRef.current !== null) {
      globalThis.clearTimeout?.(gpsPulseTimeoutRef.current);
    }
  }, []);

  useEffect(() => {
    if (hasOfficialAlert || !alertOpen) return;
    const timeoutId = globalThis.setTimeout?.(() => setAlertOpen(false), 0);
    return () => globalThis.clearTimeout?.(timeoutId);
  }, [alertOpen, hasOfficialAlert]);

  const closeChildSurface = useCallback(() => {
    if (hasDetail) closeSelectedFeature();
    else if (expandedClusterId) closeExpandedCluster();
    else if (browseExpanded) setBrowseExpanded(false);
    else setPanelMode("map");
  }, [
    browseExpanded,
    closeExpandedCluster,
    closeSelectedFeature,
    expandedClusterId,
    hasDetail,
  ]);

  usePilotBackHandler(closeChildSurface, hasChildSurface);

  useEffect(() => {
    onDetailOpenChange?.(hasChildSurface);
    return () => {
      if (hasChildSurface) onDetailOpenChange?.(false);
    };
  }, [hasChildSurface, onDetailOpenChange]);

  useEffect(() => {
    if (!hasDetail || !globalThis.document) return undefined;

    const documentLike = globalThis.document;
    const focusFrame = globalThis.requestAnimationFrame?.(
      () => detailRef.current?.focus?.({ preventScroll: true }),
    );
    const handleKeyDown = (event) => {
      if (documentLike.querySelector?.(".mf-live-webcam-player")) return;
      if (event.key === "Escape") {
        event.preventDefault();
        event.stopPropagation();
        closeSelectedFeature();
        return;
      }
      if (trapCommunityModerationFocus(
        event,
        detailRef.current,
        documentLike.activeElement,
      )) event.stopPropagation();
    };

    documentLike.addEventListener("keydown", handleKeyDown, true);
    return () => {
      if (focusFrame !== undefined) globalThis.cancelAnimationFrame?.(focusFrame);
      documentLike.removeEventListener("keydown", handleKeyDown, true);
    };
  }, [closeSelectedFeature, hasDetail]);

  useEffect(() => {
    if (
      hasDetail
      || (!expandedClusterId && panelMode === "map")
      || !globalThis.document
    ) return undefined;

    const handleKeyDown = (event) => {
      if (event.key !== "Escape") return;
      event.preventDefault();
      event.stopPropagation();
      closeChildSurface();
    };
    globalThis.document.addEventListener("keydown", handleKeyDown, true);
    return () => globalThis.document.removeEventListener("keydown", handleKeyDown, true);
  }, [closeChildSurface, expandedClusterId, hasDetail, panelMode]);

  useEffect(() => {
    let cancelled = false;
    let resizeFrame;

    async function mountMap() {
      const leafletModule = await import("leaflet");
      if (cancelled || !containerRef.current || mapRef.current) return;

      const L = leafletModule.default || leafletModule;
      const nextMap = L.map(containerRef.current, {
        attributionControl: true,
        doubleClickZoom: true,
        maxBounds: TERRITORY_ITALY_BOUNDS,
        maxBoundsViscosity: 0.8,
        maxZoom: mapMaxZoom,
        minZoom: mapMinZoom,
        scrollWheelZoom: true,
        touchZoom: true,
        zoomControl: false,
        zoomSnap: 0.5,
      });

      nextMap.attributionControl.setPrefix(false);
      const initialLocation = selectedLocationRef.current;
      if (initialLocation) {
        nextMap.setView(
          [initialLocation.lat, initialLocation.lon],
          Math.min(
            Math.max(TERRITORY_LOCATION_INITIAL_ZOOM, mapMinZoom),
            mapMaxZoom,
          ),
          { animate: false },
        );
        mapViewportKeyRef.current = `${initialLocation.lat}:${initialLocation.lon}`;
      } else {
        nextMap.fitBounds(TERRITORY_FVG_BOUNDS, {
          paddingBottomRight: [24, inline ? 156 : 118],
          paddingTopLeft: [24, 96],
        });
        const fittedZoom = Number(nextMap.getZoom?.());
        if (Number.isFinite(fittedZoom)) {
          nextMap.setZoom?.(
            Math.min(fittedZoom + TERRITORY_INITIAL_ZOOM_BOOST, mapMaxZoom),
            { animate: false },
          );
        }
        mapViewportKeyRef.current = "fallback:fvg";
      }
      nextMap.on("click", () => {
        const webcamsAreActive = panelModeRef.current === "webcams";
        closeSelectedFeature({ restoreFocus: false });
        closeExpandedCluster({ restoreFocus: false });
        setHighlightedWebcamId(null);
        if (!webcamsAreActive) {
          setBrowseExpanded(false);
          setPanelMode("map");
        }
      });
      resizeFrame = globalThis.requestAnimationFrame?.(
        () => nextMap.invalidateSize?.({ pan: false }),
      );
      mapRef.current = nextMap;
      setLeaflet(L);
      setMap(nextMap);
    }

    mountMap();
    return () => {
      cancelled = true;
      if (resizeFrame !== undefined) globalThis.cancelAnimationFrame?.(resizeFrame);
      const disposedMap = mapRef.current;
      mapRef.current = null;
      mapViewportKeyRef.current = "";
      try {
        disposedMap?.remove();
      } catch {
        // Fast Refresh can dispose the same Leaflet surface while effects are recycling.
      }
    };
  }, [
    closeExpandedCluster,
    closeSelectedFeature,
    inline,
    mapMaxZoom,
    mapMinZoom,
  ]);

  useEffect(() => {
    if (!map || mapRef.current !== map) return;

    const nextViewportKey = validLocation
      ? `${validLocation.lat}:${validLocation.lon}`
      : "fallback:fvg";
    if (mapViewportKeyRef.current === nextViewportKey) return;

    if (validLocation) {
      map.setView(
        [validLocation.lat, validLocation.lon],
        Math.min(
          Math.max(TERRITORY_LOCATION_INITIAL_ZOOM, mapMinZoom),
          mapMaxZoom,
        ),
        { animate: false },
      );
    } else {
      map.fitBounds(TERRITORY_FVG_BOUNDS, {
        paddingBottomRight: [24, inline ? 156 : 118],
        paddingTopLeft: [24, 96],
      });
      const fittedZoom = Number(map.getZoom?.());
      if (Number.isFinite(fittedZoom)) {
        map.setZoom?.(
          Math.min(fittedZoom + TERRITORY_INITIAL_ZOOM_BOOST, mapMaxZoom),
          { animate: false },
        );
      }
    }
    mapViewportKeyRef.current = nextViewportKey;
  }, [inline, map, mapMaxZoom, mapMinZoom, validLocation]);

  useEffect(() => {
    if (!map || mapRef.current !== map || !leaflet) return undefined;

    return mountTerritoryBasemapLayer({ basemap, leaflet, map });
  }, [basemap, leaflet, map]);

  useEffect(() => {
    if (!map || mapRef.current !== map || !leaflet || !validLocation) return undefined;

    const dot = leaflet.circleMarker([validLocation.lat, validLocation.lon], {
      color: "#fff",
      fillColor: "#0878c9",
      fillOpacity: 1,
      interactive: false,
      opacity: 1,
      radius: 6,
      weight: 3,
    }).addTo(map);
    return () => {
      try {
        dot.remove?.();
      } catch {
        // The owning map may already be gone during a portal or Fast Refresh teardown.
      }
    };
  }, [leaflet, map, validLocation]);

  useEffect(() => {
    if (!map || mapRef.current !== map) return undefined;

    const syncZoom = () => {
      const nextZoom = Number(map.getZoom?.());
      if (Number.isFinite(nextZoom)) setMapZoom(nextZoom);
    };

    syncZoom();
    map.on("zoom zoomend", syncZoom);
    return () => {
      try {
        map.off("zoom zoomend", syncZoom);
      } catch {
        // The map may already be disposing while the portal closes.
      }
    };
  }, [map]);

  useEffect(() => {
    if (!map || mapRef.current !== map || !webcamsVisible) return undefined;
    const points = visibleWebcamPlaceGroups
      .filter((placeGroup) => (
        Number.isFinite(placeGroup.lat) && Number.isFinite(placeGroup.lon)
      ))
      .map((placeGroup) => [placeGroup.lat, placeGroup.lon]);
    if (!points.length) return undefined;

    const focusFrame = globalThis.requestAnimationFrame?.(() => {
      map.invalidateSize?.({ pan: false });
      // The expanded browse sheet leaves too little visible map for fitBounds.
      // Keep the current camera until the compact map viewport is restored.
      if (inline && browseExpanded) return;
      if (points.length === 1) {
        map.setView?.(points[0], Math.min(Math.max(10, mapMinZoom), mapMaxZoom), {
          animate: false,
        });
        return;
      }
      map.fitBounds?.(points, {
        animate: false,
        maxZoom: Math.min(10, mapMaxZoom),
        paddingBottomRight: [48, inline ? 210 : 170],
        paddingTopLeft: [48, inline ? 120 : 72],
      });
    });

    return () => {
      if (focusFrame !== undefined) globalThis.cancelAnimationFrame?.(focusFrame);
    };
  }, [
    browseExpanded,
    inline,
    map,
    mapMaxZoom,
    mapMinZoom,
    visibleWebcamPlaceGroups,
    webcamsVisible,
  ]);

  useEffect(() => {
    if (!map || mapRef.current !== map) return undefined;

    let projectionFrame = null;
    let disposed = false;
    const projectMarkers = () => {
      if (disposed || mapRef.current !== map) return;
      const community = { ...buildFallbackPositions(markers) };
      const webcam = { ...buildFallbackPositions(visibleMapWebcams, markers.length) };
      const webcamGroups = {
        ...buildFallbackPositions(visibleWebcamPlaceGroups, markers.length),
      };
      markers.forEach((marker) => {
        if (!Number.isFinite(marker.lat) || !Number.isFinite(marker.lon)) return;
        const point = map.latLngToContainerPoint([marker.lat, marker.lon]);
        community[marker.id] = { left: `${point.x}px`, top: `${point.y}px` };
      });
      visibleMapWebcams.forEach((camera) => {
        if (!Number.isFinite(camera.lat) || !Number.isFinite(camera.lon)) return;
        const point = map.latLngToContainerPoint([camera.lat, camera.lon]);
        webcam[camera.id] = { left: `${point.x}px`, top: `${point.y}px` };
      });
      visibleWebcamPlaceGroups.forEach((placeGroup) => {
        if (!Number.isFinite(placeGroup.lat) || !Number.isFinite(placeGroup.lon)) return;
        const point = map.latLngToContainerPoint([placeGroup.lat, placeGroup.lon]);
        webcamGroups[placeGroup.id] = { left: `${point.x}px`, top: `${point.y}px` };
      });
      setPositions({ community, webcam, webcamGroups });
    };

    const scheduleProjection = () => {
      if (disposed || projectionFrame !== null) return;
      if (typeof globalThis.requestAnimationFrame !== "function") {
        projectMarkers();
        return;
      }
      // Leaflet can emit move, zoom and resize during the same visual frame.
      projectionFrame = globalThis.requestAnimationFrame(() => {
        projectionFrame = null;
        projectMarkers();
      });
    };

    projectMarkers();
    map.on("move zoom resize", scheduleProjection);
    return () => {
      disposed = true;
      if (projectionFrame !== null) globalThis.cancelAnimationFrame?.(projectionFrame);
      try {
        map.off("move zoom resize", scheduleProjection);
      } catch {
        // The map may already be disposing while the portal closes.
      }
    };
  }, [map, markers, visibleMapWebcams, visibleWebcamPlaceGroups]);

  useEffect(() => {
    if (
      typeof onReportsViewed !== "function"
      || !map
      || mapRef.current !== map
      || !["ready", "empty"].includes(communityAvailability)
      || panelMode !== "map"
      || reportOpen
      || hasDetail
      || expandedClusterId
      || radarEnabled
    ) return undefined;

    const documentLike = globalThis.document;
    const canvas = containerRef.current;
    if (!documentLike || !canvas) return undefined;
    const modalSelector = '[aria-modal="true"], dialog[open]';
    let disposed = false;
    let pendingFrame = null;
    const usesAnimationFrame = typeof globalThis.requestAnimationFrame === "function";
    const cancelPending = () => {
      if (pendingFrame === null) return;
      if (usesAnimationFrame) globalThis.cancelAnimationFrame?.(pendingFrame);
      else globalThis.clearTimeout(pendingFrame);
      pendingFrame = null;
    };
    const isMapVisible = () => {
      if (
        disposed
        || mapRef.current !== map
        || documentLike.visibilityState !== "visible"
        || !canvas.isConnected
        || documentLike.querySelector(modalSelector)
      ) return false;
      const rect = canvas.getBoundingClientRect();
      const viewportWidth = globalThis.innerWidth || documentLike.documentElement.clientWidth;
      const viewportHeight = globalThis.innerHeight || documentLike.documentElement.clientHeight;
      return rect.width > 0 && rect.height > 0
        && rect.right > 0 && rect.bottom > 0
        && rect.left < viewportWidth && rect.top < viewportHeight;
    };
    const acknowledgeVisibleReports = () => {
      pendingFrame = null;
      if (isMapVisible()) onReportsViewed();
    };
    const scheduleAcknowledgement = () => {
      cancelPending();
      if (!isMapVisible()) return;
      // The map has been positioned and its markers projected. Tile requests
      // are independent: a slow external basemap must not keep the badge unread.
      pendingFrame = usesAnimationFrame
        ? globalThis.requestAnimationFrame(acknowledgeVisibleReports)
        : globalThis.setTimeout(acknowledgeVisibleReports, 0);
    };
    const observer = typeof globalThis.IntersectionObserver === "function"
      ? new globalThis.IntersectionObserver(scheduleAcknowledgement)
      : null;
    observer?.observe(canvas);
    // Onboarding/settings dialogs may close without changing map props. Watch
    // only modal-related DOM changes, not tile arrivals or countdown text.
    const modalObserver = typeof globalThis.MutationObserver === "function"
      ? new globalThis.MutationObserver((mutations) => {
        const modalChanged = mutations.some((mutation) => (
          mutation.type === "attributes"
          || [...mutation.addedNodes, ...mutation.removedNodes].some((node) => (
            node.matches?.(modalSelector) || node.querySelector?.(modalSelector)
          ))
        ));
        if (modalChanged) scheduleAcknowledgement();
      })
      : null;
    modalObserver?.observe(documentLike.body, {
      childList: true,
      subtree: true,
      attributes: true,
      attributeFilter: ["aria-modal", "open"],
    });
    documentLike.addEventListener("visibilitychange", scheduleAcknowledgement);
    globalThis.addEventListener?.("scroll", scheduleAcknowledgement, true);
    globalThis.addEventListener?.("resize", scheduleAcknowledgement);
    scheduleAcknowledgement();

    return () => {
      disposed = true;
      cancelPending();
      observer?.disconnect();
      modalObserver?.disconnect();
      documentLike.removeEventListener("visibilitychange", scheduleAcknowledgement);
      globalThis.removeEventListener?.("scroll", scheduleAcknowledgement, true);
      globalThis.removeEventListener?.("resize", scheduleAcknowledgement);
    };
  }, [
    communityAvailability,
    expandedClusterId,
    hasDetail,
    map,
    markers,
    onReportsViewed,
    panelMode,
    radarEnabled,
    reportOpen,
    validLocation,
  ]);

  useEffect(() => {
    const cameraId = pendingWebcamClusterFocusRef.current;
    if (!cameraId || !webcamClustersExpandedByZoom) return undefined;

    const focusFrame = globalThis.requestAnimationFrame?.(() => {
      const marker = [...(regionRef.current?.querySelectorAll?.("[data-webcam-id]") || [])]
        .find((candidate) => candidate.dataset.webcamId === cameraId);
      marker?.focus?.({ preventScroll: true });
      pendingWebcamClusterFocusRef.current = "";
    });

    return () => {
      if (focusFrame !== undefined) globalThis.cancelAnimationFrame?.(focusFrame);
    };
  }, [webcamClustersExpandedByZoom, visibleMapWebcams]);

  useEffect(() => {
    const isMissing = selectedFeature?.kind === "community"
      ? !selectedCommunity
      : selectedFeature?.kind === "history"
        ? !selectedHistory
      : selectedFeature?.kind === "webcam"
        ? !selectedWebcam
        : false;
    if (!isMissing) return undefined;

    const timeoutId = globalThis.setTimeout?.(() => {
      shareAttemptRef.current += 1;
      setShareState("idle");
      setSelectedFeature(null);
    }, 0);
    return () => globalThis.clearTimeout?.(timeoutId);
  }, [selectedCommunity, selectedFeature?.kind, selectedHistory, selectedWebcam]);

  useEffect(() => {
    if (!expandedClusterId) return undefined;
    const clusterStillExists = markers.some(
      (marker) => marker.id === expandedClusterId && marker.phenomena?.length > 1,
    );
    if (clusterStillExists) return undefined;

    const timeoutId = globalThis.setTimeout?.(() => setExpandedClusterId(null), 0);
    return () => globalThis.clearTimeout?.(timeoutId);
  }, [expandedClusterId, markers]);

  const toggleCommunityCluster = (markerId, trigger) => {
    clusterTriggerRef.current = trigger || null;
    detailTriggerRef.current = null;
    setSelectedFeature(null);
    setAlertOpen(false);
    shareAttemptRef.current += 1;
    setShareState("idle");
    setBrowseExpanded(false);
    setPanelMode("map");
    setExpandedClusterId((current) => current === markerId ? null : markerId);
  };

  const zoomToWebcamCluster = (placeGroup) => {
    if (!map || !Number.isFinite(placeGroup?.lat) || !Number.isFinite(placeGroup?.lon)) return;
    detailTriggerRef.current = null;
    setSelectedFeature(null);
    setAlertOpen(false);
    shareAttemptRef.current += 1;
    setShareState("idle");
    setExpandedClusterId(null);

    const targetZoom = Math.min(
      mapMaxZoom,
      Math.max(WEBCAM_CLUSTER_EXPANSION_ZOOM, Number(map.getZoom?.()) + 2 || 0),
    );
    pendingWebcamClusterFocusRef.current = placeGroup.cameras[0]?.id || "";
    setMapZoom(targetZoom);
    map.setView([placeGroup.lat, placeGroup.lon], targetZoom, { animate: true });
  };

  const selectFeature = (kind, id, trigger, { preservePanel = false } = {}) => {
    detailTriggerRef.current = trigger || null;
    setExpandedClusterId(null);
    shareAttemptRef.current += 1;
    setShareState("idle");
    setAlertOpen(false);
    if (!preservePanel) {
      setBrowseExpanded(false);
      setPanelMode("map");
    }
    setSelectedFeature((current) => (
      current?.kind === kind && current?.id === id ? null : { id, kind }
    ));
  };
  const selectAdjacentWebcam = (offset) => {
    const cameras = selectedWebcamPlaceGroup?.cameras || [];
    if (cameras.length < 2 || selectedWebcamIndex < 0) return;
    const nextIndex = (selectedWebcamIndex + offset + cameras.length) % cameras.length;
    setSelectedFeature({ id: cameras[nextIndex].id, kind: "webcam" });
  };
  const handleNavigationKeyDown = (event, currentId) => {
    if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
    event.preventDefault();
    const ids = webcamsEnabled
      ? ["map", "reports", "webcams"]
      : ["map", "reports"];
    const currentIndex = ids.indexOf(currentId);
    const nextIndex = event.key === "Home"
      ? 0
      : event.key === "End"
        ? ids.length - 1
        : (currentIndex + (event.key === "ArrowRight" ? 1 : -1) + ids.length) % ids.length;
    const nextTab = event.currentTarget.parentElement?.querySelector(
      `[data-territory-tab="${ids[nextIndex]}"]`,
    );
    nextTab?.click();
    nextTab?.focus();
  };
  const beginDetailSwipe = (event) => {
    const swipeSurface = event.target.closest?.(
      ".mf-live-community-map__detail-grabber, .mf-live-community-map__detail-heading",
    );
    if (
      (event.pointerType && !["pen", "touch"].includes(event.pointerType))
      || event.currentTarget.scrollTop > 0
      || !swipeSurface
      || event.target.closest?.("a, button, input, select, textarea")
    ) return;

    detailSwipeRef.current = {
      pointerId: event.pointerId,
      startX: event.clientX,
      startY: event.clientY,
    };
    event.currentTarget.setPointerCapture?.(event.pointerId);
  };
  const finishDetailSwipe = (event) => {
    const swipe = detailSwipeRef.current;
    detailSwipeRef.current = null;
    if (!swipe || swipe.pointerId !== event.pointerId) return;
    if (event.currentTarget.hasPointerCapture?.(event.pointerId)) {
      event.currentTarget.releasePointerCapture?.(event.pointerId);
    }
    const deltaX = Math.abs(event.clientX - swipe.startX);
    const deltaY = event.clientY - swipe.startY;
    if (deltaY >= 72 && deltaY > deltaX * 1.25) closeSelectedFeature();
  };
  const beginWebcamSwipe = (event) => {
    if (
      (event.pointerType && !["pen", "touch"].includes(event.pointerType))
      || event.target.closest?.("a, button, input, select, textarea")
      || (selectedWebcamPlaceGroup?.cameras.length || 0) < 2
    ) return;

    webcamSwipeRef.current = {
      pointerId: event.pointerId,
      startX: event.clientX,
      startY: event.clientY,
    };
    event.currentTarget.setPointerCapture?.(event.pointerId);
  };
  const finishWebcamSwipe = (event) => {
    const swipe = webcamSwipeRef.current;
    webcamSwipeRef.current = null;
    if (!swipe || swipe.pointerId !== event.pointerId) return;
    if (event.currentTarget.hasPointerCapture?.(event.pointerId)) {
      event.currentTarget.releasePointerCapture?.(event.pointerId);
    }

    const deltaX = event.clientX - swipe.startX;
    const deltaY = event.clientY - swipe.startY;
    if (Math.abs(deltaX) < 56 || Math.abs(deltaX) <= Math.abs(deltaY) * 1.25) return;
    selectAdjacentWebcam(deltaX < 0 ? 1 : -1);
  };
  const beginDockSwipe = (event) => {
    if (!canExpandBrowse || panelMode === "map") return;
    dockSwipeHandledRef.current = false;
    dockSwipeRef.current = {
      pointerId: event.pointerId,
      startX: event.clientX,
      startY: event.clientY,
    };
    event.currentTarget.setPointerCapture?.(event.pointerId);
  };
  const finishDockSwipe = (event) => {
    const swipe = dockSwipeRef.current;
    dockSwipeRef.current = null;
    if (!swipe || swipe.pointerId !== event.pointerId) return;
    if (event.currentTarget.hasPointerCapture?.(event.pointerId)) {
      event.currentTarget.releasePointerCapture?.(event.pointerId);
    }
    const deltaX = Math.abs(event.clientX - swipe.startX);
    const deltaY = event.clientY - swipe.startY;
    if (Math.abs(deltaY) < 48 || Math.abs(deltaY) <= deltaX * 1.2) return;
    dockSwipeHandledRef.current = true;
    setBrowseExpanded(deltaY < 0);
  };
  const centerMap = () => {
    if (!map || !validLocation) return;
    closeExpandedCluster({ restoreFocus: false });
    if (gpsPulseFrameRef.current !== null) {
      globalThis.cancelAnimationFrame?.(gpsPulseFrameRef.current);
    }
    if (gpsPulseTimeoutRef.current !== null) {
      globalThis.clearTimeout?.(gpsPulseTimeoutRef.current);
    }
    setGpsPulse(false);
    gpsPulseFrameRef.current = globalThis.requestAnimationFrame?.(() => {
      setGpsPulse(true);
      gpsPulseTimeoutRef.current = globalThis.setTimeout?.(() => {
        setGpsPulse(false);
        gpsPulseTimeoutRef.current = null;
      }, 460);
      gpsPulseFrameRef.current = null;
    }) ?? null;
    map.setView(
      [validLocation.lat, validLocation.lon],
      Math.max(10, Number(map.getZoom?.()) || 10),
      { animate: true },
    );
  };
  const handleConfirmation = async (groupId, vote, trigger) => {
    if (!groupId || !onConfirm || confirmationStatuses[groupId] === "loading") return;
    await onConfirm(groupId, vote, trigger);
  };
  const shareSelectedCommunity = async () => {
    if (!selectedCommunity || shareState === "loading") return;

    const attempt = shareAttemptRef.current + 1;
    shareAttemptRef.current = attempt;
    setShareState("loading");
    const payload = buildCommunitySharePayload({
      groupId: selectedPrimaryPhenomenon?.groupId || selectedCommunity.groupId,
      legalNote: communityCopy.reportLegalCompactNote,
      place: selectedCommunity.place,
      timeLabel: selectedPrimaryPhenomenon?.timeLabel,
      typeLabel: selectedPrimaryPhenomenon?.typeLabel,
    });
    const result = await shareCommunityPayload(payload, {
      nativeDialogTitle: copy.shareDialogTitle,
      preferNativeShare: isAndroidCapacitorRuntime(),
      preferWebShare: isAndroidCapacitorRuntime(),
    });
    if (shareAttemptRef.current !== attempt) return;

    if (result?.ok) setShareState(result.method === "clipboard" ? "copied" : "shared");
    else setShareState(result?.reason === "cancelled" ? "idle" : "unavailable");
  };

  return (
    <div
      aria-label={copy.mapAria}
      className={[
        "mf-live-community-map",
        "mf-territory-map",
        inline ? "mf-territory-map--inline" : "mf-live-community-map--immersive",
        inline && panelMode !== "map" ? "mf-territory-map--panel-open" : "",
        recentListEnabled ? "mf-territory-map--recent-list" : "",
        inline && panelMode !== "map" && browseExpanded
          ? "mf-territory-map--panel-expanded"
          : "",
        inline && panelMode === "webcams" ? "mf-territory-map--webcams-open" : "",
        inline
          && panelMode === "reports"
          && !browseExpanded
          && visibleBrowseItems.length === 0
          && !recentListEnabled
          ? "mf-territory-map--reports-empty"
          : "",
        inline && radarEnabled && panelMode === "map"
          ? "mf-territory-map--radar-active"
          : "",
        expandedClusterId ? "mf-territory-map--cluster-open" : "",
      ].filter(Boolean).join(" ")}
      ref={regionRef}
      role="region"
      tabIndex={-1}
    >
      <div aria-hidden="true" className="mf-live-community-map__canvas" ref={containerRef} />

      {panelMode !== "webcams" ? (
      <div aria-label={copy.reportsLayer} className="mf-live-community-map__markers">
        {expandedClusterId ? (
          <button
            aria-label={copy.close}
            className="mf-territory-map__cluster-backdrop"
            onClick={(event) => {
              event.stopPropagation();
              closeExpandedCluster();
            }}
            tabIndex={-1}
            type="button"
          />
        ) : null}
        {markers.map((marker) => {
          const markerPosition = positions.community[marker.id]
            || fallbackPositions.community[marker.id]
            || {};
          const clusterPhenomena = marker.phenomena?.length > 1
            ? sortClusterPhenomena(marker.phenomena)
            : [];
          const isCluster = clusterPhenomena.length > 1;
          const isExpanded = isCluster && expandedClusterId === marker.id;
          const Icon = isCluster
            ? Radio
            : PILOT_LIVE_REPORT_ICONS[marker.typeId] || MapPin;

          if (isCluster) {
            const clusterFanId = `${browsePanelId}-cluster-${String(marker.id)
              .replace(/[^a-zA-Z0-9_-]/g, "-")}`;
            return (
              <div
                className={`mf-territory-map__cluster ${isExpanded ? "is-open" : ""}`.trim()}
                key={marker.id}
                style={markerPosition}
              >
                <button
                  aria-controls={clusterFanId}
                  aria-expanded={isExpanded}
                  aria-label={isExpanded
                    ? `${copy.close} · ${getCommunityMarkerLabel(marker)}`
                    : getCommunityMarkerLabel(marker)}
                  className={`mf-live-community-map__marker mf-live-community-map__marker--multiple mf-territory-map__cluster-toggle ${isExpanded ? "is-open" : ""}`.trim()}
                  onClick={(event) => {
                    event.stopPropagation();
                    toggleCommunityCluster(marker.id, event.currentTarget);
                  }}
                  ref={isExpanded ? clusterTriggerRef : undefined}
                  type="button"
                >
                  {isExpanded
                    ? <X aria-hidden="true" size={21} strokeWidth={2.5} />
                    : <Icon aria-hidden="true" size={22} strokeWidth={2.45} />}
                  {!isExpanded ? <span>{clusterPhenomena.length}</span> : null}
                </button>

                {isExpanded ? (
                  <div
                    aria-label={getCommunityMarkerLabel(marker)}
                    className="mf-territory-map__cluster-fan"
                    id={clusterFanId}
                    role="group"
                  >
                    {clusterPhenomena.map((phenomenon, index) => {
                      const PhenomenonIcon = PILOT_LIVE_REPORT_ICONS[phenomenon.typeId]
                        || MapPin;
                      const fanPosition = getClusterFanPosition(
                        index,
                        clusterPhenomena.length,
                      );
                      const phenomenonId = phenomenon.id || phenomenon.groupId;
                      return (
                        <span
                          className="mf-territory-map__cluster-arm"
                          key={phenomenon.groupId || phenomenon.id}
                          style={{
                            "--mf-cluster-angle": `${fanPosition.angle}deg`,
                            "--mf-cluster-delay": `${index * 34}ms`,
                            "--mf-cluster-distance": `${fanPosition.radius}px`,
                            "--mf-cluster-x": `${fanPosition.x}px`,
                            "--mf-cluster-y": `${fanPosition.y}px`,
                          }}
                        >
                          <span
                            aria-hidden="true"
                            className="mf-territory-map__cluster-leg"
                          />
                          <button
                            aria-label={getCommunityMarkerLabel(phenomenon)}
                            className={`mf-live-community-map__marker mf-live-community-map__marker--${phenomenon.typeId} mf-territory-map__cluster-petal`}
                            onClick={(event) => {
                              event.stopPropagation();
                              selectFeature(
                                "community",
                                phenomenonId,
                                clusterTriggerRef.current || event.currentTarget,
                              );
                            }}
                            type="button"
                          >
                            <PhenomenonIcon aria-hidden="true" size={21} strokeWidth={2.45} />
                            {phenomenon.count > 1 ? <span>{phenomenon.count}</span> : null}
                          </button>
                        </span>
                      );
                    })}
                  </div>
                ) : null}
              </div>
            );
          }

          return (
            <button
              aria-label={getCommunityMarkerLabel(marker)}
              aria-pressed={selectedCommunity?.id === marker.id}
              className={`mf-live-community-map__marker mf-live-community-map__marker--${marker.typeId}`}
              key={marker.id}
              onClick={(event) => {
                event.stopPropagation();
                selectFeature("community", marker.id, event.currentTarget);
              }}
              style={markerPosition}
              type="button"
            >
              <Icon aria-hidden="true" size={22} strokeWidth={2.45} />
              {marker.count > 1 ? <span>{marker.count}</span> : null}
            </button>
          );
        })}
      </div>
      ) : null}

      {webcamsVisible ? (
        <div aria-label={copy.webcamsLayer} className="mf-territory-map__webcam-markers">
          {visibleWebcamPlaceGroups.map((placeGroup) => {
            const showCluster = placeGroup.isCluster && !webcamClustersExpandedByZoom;
            const groupPosition = positions.webcamGroups?.[placeGroup.id]
              || fallbackPositions.webcamGroups[placeGroup.id]
              || {};

            if (!showCluster) {
              return placeGroup.cameras.map((camera) => (
                <button
                  aria-label={getWebcamMarkerLabel(copy, camera)}
                  aria-pressed={selectedWebcam?.id === camera.id}
                  className={`mf-territory-map__webcam-marker ${highlightedWebcamId === camera.id ? "is-highlighted" : ""} ${isWebcamHealthNotOk(camera) ? "is-health-not-ok" : ""}`.trim()}
                  data-webcam-id={camera.id}
                  key={camera.id}
                  onClick={(event) => {
                    event.stopPropagation();
                    selectFeature("webcam", camera.id, event.currentTarget, { preservePanel: true });
                  }}
                  style={getWebcamMarkerStyle(
                    positions.webcam[camera.id] || fallbackPositions.webcam[camera.id] || {},
                    colocatedWebcamOffsets[camera.id],
                  )}
                  type="button"
                >
                  <Camera aria-hidden="true" size={18} strokeWidth={2.35} />
                </button>
              ));
            }

            const clusterLabel = copy.webcamClusterLabel
              .replace("{place}", placeGroup.label)
              .replace("{count}", String(placeGroup.count));
            const clusterHealthLabels = [...new Set(placeGroup.cameras
              .filter(isWebcamHealthNotOk)
              .map((camera) => camera.health?.label)
              .filter(Boolean))];
            const clusterHasHealthIssue = clusterHealthLabels.length > 0;

            return (
              <div
                className="mf-territory-map__webcam-cluster"
                key={placeGroup.id}
                style={groupPosition}
              >
                <button
                  aria-label={[clusterLabel, ...clusterHealthLabels].join(" · ")}
                  className={`mf-territory-map__webcam-marker mf-territory-map__webcam-cluster-toggle ${placeGroup.cameras.some((camera) => highlightedWebcamId === camera.id) ? "is-highlighted" : ""} ${clusterHasHealthIssue ? "is-health-not-ok" : ""}`.trim()}
                  onClick={(event) => {
                    event.stopPropagation();
                    zoomToWebcamCluster(placeGroup);
                  }}
                  type="button"
                >
                  <Camera aria-hidden="true" size={19} strokeWidth={2.35} />
                  <span className="mf-territory-map__webcam-cluster-count">
                    {placeGroup.count}
                  </span>
                </button>
              </div>
            );
          })}
        </div>
      ) : null}

      <div aria-label={copy.mapControls} className="mf-territory-map__floating-controls">
        {hasOfficialAlert ? (
          <button
            aria-controls={alertDialogId}
            aria-expanded={alertOpen}
            aria-haspopup="dialog"
            aria-label={`${copy.alert}: ${officialAlert.label}`}
            className="mf-territory-map__control mf-territory-map__control--icon mf-territory-map__control--alert"
            data-alert-tone={officialAlertTone}
            onClick={(event) => {
              event.stopPropagation();
              detailTriggerRef.current = event.currentTarget;
              setSelectedFeature(null);
              setExpandedClusterId(null);
              setBrowseExpanded(false);
              setPanelMode("map");
              shareAttemptRef.current += 1;
              setShareState("idle");
              setAlertOpen(true);
            }}
            title={`${copy.alert}: ${officialAlert.label}`}
            type="button"
          >
            <TriangleAlert aria-hidden="true" size={22} strokeWidth={2.4} />
          </button>
        ) : null}
        <button
          aria-controls={radarOverlayId}
          aria-label={radarModel?.available ? copy.radar : copy.radarUnavailable}
          aria-pressed={radarEnabled}
          className="mf-territory-map__control mf-territory-map__control--icon mf-territory-map__control--radar"
          disabled={!radarModel?.available}
          onClick={() => {
            if (!radarEnabled) {
              closeSelectedFeature({ restoreFocus: false });
              setHighlightedWebcamId(null);
              setBrowseExpanded(false);
              setPanelMode("map");
            }
            closeExpandedCluster({ restoreFocus: false });
            setRadarEnabled((current) => !current);
          }}
          title={radarModel?.available ? copy.radar : copy.radarUnavailable}
          type="button"
        >
          <SatelliteDish aria-hidden="true" size={21} strokeWidth={2.25} />
        </button>
        {webcamsEnabled ? (
          <button
            aria-controls={browsePanelId}
            aria-expanded={panelMode === "webcams"}
            aria-label={`${copy.webcamsLayer}${mapWebcams.length ? ` · ${mapWebcams.length}` : ""}`}
            className={`mf-territory-map__control mf-territory-map__control--icon mf-territory-map__control--webcam ${panelMode === "webcams" ? "is-active" : ""}`.trim()}
            onClick={(event) => {
              event.stopPropagation();
              const nextWebcamOpen = panelMode !== "webcams";
              closeSelectedFeature({ restoreFocus: false });
              closeExpandedCluster({ restoreFocus: false });
              setHighlightedWebcamId(null);
              setBrowseExpanded(false);
              if (nextWebcamOpen) setRadarEnabled(false);
              setPanelMode(nextWebcamOpen ? "webcams" : "map");
            }}
            title={copy.webcamsLayer}
            type="button"
          >
            <Camera aria-hidden="true" size={21} strokeWidth={2.25} />
          </button>
        ) : null}
        <button
          aria-label={copy.center}
          className={`mf-territory-map__control mf-territory-map__control--icon mf-territory-map__control--gps ${gpsPulse ? "is-pulsing" : ""}`.trim()}
          disabled={!validLocation}
          onClick={centerMap}
          title={copy.center}
          type="button"
        >
          <LocateFixed aria-hidden="true" size={22} strokeWidth={2.25} />
        </button>
      </div>

      {webcamsVisible && !visibleMapWebcams.length ? (
        <p className="mf-territory-map__service-note" role="status">
          <Camera aria-hidden="true" size={17} strokeWidth={2.2} />
          {copy.noApprovedWebcams}
        </p>
      ) : null}

      {sharedReportUnavailable ? (
        <p
          className="mf-territory-map__service-note mf-territory-map__service-note--empty"
          role="status"
        >
          <Radio aria-hidden="true" size={17} strokeWidth={2.2} />
          {copy.sharedReportUnavailable}
        </p>
      ) : !markers.length && !webcamsVisible && !radarEnabled ? (
        <p
          className={`mf-territory-map__service-note mf-territory-map__service-note--${communityAvailability}`}
          role="status"
        >
          <Radio aria-hidden="true" size={17} strokeWidth={2.2} />
          {getCommunityAvailabilityMessage(
            communityAvailability,
            communityCopy,
            copy.noReports,
          )}
        </p>
      ) : null}

      <div
        aria-hidden={hasDetail ? "true" : undefined}
        className={[
          "mf-territory-map__dock",
          panelMode !== "map" ? "mf-territory-map__dock--open" : "",
          panelMode !== "map" && browseExpanded ? "mf-territory-map__dock--expanded" : "",
          radarEnabled && panelMode === "map" ? "mf-territory-map__dock--radar" : "",
        ].filter(Boolean).join(" ")}
        inert={hasDetail ? true : undefined}
      >
        {dockBrowseHandleEnabled ? (
          <button
            aria-controls={browseListId}
            aria-expanded={browseExpanded}
            aria-label={browseExpanded
              ? communityCopy.territoryShowLess
              : communityCopy.territoryViewAll}
            className="mf-territory-map__dock-grabber is-interactive"
            disabled={!canExpandBrowse}
            onClick={() => {
              if (dockSwipeHandledRef.current) {
                dockSwipeHandledRef.current = false;
                return;
              }
              setBrowseExpanded((current) => !current);
            }}
            onPointerCancel={() => {
              dockSwipeRef.current = null;
            }}
            onPointerDown={beginDockSwipe}
            onPointerUp={finishDockSwipe}
            type="button"
          />
        ) : (
          <span aria-hidden="true" className="mf-territory-map__dock-grabber" />
        )}
        {radarEnabled ? (
          <TerritoryRadarOverlay
            enabled
            id={radarOverlayId}
            leaflet={leaflet}
            map={map}
            radarModel={radarModel}
          />
        ) : null}
        <nav
          aria-label={copy.mapAria}
          className="mf-territory-map__navigation"
          role="tablist"
          style={{
            gridTemplateColumns: `repeat(${webcamsEnabled ? 3 : 2}, minmax(0, 1fr))`,
          }}
        >
          {[
            { id: "map", label: copy.map },
            { id: "reports", label: copy.reports },
            ...(webcamsEnabled ? [{ id: "webcams", label: copy.webcams }] : []),
          ].map(({ id, label }) => (
            <button
              aria-controls={id === "map" ? undefined : browsePanelId}
              aria-selected={panelMode === id}
              className={panelMode === id ? "is-active" : undefined}
              data-territory-tab={id}
              key={id}
              onClick={() => {
                closeSelectedFeature({ restoreFocus: false });
                closeExpandedCluster({ restoreFocus: false });
                setHighlightedWebcamId(null);
                setBrowseExpanded(false);
                if (id !== "map") setRadarEnabled(false);
                setPanelMode(id);
              }}
              onKeyDown={(event) => handleNavigationKeyDown(event, id)}
              role="tab"
              tabIndex={panelMode === id ? 0 : -1}
              type="button"
            >
              <span>{label}</span>
            </button>
          ))}
        </nav>

        {panelMode !== "map" ? (
          <section
            aria-label={panelMode === "reports"
              ? communityCopy.territoryRecentReportsTitle
              : communityCopy.territoryWebcamsTitle}
            className={[
              "mf-territory-map__browse-sheet",
              `mf-territory-map__browse-sheet--${browseExpanded ? "expanded" : "preview"}`,
              !browseExpanded
                ? "mf-territory-map__browse-sheet--compact"
                : "",
            ].filter(Boolean).join(" ")}
            id={browsePanelId}
            role="tabpanel"
          >
            <header>
              <span>
                {recentListEnabled && panelMode === "reports" ? (
                  <button className="mf-recent-list-toggle" type="button"
                    aria-controls={browseListId} aria-expanded={browseExpanded}
                    onClick={() => setBrowseExpanded((current) => !current)}>
                    <strong>{communityCopy.recentTitle}</strong>
                    {browseExpanded ? <ChevronUp aria-hidden="true" size={16} />
                      : <ChevronRight aria-hidden="true" size={16} />}
                  </button>
                ) : <strong>{panelMode === "reports"
                  ? showHistory ? communityCopy.historyTitle : communityCopy.territoryRecentReportsTitle
                  : communityCopy.territoryWebcamsTitle}</strong>}
              </span>
              {recentListEnabled && panelMode === "reports" ? <small>{communityCopy.recentWindow}</small> : null}
              {canExpandBrowse && !(recentListEnabled && panelMode === "reports") ? (
                <button
                  aria-controls={browseListId}
                  aria-expanded={browseExpanded}
                  className="mf-territory-map__browse-toggle"
                  onClick={() => setBrowseExpanded((current) => !current)}
                  type="button"
                >
                  {browseExpanded
                    ? communityCopy.territoryShowLess
                    : communityCopy.territoryViewAll}
                  {browseExpanded
                    ? <ChevronUp aria-hidden="true" size={16} />
                    : <ChevronRight aria-hidden="true" size={16} />}
                </button>
              ) : null}
            </header>

            {panelMode === "reports" && isLocalCommunityPilot() && !recentListEnabled ? (
              <div className="mf-territory-map__webcam-groups mf-community-history-navigation" aria-label={communityCopy.historyNavigation}>
                <button type="button" aria-pressed={!showHistory} className={!showHistory ? "is-active" : undefined}
                  onClick={() => setShowHistory(false)}>{communityCopy.territoryRecentReportsTitle}</button>
                <button type="button" aria-pressed={showHistory} className={showHistory ? "is-active" : undefined}
                  onClick={() => { setShowHistory(true); setBrowseExpanded(true); }}>{communityCopy.historyTitle}</button>
              </div>
            ) : null}
            {panelMode === "webcams" && availableWebcamGroups.length ? (
              <div
                aria-label={communityCopy.webcamAreaLabel}
                className="mf-territory-map__webcam-groups"
              >
                {availableWebcamGroups.map((group) => (
                  <button
                    aria-pressed={activeWebcamGroup?.id === group.id}
                    className={activeWebcamGroup?.id === group.id ? "is-active" : undefined}
                    key={group.id}
                    onClick={() => {
                      setActiveWebcamGroupId(group.id);
                      setHighlightedWebcamId(null);
                    }}
                    type="button"
                  >
                    <span>{group.label}</span>
                    <em>{group.cameras.length}</em>
                  </button>
                ))}
              </div>
            ) : null}

            <div
              className="mf-territory-map__browse-list"
              hidden={compactWebcamBrowse}
              id={browseListId}
              onScroll={recentListEnabled && panelMode === "reports" && browseExpanded ? (event) => {
                const list = event.currentTarget;
                if (list.scrollHeight - list.scrollTop - list.clientHeight < 100) recentHistory.loadMore();
              } : undefined}
            >
              {panelMode === "reports" && showHistory ? (
                <CommunityHistory key={`${location?.istatCode || ""}:${location?.lat}:${location?.lon}`}
                  location={location} copy={communityCopy} language={language} />
              ) : compactWebcamBrowse ? null : panelMode === "reports" ? (
                visibleBrowseItems.length ? visibleBrowseItems.map((report) => {
                  if (report.recentKind === "history") return <CommunityRecentHistoryRow
                    key={report.recentKey} report={report} copy={communityCopy} language={language} now={recentHistory.now}
                    onOpen={(event) => selectFeature("history", report.id, event.currentTarget, { preservePanel: true })} />;
                  const Icon = PILOT_LIVE_REPORT_ICONS[report.typeId] || MapPin;
                  const denialLabel = getCommunityDenialLabel(
                    communityCopy,
                    report.confirmations,
                  );
                  const withdrawalLabel = getCommunityMapWithdrawalLabel(
                    communityCopy,
                    report,
                  );
                  return (
                    <button
                      className={`mf-territory-map__browse-item mf-territory-map__browse-item--${report.typeId}`}
                      key={report.id}
                      onClick={(event) => selectFeature(
                        "community",
                        report.id,
                        event.currentTarget,
                        { preservePanel: true },
                      )}
                      type="button"
                    >
                      <span aria-hidden="true"><Icon size={18} strokeWidth={2.35} /></span>
                      <span>
                        <strong>{report.typeLabel}</strong>
                        <small>{[
                          report.place,
                          report.timeLabel,
                          report.countLabel,
                        ].filter(Boolean).join(" · ")}</small>
                        {recentListEnabled ? <small>{communityCopy.recentStates.active}</small> : null}
                        {!recentListEnabled && (denialLabel || withdrawalLabel) ? (
                          <small className="mf-territory-map__browse-denial-status">
                            {[denialLabel, withdrawalLabel].filter(Boolean).join(" · ")}
                          </small>
                        ) : null}
                      </span>
                      <ChevronRight aria-hidden="true" size={17} />
                    </button>
                  );
                }) : recentListEnabled ? null : (
                  <p>{getCommunityAvailabilityMessage(
                    communityAvailability,
                    communityCopy,
                    copy.noReports,
                  )}</p>
                )
              ) : visibleBrowseItems.length ? visibleBrowseItems.map((placeGroup) => {
                const camera = placeGroup.cameras[0];
                const selected = placeGroup.cameras.some(
                  (candidate) => candidate.id === selectedWebcam?.id,
                );
                const groupLabel = placeGroup.isCluster
                  ? copy.webcamClusterLabel
                    .replace("{place}", placeGroup.label)
                    .replace("{count}", String(placeGroup.count))
                  : camera.name;

                return (
                  <button
                    aria-pressed={selected}
                    className="mf-territory-map__browse-item mf-territory-map__browse-item--webcam"
                    key={placeGroup.id}
                    onBlur={() => setHighlightedWebcamId(null)}
                    onFocus={() => setHighlightedWebcamId(camera.id)}
                    onClick={(event) => selectFeature(
                      "webcam",
                      camera.id,
                      event.currentTarget,
                      { preservePanel: true },
                    )}
                    onPointerEnter={() => setHighlightedWebcamId(camera.id)}
                    onPointerLeave={() => setHighlightedWebcamId(null)}
                    type="button"
                  >
                    <WebcamBrowseThumbnail
                      camera={camera}
                      key={`${camera.id}:${camera.imageUrl || ""}:${camera.fallbackImageUrl || ""}`}
                    />
                    <span>
                      <strong>{groupLabel}</strong>
                      <small>{[
                        placeGroup.isCluster ? getCameraLocation(camera) : "",
                        camera.distanceLabel,
                      ].filter(Boolean).join(" · ")}</small>
                    </span>
                    <ChevronRight aria-hidden="true" size={17} />
                  </button>
                );
              }) : <p>{communityCopy.webcamUnavailableBody}</p>}
              {recentListEnabled && panelMode === "reports" ? <>
                {recentHistory.status === "loading" && (!visibleBrowseItems.length || browseExpanded)
                  ? <p role="status">{communityCopy.historyLoading}</p> : null}
                {recentHistory.status === "error" ? <button className="mf-recent-list-retry" type="button"
                  onClick={recentHistory.retry}>{communityCopy.historyError}</button> : null}
                {recentHistory.status === "ready" && !visibleBrowseItems.length
                  ? <p>{communityCopy.historyEmpty}</p> : null}
                {browseExpanded && recentHistory.status === "ready" && recentHistory.next
                  ? <CommunityRecentPagination loadMore={recentHistory.loadMore} /> : null}
                {browseExpanded && recentHistory.status === "ready" && !recentHistory.next && visibleBrowseItems.length
                  ? <p>{communityCopy.recentEnd}</p> : null}
              </> : null}
            </div>
          </section>
        ) : null}

        {inline && panelMode !== "webcams" && !(radarEnabled && panelMode === "map") ? (
          <button
            aria-controls={reportDialogId}
            aria-expanded={reportOpen}
            aria-haspopup="dialog"
            className="mf-territory-map__report-action"
            disabled={!onReportRequest}
            onClick={() => {
              closeSelectedFeature({ restoreFocus: false });
              closeExpandedCluster({ restoreFocus: false });
              onReportRequest?.();
            }}
            type="button"
          >
            <Send aria-hidden="true" size={18} strokeWidth={2.4} />
            {communityCopy.reportObserveCompactCta}
          </button>
        ) : null}
        {inline
          && panelMode !== "webcams"
          && !onReportRequest
          && reportUnavailableText ? (
            <p className="mf-territory-map__report-unavailable" role="status">
              {reportUnavailableText}
            </p>
          ) : null}
      </div>

      {alertOpen && hasOfficialAlert ? (
        <div className="mf-territory-map__detail-layer">
          <section
            aria-label={`${copy.alert} · ${officialAlert.label}`}
            aria-modal="true"
            className="mf-live-community-map__detail mf-territory-map__alert-detail"
            id={alertDialogId}
            ref={detailRef}
            role="dialog"
            tabIndex={-1}
          >
            <header className="mf-territory-map__alert-heading">
              <span
                aria-hidden="true"
                className="mf-territory-map__alert-icon"
                data-alert-tone={officialAlertTone}
              >
                <TriangleAlert size={24} strokeWidth={2.4} />
              </span>
              <div>
                <small>{copy.alert}</small>
                <strong>{officialAlert.label}</strong>
              </div>
              <AppIconButton
                ariaLabel={copy.close}
                className="mf-territory-map__alert-close"
                icon={X}
                onClick={() => closeSelectedFeature()}
              />
            </header>

            <dl className="mf-territory-map__alert-facts">
              <div>
                <dt>{copy.alertLevel}</dt>
                <dd>{officialAlert.label}</dd>
              </div>
              {officialAlert.validityLabel ? (
                <div>
                  <dt>{copy.alertValidity}</dt>
                  <dd>{officialAlert.validityLabel}</dd>
                </div>
              ) : null}
              <div>
                <dt>{copy.alertArea}</dt>
                <dd>{officialAlertArea}</dd>
              </div>
              {officialAlertRisk ? (
                <div>
                  <dt>{copy.alertRisk}</dt>
                  <dd>{officialAlertRisk}</dd>
                </div>
              ) : null}
              <div>
                <dt>{copy.alertSource}</dt>
                <dd>{officialAlertSource}</dd>
              </div>
            </dl>

            {typeof onOfficialAlertOpen === "function" ? (
              <button
                className="mf-territory-map__alert-details"
                onClick={() => {
                  closeSelectedFeature({ restoreFocus: false });
                  onOfficialAlertOpen();
                }}
                type="button"
              >
                <span>{copy.alertDetails}</span>
                <ChevronRight aria-hidden="true" size={18} strokeWidth={2.4} />
              </button>
            ) : null}
          </section>
        </div>
      ) : null}

      {selectedHistory ? <CommunityHistoryDetail report={selectedHistory} copy={communityCopy}
        language={language} now={recentHistory.now} detailRef={detailRef} onClose={() => closeSelectedFeature()} /> : null}

      {selectedCommunity ? (
        <div className={inline ? "mf-territory-map__detail-layer" : undefined}>
          <div
            aria-label={[
              selectedCommunity.typeLabel,
              selectedCommunity.place,
              selectedCommunityStatusLabel,
            ].filter(Boolean).join(" · ")}
            aria-modal={inline ? "true" : undefined}
            className={`mf-live-community-map__detail ${inline ? "mf-territory-map__report-detail" : ""} ${inline && pilotPresentation ? "mf-territory-map__report-detail--pilot" : ""}`.trim()}
            onPointerCancel={() => { detailSwipeRef.current = null; }}
            onPointerDown={inline ? undefined : beginDetailSwipe}
            onPointerUp={inline ? undefined : finishDetailSwipe}
            ref={detailRef}
            role="dialog"
            tabIndex={-1}
          >
            {!inline ? <span aria-hidden="true" className="mf-live-community-map__detail-grabber" /> : null}
            {inline ? (
              <>
                <div className="mf-territory-map__report-primary-heading">
                  <span
                    aria-hidden="true"
                    className={`mf-territory-map__report-type-icon mf-territory-map__report-type-icon--${selectedCommunity.typeId}`}
                  >
                    <SelectedCommunityIcon size={23} strokeWidth={2.4} />
                  </span>
                  <span className="mf-territory-map__report-heading-copy">
                    <strong>{selectedCommunity.typeLabel}</strong>
                    <small>
                      {[
                        selectedCommunity.place,
                        selectedCommunity.timeLabel
                          ? `${copy.reported} ${selectedCommunity.timeLabel}`
                          : "",
                      ].filter(Boolean).join(" · ")}
                    </small>
                  </span>
                  <span className="mf-territory-map__report-heading-actions">
                    <AppIconButton
                      aria-busy={shareState === "loading"}
                      ariaLabel={shareButtonLabel}
                      className={`mf-territory-map__report-heading-button mf-territory-map__report-share mf-territory-map__share-action ${shareSucceeded ? "is-success" : ""} ${shareState === "unavailable" ? "is-error" : ""}`.trim()}
                      disabled={shareState === "loading"}
                      icon={ShareIcon}
                      onClick={shareSelectedCommunity}
                    />
                    <AppIconButton
                      ariaLabel={communityCopy.liveMapDetailClose}
                      className="mf-territory-map__report-heading-button mf-territory-map__report-close"
                      icon={X}
                      onClick={() => closeSelectedFeature()}
                    />
                    <span
                      aria-atomic="true"
                      aria-live="polite"
                      className="mf-territory-map__share-status"
                      role="status"
                    >
                      {shareAnnouncement}
                    </span>
                  </span>
                </div>
                {!pilotPresentation || selectedCommunityIdentityPreview.identities.length > 0 ? (
                <p aria-live="polite" className={`mf-territory-map__report-community-status${pilotPresentation ? " mf-territory-map__report-community-status--identity-only" : ""}`}>
                  {!pilotPresentation ? (
                    <>
                      <span aria-hidden="true" className="mf-territory-map__report-community-status-dot" />
                      <span className="mf-territory-map__report-community-status-main">
                        <strong>{selectedCommunityStatusLabel}</strong>
                        <span aria-hidden="true">•</span>
                        <span>{copy.reportScope}</span>
                      </span>
                    </>
                  ) : null}
                  {selectedCommunityIdentityPreview.identities.length ? (
                    <CommunitySentinelCluster
                      compact={pilotPresentation}
                      copy={copy}
                      identities={selectedCommunityIdentityPreview.identities}
                      key={selectedPrimaryPhenomenon?.groupId || selectedCommunity.id}
                    />
                  ) : null}
                </p>
                ) : null}
              </>
            ) : (
              <div className="mf-live-community-map__detail-heading">
                <div>
                  <strong>{selectedCommunity.place}</strong>
                  <span>{selectedCommunity.countLabel}</span>
                </div>
                <AppIconButton ariaLabel={communityCopy.liveMapDetailClose} icon={X} onClick={() => closeSelectedFeature()} />
              </div>
            )}
            <div className="mf-live-community-map__phenomena">
              {selectedPhenomena.map((phenomenon) => {
                const status = confirmationStatuses[phenomenon.groupId] || "idle";
                const vote = getCommunityVote(personalState, phenomenon.groupId, isLocalCommunityPilot() ? phenomenon.reportIds || [] : undefined);
                const storedOwnReport = getOwnCommunityReport(personalState, phenomenon.groupId);
                const ownReport = storedOwnReport || (
                  inferredOwnGroupIds.includes(phenomenon.groupId)
                    ? { expiresAt: phenomenon.expiresAt }
                    : null
                );
                return (
                  <CommunityMapPhenomenon
                    compactManagement={inline && pilotPresentation}
                    compactVoting={inline && pilotPresentation}
                    confirmationCounts={confirmationCountsByGroup[phenomenon.groupId]}
                    confirmationStatus={status}
                    confirmationError={confirmationMessages[phenomenon.groupId]}
                    confirmationVote={vote}
                    copy={communityCopy}
                    hideConfirmationDetails={inline}
                    hideConfirmationQuestion={inline}
                    hideSummary={inline && selectedPhenomena.length === 1}
                    key={`${phenomenon.groupId || phenomenon.id}:${storedOwnReport?.reportId || "guest"}`}
                    onConfirm={!ownReport && onConfirm ? handleConfirmation : undefined}
                    onEdit={storedOwnReport?.reportId && onEdit ? (report) => { closeSelectedFeature({ restoreFocus: false }); onEdit(report); } : undefined}
                    onUpdate={storedOwnReport?.reportId && onUpdate ? updateOwnReport : undefined}
                    onWithdraw={storedOwnReport?.reportId && onWithdraw ? withdrawOwnReport : undefined}
                    onCorrect={onCorrect ? (report) => { closeSelectedFeature({ restoreFocus: false }); onCorrect(report); } : undefined}
                    onReplace={onReplace ? async (report) => { const result = await onReplace(report); if (result?.ok) closeSelectedFeature({ restoreFocus: false }); return result; } : undefined}
                    ownReport={ownReport}
                    pilotStyle={inline}
                    phenomenon={phenomenon}
                  />
                );
              })}
            </div>
          </div>
        </div>
      ) : null}

      {selectedWebcam ? (
        <div
          className={inline ? "mf-territory-map__detail-layer" : undefined}
          onClick={(event) => {
            if (event.target === event.currentTarget) {
              closeSelectedFeature({ restoreFocus: false });
            }
          }}
        >
          <div
            aria-label={`${copy.webcams} · ${selectedWebcam.name}`}
            aria-modal="true"
            className="mf-live-community-map__detail mf-territory-map__webcam-detail"
            onPointerCancel={() => { detailSwipeRef.current = null; }}
            onPointerDown={beginDetailSwipe}
            onPointerUp={finishDetailSwipe}
            ref={detailRef}
            role="dialog"
            tabIndex={-1}
          >
            <span aria-hidden="true" className="mf-live-community-map__detail-grabber" />
            <div className="mf-live-community-map__detail-heading">
              <div>
                <strong>{getCameraDetailTitle(selectedWebcam)}</strong>
                <span>{[
                  getCameraLocation(selectedWebcam),
                  selectedWebcam.distanceLabel,
                ].filter(Boolean).join(" · ")}</span>
              </div>
              <AppIconButton
                ariaLabel={copy.close}
                icon={X}
                onClick={() => closeSelectedFeature()}
              />
            </div>
            <div
              className="mf-territory-map__webcam-swipe"
              onPointerCancel={() => { webcamSwipeRef.current = null; }}
              onPointerDown={beginWebcamSwipe}
              onPointerUp={finishWebcamSwipe}
            >
              {renderWebcamDetail?.(
                selectedWebcam,
                selectedWebcamPlaceGroup?.cameras.length > 1 ? (
                  <div
                    aria-label={copy.webcamClusterLabel
                      .replace("{place}", selectedWebcamPlaceGroup.label)
                      .replace("{count}", String(selectedWebcamPlaceGroup.count))}
                    className="mf-territory-map__webcam-switcher"
                  >
                    <AppIconButton
                      ariaLabel={copy.webcamPrevious}
                      icon={ChevronLeft}
                      onClick={() => selectAdjacentWebcam(-1)}
                    />
                    <span aria-live="polite">
                      {copy.webcamPosition
                        .replace("{current}", String(selectedWebcamIndex + 1))
                        .replace("{count}", String(selectedWebcamPlaceGroup.count))}
                    </span>
                    <AppIconButton
                      ariaLabel={copy.webcamNext}
                      icon={ChevronRight}
                      onClick={() => selectAdjacentWebcam(1)}
                    />
                  </div>
                ) : null,
              )}
            </div>
          </div>
        </div>
      ) : null}

    </div>
  );
}
