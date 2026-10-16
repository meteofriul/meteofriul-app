function getPreferredSourceKind(camera) {
  if (camera?.imageUrl) return "live";
  if (camera?.fallbackImageUrl) return "static";
  return "none";
}

export function createWebcamMediaState(camera) {
  const sourceKind = getPreferredSourceKind(camera);

  return {
    liveUnavailable: false,
    mediaState: sourceKind === "none" ? "error" : "loading",
    retryToken: 0,
    sourceKind,
  };
}

export function failWebcamMedia(camera, currentState) {
  if (
    currentState.sourceKind === "live"
    && camera?.fallbackImageUrl
    && camera.fallbackImageUrl !== camera.imageUrl
  ) {
    return {
      ...currentState,
      liveUnavailable: true,
      mediaState: "loading",
      sourceKind: "static",
    };
  }

  return {
    ...currentState,
    mediaState: "error",
  };
}

export function retryWebcamMedia(camera, currentState) {
  const initialState = createWebcamMediaState(camera);

  return {
    ...initialState,
    retryToken: (currentState.retryToken || 0) + 1,
  };
}

export function canAutoRetryWebcamMedia(camera, currentState, retryLimit = 1) {
  const hasMediaSource = Boolean(camera?.imageUrl || camera?.fallbackImageUrl);
  const needsRecovery = currentState?.mediaState === "error" || currentState?.liveUnavailable;
  const retryCount = Number(currentState?.retryToken) || 0;

  return hasMediaSource && needsRecovery && retryCount < retryLimit;
}

export function getNextWebcamId(cameras, currentCameraId) {
  if (!Array.isArray(cameras) || cameras.length < 2) return "";

  const currentIndex = cameras.findIndex((camera) => camera.id === currentCameraId);
  const nextIndex = currentIndex >= 0 ? (currentIndex + 1) % cameras.length : 0;
  return cameras[nextIndex]?.id || "";
}
