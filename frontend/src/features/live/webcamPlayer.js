const APPROVED_IFRAME_URLS = new Set([
  "https://fornidisopra.panomax.com/",
  "https://sandanieledelfriuli.panomax.com/",
  "https://stream-meteoproject.eu/weathercam-player.php?code=18",
]);

const PRODUCTION_APPROVED_IFRAME_URLS = new Set([
  "https://stream-meteoproject.eu/weathercam-player.php?code=18",
]);

const WEBCAM_PLAYER_DEV_BUILD = import.meta.env.DEV === true;

function readPlayerField(camera, canonical, alias) {
  return String(camera?.[canonical] || camera?.[alias] || "").trim();
}

export function getApprovedWebcamPlayer(
  camera,
  { dev = WEBCAM_PLAYER_DEV_BUILD } = {},
) {
  const devPlayerPreview = WEBCAM_PLAYER_DEV_BUILD && dev === true;

  const mediaType = readPlayerField(camera, "mediaType", "media_type").toLowerCase();
  const playerUrl = readPlayerField(camera, "playerUrl", "player_url");

  if (mediaType !== "iframe" || !playerUrl) return null;

  try {
    const parsed = new URL(playerUrl);
    if (
      parsed.protocol !== "https:"
      || parsed.username
      || parsed.password
      || !APPROVED_IFRAME_URLS.has(parsed.href)
      || (!devPlayerPreview && !PRODUCTION_APPROVED_IFRAME_URLS.has(parsed.href))
    ) {
      return null;
    }

    return {
      mediaType: "iframe",
      playerUrl: parsed.href,
    };
  } catch {
    return null;
  }
}

export function hasApprovedWebcamPlayer(camera, options) {
  return getApprovedWebcamPlayer(camera, options) !== null;
}
