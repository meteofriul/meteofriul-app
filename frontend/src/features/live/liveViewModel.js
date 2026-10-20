import { getLiveViewCopy } from "../../copy/liveViewCopy";
import { FIXED_FVG_PLACES } from "../../data/fvgPlaces";
import { getLocationDisplayName } from "../../domain/geo/locationDisplayName";
import { getLocationMunicipalityName } from "../../domain/geo/locationIdentity";
import {
  createFallbackCommunityIdentitySnapshot,
  normalizePublicCommunityIdentitySnapshot,
} from "../community/communityIdentity";
import { LIVE_REPORT_LOCATIONS } from "./liveReportLocation";
import { isLocalCommunityPilot } from "../../services/localCommunityPilot";
import { getApprovedWebcamPlayer } from "./webcamPlayer";
import { buildWebcamPlaceGroups } from "./webcamPlaceGroups";

const CAMERA_PLACE_KEYS = Object.freeze({
  "aquileia-basilica": "aquileia",
  "barcis-lago": "barcis",
  "cividale-campanile-ex-monastero": "cividale-del-friuli",
  "cividale-natisone": "cividale-del-friuli",
  "cividale-piazza-duomo": "cividale-del-friuli",
  "cividale-piazza-paolo-diacono": "cividale-del-friuli",
  "duino-sistiana": "duino-aurisina",
  "forni-chianeit": "forni-di-sopra",
  "forni-varmost": "forni-di-sopra",
  "gemona-centro": "gemona-del-friuli",
  "gorizia-piazza-vittoria": "gorizia",
  "grado-al-bosco": "grado",
  "grado-spiaggia": "grado",
  "lignano-pineta-pontile": "lignano-sabbiadoro",
  "lignano-piazza-fontana": "lignano-sabbiadoro",
  "lignano-punta-faro": "lignano-sabbiadoro",
  "lignano-riviera": "lignano-sabbiadoro",
  "lignano-spiaggia-centrale": "lignano-sabbiadoro",
  "monfalcone-marina-julia": "monfalcone",
  "monfalcone-marina": "monfalcone",
  "piancavallo-nevelandia": "aviano",
  "piancavallo-panorama": "aviano",
  "piancavallo-sauc": "aviano",
  "sacile": "sacile",
  "san-daniele-centro": "san-daniele-del-friuli",
  "sappada-panorama": "sappada",
  "sella-nevea-canin": "chiusaforte",
  "spilimbergo-municipio": "spilimbergo",
  "tarvisio-piazza-chiesa": "tarvisio",
  "trieste-miramare": "trieste",
  "trieste-piazza-borsa": "trieste",
  "udine-panorama-castello": "udine",
  "val-saisera": "malborghetto-valbruna",
  "zoncolan-baita-goles": "sutrio",
  "zoncolan-panorama": "sutrio",
});

const GROUP_ORDER = ["nearby", "mountain", "plain", "coast"];

