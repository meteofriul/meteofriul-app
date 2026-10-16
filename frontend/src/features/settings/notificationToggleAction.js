export function getNotificationToggleAction({ enabled, permission, platform }) {
  if (!enabled || platform !== "android") return "update_preference";
  if (permission === "prompt") return "request_permission";
  if (permission === "denied") return "open_settings";
  return "update_preference";
}

export function getAutomaticLocationToggleAction({
  autoLocationEnabled,
  backgroundLocationState,
  enabled,
}) {
  if (!enabled) return "disable_location";
  if (
    autoLocationEnabled
    && backgroundLocationState === "permission_required"
  ) {
    return "open_background_settings";
  }
  if (!autoLocationEnabled) return "enable_location";
  return "none";
}
