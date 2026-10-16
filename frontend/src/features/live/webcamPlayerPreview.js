export const WEBCAM_PLAYER_PREVIEW_QUERY = "webcamPlayerQa";
export const WEBCAM_PLAYER_PREVIEW_MODE_PANOMAX = "panomax";

const WEBCAM_PLAYER_PREVIEW_DEV_BUILD = import.meta.env.DEV === true;

const PANOMAX_PREVIEW_PLAYERS = Object.freeze({
  "forni-varmost": "https://fornidisopra.panomax.com/",
  "san-daniele-centro": "https://sandanieledelfriuli.panomax.com/",
  "trieste-san-giusto": "https://trieste.panomax.com/",
});

export function getLocalWebcamPlayerPreviewMode({
  dev = WEBCAM_PLAYER_PREVIEW_DEV_BUILD,
  search = globalThis.location?.search || "",
} = {}) {
  if (!WEBCAM_PLAYER_PREVIEW_DEV_BUILD || dev !== true) return "";

  const mode = new URLSearchParams(search).get(WEBCAM_PLAYER_PREVIEW_QUERY);
  return mode === WEBCAM_PLAYER_PREVIEW_MODE_PANOMAX ? mode : "";
}

export function createWebcamPlayerPreviewState(
  dataState,
  { dev = WEBCAM_PLAYER_PREVIEW_DEV_BUILD } = {},
) {
  if (!WEBCAM_PLAYER_PREVIEW_DEV_BUILD || dev !== true) return dataState;

  const webcams = dataState?.webcams?.payload?.webcams;
  if (!Array.isArray(webcams)) return dataState;

  return {
    ...dataState,
    webcams: {
      ...dataState.webcams,
      payload: {
        ...dataState.webcams.payload,
        webcams: webcams.map((camera) => {
          const playerUrl = PANOMAX_PREVIEW_PLAYERS[camera?.id];
          return playerUrl
            ? { ...camera, mediaType: "iframe", playerUrl }
            : camera;
        }),
      },
    },
  };
}
