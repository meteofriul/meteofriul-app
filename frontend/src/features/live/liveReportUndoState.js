import { communityStorageKey } from "../../services/localCommunityPilot";

export const LIVE_REPORT_UNDO_STATE_KEY = communityStorageKey("meteoFriul:communityReportUndo:v1");

const defaultMemoryState = { value: null };

function resolveStorage(storage) {
  if (storage !== undefined) return storage;

  try {
    return globalThis.sessionStorage;
  } catch {
    return null;
  }
}

function normalizeUndoState(value, now) {
  if (!value || typeof value !== "object") return null;

  const reportId = String(value.reportId || "").trim();
  const undoUntil = Number(value.undoUntil);
  if (!reportId || !Number.isFinite(undoUntil) || undoUntil <= now) return null;

  return { reportId, undoUntil };
}

function removeStoredUndoState(storage) {
  try {
    storage?.removeItem?.(LIVE_REPORT_UNDO_STATE_KEY);
  } catch {
    // The in-memory session state remains authoritative when storage is unavailable.
  }
}

export function clearLiveReportUndoState({
  memoryState = defaultMemoryState,
  storage,
} = {}) {
  memoryState.value = null;
  removeStoredUndoState(resolveStorage(storage));
}

export function readLiveReportUndoState({
  memoryState = defaultMemoryState,
  now = Date.now(),
  storage,
} = {}) {
  const currentTime = Number(now);
  const effectiveNow = Number.isFinite(currentTime) ? currentTime : Date.now();
  const resolvedStorage = resolveStorage(storage);
  let storedState = null;

  try {
    const stored = resolvedStorage?.getItem?.(LIVE_REPORT_UNDO_STATE_KEY);
    storedState = stored ? normalizeUndoState(JSON.parse(stored), effectiveNow) : null;
  } catch {
    // Fall through to the in-memory state for this app session.
  }

  const state = storedState || normalizeUndoState(memoryState.value, effectiveNow);
  if (!state) {
    clearLiveReportUndoState({ memoryState, storage: resolvedStorage });
    return null;
  }

  memoryState.value = state;
  return state;
}

export function writeLiveReportUndoState(
  value,
  {
    memoryState = defaultMemoryState,
    now = Date.now(),
    storage,
  } = {},
) {
  const currentTime = Number(now);
  const effectiveNow = Number.isFinite(currentTime) ? currentTime : Date.now();
  const state = normalizeUndoState(value, effectiveNow);

  if (!state) {
    clearLiveReportUndoState({ memoryState, storage });
    return null;
  }

  memoryState.value = state;
  try {
    resolveStorage(storage)?.setItem?.(LIVE_REPORT_UNDO_STATE_KEY, JSON.stringify(state));
  } catch {
    // Module memory keeps undo available for the current app session.
  }

  return state;
}
