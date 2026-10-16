export function getSelectedWebcamId(group, rememberedCameraId = "") {
  if (!group?.cameras?.length) return "";

  return group.cameras.some((camera) => camera.id === rememberedCameraId)
    ? rememberedCameraId
    : group.cameras[0]?.id || "";
}

export function rememberWebcamSelection(selections, groupId, cameraId) {
  if (!groupId || !cameraId || selections?.[groupId] === cameraId) {
    return selections || {};
  }

  return {
    ...(selections || {}),
    [groupId]: cameraId,
  };
}
