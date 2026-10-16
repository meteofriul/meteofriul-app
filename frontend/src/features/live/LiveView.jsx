import {
  ArrowRight,
  Camera,
  ChevronDown,
  ChevronUp,
  Clock,
  ExternalLink,
  Heart,
  ImageOff,
  LocateFixed,
  MapPin,
  Maximize2,
  Pencil,
  Play,
  Radio,
  RefreshCw,
  Send,
  ShieldCheck,
  Smile,
  Undo2,
  UsersRound,
  X,
} from "lucide-react";
import { useCallback, useEffect, useId, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { usePilotBackHandler } from "../../app/usePilotBackHandler";

import { isPilotCommunityReportingAvailable } from "../../services/firebaseAppCheckAdapter";
import { AppButton } from "../../ui/components/AppButton";
import { AppIconButton } from "../../ui/components/AppIconButton";
import { AppTabs } from "../../ui/components/AppTabs";
import { LocationChangeButton } from "../../ui/components/LocationChangeButton";
import { OfficialAlertCompactLink } from "../../ui/components/OfficialAlertCompactLink";
import { TabPage } from "../../ui/layout/TabPage";
import { BulletinRadarCard } from "../bulletin/BulletinRadarCard";
import { CommunityAvatar } from "../community/CommunityAvatar";
import {
  getCommunityIdentityPreview,
  normalizePublicCommunityIdentitySnapshot,
} from "../community/communityIdentity";
import { isDefinitiveAppExperience } from "../../services/localWeatherPilot";
import { isLocalCommunityPilot } from "../../services/localCommunityPilot";
import { getPilotMutationFeedback, readPilotPendingOperations, readPilotReplacement, reconcilePilotReportOperation } from "./pilotReportOperations";
import {
  CommunityGuidelinesConsentDialog,
  CommunityMap,
} from "./CommunityMap";
import { TerritoryImmersiveMap } from "./TerritoryImmersiveMap";
import {
  hasCommunityGuidelinesConsent,
  rememberCommunityGuidelinesConsent,
} from "./communityGuidelinesConsent";
import {
  isolateCommunityModalBackground,
  trapCommunityModerationFocus,
} from "./communityModerationFocus";
import {
  getCommunityContributionCount,
  getCommunityVote,
  getOwnCommunityReport,
  readCommunityPersonalState,
  rememberCommunityMapWithdrawal,
  rememberCommunityVote,
} from "./communityPersonalState";
import {
  filterCommunityMapMarkers,
  getAcquiredCommunityMapWithdrawals,
} from "./communityMapVisibility";
import {
  filterCommunityExpiredReportsFromMap,
  filterCommunityWithdrawnReportsModel,
} from "./communityReportWithdrawal";
import {
  getCommunityActiveCount,
  getCommunityActiveSummary,
  getCommunityAvailability,
  getCommunityConfirmationSummary,
  getCommunityContributionLabel,
  getCommunityDenialLabel,
  getCommunityMapWithdrawalLabel,
  getCommunityNearbyMatchSummary,
  getCommunityRecentSummary,
  getCommunityUpdatedLabel,
  getOwnReportExpiryLabel,
} from "./communitySocialPresentation";
import {
  findNearbyMatchingCommunityGroups,
  selectCommunityNearbyMatch,
} from "./liveReportLocation";
import {
  blockCommunityReportPreviewSubmission,
  createCommunityReportPreviewLocation,
} from "./communityReportPreview";
import { lockCommunityReportSheetScroll } from "./communityReportSheetState";
import { WebcamPlayerDialog } from "./WebcamPlayerDialog";
import { WebcamImageViewerDialog } from "./WebcamImageViewerDialog";
import { getReportFeedback } from "./liveReportFeedback";
import {
  hasReportLocationNoticeConsent,
  rememberReportLocationNoticeConsent,
} from "./reportLocationNoticeConsent";
import { LIVE_REPORT_ICONS, PILOT_LIVE_REPORT_ICONS } from "./liveReportIcons";
import { COMMUNITY_GUIDELINES_POLICY_VERSION } from "./liveReportPolicy";
import { runLiveReportSubmission } from "./liveReportSubmission";
import { getPilotReportEditIntent, reviewPilotReportEditIntent } from "./pilotReportEditIntent";
import {
  canAutoRetryWebcamMedia,
  createWebcamMediaState,
  failWebcamMedia,
  getNextWebcamId,
  retryWebcamMedia,
} from "./webcamMediaState";
import {
  getSelectedWebcamId,
  rememberWebcamSelection,
} from "./webcamSelectionState";
import { buildWebcamSnapshotUrl, watchWebcamSnapshot } from "./webcamSnapshotRefresh";
import {
  fetchWebcamSnapshotUpdatedAt,
  getWebcamSnapshotBadgeLabel,
  isWebcamSnapshotRecent,
} from "./webcamSnapshotMetadata";

const TERRITORY_SOURCE_LINKS = Object.freeze([
  {
    href: "https://www.protezionecivile.fvg.it/it/allerte",
    labelKey: "territorySourceAlerts",
  },
  {
    href: "https://www.meteo.fvg.it/neve.php",
    labelKey: "territorySourceSnow",
  },
  {
    href: "https://www.protezionecivile.fvg.it/it/servizio-di-piena",
    labelKey: "territorySourceWaterways",
  },
  {
    href: "https://mappe.protezionecivile.gov.it/it/mappe-e-dashboard-rischi/piattaforma-radar/",
    labelKey: "territorySourceRadar",
  },
]);

function getItemCommunityIdentityPreview(item, { limit = 3, placeName } = {}) {
  const sourceKeys = Array.isArray(item?.sourceKeys)
    ? item.sourceKeys
    : [item?.sourceKey].filter(Boolean);
  const identities = Array.isArray(item?.identities)
    ? [...item.identities]
    : [];
  const directIdentity = normalizePublicCommunityIdentitySnapshot(item?.identity);

  if (directIdentity) {
    const directSourceKey = String(item?.sourceKey || sourceKeys[0] || "").trim();
    const directEntry = { identity: directIdentity, sourceKey: directSourceKey };
    const directFingerprint = JSON.stringify(directIdentity);
    const existingIndex = identities.findIndex((entry) => {
      const entrySourceKey = String(entry?.sourceKey ?? entry?.source_key ?? "").trim();
      const entryIdentity = normalizePublicCommunityIdentitySnapshot(entry?.identity ?? entry);
      return (directSourceKey && entrySourceKey === directSourceKey)
        || (entryIdentity && JSON.stringify(entryIdentity) === directFingerprint);
    });

    if (existingIndex >= 0) {
      identities[existingIndex] = {
        ...identities[existingIndex],
        identity: directIdentity,
      };
    } else identities.unshift(directEntry);
  }

  return getCommunityIdentityPreview({
    identities,
    limit,
    placeName: placeName || item?.place,
    sourceKeys,
  });
}

function CommunityIdentityPreview({
  className = "",
  item,
  limit = 3,
  placeName,
}) {
  const preview = getItemCommunityIdentityPreview(item, { limit, placeName });
  if (!preview.totalCount) return null;

  const accessibleAliases = preview.identities.map(({ alias }) => alias).join(", ");
  const classes = ["mf-live-community-identities", className].filter(Boolean).join(" ");

  return (
    <small
      aria-label={`${accessibleAliases}${preview.hiddenCount ? `, +${preview.hiddenCount}` : ""}`}
      className={classes}
    >
      {preview.identities.map((identity, index) => (
        <span className="mf-live-community-identity" key={`${identity.alias}-${index}`}>
          <CommunityAvatar decorative size={20} snapshot={identity} />
          {" "}
          <span>{identity.alias}</span>
          {index < preview.identities.length - 1 ? (
            <span aria-hidden="true" className="mf-live-community-identity__separator"> · </span>
          ) : null}
        </span>
      ))}
      {preview.hiddenCount ? (
        <span className="mf-live-community-identity__more"> +{preview.hiddenCount}</span>
      ) : null}
    </small>
  );
}

function SourceStatus({ status }) {
  if (!status || ["fresh", "ok", "cache"].includes(status.id)) return null;

  return (
    <span
      className={`mf-live-status mf-live-status--${status.tone}`}
      role="status"
      title={status.label}
    >
      <span aria-hidden="true" />
      {status.label}
    </span>
  );
}

function sourceCreditsMatch(first, second) {
  const normalize = (value) => String(value || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "");
  const firstCredit = normalize(first);
  return Boolean(firstCredit) && firstCredit === normalize(second);
}

function SectionHeader({ icon: Icon, meta, title, titleId }) {
  return (
    <div className="mf-live-section-header">
      <div>
        <span className="mf-live-section-header__icon" aria-hidden="true">
          <Icon size={18} strokeWidth={2.35} />
        </span>
        <h2 id={titleId}>{title}</h2>
      </div>
      {meta}
    </div>
  );
}

function LocationContext({ copy, disabled = false, locationLabel, onChangeLocation }) {
  if (!locationLabel) return null;

  return (
    <div className="mf-live-location-context">
      <MapPin aria-hidden="true" size={14} strokeWidth={2.4} />
      <strong>{locationLabel}</strong>
      {onChangeLocation ? (
        <LocationChangeButton
          disabled={disabled}
          label={copy.locationChange}
          onClick={onChangeLocation}
        />
      ) : null}
    </div>
  );
}

function TerritorySources({ copy }) {
  return (
    <section
      aria-labelledby="live-territory-sources-title"
      className="mf-live-territory-sources"
    >
      <div className="mf-live-territory-sources__header">
        <span aria-hidden="true" className="mf-live-territory-sources__icon">
          <ShieldCheck size={17} strokeWidth={2.3} />
        </span>
        <div>
          <h2 id="live-territory-sources-title">{copy.territorySourcesTitle}</h2>
          <p>{copy.territorySourcesBody}</p>
        </div>
      </div>
      <div className="mf-live-territory-sources__links">
        {TERRITORY_SOURCE_LINKS.map((source) => (
          <a
            href={source.href}
            key={source.labelKey}
            rel="noreferrer"
            target="_blank"
          >
            <span>{copy[source.labelKey]}</span>
            <ExternalLink aria-hidden="true" size={14} strokeWidth={2.25} />
          </a>
        ))}
      </div>
      <p className="mf-live-territory-sources__note">{copy.territorySourcesNote}</p>
    </section>
  );
}

const WEBCAM_LOAD_TIMEOUT_MS = 6500;
const WEBCAM_SNAPSHOT_LOAD_TIMEOUT_MS = 15_000;
const WEBCAM_AUTO_RETRY_MS = 60_000;
const WEBCAM_AUTO_RETRY_LIMIT = 1;
const WEBCAM_MANUAL_REFRESH_COOLDOWN_MS = 12_000;

function getCommunityMutationErrorCode(result) {
  return typeof result?.detail === "object"
    ? String(result.detail?.code || "").trim()
    : "";
}

function appendRetryToken(imageUrl, retryToken) {
  if (!imageUrl || retryToken <= 0) return imageUrl;

  const hashIndex = imageUrl.indexOf("#");
  const baseUrl = hashIndex >= 0 ? imageUrl.slice(0, hashIndex) : imageUrl;
  const hash = hashIndex >= 0 ? imageUrl.slice(hashIndex) : "";
  const separator = baseUrl.includes("?") ? "&" : "?";
  return `${baseUrl}${separator}mf_retry=${retryToken}${hash}`;
}

export function WebcamFailureActions({ copy, onNext }) {
  if (!onNext) return null;

  return (
    <div className="mf-live-webcam-preview__fallback-actions">
      <button onClick={onNext} type="button">
        <span>{copy.webcamNext}</span>
        <ArrowRight aria-hidden="true" size={16} strokeWidth={2.35} />
      </button>
    </div>
  );
}

export function WebcamFailureCopy({ copy, media, autoRetryScheduled = false }) {
  const liveImageFailed = media.liveUnavailable || media.sourceKind === "live";

  return (
    <div className="mf-live-webcam-preview__fallback-copy" role="status">
      <strong>{liveImageFailed ? copy.webcamTemporaryUnavailable : copy.webcamImageUnavailable}</strong>
      <span>
        {autoRetryScheduled
          ? copy.webcamAutomaticRetry
          : copy.webcamTryAnother}
      </span>
    </div>
  );
}

function WebcamLoadingSkeleton({ copy }) {
  return (
    <div
      aria-busy="true"
      aria-label={copy.webcamLoading}
      className="mf-live-webcam-skeleton"
      role="status"
    >
      <div aria-hidden="true" className="mf-live-webcam-skeleton__tabs">
        <span />
        <span />
        <span />
        <span />
      </div>
      <div aria-hidden="true" className="mf-live-webcam-skeleton__preview">
        <div className="mf-live-webcam-skeleton__media" />
        <div className="mf-live-webcam-skeleton__caption">
          <span />
          <span />
        </div>
      </div>
      <div aria-hidden="true" className="mf-live-webcam-skeleton__rail">
        <span />
        <span />
        <span />
      </div>
    </div>
  );
}

function WebcamPreview({
  camera,
  copy,
  highPriority = true,
  language = "it",
  mediaOverlay = null,
  onNextCamera,
  showIdentity = true,
}) {
  const [media, setMedia] = useState(() => createWebcamMediaState(camera));
  const [isPlayerOpen, setPlayerOpen] = useState(false);
  const [isImageViewerOpen, setImageViewerOpen] = useState(false);
  const [manualRefreshLocked, setManualRefreshLocked] = useState(false);
  const [snapshotUpdatedAt, setSnapshotUpdatedAt] = useState(camera.capturedAt || "");
  const [snapshotMetadataVerified, setSnapshotMetadataVerified] = useState(false);
  const mediaRef = useRef(null);
  const manualRefreshTimerRef = useRef(null);
  const [snapshotRequestTime, setSnapshotRequestTime] = useState(0);
  const { imageUrl: cameraImageUrl, fallbackImageUrl } = camera;
  const isSnapshot = camera.mediaType === "snapshot" && Boolean(cameraImageUrl);
  const {
    liveUnavailable,
    mediaState,
    retryToken,
    sourceKind,
  } = media;
  const imageUrl = sourceKind === "live"
    ? isSnapshot ? buildWebcamSnapshotUrl(camera.imageUrl, snapshotRequestTime) : camera.imageUrl
    : camera.fallbackImageUrl;
  const retryableImageUrl = appendRetryToken(imageUrl, retryToken);

  const requestSnapshotRefresh = useCallback((requestedAt) => {
    setSnapshotUpdatedAt("");
    setSnapshotMetadataVerified(false);
    setSnapshotRequestTime(requestedAt);
    setMedia(createWebcamMediaState({ imageUrl: cameraImageUrl, fallbackImageUrl }));
  }, [cameraImageUrl, fallbackImageUrl]);

  useEffect(() => {
    if (!isSnapshot) return undefined;

    return watchWebcamSnapshot({
      element: mediaRef.current,
      onRefresh: requestSnapshotRefresh,
    });
  }, [isSnapshot, requestSnapshotRefresh]);

  useEffect(() => {
    if (
      !isSnapshot
      || snapshotRequestTime <= 0
      || mediaState !== "loaded"
      || sourceKind !== "live"
    ) return undefined;

    let active = true;
    fetchWebcamSnapshotUpdatedAt(cameraImageUrl).then((updatedAt) => {
      if (active) {
        setSnapshotUpdatedAt(updatedAt);
        setSnapshotMetadataVerified(Boolean(updatedAt));
      }
    });
    return () => { active = false; };
  }, [cameraImageUrl, isSnapshot, mediaState, snapshotRequestTime, sourceKind]);

  useEffect(() => () => {
    if (manualRefreshTimerRef.current !== null) {
      globalThis.clearTimeout?.(manualRefreshTimerRef.current);
    }
  }, []);

  const handleManualSnapshotRefresh = useCallback(() => {
    if (!isSnapshot || manualRefreshLocked || mediaState === "loading") return;

    requestSnapshotRefresh(Date.now());
    setManualRefreshLocked(true);
    if (manualRefreshTimerRef.current !== null) {
      globalThis.clearTimeout?.(manualRefreshTimerRef.current);
    }
    manualRefreshTimerRef.current = globalThis.setTimeout?.(() => {
      manualRefreshTimerRef.current = null;
      setManualRefreshLocked(false);
    }, WEBCAM_MANUAL_REFRESH_COOLDOWN_MS) ?? null;
  }, [isSnapshot, manualRefreshLocked, mediaState, requestSnapshotRefresh]);

  const handleMediaFailure = useCallback(() => {
    setMedia((current) => failWebcamMedia(camera, current));
  }, [camera]);

  useEffect(() => {
    if (mediaState !== "loading" || sourceKind === "none" || !retryableImageUrl) return undefined;

    const loadTimeoutMs = isSnapshot && sourceKind === "live"
      ? WEBCAM_SNAPSHOT_LOAD_TIMEOUT_MS
      : WEBCAM_LOAD_TIMEOUT_MS;
    const timeoutId = window.setTimeout(handleMediaFailure, loadTimeoutMs);

    return () => window.clearTimeout(timeoutId);
  }, [handleMediaFailure, isSnapshot, mediaState, retryToken, retryableImageUrl, sourceKind]);

  const autoRetryScheduled = !isSnapshot && canAutoRetryWebcamMedia(
    camera,
    media,
    WEBCAM_AUTO_RETRY_LIMIT,
  );

  useEffect(() => {
    if (!autoRetryScheduled) return undefined;

    const timeoutId = window.setTimeout(() => {
      setMedia((current) => (
        canAutoRetryWebcamMedia(camera, current, WEBCAM_AUTO_RETRY_LIMIT)
          ? retryWebcamMedia(camera, current)
          : current
      ));
    }, WEBCAM_AUTO_RETRY_MS);

    return () => window.clearTimeout(timeoutId);
  }, [autoRetryScheduled, camera]);

  const imageAlt = `${sourceKind === "static" ? copy.webcamStaticImage : isSnapshot ? copy.webcamSnapshotImage : copy.webcamTitle}: ${camera.name}`;
  const sourceActionLabel = camera.imageUrl ? copy.webcamOpenSource : copy.webcamOpenExternal;
  const sourceActionAccessibleLabel = (camera.imageUrl ? copy.webcamOpenSourceNewTab : copy.webcamOpenExternalNewTab)
    .replace("{camera}", camera.name);
  const cameraLocation = camera.locationLabel || camera.area;
  const showCameraLocation = cameraLocation
    && cameraLocation.localeCompare(camera.name, undefined, { sensitivity: "base" }) !== 0;
  const hasLocationMeta = showCameraLocation || camera.distanceLabel;
  const providerMatchesAttribution = camera.attribution
    && sourceKind === "live"
    && sourceCreditsMatch(camera.attribution, camera.provider);
  const providerAttributionUrl = providerMatchesAttribution
    && camera.attributionUrl
    && camera.attributionUrl !== camera.sourceUrl
    ? camera.attributionUrl
    : "";
  const snapshotNow = new Date();
  const snapshotBadgeLabel = getWebcamSnapshotBadgeLabel({
    copy,
    language,
    now: snapshotNow,
    updatedAt: snapshotUpdatedAt,
  });
  const snapshotIsRecent = snapshotMetadataVerified && isWebcamSnapshotRecent({
    now: snapshotNow,
    updatedAt: snapshotUpdatedAt,
  });
  const canExpandImage = Boolean(retryableImageUrl) && mediaState === "loaded";

  return (
    <figure className="mf-live-webcam-preview" data-kind={isSnapshot ? "snapshot" : undefined}>
      <div className="mf-live-webcam-preview__media" data-source={sourceKind} data-state={mediaState} ref={mediaRef}>
        {mediaState !== "error" ? (
          <>
            <img
              alt={imageAlt}
              decoding="async"
              fetchPriority={isSnapshot || !highPriority ? "auto" : "high"}
              key={`${sourceKind}:${retryableImageUrl}`}
              onError={handleMediaFailure}
              onLoad={() => setMedia((current) => ({ ...current, mediaState: "loaded" }))}
              referrerPolicy={isSnapshot ? "no-referrer" : undefined}
              src={retryableImageUrl || undefined}
            />
            {mediaState === "loading" ? (
              <div aria-hidden="true" className="mf-live-webcam-preview__loading" />
            ) : null}
            {isSnapshot && sourceKind === "live" && mediaState === "loaded" ? (
              <span className={`mf-live-webcam-preview__media-badge${snapshotIsRecent ? " is-recent" : ""}`}>
                {snapshotBadgeLabel}
              </span>
            ) : null}
            {isSnapshot || canExpandImage ? (
              <div className="mf-live-webcam-preview__media-actions">
                {isSnapshot ? (
                  <button
                    aria-label={mediaState === "loading"
                      ? copy.webcamSnapshotRefreshPending
                      : copy.webcamSnapshotRefresh}
                    className={`mf-live-webcam-preview__media-action${mediaState === "loading" ? " is-loading" : ""}`}
                    disabled={manualRefreshLocked || mediaState === "loading"}
                    onClick={handleManualSnapshotRefresh}
                    title={copy.webcamSnapshotRefresh}
                    type="button"
                  >
                    <RefreshCw aria-hidden="true" size={18} strokeWidth={2.25} />
                  </button>
                ) : null}
                {canExpandImage ? (
                  <button
                    aria-haspopup="dialog"
                    aria-label={copy.webcamImageExpand}
                    className="mf-live-webcam-preview__media-action"
                    onClick={() => setImageViewerOpen(true)}
                    title={copy.webcamImageExpand}
                    type="button"
                  >
                    <Maximize2 aria-hidden="true" size={18} strokeWidth={2.25} />
                  </button>
                ) : null}
              </div>
            ) : null}
            {camera.playerUrl ? (
              <button
                aria-haspopup="dialog"
                aria-label={copy.webcamOpenLiveFor.replace("{camera}", camera.name)}
                className="mf-live-webcam-preview__live-trigger"
                onClick={() => setPlayerOpen(true)}
                type="button"
              >
                <span aria-hidden="true"><Play fill="currentColor" size={17} strokeWidth={2.2} /></span>
                <strong>{copy.webcamOpenLive}</strong>
              </button>
            ) : camera.sourceUrl && sourceKind !== "live" ? (
              <a
                aria-label={sourceActionAccessibleLabel}
                className="mf-live-webcam-preview__external-trigger"
                href={camera.sourceUrl}
                rel="noopener noreferrer"
                target="_blank"
              >
                <span aria-hidden="true"><ExternalLink size={17} strokeWidth={2.2} /></span>
                <strong>{sourceActionLabel}</strong>
              </a>
            ) : null}
            {liveUnavailable ? (
              <div className="mf-live-webcam-preview__fallback-notice">
                <span role="status">{copy.webcamStaticFallback}</span>
                <WebcamFailureActions
                  copy={copy}
                  onNext={onNextCamera}
                />
              </div>
            ) : null}
          </>
        ) : (
          <div
            aria-label={copy.webcamImageUnavailable}
            className="mf-live-webcam-preview__fallback"
            role="group"
          >
            {isSnapshot ? (
              <div className="mf-live-webcam-preview__media-actions">
                <button
                  aria-label={copy.webcamSnapshotRefresh}
                  className="mf-live-webcam-preview__media-action"
                  disabled={manualRefreshLocked}
                  onClick={handleManualSnapshotRefresh}
                  title={copy.webcamSnapshotRefresh}
                  type="button"
                >
                  <RefreshCw aria-hidden="true" size={18} strokeWidth={2.25} />
                </button>
              </div>
            ) : null}
            <div aria-hidden="true" className="mf-live-webcam-preview__fallback-visual">
              <Smile size={36} strokeWidth={1.85} />
              <span>
                <ImageOff size={15} strokeWidth={2.25} />
              </span>
            </div>
            <WebcamFailureCopy copy={copy} media={media} autoRetryScheduled={autoRetryScheduled} />
            <WebcamFailureActions
              copy={copy}
              onNext={onNextCamera}
            />
          </div>
        )}
        {mediaOverlay}
      </div>
      <figcaption>
        <div className="mf-live-webcam-preview__details">
          {showIdentity ? (
            <div className="mf-live-webcam-preview__identity">
              <strong>{camera.name}</strong>
              {hasLocationMeta ? (
                <span className="mf-live-webcam-preview__location">
                  <MapPin aria-hidden="true" size={13} strokeWidth={2.3} />
                  {showCameraLocation ? (
                    <span className="mf-live-webcam-preview__location-text">{cameraLocation}</span>
                  ) : null}
                  {showCameraLocation && camera.distanceLabel ? (
                    <span aria-hidden="true" className="mf-live-webcam-preview__location-separator">·</span>
                  ) : null}
                  {camera.distanceLabel ? (
                    <span className="mf-live-webcam-preview__distance">{camera.distanceLabel}</span>
                  ) : null}
                </span>
              ) : null}
            </div>
          ) : null}
          <div className="mf-live-webcam-preview__source">
            <div className="mf-live-webcam-preview__source-meta">
              <span className="mf-live-webcam-preview__source-credit">
                <span className="mf-live-webcam-preview__source-label">{copy.webcamSourceLabel}:</span>
                {providerAttributionUrl ? (
                  <a
                    className="mf-live-webcam-preview__attribution"
                    href={providerAttributionUrl}
                    rel="noopener noreferrer"
                    target="_blank"
                  >
                    <span className="mf-live-webcam-preview__provider">{camera.provider}</span>
                  </a>
                ) : (
                  <span className="mf-live-webcam-preview__provider">{camera.provider}</span>
                )}
              </span>
              {camera.attribution
                && sourceKind === "live"
                && !providerMatchesAttribution ? (
                camera.attributionUrl && camera.attributionUrl !== camera.sourceUrl ? (
                  <a
                    className="mf-live-webcam-preview__attribution"
                    href={camera.attributionUrl}
                    rel="noopener noreferrer"
                    target="_blank"
                  >
                    {camera.attribution}
                  </a>
                ) : (
                  <span className="mf-live-webcam-preview__attribution">{camera.attribution}</span>
                )
              ) : null}
              <SourceStatus status={camera.health} />
            </div>
            {camera.sourceUrl && (sourceKind === "live" || mediaState === "error" || camera.playerUrl) ? (
              <a
                aria-label={sourceActionAccessibleLabel}
                className="mf-live-webcam-preview__source-action"
                href={camera.sourceUrl}
                rel="noopener noreferrer"
                target="_blank"
                title={sourceActionLabel}
              >
                <ExternalLink aria-hidden="true" size={17} strokeWidth={2.3} />
              </a>
            ) : null}
          </div>
        </div>
      </figcaption>
      {isPlayerOpen ? (
        <WebcamPlayerDialog
          camera={camera}
          copy={copy}
          onClose={() => setPlayerOpen(false)}
        />
      ) : null}
      {isImageViewerOpen && retryableImageUrl ? (
        <WebcamImageViewerDialog
          camera={camera}
          copy={copy}
          imageUrl={retryableImageUrl}
          onClose={() => setImageViewerOpen(false)}
        />
      ) : null}
    </figure>
  );
}

const WEBCAM_PANEL_ID = "live-webcam-panel";

function WebcamCarouselItem({ camera, cameraIndex, copy, language, onNextCamera, total }) {
  const itemRef = useRef(null);
  const [shouldLoad, setShouldLoad] = useState(() => (
    cameraIndex === 0 || typeof globalThis.IntersectionObserver !== "function"
  ));

  useEffect(() => {
    if (shouldLoad || !itemRef.current) return undefined;

    const IntersectionObserverClass = globalThis.IntersectionObserver;
    if (typeof IntersectionObserverClass !== "function") return undefined;

    const observer = new IntersectionObserverClass((entries) => {
      if (!entries.some((entry) => entry.target === itemRef.current && entry.isIntersecting)) return;
      setShouldLoad(true);
      observer.disconnect();
    }, { rootMargin: "0px 96px" });
    observer.observe(itemRef.current);

    return () => observer.disconnect();
  }, [shouldLoad]);

  return (
    <div
      aria-busy={shouldLoad ? undefined : "true"}
      aria-posinset={cameraIndex + 1}
      aria-setsize={total}
      className="mf-live-webcam-carousel__item"
      onFocus={() => {
        setShouldLoad(true);
        itemRef.current?.scrollIntoView({ behavior: "auto", block: "nearest", inline: "start" });
      }}
      ref={itemRef}
      role="listitem"
      tabIndex={0}
    >
      {shouldLoad ? (
        <WebcamPreview
          camera={camera}
          copy={copy}
          highPriority={cameraIndex === 0}
          key={`${camera.id}:${camera.imageUrl}:${camera.fallbackImageUrl}:${camera.playerUrl}:${camera.mediaType}`}
          language={language}
          onNextCamera={onNextCamera}
        />
      ) : (
        <figure className="mf-live-webcam-carousel__placeholder">
          <span aria-hidden="true" className="mf-live-webcam-carousel__placeholder-media" />
          <figcaption>{camera.name}</figcaption>
        </figure>
      )}
    </div>
  );
}

function WebcamPanel({ carouselLayout = false, model }) {
  const groups = model.groups;
  const [activeGroupId, setActiveGroupId] = useState(groups[0]?.id || "");
  const [selectedCameraIds, setSelectedCameraIds] = useState(() => {
    const firstGroup = groups[0];
    const firstCameraId = firstGroup?.cameras[0]?.id;
    return firstGroup?.id && firstCameraId ? { [firstGroup.id]: firstCameraId } : {};
  });
  const effectiveGroupId = groups.some((group) => group.id === activeGroupId)
    ? activeGroupId
    : groups[0]?.id || "";
  const activeGroup = groups.find((group) => group.id === effectiveGroupId) || groups[0];
  const selectedCameraId = getSelectedWebcamId(
    activeGroup,
    selectedCameraIds[effectiveGroupId],
  );
  const selectedCamera = activeGroup?.cameras.find((camera) => camera.id === selectedCameraId);
  const [pickerOpen, setPickerOpen] = useState(false);
  const pickerTriggerRef = useRef(null);
  const tabs = useMemo(() => groups.map((group) => ({
    ariaLabel: model.copy.webcamCountLabel
      .replace("{label}", group.label)
      .replace("{count}", String(group.count)),
    controlsId: WEBCAM_PANEL_ID,
    id: group.id,
    label: group.label,
    meta: `(${group.count})`,
    tabId: `live-webcam-tab-${group.id}`,
  })), [groups, model.copy.webcamCountLabel]);
  const distanceOriginLabel = model.locationLabel
    && activeGroup?.cameras.some((camera) => camera.distanceLabel)
    ? model.copy.webcamDistanceOrigin.replace("{place}", model.locationLabel)
    : "";
  const nextCameraId = getNextWebcamId(activeGroup?.cameras, selectedCamera?.id);
  const pickerOptionsId = `live-webcam-options-${activeGroup?.id || "empty"}`;

  return (
    <section className="mf-live-card mf-live-card--webcam" aria-labelledby="live-webcam-title">
      <SectionHeader
        icon={Camera}
        meta={activeGroup && selectedCamera ? <SourceStatus status={model.status} /> : null}
        title={model.title}
        titleId="live-webcam-title"
      />
      {activeGroup && selectedCamera ? (
        <div className="mf-live-webcam-viewer">
          <div className="mf-live-webcam-groups">
            <AppTabs
              activeId={activeGroup.id}
              ariaLabel={model.copy.webcamAreaLabel}
              items={tabs}
              onChange={(groupId) => {
                if (groupId === effectiveGroupId) return;
                setPickerOpen(false);
                setActiveGroupId(groupId);
              }}
            />
          </div>
          <div
            aria-labelledby={`live-webcam-tab-${activeGroup.id}`}
            className="mf-live-webcam-content"
            id={WEBCAM_PANEL_ID}
            role="tabpanel"
          >
            {carouselLayout ? (
              <div
                aria-label={`${model.title}: ${activeGroup.label}`}
                className="mf-live-webcam-carousel"
                key={activeGroup.id}
                ref={pickerTriggerRef}
                role="list"
              >
                {activeGroup.cameras.map((camera, cameraIndex) => {
                  const followingIndex = cameraIndex + 1 < activeGroup.cameras.length
                    ? cameraIndex + 1
                    : 0;
                  const canShowNext = activeGroup.cameras.length > 1;

                  return (
                    <WebcamCarouselItem
                      camera={camera}
                      cameraIndex={cameraIndex}
                      copy={model.copy}
                      key={camera.id}
                      language={model.language}
                      onNextCamera={canShowNext ? () => {
                        const nextItem = pickerTriggerRef.current?.children[followingIndex];
                        nextItem?.scrollIntoView({ behavior: "auto", block: "nearest", inline: "start" });
                        nextItem?.focus({ preventScroll: true });
                      } : null}
                      total={activeGroup.cameras.length}
                    />
                  );
                })}
              </div>
            ) : (
              <>
                <WebcamPreview
                  camera={selectedCamera}
                  copy={model.copy}
                  key={`${selectedCamera.id}:${selectedCamera.imageUrl}:${selectedCamera.fallbackImageUrl}:${selectedCamera.playerUrl}:${selectedCamera.mediaType}`}
                  language={model.language}
                  onNextCamera={nextCameraId ? () => setSelectedCameraIds((current) => (
                    rememberWebcamSelection(current, effectiveGroupId, nextCameraId)
                  )) : null}
                />
                <div
                  className="mf-live-webcam-picker"
                  onKeyDown={(event) => {
                    if (event.key !== "Escape" || !pickerOpen) return;
                    event.preventDefault();
                    setPickerOpen(false);
                    pickerTriggerRef.current?.focus();
                  }}
                >
                  <div className="mf-live-webcam-picker__heading">
                    <span>{model.copy.webcamSelectLabel}</span>
                    {distanceOriginLabel ? <small>{distanceOriginLabel}</small> : null}
                  </div>
                  <button
                    aria-controls={pickerOptionsId}
                    aria-expanded={pickerOpen}
                    aria-label={[
                      model.copy.webcamSelectLabel,
                      selectedCamera.name,
                      selectedCamera.distanceLabel,
                    ].filter(Boolean).join(": ")}
                    className="mf-live-webcam-picker__trigger"
                    onClick={() => setPickerOpen((current) => !current)}
                    ref={pickerTriggerRef}
                    type="button"
                  >
                    <span className="mf-live-webcam-picker__selection">
                      <strong>{selectedCamera.name}</strong>
                      {selectedCamera.distanceLabel ? <small>{selectedCamera.distanceLabel}</small> : null}
                    </span>
                    {pickerOpen ? (
                      <ChevronUp aria-hidden="true" size={18} strokeWidth={2.4} />
                    ) : (
                      <ChevronDown aria-hidden="true" size={18} strokeWidth={2.4} />
                    )}
                  </button>
                  <ul
                    aria-label={model.copy.webcamSelectLabel}
                    className="mf-live-webcam-picker__options"
                    hidden={!pickerOpen}
                    id={pickerOptionsId}
                  >
                    {activeGroup.cameras.map((camera) => {
                      const selected = camera.id === selectedCamera.id;
                      return (
                        <li key={camera.id}>
                          <button
                            aria-pressed={selected}
                            className={selected ? "is-active" : ""}
                            onClick={() => {
                              setSelectedCameraIds((current) => (
                                rememberWebcamSelection(current, effectiveGroupId, camera.id)
                              ));
                              setPickerOpen(false);
                              pickerTriggerRef.current?.focus();
                            }}
                            type="button"
                          >
                            <span aria-hidden="true" className="mf-live-webcam-picker__check">
                              {selected ? "✓" : ""}
                            </span>
                            <span className="mf-live-webcam-picker__option-main">
                              <span className="mf-live-webcam-picker__option-name">{camera.name}</span>
                              {camera.playerUrl ? (
                                <span
                                  aria-label={model.copy.webcamLiveDialogTitle}
                                  className="mf-live-webcam-picker__live-icon"
                                  title={model.copy.webcamLiveDialogTitle}
                                >
                                  <Play aria-hidden="true" fill="currentColor" size={10} strokeWidth={2.4} />
                                </span>
                              ) : null}
                            </span>
                            {camera.distanceLabel ? <small>{camera.distanceLabel}</small> : null}
                          </button>
                        </li>
                      );
                    })}
                  </ul>
                </div>
              </>
            )}
          </div>
        </div>
      ) : model.status?.id === "loading" ? (
        <WebcamLoadingSkeleton copy={model.copy} />
      ) : (
        <div aria-live="polite" className="mf-live-empty" role="status">
          <ImageOff aria-hidden="true" size={24} strokeWidth={2.1} />
          <div>
            <strong>{model.emptyTitle}</strong>
            <p>{model.emptyBody}</p>
          </div>
        </div>
      )}
    </section>
  );
}

export function CommunityReportForm({
  activeGroups = [],
  copy,
  dialogId,
  maxDistanceKm,
  onClose,
  onConfirmNearby,
  onLocate,
  onPersonalStateChange,
  onSelfMatchDetected,
  onSubmit,
  onUndo,
  onViewMap,
  locations,
  options,
  pendingReportUndo,
  personalStorage,
  personalState,
  pilotStyle = false,
  previewOnly = false,
  selfMatchGroupIds = [],
  sheet = false,
  simulationOnly = false,
  ttlLabel,
  correctionReport = null,
  replacementToken = "",
  managedReport = null,
  onManagedUpdate,
}) {
  const pilotRules = isDefinitiveAppExperience() || isLocalCommunityPilot();
  const pendingIntent = pilotRules && !simulationOnly ? readPilotPendingOperations({ storage: personalStorage })[0] : null;
  const [selectedTypeId, setSelectedTypeId] = useState(() => pendingIntent?.typeId || managedReport?.typeId || correctionReport?.typeId || "");
  const [pendingEdit, setPendingEdit] = useState(() => {
    if (!managedReport) return null;
    if (managedReport.pendingUpdate) return { intent: "update", uncertain: true };
    if (pendingIntent?.reportId === managedReport.reportId && ["correct", "replace"].includes(pendingIntent?.kind)) {
      return { intent: pendingIntent.kind, uncertain: true };
    }
    return null;
  });
  const [submitState, setSubmitState] = useState({ status: "idle", text: "" });
  const [isUndoing, setUndoing] = useState(false);
  const [expiredUndoKey, setExpiredUndoKey] = useState("");
  const [locationState, setLocationState] = useState({
    data: null,
    status: "loading",
    text: copy.reportGpsLoading,
  });
  const [isLocationEditorOpen, setLocationEditorOpen] = useState(false);
  const [ignoredMatchGroupIds, setIgnoredMatchGroupIds] = useState([]);
  const [matchNow, setMatchNow] = useState(() => Date.now());
  const [receiptNow, setReceiptNow] = useState(() => Date.now());
  const [hasAcceptedTerms, setHasAcceptedTerms] = useState(
    () => hasCommunityGuidelinesConsent(
      COMMUNITY_GUIDELINES_POLICY_VERSION,
      { storage: personalStorage },
    ) && hasReportLocationNoticeConsent({ storage: personalStorage }),
  );
  const dialogRef = useRef(null);
  const onCloseRef = useRef(onClose);
  const successRef = useRef(null);
  const submissionInFlightRef = useRef(false);
  const generatedDialogId = useId();
  const reportDialogId = dialogId || `community-report-${generatedDialogId}`;
  const reportTitleId = `${reportDialogId}-title`;
  const reportDescriptionId = `${reportDialogId}-description`;
  const reportLocationSelectorId = `${reportDialogId}-location-selector`;
  const isSubmitting = submitState.status === "loading";
  usePilotBackHandler(() => {
    if (submissionInFlightRef.current) return;
    if (isLocationEditorOpen) setLocationEditorOpen(false);
    else onCloseRef.current?.();
  }, sheet);
  const isSuccess = submitState.status === "success";
  const isLocationReady = locationState.status === "ready";
  const editIntent = managedReport
    ? pendingEdit?.intent || getPilotReportEditIntent(managedReport, selectedTypeId, matchNow)
    : "";
  const editHint = pendingEdit?.withdrawn ? copy.reportEditReplacementPending
    : editIntent === "update" ? copy.reportContinuesHint
      : editIntent === "correct" ? copy.reportCorrectionHint
        : editIntent === "replace" ? copy.reportEditReplacementHint
          : editIntent === "unavailable" ? copy.reportChangeUnavailable : "";
  const editSubmitLabel = pendingEdit?.uncertain ? copy.reportEditRetry
    : pendingEdit?.withdrawn ? copy.reportEditCompleteReplacement
      : editIntent === "update" ? copy.reportEditRenew : copy.reportEditConfirm;
  const editDescription = pendingEdit?.withdrawn ? copy.reportEditReplacementPending
    : pendingEdit?.uncertain ? copy.reportEditPending : copy.reportEditBody;
  const nearbyMatches = useMemo(() => (
    !managedReport && !correctionReport && !replacementToken && isLocationReady && selectedTypeId
      ? findNearbyMatchingCommunityGroups(activeGroups, {
        coords: locationState.data.coords,
        maxDistanceKm,
        now: matchNow,
        typeId: selectedTypeId,
      }).filter((match) => !ignoredMatchGroupIds.includes(match.groupId)
        && (!pilotRules || simulationOnly || match.istatCode === locationState.data.istatCode))
      : []
  ), [
    activeGroups,
    ignoredMatchGroupIds,
    isLocationReady,
    locationState.data,
    matchNow,
    maxDistanceKm,
    selectedTypeId,
    correctionReport,
    managedReport,
    replacementToken,
    pilotRules,
    simulationOnly,
  ]);
  const {
    match: nearbyMatch,
    state: nearbyMatchState,
  } = selectCommunityNearbyMatch(nearbyMatches, personalState, selfMatchGroupIds);
  const localUndo = submitState.status === "success"
    ? { reportId: submitState.reportId, undoUntil: submitState.undoUntil }
    : null;
  const activeUndo = localUndo?.reportId ? localUndo : pendingReportUndo;
  const activeUndoUntil = Number(activeUndo?.undoUntil);
  const activeUndoKey = activeUndo?.reportId && Number.isFinite(activeUndoUntil)
    ? `${activeUndo.reportId}:${activeUndoUntil}`
    : "";
  const canUndo = Boolean(
    !pilotRules && onUndo
    && activeUndo?.reportId
    && Number.isFinite(activeUndoUntil)
    && activeUndoKey !== expiredUndoKey,
  );

  useEffect(() => {
    onCloseRef.current = onClose;
  }, [onClose]);

  useEffect(() => {
    if (!sheet || !globalThis.document) return undefined;

    const documentLike = globalThis.document;
    const previousFocus = documentLike.activeElement;
    const releaseBackground = isolateCommunityModalBackground(documentLike);
    const releaseScroll = lockCommunityReportSheetScroll(documentLike);
    const focusFrame = globalThis.requestAnimationFrame?.(
      () => dialogRef.current?.focus?.({ preventScroll: true }),
    );

    const handleKeyDown = (event) => {
      if (event.key === "Escape") {
        if (submissionInFlightRef.current) return;
        event.preventDefault();
        onCloseRef.current();
        return;
      }

      trapCommunityModerationFocus(
        event,
        dialogRef.current,
        documentLike.activeElement,
      );
    };

    documentLike.addEventListener("keydown", handleKeyDown);

    return () => {
      if (focusFrame !== undefined) globalThis.cancelAnimationFrame?.(focusFrame);
      documentLike.removeEventListener("keydown", handleKeyDown);
      releaseScroll();
      releaseBackground();
      globalThis.requestAnimationFrame?.(() => {
        if (previousFocus?.isConnected) previousFocus.focus?.({ preventScroll: true });
      });
    };
  }, [sheet]);

  useEffect(() => {
    const undoUntil = activeUndoUntil;
    if (!activeUndoKey || !Number.isFinite(undoUntil)) return undefined;

    const timeoutId = globalThis.setTimeout?.(
      () => setExpiredUndoKey(activeUndoKey),
      Math.max(0, undoUntil - Date.now()),
    );

    return () => {
      if (timeoutId !== undefined) globalThis.clearTimeout?.(timeoutId);
    };
  }, [activeUndoKey, activeUndoUntil]);

  useEffect(() => {
    if (!isSuccess) return undefined;

    const focusFrame = globalThis.requestAnimationFrame?.(
      () => successRef.current?.focus?.({ preventScroll: true }),
    );
    const refreshTimeoutId = globalThis.setTimeout?.(
      () => setReceiptNow(Date.now()),
      0,
    );
    const intervalId = globalThis.setInterval?.(
      () => setReceiptNow(Date.now()),
      30_000,
    );
    return () => {
      if (focusFrame !== undefined) globalThis.cancelAnimationFrame?.(focusFrame);
      if (refreshTimeoutId !== undefined) globalThis.clearTimeout?.(refreshTimeoutId);
      if (intervalId !== undefined) globalThis.clearInterval?.(intervalId);
    };
  }, [isSuccess]);

  useEffect(() => {
    if (!isLocationReady || !selectedTypeId || isSuccess) return undefined;

    const refreshTimeoutId = globalThis.setTimeout?.(
      () => setMatchNow(Date.now()),
      0,
    );
    const intervalId = globalThis.setInterval?.(
      () => setMatchNow(Date.now()),
      15_000,
    );
    return () => {
      if (refreshTimeoutId !== undefined) globalThis.clearTimeout?.(refreshTimeoutId);
      if (intervalId !== undefined) globalThis.clearInterval?.(intervalId);
    };
  }, [
    isLocationReady,
    isSuccess,
    locationState.data?.selectedPlace,
    selectedTypeId,
  ]);

  const requestLocation = useCallback(async () => {
    if (!onLocate) {
      setLocationState({ data: null, status: "error", text: copy.reportGpsUnavailable });
      return;
    }

    setLocationState({ data: null, status: "loading", text: copy.reportGpsLoading });
    setLocationEditorOpen(false);
    setSubmitState({ status: "idle", text: "" });
    const result = await onLocate({ locations, maxDistanceKm });

    if (!result?.ok) {
      setLocationState({
        data: null,
        status: "error",
        text: getReportFeedback(copy, result),
      });
      return;
    }

    setLocationState({
      data: result,
      status: "ready",
      text: copy.reportLocationReady,
    });
  }, [copy, locations, maxDistanceKm, onLocate]);

  useEffect(() => {
    let cancelled = false;

    async function locateOnOpen() {
      const result = await Promise.resolve(
        onLocate
          ? onLocate({ locations, maxDistanceKm })
          : { ok: false, reason: "unavailable" },
      );
      if (cancelled) return;

      if (!result?.ok) {
        setLocationState({
          data: null,
          status: "error",
          text: getReportFeedback(copy, result),
        });
        return;
      }

      setLocationState({
        data: result,
        status: "ready",
        text: copy.reportLocationReady,
      });
    }

    locateOnOpen();

    return () => {
      cancelled = true;
    };
  }, [copy, locations, maxDistanceKm, onLocate]);

  const handleSubmit = async (event) => {
    event.preventDefault();
    if (submissionInFlightRef.current) return;
    if (previewOnly) return;

    if (!selectedTypeId) {
      setSubmitState({ status: "error", text: copy.reportChooseType });
      return;
    }
    if (!isLocationReady) {
      setSubmitState({ status: "error", text: locationState.text });
      return;
    }
    if (!hasAcceptedTerms) {
      setSubmitState({ status: "error", text: copy.reportTermsBody });
      return;
    }

    if (["own", "voted"].includes(nearbyMatchState)) return;

    if (managedReport) {
      // Never silently turn a correction into a withdrawal when the 5-minute
      // window closes between rendering the explanation and tapping confirm.
      const review = reviewPilotReportEditIntent(managedReport, selectedTypeId);
      const currentIntent = pendingEdit?.intent || review.intent;
      if (currentIntent !== editIntent) {
        setMatchNow(review.reviewedAt);
        setSubmitState({ status: "error", text: copy.reportEditChanged });
        return;
      }
      if (editIntent === "unavailable") return;
    }

    const requiresCurrentLocation = !nearbyMatch
      && !(managedReport && editIntent === "update");
    const previouslySelectedPlace = locationState.data?.selectedPlace;
    let submissionLocation = locationState.data;
    if (requiresCurrentLocation) {
      setLocationState({ data: null, status: "loading", text: copy.reportGpsLoading });
      setLocationEditorOpen(false);
    }
    setSubmitState({
      status: "loading",
      text: requiresCurrentLocation ? copy.reportGpsLoading : copy.reportSending,
    });
    let result;
    try {
      const submission = await runLiveReportSubmission({
        inFlightRef: submissionInFlightRef,
        operation: async () => {
          if (requiresCurrentLocation) {
            let refreshedLocation;
            try {
              refreshedLocation = await Promise.resolve(
                onLocate
                  ? onLocate({ locations, maxDistanceKm, requireCurrent: true })
                  : { ok: false, reason: "unavailable" },
              );
            } catch (error) {
              refreshedLocation = {
                error: error instanceof Error ? error.message : String(error || ""),
                ok: false,
                reason: "location_verification_failed",
              };
            }
            if (!refreshedLocation?.ok) {
              return { ...refreshedLocation, locationVerificationFailed: true };
            }

            const canKeepSelectedPlace = !pilotRules
              && Array.isArray(refreshedLocation.nearbyPlaces)
              && refreshedLocation.nearbyPlaces.some(
                (place) => place?.place === previouslySelectedPlace,
              );
            submissionLocation = canKeepSelectedPlace
              ? { ...refreshedLocation, selectedPlace: previouslySelectedPlace }
              : refreshedLocation;
            setLocationState({
              data: submissionLocation,
              status: "ready",
              text: copy.reportLocationReady,
            });
            setSubmitState({ status: "loading", text: copy.reportSending });
          }

          if (managedReport && editIntent === "update") {
            return onManagedUpdate?.(managedReport)
              || Promise.resolve({ ok: false, reason: "unavailable" });
          }
          if (nearbyMatch) {
            return onConfirmNearby?.({
              expiresAt: nearbyMatch.expiresAt,
              groupId: nearbyMatch.groupId,
              vote: "yes",
            }) || Promise.resolve({ ok: false, reason: "unavailable" });
          }
          return onSubmit(selectedTypeId, submissionLocation, {
            acceptedTerms: hasAcceptedTerms,
            policyVersion: COMMUNITY_GUIDELINES_POLICY_VERSION,
            ...(pilotRules ? {
              correctionReport: editIntent === "correct" ? managedReport : correctionReport,
              replacementReport: editIntent === "replace" ? managedReport : null,
              replacementToken: pendingEdit?.replacementToken || replacementToken,
            } : {}),
          });
        },
      });
      if (!submission.started) return;
      result = submission.result;
    } catch (error) {
      result = {
        error: error instanceof Error ? error.message : String(error || ""),
        ok: false,
        reason: "request_failed",
        ...(managedReport ? { uncertain: true } : {}),
      };
    }
    if (result?.locationVerificationFailed) {
      setLocationState({
        data: null,
        status: "error",
        text: getReportFeedback(copy, result),
      });
    }
    if (result?.ok) {
      setPendingEdit(null);
      rememberCommunityGuidelinesConsent(
        COMMUNITY_GUIDELINES_POLICY_VERSION,
        { storage: personalStorage },
      );
      rememberReportLocationNoticeConsent({ storage: personalStorage });
      if (!nearbyMatch) onPersonalStateChange?.();
    } else if (nearbyMatch) {
      const errorCode = getCommunityMutationErrorCode(result);
      if (errorCode === "community_self_confirmation_not_allowed") {
        onSelfMatchDetected?.(nearbyMatch.groupId);
      } else if (Number(result?.status) === 404) {
        setIgnoredMatchGroupIds((current) => (
          current.includes(nearbyMatch.groupId)
            ? current
            : [...current, nearbyMatch.groupId]
        ));
      }
    }
    const uncertainEdit = Boolean(managedReport && !result?.ok && (result?.uncertain
      || result?.reason === "pending_operation"
      || (editIntent === "update" && result?.reason === "request_failed"
        && (!result.status || result.status >= 500 || result.status === 408))));
    if (managedReport && !result?.ok) {
      const withdrawn = result?.replacementWithdrawn === true || pendingEdit?.withdrawn === true;
      setPendingEdit(uncertainEdit || withdrawn ? {
        intent: editIntent, uncertain: uncertainEdit, withdrawn,
        replacementToken: result?.replacementToken || pendingEdit?.replacementToken,
      } : null);
      // A replacement may have retired the old report even if creation failed.
      // Refresh local receipts/token state on every result, not only success.
      onPersonalStateChange?.();
      if (["stale_or_imprecise", "location_required", "location_mismatch"].includes(result?.reason)) {
        setLocationState({
          data: null, status: "error",
          text: result.reason === "location_mismatch" ? copy.reportUpdateLocationError : copy.reportGpsUnavailable,
        });
      }
    }
    if (pilotRules && /replacement/.test(String(result?.code || result?.detail?.code || ""))) {
      onPersonalStateChange?.();
    }
    setSubmitState({
      expiresAt: nearbyMatch?.expiresAt || result?.report?.expiresAt || null,
      kind: nearbyMatch ? "confirmation" : "report",
      match: nearbyMatch,
      report: result?.report || null,
      editIntent,
      reportId: result?.report?.id || null,
      status: result?.ok ? "success" : "error",
      text: result?.replacementPhase ? getPilotMutationFeedback(result)
        : uncertainEdit ? copy.reportEditPending : getReportFeedback(copy, result),
      undoUntil: result?.undoUntil || null,
      expired: result?.expired === true,
    });
  };

  const handleUndo = async () => {
    if (!canUndo || isUndoing) return;

    setUndoing(true);
    const result = await onUndo(activeUndo.reportId);
    setUndoing(false);

    if (result?.ok) {
      setExpiredUndoKey(activeUndoKey);
      setSubmitState({ status: "idle", text: copy.reportUndoSuccess });
      onPersonalStateChange?.();
      return;
    }

    setSubmitState((current) => ({
      ...current,
      status: "error",
      text: copy.reportUndoError,
    }));
  };

  const successItem = submitState.report || submitState.match || null;
  const successTypeLabel = successItem
    ? successItem.typeLabel
      || copy.reportTypes[successItem.typeId]
      || copy.reportTypes.unknown
    : "";
  const isPilotReportSuccess = pilotStyle && submitState.kind === "report";
  const isCenteredReceipt = isSuccess && isPilotReportSuccess;
  const successDescription = submitState.expired
    ? "L’operazione era riuscita, ma questa osservazione è già scaduta."
    : submitState.editIntent === "update" ? copy.reportEditUpdatedBody
    : correctionReport || submitState.editIntent === "correct"
      ? "Correzione salvata. La scadenza resta invariata."
      : copy.reportSuccessBody;
  const SuccessReportIcon = PILOT_LIVE_REPORT_ICONS[successItem?.typeId] || Radio;
  const successHasIdentity = isPilotReportSuccess && Boolean(
    getItemCommunityIdentityPreview(successItem, {
      limit: 1,
      placeName: successItem?.place,
    }).totalCount,
  );
  const successExpiryLabel = getOwnReportExpiryLabel(
    copy,
    submitState.expiresAt || successItem?.expiresAt,
    receiptNow,
    { maxMinutes: isPilotReportSuccess ? 60 : undefined },
  );
  const nearbyMatchSummary = nearbyMatch
    ? getCommunityNearbyMatchSummary(copy, nearbyMatch)
    : "";
  const nearbyMatchNotice = nearbyMatchState === "own"
    ? copy.communityMatchOwn
    : nearbyMatchState === "voted"
      ? copy.communityMatchVoted
      : nearbyMatchSummary;

  const form = (
    <form
      aria-describedby={sheet ? reportDescriptionId : undefined}
      aria-labelledby={sheet ? reportTitleId : undefined}
      aria-modal={sheet ? "true" : undefined}
      className={[
        "mf-live-report-form",
        sheet ? "mf-live-report-form--sheet" : "",
        pilotStyle ? "mf-live-report-form--pilot" : "",
        isCenteredReceipt ? "mf-live-report-form--receipt" : "",
      ].filter(Boolean).join(" ")}
      id={sheet ? reportDialogId : undefined}
      onSubmit={handleSubmit}
      ref={dialogRef}
      role={sheet ? "dialog" : undefined}
      tabIndex={-1}
    >
      <div className="mf-live-report-form__header">
        {!isCenteredReceipt ? <div>
          <strong id={sheet ? reportTitleId : undefined}>
            {isSuccess ? copy.reportSuccessTitle : managedReport ? copy.reportEditTitle : correctionReport ? "Correggi osservazione" : copy.reportQuestion}
          </strong>
          <span id={sheet ? reportDescriptionId : undefined}>
            {isSuccess ? successDescription : managedReport ? editDescription : correctionReport ? "Puoi correggere fenomeno e Comune entro 5 minuti. La posizione viene verificata con il GPS." : replacementToken ? "Sostituzione senza attesa. Il nuovo invio conta nei limiti di 4/60 minuti e 12/24 ore." : copy.reportBody}
          </span>
        </div> : null}
        <AppIconButton
          ariaLabel={copy.reportClose}
          disabled={isSubmitting}
          icon={X}
          onClick={() => {
            if (!submissionInFlightRef.current) onCloseRef.current();
          }}
        />
      </div>
      <div className="mf-live-report-form__body">
        {isSuccess ? (
          <div
            aria-live="polite"
            className={`mf-live-report-success ${isPilotReportSuccess ? "mf-live-report-success--pilot-receipt" : ""}`.trim()}
            ref={successRef}
            role="status"
            tabIndex={-1}
          >
            <span aria-hidden="true" className="mf-live-report-success__icon">
              <Heart fill="currentColor" size={26} strokeWidth={2.1} />
            </span>
            {isPilotReportSuccess ? (
              <>
                <strong className="mf-live-report-success__title" id={sheet ? reportTitleId : undefined}>
                  {submitState.editIntent === "update" ? copy.reportEditUpdated : correctionReport || submitState.editIntent === "correct" ? "Osservazione corretta" : copy.reportSuccessReceipt}
                </strong>
                <p className="mf-live-report-success__description" id={sheet ? reportDescriptionId : undefined}>
                  {successDescription}
                </p>
                <div className="mf-live-report-success__summary">
                  <div className="mf-live-report-success__summary-row">
                    <div className="mf-live-report-success__phenomenon">
                      <span
                        aria-hidden="true"
                        className={`mf-live-report-success__phenomenon-icon mf-live-report-option--${successItem?.typeId || "unknown"}`}
                      >
                        <SuccessReportIcon size={17} strokeWidth={2.35} />
                      </span>
                      <strong>{successTypeLabel}</strong>
                    </div>
                    {successExpiryLabel ? (
                      <small className="mf-live-report-success__expiry">
                        {successExpiryLabel}
                      </small>
                    ) : null}
                  </div>
                  {successItem?.place ? (
                    <p className="mf-live-report-success__place">{successItem.place}</p>
                  ) : null}
                  {successHasIdentity ? (
                    <div className="mf-live-report-success__identity-block">
                      <small className="mf-live-report-success__identity-label">
                        {copy.reportSuccessIdentityLabel}
                      </small>
                      <CommunityIdentityPreview
                        className="mf-live-report-success__identity-inline"
                        item={successItem}
                        limit={1}
                        placeName={successItem?.place}
                      />
                    </div>
                  ) : null}
                </div>
              </>
            ) : (
              <>
                <strong>
                  {submitState.kind === "confirmation"
                    ? copy.reportSuccessConfirmation
                    : copy.ownReportLabel}
                </strong>
                <span>
                  {[successTypeLabel, successItem?.place].filter(Boolean).join(" · ")}
                </span>
                <CommunityIdentityPreview
                  className="mf-live-report-success__identity"
                  item={successItem}
                  limit={submitState.kind === "confirmation" ? 3 : 1}
                  placeName={successItem?.place}
                />
                {successExpiryLabel ? <small>{successExpiryLabel}</small> : null}
              </>
            )}
          </div>
        ) : (
          <>
            {pendingIntent ? <p className="mf-live-report-feedback" role="status">Verifica dell’operazione precedente{pendingIntent.selectedPlace ? ` a ${pendingIntent.selectedPlace}` : ""}. Il nuovo GPS serve a riprovare la stessa operazione.</p> : null}
            <div className="mf-live-report-options">
              {options.map((option) => {
                const reportIcons = pilotStyle ? PILOT_LIVE_REPORT_ICONS : LIVE_REPORT_ICONS;
                const Icon = reportIcons[option.id] || Radio;

                return (
                  <button
                    aria-pressed={selectedTypeId === option.id}
                    className={`mf-live-report-option mf-live-report-option--${option.id} ${selectedTypeId === option.id ? "is-active" : ""}`.trim()}
                    disabled={isSubmitting || Boolean(pendingIntent?.typeId) || Boolean(pendingEdit)}
                    key={option.id}
                    onClick={() => {
                      setSelectedTypeId(option.id);
                      setSubmitState({ status: "idle", text: "" });
                    }}
                    type="button"
                  >
                    <span aria-hidden="true"><Icon size={17} strokeWidth={2.35} /></span>
                    <strong>{option.label}</strong>
                  </button>
                );
              })}
            </div>
            {previewOnly || simulationOnly ? (
              <p className="mf-live-note mf-live-note--official" role="status">
                <ShieldCheck aria-hidden="true" size={15} strokeWidth={2.3} />
                {copy.reportPreviewOnly}
              </p>
            ) : null}
            <div className={`mf-live-report-location mf-live-report-location--${locationState.status}`}>
              <span className="mf-live-report-location__icon" aria-hidden="true">
                <LocateFixed size={18} strokeWidth={2.35} />
              </span>
              <div className="mf-live-report-location__copy">
                {!pilotStyle || !isLocationReady ? (
                  <small>{isLocationReady ? copy.reportLocation : copy.reportLocationStatus}</small>
                ) : null}
                <strong>
                  {isLocationReady
                    ? pilotStyle
                      ? copy.reportLocationFrom.replace("{place}", locationState.data.selectedPlace)
                      : locationState.data.selectedPlace
                    : locationState.text}
                </strong>
                {pilotStyle && isLocationReady ? (
                  <>
                    <span className="mf-live-report-location__source">
                      {previewOnly || simulationOnly || locationState.data.source === "local_preview"
                        ? copy.reportLocationPreviewSource
                        : copy.reportLocationGpsSource}
                    </span>
                    <span className="mf-live-report-location__rule">
                      {copy.reportLocationRadius.replace("{distance}", String(maxDistanceKm))}
                    </span>
                  </>
                ) : null}
              </div>
              <div className="mf-live-report-location__actions">
                {!pilotStyle && isLocationReady && locationState.data.nearbyPlaces.length > 1 ? (
                  <AppIconButton
                    aria-controls={reportLocationSelectorId}
                    aria-expanded={isLocationEditorOpen}
                    ariaLabel={copy.reportLocationChange}
                    disabled={isSubmitting}
                    icon={Pencil}
                    onClick={() => setLocationEditorOpen((current) => !current)}
                    variant="ghost"
                  />
                ) : null}
                {!isLocationReady ? (
                  <AppIconButton
                    ariaLabel={copy.reportGpsRetry}
                    disabled={isSubmitting || locationState.status === "loading"}
                    icon={RefreshCw}
                    onClick={requestLocation}
                    variant="ghost"
                  />
                ) : null}
              </div>
            </div>
            {!pilotStyle && isLocationEditorOpen && isLocationReady ? (
              <label className="mf-live-report-location__selector" id={reportLocationSelectorId}>
                <span>{copy.reportLocationChange}</span>
                <select
                  disabled={isSubmitting}
                  onChange={(event) => {
                    const selectedPlace = event.target.value;
                    setLocationState((current) => ({
                      ...current,
                      data: { ...current.data, selectedPlace },
                    }));
                    setLocationEditorOpen(false);
                    setSubmitState({ status: "idle", text: "" });
                  }}
                  value={locationState.data.selectedPlace}
                >
                  {locationState.data.nearbyPlaces.map((location) => (
                    <option key={location.place} value={location.place}>{location.place}</option>
                  ))}
                </select>
                <small>{copy.reportLocationLimit.replace("{distance}", String(maxDistanceKm))}</small>
              </label>
            ) : null}
            {nearbyMatch ? (
              <div aria-live="polite" className={`mf-live-report-match mf-live-report-match--${nearbyMatchState}`} role="status">
                <span aria-hidden="true"><UsersRound size={19} strokeWidth={2.25} /></span>
                <div>
                  <strong>{nearbyMatchNotice}</strong>
                  {nearbyMatch.place ? <small>{nearbyMatch.place}</small> : null}
                </div>
              </div>
            ) : null}
            <p className="mf-live-report-location-privacy" id={`${reportDialogId}-location-privacy`}>
              {copy.reportPreciseLocationNotice}
            </p>
            {!hasAcceptedTerms ? (
              <fieldset className="mf-live-report-terms">
                <legend>{copy.reportTermsTitle}</legend>
                <label>
                  <input
                    aria-describedby={`${reportDialogId}-location-privacy`}
                    checked={false}
                    disabled={isSubmitting}
                    onChange={(event) => {
                      if (!event.target.checked) return;
                      if (!previewOnly) {
                        rememberCommunityGuidelinesConsent(
                          COMMUNITY_GUIDELINES_POLICY_VERSION,
                          { storage: personalStorage },
                        );
                        rememberReportLocationNoticeConsent({ storage: personalStorage });
                      }
                      setHasAcceptedTerms(true);
                      setSubmitState({ status: "idle", text: "" });
                    }}
                    type="checkbox"
                  />
                  <span>{copy.reportTermsAccept}</span>
                </label>
                <details>
                  <summary>{copy.reportTermsRead}</summary>
                  <p>{copy.reportTermsBody}</p>
                </details>
              </fieldset>
            ) : null}
            {pilotStyle ? (
              <p className="mf-live-report-duration">
                <Clock aria-hidden="true" size={15} strokeWidth={2.3} />
                <span>{managedReport ? editHint : correctionReport ? "La correzione non prolunga la scadenza dell’osservazione." : ttlLabel || copy.reportExpires}</span>
              </p>
            ) : (
              <div className="mf-live-report-meta">
                <strong>{ttlLabel || copy.reportExpires}</strong>
                <span>{copy.reportSafety}</span>
              </div>
            )}
            {submitState.text ? (
              <p
                aria-live="polite"
                className={`mf-live-report-feedback mf-live-report-feedback--${submitState.status}`}
                role="status"
              >
                {submitState.text}
              </p>
            ) : null}
          </>
        )}
      </div>
      <div className="mf-live-report-form__footer">
        {isSuccess || ["own", "voted"].includes(nearbyMatchState) ? (
          <AppButton
            className="mf-live-report-map-action"
            icon={MapPin}
            onClick={() => {
              if (onViewMap) onViewMap();
              else onCloseRef.current();
            }}
            type="button"
          >
            {copy.reportSuccessMap}
          </AppButton>
        ) : (
          <AppButton
            className="mf-live-report-submit"
            disabled={previewOnly || !selectedTypeId || !isLocationReady || !hasAcceptedTerms || isSubmitting || canUndo || editIntent === "unavailable" || (editIntent === "update" && !onManagedUpdate)}
            icon={nearbyMatch ? UsersRound : Send}
            type="submit"
          >
            {previewOnly
              ? nearbyMatch
                ? copy.confirmationAction
                : copy.reportPreviewSubmit
              : isSubmitting
                ? copy.reportSending
                : nearbyMatch
                  ? copy.confirmationAction
                  : managedReport ? editSubmitLabel
                    : correctionReport ? "Conferma correzione" : copy.reportSubmit}
          </AppButton>
        )}
        {pilotStyle && !isSuccess && !["own", "voted"].includes(nearbyMatchState) ? (
          <small className="mf-live-report-safety">{copy.reportSafety}</small>
        ) : null}
        {canUndo ? (
          <AppButton
            className="mf-live-report-undo"
            disabled={isUndoing}
            icon={Undo2}
            onClick={handleUndo}
            type="button"
            variant="secondary"
          >
            {copy.reportUndo}
          </AppButton>
        ) : null}
      </div>
    </form>
  );

  if (!sheet) return form;

  const layer = (
    <div className="mf-live-report-layer">
      <button
        aria-hidden="true"
        className="mf-live-report-layer__backdrop"
        onClick={() => {
          if (!submissionInFlightRef.current) onCloseRef.current();
        }}
        tabIndex={-1}
        type="button"
      />
      {form}
    </div>
  );

  return globalThis.document?.body
    ? createPortal(layer, globalThis.document.body)
    : layer;
}

export function CommunityExpiredUpdateDialog({ copy, onClose, onNewObservation }) {
  const dialogRef = useRef(null);
  const generatedId = useId();
  const titleId = `community-expired-update-title-${generatedId}`;
  const descriptionId = `community-expired-update-description-${generatedId}`;
  usePilotBackHandler(onClose);

  useEffect(() => isolateCommunityModalBackground(), []);

  useEffect(() => {
    const documentLike = globalThis.document;
    if (!documentLike) return undefined;
    const focusFrame = globalThis.requestAnimationFrame?.(
      () => dialogRef.current?.focus?.({ preventScroll: true }),
    );
    const handleKeyDown = (event) => {
      if (event.key === "Escape") {
        event.preventDefault();
        onClose?.();
        return;
      }
      trapCommunityModerationFocus(event, dialogRef.current, documentLike.activeElement);
    };
    documentLike.addEventListener("keydown", handleKeyDown);
    return () => {
      if (focusFrame !== undefined) globalThis.cancelAnimationFrame?.(focusFrame);
      documentLike.removeEventListener("keydown", handleKeyDown);
    };
  }, [onClose]);

  const dialog = (
    <div className="mf-live-moderation-backdrop">
      <section
        aria-describedby={descriptionId}
        aria-labelledby={titleId}
        aria-modal="true"
        className="mf-live-moderation-dialog mf-live-expired-update-dialog"
        ref={dialogRef}
        role="dialog"
        tabIndex={-1}
      >
        <div className="mf-live-moderation-dialog__heading">
          <div>
            <strong id={titleId}>{copy.reportUpdateExpiredTitle}</strong>
            <p id={descriptionId}>{copy.reportUpdateExpiredBody}</p>
          </div>
        </div>
        <div className="mf-live-expired-update-dialog__actions">
          <button onClick={onClose} type="button">{copy.reportUpdateExpiredClose}</button>
          <button className="is-primary" onClick={onNewObservation} type="button">
            {copy.reportUpdateExpiredNew}
          </button>
        </div>
      </section>
    </div>
  );

  return globalThis.document?.body ? createPortal(dialog, globalThis.document.body) : dialog;
}

export function CommunityPendingUpdateRecovery({ compact = false, copy, onRetry, pending }) {
  const [status, setStatus] = useState("idle");
  const titleId = `community-pending-update-title-${useId()}`;

  const retry = async () => {
    if (status === "loading" || !onRetry) return;
    setStatus("loading");
    const result = await Promise.resolve(onRetry({
      ...pending,
      revision: pending.expectedRevision,
    }))
      .catch(() => ({ ok: false, reason: "request_failed" }));
    if (result?.ok) setStatus("success");
    else if ([
      "observation_expired",
      "observation_conflict",
      "observation_rejected",
    ].includes(result?.reason)) {
      setStatus("idle");
    } else setStatus("error");
  };

  return (
    <aside
      aria-labelledby={titleId}
      className={`mf-live-pending-update ${compact ? "mf-live-pending-update--overlay" : ""}`.trim()}
    >
      <div>
        <strong id={titleId}>{copy.reportUpdatePendingTitle}</strong>
        <span>{copy.reportUpdatePendingBody}</span>
        {status === "error" ? (
          <small aria-live="polite" role="status">{copy.reportUpdateError}</small>
        ) : null}
      </div>
      <button disabled={status === "loading"} onClick={retry} type="button">
        <RefreshCw aria-hidden="true" size={14} strokeWidth={2.3} />
        {status === "loading"
          ? copy.reportUpdating
          : status === "error"
            ? copy.reportUpdateRetry
            : copy.reportUpdatePendingAction}
      </button>
    </aside>
  );
}

function CommunityPanel({
  compactLayout = false,
  language = "it",
  model: sourceModel,
  officialAlert = null,
  onOfficialAlertOpen,
  onReportConfirm,
  onReportLocate,
  onReportSubmit,
  onReportUndo,
  onReportUpdate,
  onReportWithdraw,
  onReportRefresh,
  onReportsViewed,
  pendingReportUndo,
  pendingReportUpdates = [],
  personalStorage,
  reportingEnabled,
  reportingPreview,
  reportingSimulation,
  reportingUnavailableText,
  radarModel = null,
  sharedReportId = "",
  sharedReportLoadSettled = false,
  theme = "light",
  webcamModel = null,
}) {
  const readPersonalState = useCallback(
    () => readCommunityPersonalState({ storage: personalStorage }),
    [personalStorage],
  );
  const [personalState, setPersonalState] = useState(readPersonalState);
  const model = useMemo(
    () => filterCommunityExpiredReportsFromMap(
      filterCommunityWithdrawnReportsModel(sourceModel, personalState),
      personalState,
    ),
    [personalState, sourceModel],
  );
  const [isReportFormOpen, setReportFormOpen] = useState(false);
  const pilotRules = isDefinitiveAppExperience() || isLocalCommunityPilot();
  const [editingReport, setEditingReport] = useState(null);
  const [managedReport, setManagedReport] = useState(null);
  const [replacement, setReplacement] = useState(() => pilotRules && !reportingSimulation ? readPilotReplacement({ storage: personalStorage }) : null);
  const [pendingMutation, setPendingMutation] = useState(() => pilotRules && !reportingSimulation ? readPilotPendingOperations({ storage: personalStorage })[0] || null : null);
  const [recoveryText, setRecoveryText] = useState("");
  const [isRecovering, setRecovering] = useState(false);
  const [expiredUpdateRecovery, setExpiredUpdateRecovery] = useState(null);
  const [updateRejectionNotice, setUpdateRejectionNotice] = useState(false);
  const [dismissedUndoKey, setDismissedUndoKey] = useState("");
  const [confirmationCountState, setConfirmationCountState] = useState(() => ({
    counts: {},
    model: sourceModel,
  }));
  const [confirmationStatuses, setConfirmationStatuses] = useState({});
  const [inferredOwnGroupIds, setInferredOwnGroupIds] = useState([]);
  const [pendingMapFocus, setPendingMapFocus] = useState(false);
  const [pendingConfirmation, setPendingConfirmation] = useState(null);
  const confirmationTriggerRef = useRef(null);
  const confirmationCountsByGroup = confirmationCountState.model === sourceModel
    ? confirmationCountState.counts
    : {};
  const mapRegionRef = useRef(null);
  const panelRef = useRef(null);
  const reportSheetId = `community-report-sheet-${useId()}`;
  const communityMapRegionId = `community-map-region-${useId()}`;
  const mapMarkers = useMemo(
    () => filterCommunityMapMarkers(model.markers, personalState, model.copy),
    [model.copy, model.markers, personalState],
  );
  const handleReportsViewed = useCallback(() => {
    onReportsViewed?.({ ...model, markers: mapMarkers }, personalState);
  }, [mapMarkers, model, onReportsViewed, personalState]);
  const activeCount = getCommunityActiveCount(model.items);
  const communitySummary = compactLayout
    ? getCommunityRecentSummary(model.copy, activeCount)
    : getCommunityActiveSummary(model.copy, activeCount);
  const contributionCount = getCommunityContributionCount(personalState);
  const availability = getCommunityAvailability({
    ...model,
    markers: mapMarkers,
  });
  const updatedLabel = getCommunityUpdatedLabel(model.copy, {
    ageMs: model.sourceAgeMs,
    sourceUpdatedAt: model.sourceUpdatedAt,
  });
  const visibleItems = model.items.slice(0, 3);
  const webcamList = useMemo(() => {
    const cameras = [
      ...(webcamModel?.mapCandidates || []),
      ...(webcamModel?.groups || []).flatMap((group) => group.cameras || []),
    ];
    const seen = new Set();
    return cameras.filter((camera) => {
      if (!camera?.id || seen.has(camera.id)) return false;
      seen.add(camera.id);
      return true;
    });
  }, [webcamModel?.groups, webcamModel?.mapCandidates]);
  const activeGroups = availability.kind === "ready"
    ? mapMarkers.flatMap((marker) => marker.phenomena || [marker])
    : [];
  const pendingUndoKey = pendingReportUndo?.reportId && pendingReportUndo?.undoUntil
    ? `${pendingReportUndo.reportId}:${pendingReportUndo.undoUntil}`
    : "";
  const shouldShowReportForm = isReportFormOpen
    || Boolean(pendingUndoKey && pendingUndoKey !== dismissedUndoKey);
  const reportSubmit = reportingPreview
    ? blockCommunityReportPreviewSubmission
    : onReportSubmit;
  const allowCommunityMutations = reportingEnabled && !reportingPreview;
  const pendingReportUpdate = pendingReportUpdates.find((pending) => (
    !personalState.reports.some((report) => report.reportId === pending.reportId)
  )) || null;
  const closeReportForm = useCallback(() => {
    setReportFormOpen(false);
    setEditingReport(null);
    setManagedReport(null);
    if (isLocalCommunityPilot() && !reportingSimulation) {
      setPendingMutation(readPilotPendingOperations({ storage: personalStorage })[0] || null);
      setReplacement(readPilotReplacement({ storage: personalStorage }));
    }
    if (pendingUndoKey) setDismissedUndoKey(pendingUndoKey);
  }, [pendingUndoKey, personalStorage, reportingSimulation]);
  const viewCommunityMap = useCallback(() => {
    closeReportForm();
    setPendingMapFocus(true);
  }, [closeReportForm]);

  useEffect(() => {
    if (!pendingMapFocus) return undefined;

    const focusFrame = globalThis.requestAnimationFrame?.(() => {
      const mapRegion = mapRegionRef.current?.querySelector?.('[role="region"]');
      if (!mapRegion) return;

      if (!compactLayout) {
        mapRegion.scrollIntoView?.({ behavior: "smooth", block: "center" });
      }
      mapRegion.focus?.({ preventScroll: true });
      setPendingMapFocus(false);
    });
    return () => {
      if (focusFrame !== undefined) globalThis.cancelAnimationFrame?.(focusFrame);
    };
  }, [compactLayout, pendingMapFocus]);

  useEffect(() => {
    const timeoutId = globalThis.setTimeout?.(
      () => setPersonalState(readPersonalState()),
      0,
    );
    return () => {
      if (timeoutId !== undefined) globalThis.clearTimeout?.(timeoutId);
    };
  }, [readPersonalState, sourceModel.items, sourceModel.markers]);

  useEffect(() => {
    const timeoutId = globalThis.setTimeout?.(() => {
      setPersonalState((current) => {
        const acquired = getAcquiredCommunityMapWithdrawals(sourceModel, current);
        if (!acquired.length) return current;

        return acquired.reduce(
          (next, withdrawal) => rememberCommunityMapWithdrawal(
            next,
            withdrawal,
            { storage: personalStorage },
          ),
          current,
        );
      });
    }, 0);
    return () => {
      if (timeoutId !== undefined) globalThis.clearTimeout?.(timeoutId);
    };
  }, [personalStorage, sourceModel]);

  useEffect(() => {
    const expiries = [
      ...personalState.reports,
      ...personalState.votes,
      ...personalState.mapWithdrawals,
      ...(personalState.reportWithdrawals || []),
      ...(personalState.reportExpirations || []),
      personalState.dailyContributions,
    ]
      .map((entry) => Number(entry.expiresAt))
      .filter((expiresAt) => Number.isFinite(expiresAt) && expiresAt > Date.now());
    if (!expiries.length) return undefined;

    const timeoutId = globalThis.setTimeout?.(
      () => setPersonalState(readPersonalState()),
      Math.max(0, Math.min(...expiries) - Date.now()) + 25,
    );
    return () => {
      if (timeoutId !== undefined) globalThis.clearTimeout?.(timeoutId);
    };
  }, [personalState, readPersonalState]);

  const performReportConfirmation = async ({ expiresAt, groupId, vote }) => {
    if (
      !onReportConfirm
      || getOwnCommunityReport(personalState, groupId)
      || getCommunityVote(personalState, groupId) === "no"
    ) {
      return { ok: false, reason: "unavailable" };
    }

    setConfirmationStatuses((current) => ({ ...current, [groupId]: "loading" }));
    const result = await onReportConfirm(groupId, vote, {
      acceptedTerms: true,
      policyVersion: COMMUNITY_GUIDELINES_POLICY_VERSION,
    });
    setConfirmationStatuses((current) => ({
      ...current,
      [groupId]: result?.ok ? "success" : "error",
    }));

    if (result?.ok) {
      const returnedCounts = result.confirmations || result.group?.confirmations;
      if (returnedCounts) {
        setConfirmationCountState((current) => ({
          counts: {
            ...(current.model === sourceModel ? current.counts : {}),
            [groupId]: {
              no: Math.max(0, Number(returnedCounts.no) || 0),
              yes: Math.max(0, Number(returnedCounts.yes) || 0),
            },
          },
          model: sourceModel,
        }));
      }
      let nextPersonalState = rememberCommunityVote(
        readPersonalState(),
        {
          expiresAt,
          groupId,
          vote: result.vote || vote,
        },
        { storage: personalStorage },
      );
      if (Math.max(0, Number(result.confirmations?.no) || 0) >= 3) {
        nextPersonalState = rememberCommunityMapWithdrawal(
          nextPersonalState,
          { expiresAt, groupId },
          { storage: personalStorage },
        );
      }
      setPersonalState(nextPersonalState);
    } else if (
      getCommunityMutationErrorCode(result) === "community_self_confirmation_not_allowed"
    ) {
      setInferredOwnGroupIds((current) => (
        current.includes(groupId) ? current : [...current, groupId]
      ));
    }
    return result;
  };

  const requestReportConfirmation = async (groupId, vote, trigger) => {
    const entry = model.items.find((item) => item.groupId === groupId)
      || model.markers
        .flatMap((marker) => marker.phenomena || [marker])
        .find((item) => item.groupId === groupId);
    const command = { expiresAt: entry?.expiresAt, groupId, vote };

    if (!hasCommunityGuidelinesConsent(
      COMMUNITY_GUIDELINES_POLICY_VERSION,
      { storage: personalStorage },
    )) {
      confirmationTriggerRef.current = compactLayout ? trigger : null;
      setPendingConfirmation(command);
      return { ok: false, pendingConsent: true };
    }

    return performReportConfirmation(command);
  };

  const restoreConfirmationFocus = useCallback(() => {
    const trigger = confirmationTriggerRef.current;
    confirmationTriggerRef.current = null;
    globalThis.requestAnimationFrame?.(() => {
      if (trigger?.isConnected) trigger.focus?.({ preventScroll: true });
      else if (compactLayout) {
        mapRegionRef.current
          ?.querySelector?.('[role="region"]')
          ?.focus?.({ preventScroll: true });
      } else {
        panelRef.current?.focus?.({ preventScroll: true });
      }
    });
  }, [compactLayout]);
  const restoreCommunityPanelFocus = useCallback(() => {
    globalThis.requestAnimationFrame?.(() => {
      const mapRegion = mapRegionRef.current?.querySelector?.('[role="region"]');
      if (mapRegion) mapRegion.focus?.({ preventScroll: true });
      else panelRef.current?.focus?.({ preventScroll: true });
    });
  }, []);
  const closeExpiredUpdateRecovery = useCallback(() => {
    setExpiredUpdateRecovery(null);
    restoreCommunityPanelFocus();
  }, [restoreCommunityPanelFocus]);

  const acceptConfirmationTerms = async () => {
    const command = pendingConfirmation;
    rememberCommunityGuidelinesConsent(
      COMMUNITY_GUIDELINES_POLICY_VERSION,
      { storage: personalStorage },
    );
    if (command) await performReportConfirmation(command);
    setPendingConfirmation(null);
    restoreConfirmationFocus();
  };
  const withdrawOwnReport = async (reportId, options) => {
    if (!onReportWithdraw) return { ok: false, reason: "unavailable" };
    const result = await onReportWithdraw(reportId, options);
    if (result?.ok) setPersonalState(readPersonalState());
    if (pilotRules) setPendingMutation(readPilotPendingOperations({ storage: personalStorage })[0] || null);
    return result;
  };
  const correctOwnReport = (report) => {
    setManagedReport(null);
    setEditingReport(report);
    setReportFormOpen(true);
  };
  const manageOwnReport = (report) => {
    setEditingReport(null);
    setManagedReport({
      ...report,
      pendingUpdate: pendingReportUpdates.some((pending) => pending.reportId === report.reportId),
    });
    setReportFormOpen(true);
  };
  const replaceOwnReport = async (report) => {
    const result = await withdrawOwnReport(report.reportId, { replace: true, report });
    if (result?.ok && result.replacementToken) {
      setReplacement(reportingSimulation ? { token: result.replacementToken } : readPilotReplacement({ storage: personalStorage }));
      setEditingReport(null);
      setReportFormOpen(true);
    }
    return result;
  };
  const recoverMutation = async () => {
    if (!pendingMutation || isRecovering) return;
    setRecovering(true);
    let result = await reconcilePilotReportOperation(pendingMutation, { storage: personalStorage });
    if (result.notFound && ["withdraw", "replace"].includes(pendingMutation.kind)) {
      result = await onReportWithdraw?.(pendingMutation.reportId, {
        replace: pendingMutation.kind === "replace",
        report: { reportId: pendingMutation.reportId, revision: pendingMutation.expectedRevision },
      }) || result;
    }
    if (result.ok && onReportRefresh) {
      try { await onReportRefresh(); } catch { /* Accepted receipt remains recoverable even when the feed is offline. */ }
    }
    setRecovering(false);
    setPersonalState(readPersonalState());
    setPendingMutation(readPilotPendingOperations({ storage: personalStorage })[0] || null);
    setReplacement(readPilotReplacement({ storage: personalStorage }));
    if (result.ok) {
      setRecoveryText("");
      if (result.replacementToken) setReportFormOpen(true);
    } else {
      setRecoveryText(getPilotMutationFeedback(result));
      if (result.notFound && ["create", "correct"].includes(pendingMutation.kind)) {
        setEditingReport(pendingMutation.kind === "correct" ? {
          reportId: pendingMutation.reportId, revision: pendingMutation.expectedRevision,
          typeId: pendingMutation.typeId,
        } : null);
        setReportFormOpen(true);
      }
    }
  };
  const updateOwnReport = async (report) => {
    if (!onReportUpdate) return { ok: false, reason: "unavailable" };
    const result = await onReportUpdate(report);
    setPersonalState(readPersonalState());
    if (result?.reason === "observation_expired") {
      closeReportForm();
      setExpiredUpdateRecovery({
        reportId: result.reportId,
        serverState: result.serverState || null,
      });
    } else if (result?.reason === "observation_rejected") {
      closeReportForm();
      setUpdateRejectionNotice(true);
    }
    return result;
  };

  const renderCommunityMap = (immersive = false) => (
    <CommunityMap
      confirmationCountsByGroup={confirmationCountsByGroup}
      confirmationStatuses={confirmationStatuses}
      copy={model.copy}
      immersive={immersive}
      inferredOwnGroupIds={inferredOwnGroupIds}
      markers={mapMarkers}
      onConfirm={allowCommunityMutations ? requestReportConfirmation : undefined}
      onUpdate={allowCommunityMutations && onReportUpdate ? updateOwnReport : undefined}
      onWithdraw={allowCommunityMutations && onReportWithdraw ? withdrawOwnReport : undefined}
      onCorrect={pilotRules && allowCommunityMutations ? correctOwnReport : undefined}
      onEdit={pilotRules && compactLayout && allowCommunityMutations ? manageOwnReport : undefined}
      onReplace={pilotRules && allowCommunityMutations && onReportWithdraw ? replaceOwnReport : undefined}
      personalState={personalState}
      theme={theme}
    />
  );
  const reportFormSheet = shouldShowReportForm ? (
    <CommunityReportForm
      activeGroups={activeGroups}
      copy={model.copy}
      correctionReport={editingReport}
      managedReport={managedReport}
      onManagedUpdate={allowCommunityMutations && onReportUpdate ? updateOwnReport : undefined}
      replacementToken={!editingReport ? replacement?.token || "" : ""}
      dialogId={reportSheetId}
      locations={model.reportLocations}
      maxDistanceKm={model.maxDistanceKm}
      onClose={closeReportForm}
      onConfirmNearby={allowCommunityMutations ? performReportConfirmation : undefined}
      onLocate={onReportLocate}
      onPersonalStateChange={() => {
        setPersonalState(readPersonalState());
        if (pilotRules) setReplacement(reportingSimulation ? null : readPilotReplacement({ storage: personalStorage }));
      }}
      onSelfMatchDetected={(groupId) => {
        setInferredOwnGroupIds((current) => (
          current.includes(groupId) ? current : [...current, groupId]
        ));
      }}
      onSubmit={reportSubmit}
      onUndo={reportingPreview ? undefined : onReportUndo}
      onViewMap={viewCommunityMap}
      options={model.reportOptions}
      pendingReportUndo={reportingPreview ? null : pendingReportUndo}
      personalStorage={personalStorage}
      personalState={personalState}
      pilotStyle={compactLayout}
      previewOnly={reportingPreview}
      selfMatchGroupIds={inferredOwnGroupIds}
      sheet
      simulationOnly={reportingSimulation}
      ttlLabel={model.ttlLabel}
    />
  ) : null;
  const pendingUpdateRecovery = allowCommunityMutations && pendingReportUpdate ? (
    <CommunityPendingUpdateRecovery
      compact={compactLayout}
      copy={model.copy}
      key={pendingReportUpdate.operationId}
      onRetry={updateOwnReport}
      pending={pendingReportUpdate}
    />
  ) : null;
  const pendingMutationRecovery = pilotRules && pendingMutation ? (
    <aside className={`mf-live-update-rejected ${compactLayout ? "mf-live-update-rejected--overlay" : ""}`.trim()}>
      <span role="status">{recoveryText || "Un’operazione è ancora da verificare. Recupera l’esito prima di un nuovo invio."}</span>
      <button disabled={isRecovering} onClick={recoverMutation} type="button">{isRecovering ? "Verifica…" : "Verifica esito"}</button>
    </aside>
  ) : null;
  const rejectedUpdateNotice = updateRejectionNotice ? (
    <aside
      aria-label={model.copy.reportUpdateRejected}
      className={`mf-live-update-rejected ${compactLayout ? "mf-live-update-rejected--overlay" : ""}`.trim()}
    >
      <span aria-live="polite" role="status">{model.copy.reportUpdateRejected}</span>
      <button
        aria-label={model.copy.reportUpdateExpiredClose}
        onClick={() => setUpdateRejectionNotice(false)}
        type="button"
      >
        <X aria-hidden="true" size={15} strokeWidth={2.4} />
      </button>
    </aside>
  ) : null;

  if (compactLayout) {
    return (
      <section
        aria-label={model.copy.liveMapTitle}
        className="mf-live-community-map-layer mf-live-community-map-layer--pilot mf-live-community-map-layer--inline mf-live-territory-workspace"
        id={communityMapRegionId}
        ref={panelRef}
      >
        <div className="mf-live-community-map-region" ref={mapRegionRef}>
          <TerritoryImmersiveMap
            communityAvailability={availability.kind}
            communityCopy={model.copy}
            confirmationCountsByGroup={confirmationCountsByGroup}
            confirmationStatuses={confirmationStatuses}
            inferredOwnGroupIds={inferredOwnGroupIds}
            inline
            key={webcamModel?.supported === false ? "webcams-disabled" : "webcams-enabled"}
            language={language}
            location={model.locationPoint || radarModel?.location}
            mapWebcams={webcamModel?.mapCandidates || []}
            markers={mapMarkers}
            onReportsViewed={onReportsViewed ? handleReportsViewed : undefined}
            onConfirm={allowCommunityMutations ? requestReportConfirmation : undefined}
            officialAlert={officialAlert}
            onOfficialAlertOpen={onOfficialAlertOpen}
            onReportRequest={reportingEnabled && reportSubmit
              ? () => setReportFormOpen(true)
              : undefined}
            onUpdate={allowCommunityMutations && onReportUpdate ? updateOwnReport : undefined}
            onWithdraw={allowCommunityMutations && onReportWithdraw ? withdrawOwnReport : undefined}
            onCorrect={pilotRules && allowCommunityMutations ? correctOwnReport : undefined}
            onEdit={pilotRules && allowCommunityMutations ? manageOwnReport : undefined}
            onReplace={pilotRules && allowCommunityMutations && onReportWithdraw ? replaceOwnReport : undefined}
            personalState={personalState}
            radarModel={radarModel}
            reportUnavailableText={reportingUnavailableText}
            reportItems={model.items}
            reportDialogId={reportSheetId}
            reportOpen={shouldShowReportForm}
            sharedReportId={sharedReportId}
            sharedReportLoadSettled={sharedReportLoadSettled}
            theme={theme}
            renderWebcamDetail={(camera, mediaOverlay) => (
              <WebcamPreview
                camera={camera}
                copy={model.copy}
                highPriority
                key={`${camera.id}:${camera.imageUrl}:${camera.fallbackImageUrl}:${camera.playerUrl}:${camera.mediaType}`}
                language={language}
                mediaOverlay={mediaOverlay}
                showIdentity={false}
              />
            )}
            webcamGroups={webcamModel?.groups || []}
            webcamList={webcamList}
            webcamsEnabled={webcamModel?.supported !== false}
          />
        </div>
        {pendingUpdateRecovery}
        {pendingMutationRecovery}
        {rejectedUpdateNotice}
        {reportFormSheet}
        {pendingConfirmation ? (
          <CommunityGuidelinesConsentDialog
            copy={model.copy}
            onAccept={acceptConfirmationTerms}
            onClose={() => {
              setPendingConfirmation(null);
              restoreConfirmationFocus();
            }}
          />
        ) : null}
        {expiredUpdateRecovery ? (
          <CommunityExpiredUpdateDialog
            copy={model.copy}
            onClose={closeExpiredUpdateRecovery}
            onNewObservation={() => {
              setExpiredUpdateRecovery(null);
              setReportFormOpen(true);
            }}
          />
        ) : null}
      </section>
    );
  }

  return (
    <section
      aria-labelledby="live-community-title"
      className="mf-live-card mf-live-card--community"
      ref={panelRef}
      tabIndex={-1}
    >
      <SectionHeader
        icon={Radio}
        meta={!availability.hasContent && ["loading", "error"].includes(availability.kind) ? (
          null
        ) : (
          <div className="mf-live-community-summary">
            <strong>{communitySummary}</strong>
            {updatedLabel ? <span>{updatedLabel}</span> : null}
            {contributionCount > 0 ? (
              <span
                aria-label={getCommunityContributionLabel(model.copy, contributionCount)}
                className="mf-live-community-contribution"
                role="img"
                title={getCommunityContributionLabel(model.copy, contributionCount)}
              >
                <Heart aria-hidden="true" fill="currentColor" size={12} strokeWidth={2.2} />
                <b aria-hidden="true">{contributionCount}</b>
              </span>
            ) : null}
          </div>
        )}
        title={compactLayout ? model.copy.territoryCommunityTitle : model.title}
        titleId="live-community-title"
      />
      {!compactLayout ? (
        <p className="mf-live-community-intro">{model.body}</p>
      ) : null}
      {reportingEnabled && reportSubmit ? (
        <>
          <AppButton
            aria-controls={reportSheetId}
            aria-expanded={shouldShowReportForm}
            aria-haspopup="dialog"
            className="mf-live-report-open"
            icon={Send}
            onClick={() => setReportFormOpen(true)}
            variant={compactLayout ? "primary" : "secondary"}
          >
            {compactLayout
              ? model.copy.reportObserveCompactCta
              : model.copy.reportObserveCta}
          </AppButton>
          {reportFormSheet}
        </>
      ) : onReportSubmit ? (
        <>
          {availability.hasContent ? <p className="mf-live-note mf-live-note--official" role="status">
            <ShieldCheck aria-hidden="true" size={15} strokeWidth={2.3} />
            {reportingUnavailableText}
          </p> : null}
        </>
      ) : null}
      {pendingUpdateRecovery}
      {pendingMutationRecovery}
      {rejectedUpdateNotice}
      {!availability.hasContent ? (
        <div
          className={`mf-live-community-state mf-live-community-state--${availability.kind}`}
          role="status"
        >
          {availability.kind === "empty" ? (
            <MapPin aria-hidden="true" size={20} strokeWidth={2.2} />
          ) : (
            <RefreshCw aria-hidden="true" size={20} strokeWidth={2.2} />
          )}
          <div>
            {compactLayout && availability.kind === "empty" ? (
              <>
                <strong>{model.copy.communityNoRecentTitle}</strong>
                <span>{model.copy.communityNoRecentBody}</span>
                <small>{model.copy.communityNoRecentCaution}</small>
              </>
            ) : (
              <span>
                {availability.kind === "loading"
                  ? model.copy.communityLoadingBody
                  : availability.kind === "error"
                    ? model.copy.communityErrorBody
                    : availability.kind === "stale"
                      ? model.copy.communityStaleBody
                      : model.copy.liveMapEmptyBody}
              </span>
            )}
          </div>
        </div>
      ) : null}
      {model.items.length ? (
        <div className="mf-live-community-feed">
          {!compactLayout ? <h3>{model.copy.communityFeedTitle}</h3> : null}
          <div
            aria-label={model.copy.communityFeedTitle}
            className={`mf-live-community-list ${compactLayout ? "mf-live-community-list--carousel" : ""}`.trim()}
            role={compactLayout ? "list" : undefined}
          >
            {visibleItems.map((item) => {
              const Icon = LIVE_REPORT_ICONS[item.typeId] || Radio;
              const confirmationSummary = getCommunityConfirmationSummary(
                model.copy,
                item.confirmations,
              );
              const denialLabel = getCommunityDenialLabel(model.copy, item.confirmations);
              const withdrawalLabel = getCommunityMapWithdrawalLabel(model.copy, item);
              const ownReport = getOwnCommunityReport(personalState, item.groupId);
              const isOwnReport = Boolean(
                ownReport || inferredOwnGroupIds.includes(item.groupId),
              );
              const ownExpiry = ownReport
                ? getOwnReportExpiryLabel(model.copy, ownReport.expiresAt)
                : "";
              const vote = getCommunityVote(personalState, item.groupId);
              const confirmationStatus = confirmationStatuses[item.groupId] || "idle";
              const votingLocked = vote === "no";

              return (
                <article
                  className={`mf-live-community-item mf-live-community-item--${item.typeId} ${isOwnReport ? "is-own" : ""}`.trim()}
                  key={item.id}
                  role={compactLayout ? "listitem" : undefined}
                >
                  <span aria-hidden="true"><Icon size={18} strokeWidth={2.25} /></span>
                  <div className="mf-live-community-item__copy">
                    <strong>{item.typeLabel}</strong>
                    <small>
                      {[item.place, item.distanceLabel, item.timeLabel]
                        .filter(Boolean)
                        .join(" · ")}
                    </small>
                    {!compactLayout ? (
                      <small className="mf-live-community-item__activity">
                        {[item.countLabel, confirmationSummary].filter(Boolean).join(" · ")}
                      </small>
                    ) : null}
                    {denialLabel || withdrawalLabel ? (
                      <small className="mf-live-community-item__denial-status">
                        {[denialLabel, withdrawalLabel].filter(Boolean).join(" · ")}
                      </small>
                    ) : null}
                    {isOwnReport ? (
                      <>
                        <small className="mf-live-community-item__own">
                          {[model.copy.ownReportLabel, ownExpiry].filter(Boolean).join(" · ")}
                        </small>
                        {ownReport ? (
                          <CommunityIdentityPreview
                            className="mf-live-community-source"
                            item={ownReport}
                            limit={1}
                            placeName={ownReport.place || item.place}
                          />
                        ) : null}
                      </>
                    ) : (
                      <CommunityIdentityPreview
                        className="mf-live-community-source"
                        item={item}
                        limit={3}
                        placeName={item.place}
                      />
                    )}
                  </div>
                  <div className="mf-live-community-item__actions">
                    {!isOwnReport && allowCommunityMutations && onReportConfirm ? (
                      <>
                        <button
                          className="mf-live-community-item__confirm"
                          disabled={confirmationStatus === "loading" || votingLocked}
                          onClick={(event) => requestReportConfirmation(
                            item.groupId,
                            "yes",
                            event.currentTarget,
                          )}
                          type="button"
                        >
                          {vote === "yes"
                            ? model.copy.confirmationDone
                            : model.copy.confirmationAction}
                        </button>
                        <button
                          aria-label={`${model.copy.confirmationEndedAction}. ${model.copy.denialExplanation}`}
                          className="mf-live-community-item__deny"
                          disabled={confirmationStatus === "loading" || votingLocked}
                          onClick={(event) => requestReportConfirmation(
                            item.groupId,
                            "no",
                            event.currentTarget,
                          )}
                          title={model.copy.denialExplanation}
                          type="button"
                        >
                          {votingLocked
                            ? model.copy.denialDone
                            : model.copy.confirmationEndedAction}
                        </button>
                      </>
                    ) : null}
                  </div>
                </article>
              );
            })}
          </div>
        </div>
      ) : null}
      {availability.hasContent && !compactLayout ? (
        <div
          className="mf-live-community-map-region"
          id={communityMapRegionId}
          ref={mapRegionRef}
        >
          {renderCommunityMap()}
        </div>
      ) : null}
      {availability.hasContent && availability.kind === "stale" ? (
        <p className="mf-live-community-stale" role="status">
          {model.copy.communityStaleBody}
        </p>
      ) : null}
      <p className="mf-live-note mf-live-note--official">
        <ShieldCheck aria-hidden="true" size={15} strokeWidth={2.3} />
        {compactLayout ? model.copy.reportLegalCompactNote : model.legalNote}
      </p>
      {pendingConfirmation ? (
        <CommunityGuidelinesConsentDialog
          copy={model.copy}
          onAccept={acceptConfirmationTerms}
          onClose={() => {
            setPendingConfirmation(null);
            restoreConfirmationFocus();
          }}
        />
      ) : null}
      {expiredUpdateRecovery ? (
        <CommunityExpiredUpdateDialog
          copy={model.copy}
          onClose={closeExpiredUpdateRecovery}
          onNewObservation={() => {
            setExpiredUpdateRecovery(null);
            setReportFormOpen(true);
          }}
        />
      ) : null}
    </section>
  );
}

export function LiveView({
  compactLayout = false,
  language = "it",
  model,
  officialAlert,
  onChangeLocation,
  onOfficialAlertOpen,
  onReportConfirm,
  onReportLocate,
  onReportSubmit,
  onReportUndo,
  onReportUpdate,
  onReportWithdraw,
  onReportRefresh,
  onReportsViewed,
  pendingReportUndo,
  pendingReportUpdates = [],
  personalStorage,
  radarModel = null,
  reportingEnabled = isPilotCommunityReportingAvailable(),
  reportingUnavailableText: reportingUnavailableTextProp = "",
  reportingPreview = false,
  reportingSimulation = false,
  sharedReportId = "",
  sharedReportLoadSettled = false,
  showLocationContext = true,
  submissionLocked = false,
  theme = "light",
}) {
  const reportingUnavailableText = reportingUnavailableTextProp || (language === "fur"
    ? "L’inviament des segnalazions nol è configurât par cheste version. Webcam e mape a restin disponibilis."
    : "L’invio delle segnalazioni non è configurato per questa versione. Webcam e mappa restano disponibili.");
  const effectiveReportingEnabled = reportingEnabled || reportingPreview || reportingSimulation;
  const effectiveReportLocate = reportingPreview || reportingSimulation
    ? ({ locations, maxDistanceKm }) => Promise.resolve(createCommunityReportPreviewLocation({
      locations,
      maxDistanceKm,
      preferredPlace: model.locationPlace || model.locationLabel,
    }))
    : onReportLocate;
  const officialAlertPanel = (
    <OfficialAlertCompactLink
      alert={officialAlert}
      language={language}
      onOpen={onOfficialAlertOpen}
    />
  );
  const radarPanel = (
    <BulletinRadarCard
      language={language}
      model={radarModel}
      overlayControls={compactLayout}
      persistent={isDefinitiveAppExperience()}
    />
  );
  const webcamPanel = (
    <WebcamPanel carouselLayout={compactLayout} model={{
      ...model.webcams,
      copy: model.copy,
      language,
      locationLabel: model.locationLabel,
    }} />
  );
  const communityPanel = (
    <CommunityPanel
      compactLayout={compactLayout}
      language={language}
      model={{
        ...model.community,
        copy: model.copy,
        locationLabel: model.locationLabel,
        locationPoint: model.locationPoint,
      }}
      officialAlert={officialAlert}
      onOfficialAlertOpen={onOfficialAlertOpen}
      onReportConfirm={onReportConfirm}
      onReportLocate={effectiveReportLocate}
      onReportSubmit={onReportSubmit}
      onReportUndo={onReportUndo}
      onReportUpdate={onReportUpdate}
      onReportWithdraw={onReportWithdraw}
      onReportRefresh={onReportRefresh}
      onReportsViewed={onReportsViewed}
      pendingReportUndo={pendingReportUndo}
      pendingReportUpdates={pendingReportUpdates}
      personalStorage={personalStorage}
      reportingEnabled={effectiveReportingEnabled}
      reportingPreview={reportingPreview}
      reportingSimulation={reportingSimulation}
      reportingUnavailableText={reportingUnavailableText}
      radarModel={radarModel}
      sharedReportId={sharedReportId}
      sharedReportLoadSettled={sharedReportLoadSettled}
      theme={theme}
      webcamModel={model.webcams}
    />
  );

  return (
    <TabPage className="mf-tab-page--live" language={language} title={model.title} titleMode="hidden">
      <div className={`mf-live-view ${compactLayout ? "mf-live-view--compact-territory" : ""}`.trim()}>
        {showLocationContext ? (
          <LocationContext
            copy={model.copy}
            disabled={submissionLocked}
            locationLabel={model.locationLabel}
            onChangeLocation={onChangeLocation}
          />
        ) : null}
        {compactLayout ? (
          communityPanel
        ) : (
          <>
            {officialAlertPanel}
            {radarPanel}
            {webcamPanel}
            {communityPanel}
          </>
        )}
      </div>
    </TabPage>
  );
}
