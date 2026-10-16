export const WEB_STARTUP_ONBOARDING_STORAGE_KEY = "mfWebStartupOnboarding:v1";

const TERMINAL_STATES = new Set(["completed", "dismissed"]);

export function readWebStartupOnboardingState({
  storage = globalThis.window?.localStorage,
} = {}) {
  try {
    const value = String(storage?.getItem?.(WEB_STARTUP_ONBOARDING_STORAGE_KEY) || "")
      .trim()
      .toLowerCase();
    return TERMINAL_STATES.has(value) ? value : "pending";
  } catch {
    return "pending";
  }
}

export function writeWebStartupOnboardingState(
  state,
  { storage = globalThis.window?.localStorage } = {},
) {
  const normalized = TERMINAL_STATES.has(state) ? state : "dismissed";
  try {
    storage?.setItem?.(WEB_STARTUP_ONBOARDING_STORAGE_KEY, normalized);
  } catch {
    // The onboarding can still close when browser storage is unavailable.
  }
  return normalized;
}
