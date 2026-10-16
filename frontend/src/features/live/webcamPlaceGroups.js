const DEFAULT_SORT_ORDER = 999;
export const WEBCAM_CLUSTER_EXPANSION_ZOOM = 12;
const COLOCATED_MARKER_RADIUS = 20;

function normalizeText(value) {
  return String(value || "").trim();
}

function getSortOrder(camera) {
  const sortOrder = Number(camera?.sortOrder);
  return Number.isFinite(sortOrder) ? sortOrder : DEFAULT_SORT_ORDER;
}

function compareText(first, second) {
  const normalizedFirst = normalizeText(first).toLocaleLowerCase("it");
  const normalizedSecond = normalizeText(second).toLocaleLowerCase("it");

  if (normalizedFirst < normalizedSecond) return -1;
  if (normalizedFirst > normalizedSecond) return 1;
  return 0;
}

function compareCameras(first, second) {
  return getSortOrder(first) - getSortOrder(second)
    || compareText(first?.name, second?.name)
    || compareText(first?.id, second?.id);
}

function getCameraPoint(camera) {
  if (
    camera?.lat == null
    || camera.lat === ""
    || camera?.lon == null
    || camera.lon === ""
  ) return null;

  const lat = Number(camera?.lat);
  const lon = Number(camera?.lon);

  return Number.isFinite(lat) && Number.isFinite(lon) ? { lat, lon } : null;
}

function getCentroid(cameras) {
  const points = cameras.map(getCameraPoint).filter(Boolean);
  if (!points.length) return { lat: null, lon: null };

  const totals = points.reduce((current, point) => ({
    lat: current.lat + point.lat,
    lon: current.lon + point.lon,
  }), { lat: 0, lon: 0 });

  return {
    lat: totals.lat / points.length,
    lon: totals.lon / points.length,
  };
}

function getGroupLabel(cameras) {
  return cameras.map((camera) => normalizeText(camera?.mapClusterLabel)).find(Boolean)
    || cameras.map((camera) => normalizeText(camera?.place)).find(Boolean)
    || normalizeText(cameras[0]?.name);
}

function createPlaceGroup({ cameras, id, mapClusterId = "" }) {
  const sortedCameras = [...cameras].sort(compareCameras);
  const centroid = getCentroid(sortedCameras);

  return {
    cameras: sortedCameras,
    count: sortedCameras.length,
    id,
    isCluster: Boolean(mapClusterId && sortedCameras.length > 1),
    label: getGroupLabel(sortedCameras),
    lat: centroid.lat,
    lon: centroid.lon,
    mapClusterId,
    sortOrder: getSortOrder(sortedCameras[0]),
  };
}

/**
 * Groups only cameras that explicitly opt into the same map cluster.
 * Cameras without mapClusterId remain independent even when their place matches.
 */
export function buildWebcamPlaceGroups(cameras = []) {
  const explicitClusters = new Map();
  const placeGroups = [];

  (Array.isArray(cameras) ? cameras : []).filter((camera) => camera?.id).forEach((camera) => {
    const mapClusterId = normalizeText(camera.mapClusterId);
    if (!mapClusterId) {
      placeGroups.push(createPlaceGroup({
        cameras: [camera],
        id: `camera:${camera.id}`,
      }));
      return;
    }

    const clusterCameras = explicitClusters.get(mapClusterId) || [];
    clusterCameras.push(camera);
    explicitClusters.set(mapClusterId, clusterCameras);
  });

  explicitClusters.forEach((clusterCameras, mapClusterId) => {
    placeGroups.push(createPlaceGroup({
      cameras: clusterCameras,
      id: `cluster:${mapClusterId}`,
      mapClusterId,
    }));
  });

  return placeGroups.sort((first, second) => (
    first.sortOrder - second.sortOrder
    || compareText(first.label, second.label)
    || compareText(first.id, second.id)
  ));
}

/**
 * Returns deterministic pixel-only offsets for cameras that share the exact
 * same coordinates. Geographic coordinates stay untouched; the offset is
 * applied only after Leaflet projects them at close zoom.
 */
export function buildColocatedWebcamMarkerOffsets(cameras = []) {
  const coordinateGroups = new Map();
  const offsets = {};

  (Array.isArray(cameras) ? cameras : []).filter((camera) => camera?.id).forEach((camera) => {
    const point = getCameraPoint(camera);
    if (!point) return;

    const key = `${point.lat.toFixed(6)}:${point.lon.toFixed(6)}`;
    const grouped = coordinateGroups.get(key) || [];
    grouped.push(camera);
    coordinateGroups.set(key, grouped);
  });

  coordinateGroups.forEach((groupedCameras) => {
    if (groupedCameras.length < 2) return;

    [...groupedCameras].sort(compareCameras).forEach((camera, index, sorted) => {
      const angle = (-180 + (360 * index) / sorted.length) * (Math.PI / 180);
      const x = Math.round(Math.cos(angle) * COLOCATED_MARKER_RADIUS);
      const y = Math.round(Math.sin(angle) * COLOCATED_MARKER_RADIUS);
      offsets[camera.id] = {
        x: Object.is(x, -0) ? 0 : x,
        y: Object.is(y, -0) ? 0 : y,
      };
    });
  });

  return offsets;
}
