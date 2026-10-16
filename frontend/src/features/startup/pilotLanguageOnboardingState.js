export const PILOT_LANGUAGE_ONBOARDING_STORAGE_KEY = "mfPilotLanguageOnboarding:v1";

const COMPLETED_STATE = "completed";

export function readPilotLanguageOnboardingState({
  storage = globalThis.window?.localStorage,
} = {}) {
  try {
    return storage?.getItem?.(PILOT_LANGUAGE_ONBOARDING_STORAGE_KEY) === COMPLETED_STATE
      ? COMPLETED_STATE
      : "pending";
  } catch {
    return "pending";
  }
}

export function writePilotLanguageOnboardingState({
  storage = globalThis.window?.localStorage,
} = {}) {
  try {
    storage?.setItem?.(PILOT_LANGUAGE_ONBOARDING_STORAGE_KEY, COMPLETED_STATE);
  } catch {
    // The welcome can still close when browser storage is unavailable.
  }
  return COMPLETED_STATE;
}

export function shouldShowPilotLanguageOnboarding({
  pilot = false,
  state = "pending",
} = {}) {
  return pilot && state !== COMPLETED_STATE;
}