function normalizeToken(value) {
  return String(value || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
}

function getPilotCommunityIdentity(report) {
  if (!isLocalCommunityPilot()) return {};
  const istatCode = String(report?.istatCode || report?.istat_code || "").trim();
  return {
    istatCode: /^\d{6}$/.test(istatCode) ? istatCode : "",
    regionId: String(report?.regionId || report?.region_id || "").trim(),
    provinceCode: String(report?.provinceCode || report?.province_code || "").trim(),
    lineageGroupIds: Array.isArray(report?.lineageGroupIds) ? report.lineageGroupIds.map(String) : [],
  };
}

function getCommunityMunicipalityKey(report) {
  if (isLocalCommunityPilot()) {
    const { istatCode } = getPilotCommunityIdentity(report);
    if (istatCode) return `istat:${istatCode}`;
    const lat = getFiniteCoordinate(report?.lat);
    const lon = getFiniteCoordinate(report?.lon);
    if (Number.isFinite(lat) && Number.isFinite(lon)) return `point:${lat}:${lon}`;
    // A legacy report without canonical identity/coordinates cannot safely be
    // combined with another municipality merely because their names match.
    return `group:${report?.groupId || report?.group_id || report?.id || "unknown"}`;
  }
  return normalizeToken(report?.place)
    || `${report?.lat ?? "unknown"}:${report?.lon ?? "unknown"}`;
}

function getCommunityFallbackGroupId(report, typeId, place) {
  return `${typeId}:${isLocalCommunityPilot() ? getCommunityMunicipalityKey(report) : place}`;
}

function getPlaceByName(name) {
  const token = normalizeToken(name);
  return Object.values(FIXED_FVG_PLACES).find((place) => normalizeToken(place.name) === token) || null;
}

function getLocationPoint(location) {
  const lat = location?.lat == null || location.lat === "" ? Number.NaN : Number(location.lat);
  const lon = location?.lon == null || location.lon === "" ? Number.NaN : Number(location.lon);

  if (Number.isFinite(lat) && Number.isFinite(lon)) return { lat, lon };

  const place = getPlaceByName(location?.city);
  return place ? { lat: place.latitude, lon: place.longitude } : null;
}

function getCameraPlace(camera) {
  const key = CAMERA_PLACE_KEYS[camera.id];
  return key ? FIXED_FVG_PLACES[key] || null : null;
}

function getCameraMapPlace(camera) {
  return getCameraPlace(camera) || getPlaceByName(camera.municipality);
}

function getFiniteCoordinate(...values) {
  for (const value of values) {
    if (value == null || value === "") continue;
    const normalized = Number(value);
    if (Number.isFinite(normalized)) return normalized;
  }

  return Number.NaN;
}

function getCameraPoint(camera, fallbackPlace) {
  const lat = getFiniteCoordinate(
    camera.lat,
    camera.latitude,
    camera.coordinates?.lat,
    camera.coordinates?.latitude,
  );
  const lon = getFiniteCoordinate(
    camera.lon,
    camera.lng,
    camera.longitude,
    camera.coordinates?.lon,
    camera.coordinates?.lng,
    camera.coordinates?.longitude,
  );

  if (lat >= -90 && lat <= 90 && lon >= -180 && lon <= 180) {
    return { lat, lon, positionPrecision: "declared" };
  }
  return fallbackPlace
    ? {
        lat: fallbackPlace.latitude,
        lon: fallbackPlace.longitude,
        positionPrecision: "municipality",
      }
    : null;
}

function getCameraImageUrls(camera) {
  const imageUrl = String(camera.imageUrl || camera.image_url || "").trim();
  const fallbackImageUrl = String(
    camera.fallbackImageUrl
      || camera.fallback_image_url
      || camera.staticImageUrl
      || camera.static_image_url
      || "",
  ).trim();
  const declaredMediaType = String(
    camera.mediaType
      || camera.media_type
      || camera.imageType
      || camera.image_type
      || camera.displayMode
      || camera.display_mode
      || "",
  ).trim().toLowerCase();
  const imageIsStatic = camera.isStaticImage === true
    || camera.is_static_image === true
    || ["photo", "static", "territorial"].includes(declaredMediaType);

  return {
    fallbackImageUrl: imageIsStatic ? imageUrl || fallbackImageUrl : fallbackImageUrl,
    imageUrl: imageIsStatic ? "" : imageUrl,
  };
}

function getCameraMapApproval(camera) {
  const editorialStatus = String(
    camera.editorialStatus
      || camera.editorial_status
      || camera.mapStatus
      || camera.map_status
      || "",
  ).trim().toLowerCase();
  const mapEnabled = camera.mapEnabled === true
    || camera.map_enabled === true
    || editorialStatus === "map_ready";

  return {
    mapEnabled,
    mapStatus: mapEnabled ? "map_ready" : editorialStatus,
  };
}

function labelsMatchSemantically(first, second) {
  const firstToken = normalizeToken(first);
  return Boolean(firstToken) && firstToken === normalizeToken(second);
}

function labelContainsLabel(container, candidate) {
  const containerToken = normalizeToken(container);
  const candidateToken = normalizeToken(candidate);
  return Boolean(containerToken && candidateToken)
    && `-${containerToken}-`.includes(`-${candidateToken}-`);
}

function getCameraLocationLabel(camera, fallbackPlace, cameraName) {
  const municipality = String(camera.municipality || fallbackPlace?.name || "").trim();
  const area = String(camera.area || "").trim();
  const candidates = [municipality, area].filter(Boolean);
  const parts = candidates.filter((value, index, values) => {
    const valueToken = normalizeToken(value);
    if (values.findIndex((candidate) => normalizeToken(candidate) === valueToken) !== index) return false;

    return !values.some((candidate, candidateIndex) => (
      candidateIndex !== index
      && normalizeToken(candidate).length > valueToken.length
      && labelContainsLabel(candidate, value)
    ));
  });
  const locationLabel = parts.join(" · ");

  // The view compares the two strings before rendering the location metadata.
  // Canonicalizing punctuation-only variants to the camera name prevents labels
  // such as "Maniago - Piazza Italia" / "Maniago · Piazza Italia" from appearing twice.
  return labelsMatchSemantically(locationLabel, cameraName) ? cameraName : locationLabel;
}

function distanceKm(first, second) {
  if (!first || !second) return null;

  const toRadians = (value) => (value * Math.PI) / 180;
  const latDelta = toRadians(second.lat - first.lat);
  const lonDelta = toRadians(second.lon - first.lon);
  const firstLat = toRadians(first.lat);
  const secondLat = toRadians(second.lat);
  const a = Math.sin(latDelta / 2) ** 2
    + Math.cos(firstLat) * Math.cos(secondLat) * Math.sin(lonDelta / 2) ** 2;
  const clamped = Math.min(1, Math.max(0, a));

  return 6371 * 2 * Math.atan2(Math.sqrt(clamped), Math.sqrt(1 - clamped));
}

function formatDistance(value, language, approximate = false) {
  if (!Number.isFinite(value)) return "";

  const formatted = new Intl.NumberFormat(language === "fur" ? "fur-IT" : "it-IT", {
    maximumFractionDigits: value < 10 ? 1 : 0,
  }).format(value);

  return `${approximate ? "~" : ""}${formatted} km`;
}

function buildSourceStatus(status, copy) {
  const normalized = String(status || "unknown").toLowerCase();
  const labelKey = normalized === "fresh" || normalized === "ok"
    ? "sourceHealthOk"
    : normalized === "cache"
      ? "sourceHealthCached"
      : normalized === "stale" || normalized === "degraded" || normalized === "fallback"
        ? "sourceHealthDegraded"
        : normalized === "error" || normalized === "offline" || normalized === "unavailable"
          ? "sourceHealthOffline"
          : "sourceHealthLoading";

  return {
    id: normalized,
    label: copy[labelKey],
    tone: labelKey === "sourceHealthOk"
      ? "ok"
      : labelKey === "sourceHealthOffline"
        ? "offline"
        : "neutral",
  };
}

function getCommunityReportDistance(payload) {
  const value = Number(payload?.max_distance_km);

  return Number.isFinite(value) && value > 0 ? Math.min(value, 5) : 5;
}

function getCommunityReportLocations(payload) {
  const locations = Array.isArray(payload?.locations) ? payload.locations : [];
  const normalized = locations
    .map((location) => ({
      lat: Number(location.lat),
      lon: Number(location.lon),
      place: String(location.place || "").trim(),
    }))
    .filter((location) => location.place && Number.isFinite(location.lat) && Number.isFinite(location.lon));

  return normalized.length ? normalized : LIVE_REPORT_LOCATIONS;
}

function normalizeCamera(camera, { copy, language, locationPoint }) {
  const place = getCameraPlace(camera);
  const cameraPoint = getCameraPoint(camera, place);
  const mapPoint = getCameraPoint(camera, getCameraMapPlace(camera));
  const distance = distanceKm(locationPoint, cameraPoint);
  const health = String(camera.health || "unknown").toLowerCase();
  const imageUrls = getCameraImageUrls(camera);
  const mapApproval = getCameraMapApproval(camera);
  const player = getApprovedWebcamPlayer(camera);
  const name = String(camera.name || place?.name || copy.webcamTitle).trim();
  const checkedAt = String(camera.checkedAt || camera.checked_at || "").trim();
  const capturedAt = String(camera.capturedAt || camera.captured_at || "").trim();
  let attributionUrl = "";
  try {
    const url = new URL(String(camera.attributionUrl || camera.attribution_url || ""));
    if (url.protocol === "https:" && !url.username && !url.password) attributionUrl = url.href;
  } catch {
    // Attribution remains readable even when its optional link is invalid.
  }

  const mediaType = player?.mediaType || (
    imageUrls.imageUrl && String(camera.mediaType || camera.media_type || "").toLowerCase() === "snapshot"
      ? "snapshot"
      : ""
  );
  const playerUrl = player?.playerUrl || "";
  const sourceUrl = String(
    camera.sourcePage
      || camera.source_page
      || camera.sourceUrl
      || camera.source_url
      || camera.externalUrl
      || camera.external_url
      || "",
  );
  const mediaMode = mediaType === "snapshot" && imageUrls.imageUrl
    ? "snapshot"
    : mediaType === "iframe" && playerUrl
      ? "player"
      : imageUrls.fallbackImageUrl
        ? "fallback"
        : sourceUrl
          ? "source"
          : "";

  return {
    area: camera.area || place?.name || "",
    attribution: String(camera.attribution || camera.attribution_text || "").trim(),
    attributionUrl,
    category: camera.category || "",
    capturedAt,
    checkedAt,
    distanceKm: distance,
    distanceLabel: formatDistance(
      distance,
      language,
      cameraPoint?.positionPrecision === "municipality",
    ),
    group: String(camera.group || ""),
    health: buildSourceStatus(health, copy),
    id: String(camera.id || ""),
    ...imageUrls,
    lat: mapPoint?.lat ?? null,
    locationLabel: getCameraLocationLabel(camera, place, name),
    lon: mapPoint?.lon ?? null,
    mapClusterId: String(camera.mapClusterId || camera.map_cluster_id || "").trim(),
    mapClusterLabel: String(camera.mapClusterLabel || camera.map_cluster_label || "").trim(),
    ...mapApproval,
    mediaMode,
    mediaType,
    name,
    place: camera.municipality || place?.name || camera.area || "",
    playerUrl,
    positionIsApproximate: mapPoint?.positionPrecision === "municipality",
    positionPrecision: mapPoint?.positionPrecision || "",
    provider: String(camera.provider || (language === "fur" ? "Font esterne" : "Fonte esterna")),
    sortOrder: Number(camera.sortOrder) || 999,
    sourceUrl,
  };
}

function buildWebcamGroups(normalizedCameras, { copy, language, location }) {
  const normalized = normalizedCameras
    .filter((camera) => camera.imageUrl || camera.fallbackImageUrl);
  const groups = {
    coast: normalized.filter((camera) => camera.group === "coast"),
    mountain: normalized.filter((camera) => camera.group === "mountain"),
    plain: normalized.filter((camera) => camera.group === "plain"),
  };

  Object.values(groups).forEach((items) => items.sort((first, second) => first.sortOrder - second.sortOrder));

  const nearby = buildWebcamPlaceGroups(
    normalized.filter((camera) => Number.isFinite(camera.distanceKm)),
  )
    .map((placeGroup) => ({
      ...placeGroup,
      distanceKm: Math.min(...placeGroup.cameras.map((camera) => camera.distanceKm)),
    }))
    .sort((first, second) => first.distanceKm - second.distanceKm || first.sortOrder - second.sortOrder)
    .slice(0, 5)
    .flatMap((placeGroup) => placeGroup.cameras);
  const definitions = {
    coast: { label: copy.webcamGroupCoast, place: copy.webcamGroupCoastBody },
    mountain: { label: copy.webcamGroupMountain, place: copy.webcamGroupMountainBody },
    nearby: {
      label: copy.webcamGroupNearby,
      place: getLocationDisplayName(location, language) || copy.webcamGroupNearbyBody,
    },
    plain: { label: copy.webcamGroupPlain, place: copy.webcamGroupPlainBody },
  };

  return GROUP_ORDER
    .map((id) => ({
      cameras: id === "nearby" ? nearby : groups[id] || [],
      id,
      label: definitions[id].label,
      place: definitions[id].place,
    }))
    .filter((group) => group.cameras.length > 0)
    .map((group) => ({ ...group, count: group.cameras.length }));
}

function getReportTypeLabel(typeId, copy) {
  return copy.reportTypes[typeId] || copy.reportTypes.unknown;
}

function formatReportTime(createdAt, { copy, now }) {
  const timestamp = Number(createdAt);
  if (!Number.isFinite(timestamp)) return "";

  const minutes = Math.max(0, Math.floor((now.getTime() - timestamp) / 60000));
  if (minutes < 1) return copy.reportNow;
  return copy.reportMinutesAgo.replace("{minutes}", String(minutes));
}

function getActiveReports(reports, now) {
  const timestamp = now.getTime();

  return (reports || []).filter((report) => (
    !Number.isFinite(Number(report.expiresAt)) || Number(report.expiresAt) > timestamp
  ));
}

function getReportActivityAt(report) {
  return Number(
    report?.updatedAt
    || report?.updated_at
    || report?.createdAt
    || report?.created_at,
  ) || 0;
}

function getReportOriginalCreatedAt(report) {
  return Number(report?.originalCreatedAt || report?.createdAt || report?.created_at) || 0;
}

function getReportTimeLabel(report, { copy, now }) {
  const updatedAt = Number(report?.updatedAt || report?.updated_at);
  return Number.isFinite(updatedAt) && updatedAt > 0
    ? formatReportTime(updatedAt, { copy, now })
    : report?.time || formatReportTime(getReportActivityAt(report), { copy, now });
}

function getReportSourceKeys(report) {
  const identityEntries = Array.isArray(report?.identities) ? report.identities : [];
  const candidates = [
    ...(Array.isArray(report?.sourceKeys) ? report.sourceKeys : []),
    ...(Array.isArray(report?.source_keys) ? report.source_keys : []),
    ...identityEntries.map((entry) => entry?.sourceKey ?? entry?.source_key),
    report?.sourceKey,
    report?.source_key,
  ];

  return [...new Set(candidates.map((value) => String(value || "").trim()).filter(Boolean))];
}

function getReportIdentity(report) {
  return normalizePublicCommunityIdentitySnapshot(report?.identity);
}

function getReportIdentityEntries(report) {
  const sourceKeys = getReportSourceKeys(report);
  const place = String(report?.place || "").trim();
  const entriesBySource = new Map();

  (Array.isArray(report?.identities) ? report.identities : []).forEach((entry) => {
    const sourceKey = String(entry?.sourceKey ?? entry?.source_key ?? "").trim();
    if (!sourceKey) return;

    const identity = normalizePublicCommunityIdentitySnapshot(entry?.identity);
    const current = entriesBySource.get(sourceKey);
    if (!current || (!current.identity && identity)) {
      entriesBySource.set(sourceKey, { identity, sourceKey });
    }
  });

  const reportIdentity = getReportIdentity(report);
  const directSourceKey = String(report?.sourceKey ?? report?.source_key ?? "").trim()
    || (sourceKeys.length === 1 ? sourceKeys[0] : "");
  if (directSourceKey && reportIdentity) {
    entriesBySource.set(directSourceKey, {
      identity: reportIdentity,
      sourceKey: directSourceKey,
    });
  }

  return sourceKeys.map((sourceKey) => ({
    identity: entriesBySource.get(sourceKey)?.identity
      || createFallbackCommunityIdentitySnapshot(sourceKey, place),
    sourceKey,
  }));
}

function mergeReportIdentityEntries(...collections) {
  const entriesBySource = new Map();

  collections.flat().forEach((entry) => {
    const sourceKey = String(entry?.sourceKey || "").trim();
    if (!sourceKey) return;

    const identity = normalizePublicCommunityIdentitySnapshot(entry?.identity);
    if (identity) entriesBySource.set(sourceKey, { identity, sourceKey });
  });

  return [...entriesBySource.values()];
}

function getPrimaryReportIdentity(report, identities = getReportIdentityEntries(report)) {
  const identity = getReportIdentity(report);
  if (identity) return identity;

  const directSourceKey = String(report?.sourceKey ?? report?.source_key ?? "").trim();
  return identities.find((entry) => entry.sourceKey === directSourceKey)?.identity
    || (identities.length === 1 ? identities[0].identity : null);
}

function buildCommunityContributions(payload, { copy, now }) {
  const contributionsByGroup = new Map();

  getActiveReports(payload?.reports, now).forEach((report) => {
    const typeId = String(report.typeId || report.type_id || "unknown");
    const place = String(report.place || "");
    const groupId = String(report.groupId || report.group_id || getCommunityFallbackGroupId(report, typeId, place));
    const sourceKeys = getReportSourceKeys(report);
    const identities = getReportIdentityEntries(report);
    const createdAt = getReportActivityAt(report);
    const contribution = {
      createdAt,
      expiresAt: Number(report.expiresAt || report.expires_at) || 0,
      id: String(report.id || ""),
      identities,
      identity: getPrimaryReportIdentity(report, identities),
      originalCreatedAt: getReportOriginalCreatedAt(report),
      revision: Math.max(1, Math.floor(Number(report?.revision) || 1)),
      sourceKey: sourceKeys.length === 1 ? sourceKeys[0] : "",
      sourceKeys,
      timeLabel: getReportTimeLabel(report, { copy, now }),
    };

    contributionsByGroup.set(groupId, [
      ...(contributionsByGroup.get(groupId) || []),
      contribution,
    ]);
  });

  contributionsByGroup.forEach((contributions) => {
    contributions.sort((first, second) => second.createdAt - first.createdAt);
  });

  return contributionsByGroup;
}

function groupReportsForMap(reports) {
  const groups = new Map();

  [...reports]
    .sort((first, second) => (
      getReportActivityAt(first) - getReportActivityAt(second)
    ))
    .forEach((report) => {
      const typeId = String(report.typeId || report.type_id || "unknown");
      const place = String(report.place || "");
      const groupId = String(report.groupId || report.group_id || getCommunityFallbackGroupId(report, typeId, place));
      const current = groups.get(groupId);
      const identities = getReportIdentityEntries(report);

      if (!current) {
        groups.set(groupId, {
          ...report,
          count: 1,
          groupId,
          id: groupId,
          identities,
          originalCreatedAt: getReportOriginalCreatedAt(report),
          reportIds: [report.id],
          sourceKeys: getReportSourceKeys(report),
        });
        return;
      }

      current.count += 1;
      current.reportIds.push(report.id);
      current.sourceKeys = [...new Set([
        ...(current.sourceKeys || []),
        ...getReportSourceKeys(report),
      ])];
      current.identities = mergeReportIdentityEntries(current.identities, identities);
      if (getReportActivityAt(report) > getReportActivityAt(current)) {
        current.createdAt = getReportActivityAt(report);
        current.updatedAt = current.createdAt;
        current.expiresAt = report.expiresAt;
        current.identity = getReportIdentity(report);
        current.originalCreatedAt = getReportOriginalCreatedAt(report);
        current.revision = Math.max(1, Math.floor(Number(report?.revision) || 1));
        current.sourceKey = String(report.sourceKey || report.source_key || "").trim();
        current.time = report.time;
      }
    });

  return [...groups.values()];
}

function buildCommunityMarkers(payload, { copy, language, location, now }) {
  const sourceGroups = getActiveReports(payload?.map_groups, now);
  const activeGroups = sourceGroups.length
    ? sourceGroups
    : groupReportsForMap(getActiveReports(payload?.reports, now));
  const contributionsByGroup = buildCommunityContributions(payload, { copy, now });
  const locationPoint = getLocationPoint(location);

  const normalizedGroups = activeGroups
    .map((report) => {
      const lat = isLocalCommunityPilot() ? getFiniteCoordinate(report.lat) : Number(report.lat);
      const lon = isLocalCommunityPilot() ? getFiniteCoordinate(report.lon) : Number(report.lon);
      const count = Math.max(1, Number(report.count) || 1);
      const distance = Number.isFinite(lat) && Number.isFinite(lon)
        ? distanceKm(locationPoint, { lat, lon })
        : null;
      const typeId = String(report.typeId || report.type_id || "unknown");
      const sourceKeys = getReportSourceKeys(report);
      const identities = getReportIdentityEntries(report);
      const groupId = String(report.groupId || report.group_id || report.id || "");

      return {
        ...getPilotCommunityIdentity(report),
        confirmations: {
          no: Math.max(0, Number(report.confirmations?.no) || 0),
          yes: Math.max(0, Number(report.confirmations?.yes) || 0),
        },
        count,
        countLabel: count === 1
          ? copy.reportCountOne
          : copy.reportCountMany.replace("{count}", String(count)),
        contributions: contributionsByGroup.get(groupId) || [],
        createdAt: getReportActivityAt(report),
        expiresAt: Number(report.expiresAt || report.expires_at) || 0,
        distanceKm: distance,
        distanceLabel: formatDistance(distance, language),
        groupId,
        id: String(report.id || report.groupId || report.group_id || ""),
        identities,
        identity: getPrimaryReportIdentity(report, identities),
        lat: Number.isFinite(lat) ? lat : null,
        lon: Number.isFinite(lon) ? lon : null,
        originalCreatedAt: getReportOriginalCreatedAt(report),
        place: String(report.place || ""),
        reportIds: Array.isArray(report.reportIds)
          ? report.reportIds.map((id) => String(id || "").trim()).filter(Boolean)
          : Array.isArray(report.report_ids)
            ? report.report_ids.map((id) => String(id || "").trim()).filter(Boolean)
            : [],
        sourceKey: sourceKeys.length === 1 ? sourceKeys[0] : "",
        sourceKeys,
        revision: Math.max(1, Math.floor(Number(report?.revision) || 1)),
        timeLabel: getReportTimeLabel(report, { copy, now }),
        typeId,
        typeLabel: getReportTypeLabel(typeId, copy),
        x: Number.isFinite(Number(report.x)) ? Number(report.x) : null,
        y: Number.isFinite(Number(report.y)) ? Number(report.y) : null,
      };
    })
    .filter((report) => report.id)
    .sort((first, second) => second.createdAt - first.createdAt);

  const municipalityMarkers = new Map();

  normalizedGroups.forEach((group) => {
    const placeKey = getCommunityMunicipalityKey(group);
    const markerId = `place:${placeKey}`;
    const current = municipalityMarkers.get(markerId);

    if (!current) {
      municipalityMarkers.set(markerId, {
        ...group,
        id: markerId,
        phenomena: [group],
      });
      return;
    }

    current.count += group.count;
    current.confirmations = {
      no: current.confirmations.no + group.confirmations.no,
      yes: current.confirmations.yes + group.confirmations.yes,
    };
    current.sourceKeys = [...new Set([
      ...(current.sourceKeys || []),
      ...(group.sourceKeys || []),
    ])];
    current.sourceKey = current.sourceKeys.length === 1 ? current.sourceKeys[0] : "";
    current.identities = mergeReportIdentityEntries(current.identities, group.identities);
    current.phenomena.push(group);

    if (group.createdAt > current.createdAt) {
      current.createdAt = group.createdAt;
      current.identity = group.identity;
      current.timeLabel = group.timeLabel;
      current.typeId = group.typeId;
      current.typeLabel = group.typeLabel;
    }
  });

  return [...municipalityMarkers.values()]
    .map((marker) => ({
      ...marker,
      countLabel: marker.count === 1
        ? copy.reportCountOne
        : copy.reportCountMany.replace("{count}", String(marker.count)),
      phenomena: marker.phenomena.sort((first, second) => second.createdAt - first.createdAt),
      typeId: marker.phenomena.length > 1 ? "multiple" : marker.typeId,
      typeLabel: marker.phenomena.length > 1 ? copy.reportMultiplePhenomena : marker.typeLabel,
    }))
    .sort((first, second) => second.createdAt - first.createdAt);
}

function buildCommunityItems(payload, { copy, language, location, now }) {
  const locationPoint = getLocationPoint(location);
  const sourceGroups = getActiveReports(payload?.map_groups, now);
  const activeGroups = sourceGroups.length
    ? sourceGroups
    : groupReportsForMap(getActiveReports(payload?.reports, now));
  const contributionsByGroup = buildCommunityContributions(payload, { copy, now });

  return activeGroups
    .map((report) => {
      const lat = Number(report.lat);
      const lon = Number(report.lon);
      const distance = Number.isFinite(lat) && Number.isFinite(lon)
        ? distanceKm(locationPoint, { lat, lon })
        : null;
      const sourceKeys = getReportSourceKeys(report);
      const identities = getReportIdentityEntries(report);
      const count = Math.max(1, Number(report.count) || 1);
      const groupId = String(report.groupId || report.group_id || report.id || "");

      return {
        ...getPilotCommunityIdentity(report),
        confirmations: {
          no: Math.max(0, Number(report.confirmations?.no) || 0),
          yes: Math.max(0, Number(report.confirmations?.yes || report.confirmationCount) || 0),
        },
        count,
        countLabel: count === 1
          ? copy.reportCountOne
          : copy.reportCountMany.replace("{count}", String(count)),
        contributions: contributionsByGroup.get(groupId) || [],
        createdAt: getReportActivityAt(report),
        distanceKm: distance,
        distanceLabel: formatDistance(distance, language),
        expiresAt: Number(report.expiresAt || report.expires_at) || 0,
        groupId,
        id: groupId,
        identities,
        identity: getPrimaryReportIdentity(report, identities),
        originalCreatedAt: getReportOriginalCreatedAt(report),
        place: String(report.place || ""),
        reportIds: Array.isArray(report.reportIds)
          ? report.reportIds.map((id) => String(id || "").trim()).filter(Boolean)
          : Array.isArray(report.report_ids)
            ? report.report_ids.map((id) => String(id || "").trim()).filter(Boolean)
            : (contributionsByGroup.get(groupId) || []).map((item) => item.id).filter(Boolean),
        sourceKey: sourceKeys.length === 1 ? sourceKeys[0] : "",
        sourceKeys,
        revision: Math.max(1, Math.floor(Number(report?.revision) || 1)),
        timeLabel: getReportTimeLabel(report, { copy, now }),
        typeId: String(report.typeId || report.type_id || "unknown"),
        typeLabel: getReportTypeLabel(report.typeId || report.type_id, copy),
      };
    })
    .sort((first, second) => {
      const recencyDifference = Number(second.createdAt || 0) - Number(first.createdAt || 0);
      if (recencyDifference) return recencyDifference;
      const firstDistance = Number.isFinite(first.distanceKm) ? first.distanceKm : Number.POSITIVE_INFINITY;
      const secondDistance = Number.isFinite(second.distanceKm) ? second.distanceKm : Number.POSITIVE_INFINITY;
      return firstDistance - secondDistance
        || String(first.groupId).localeCompare(String(second.groupId), "it");
    });
}

export function buildLiveViewModel(
  dataState,
  {
    language = "it",
    location = null,
    now = new Date(),
    webcamsEnabled = true,
  } = {},
) {
  const copy = { ...getLiveViewCopy(language) };
  if (isLocalCommunityPilot()) {
    copy.reportBody = language === "fur"
      ? "Segnale il timp atuâl te tô zone."
      : "Segnala il meteo attuale nella tua zona.";
    copy.reportGpsTooFar = language === "fur"
      ? "La posizion no corispuint a un Comun talian verificât."
      : "La posizione non corrisponde a un Comune italiano verificato.";
    copy.reportLocationRadius = language === "fur"
      ? "Posizion aproximade a tutele de tô riservatece."
      : "Posizione approssimata a tutela della tua privacy.";
    copy.reportExpires = language === "fur"
      ? "E restarà visibile su la mape par 60 minûts."
      : "Rimarrà visibile sulla mappa per 60 minuti.";
    copy.reportSafety = language === "fur"
      ? "In câs di situazions critichis o pericui imediâts, clame il 112."
      : "In caso di situazioni critiche o pericoli immediati, contatta il 112.";
    copy.liveSheetDisclaimer = language === "fur"
      ? "Segnalazions di prove no validâts. Par alertis consulte la Protezion Civîl e lis fonts uficiâls de tô regjon."
      : "Segnalazioni di prova non validate. Per allerte consulta la Protezione Civile e le fonti ufficiali della tua regione.";
    copy.liveMapInfoOfficial = copy.liveSheetDisclaimer;
  }
  const webcamSection = dataState?.webcams || {};
  const communitySection = dataState?.community || {};
  const webcamPayload = webcamSection.payload;
  const communityPayload = communitySection.payload;
  const locationPoint = getLocationPoint(location);
  const normalizedWebcams = (webcamsEnabled ? webcamPayload?.webcams || [] : [])
    .filter((camera) => camera?.id)
    .map((camera) => normalizeCamera(camera, { copy, language, locationPoint }));
  const webcamGroups = buildWebcamGroups(normalizedWebcams, { copy, language, location });
  const webcamMapCandidates = normalizedWebcams.filter((camera) => (
    Number.isFinite(camera.lat)
    && Number.isFinite(camera.lon)
    && Boolean(camera.mediaMode)
  ));
  const webcamMapItems = webcamMapCandidates.filter((camera) => camera.mapEnabled);
  const communityItems = buildCommunityItems(communityPayload, { copy, language, location, now });
  const communityMarkers = buildCommunityMarkers(communityPayload, { copy, language, location, now });

  return {
    community: {
      body: copy.liveMapBody,
      emptyBody: copy.liveMapEmptyBody,
      emptyTitle: copy.liveMapEmptyTitle,
      enabled: Boolean(communityPayload),
      items: communityItems,
      legalNote: copy.reportLegalNote,
      markers: communityMarkers,
      maxDistanceKm: getCommunityReportDistance(communityPayload),
      reportLocations: getCommunityReportLocations(communityPayload),
      reportOptions: Object.entries(copy.reportTypes)
        .filter(([id]) => id !== "unknown")
        .map(([id, label]) => ({ id, label })),
      sourceAgeMs: Math.max(0, Number(communitySection.ageMs) || 0),
      sourceUpdatedAt: communityPayload?.generated_at || "",
      status: buildSourceStatus(communitySection.status, copy),
      title: copy.liveMapTitle,
      ttlLabel: copy.reportExpires,
    },
    copy,
    locationLabel: getLocationDisplayName(location, language),
    locationPoint,
    locationPlace: getLocationMunicipalityName(location),
    subtitle: copy.viewSubtitle,
    title: copy.viewTitle,
    webcams: {
      available: webcamGroups.length > 0,
      emptyBody: webcamsEnabled
        ? copy.webcamUnavailableBody
        : copy.webcamAreaUnavailableBody,
      emptyTitle: webcamsEnabled
        ? copy.webcamUnavailableTitle
        : copy.webcamAreaUnavailableTitle,
      groups: webcamGroups,
      mapCandidates: webcamMapCandidates,
      mapItems: webcamMapItems,
      sourceUpdatedAt: webcamPayload?.generated_at || webcamPayload?.source_updated_at || "",
      status: buildSourceStatus(webcamsEnabled ? webcamSection.status : "unsupported", copy),
      supported: webcamsEnabled,
      title: copy.webcamTitle,
    },
  };
}
