import {
  OFFICIAL_ALERT_STATES,
  classifyOfficialAlertState,
} from "../domain/alerts/officialAlerts";
import { fetchOfficialAlertsPayload } from "./bulletinApi";
import {
  readRegionalOfficialAlertsCache,
  reconcileRegionalOfficialAlerts,
} from "./officialAlertsCache";

const AUTHORITATIVE_ALERT_STATES = new Set([
  OFFICIAL_ALERT_STATES.ACTIVE,
  OFFICIAL_ALERT_STATES.INACTIVE_CONFIRMED,
]);

const DEFAULT_RUNTIME_LOAD_SCOPE = {};
const runtimeLoadCoordinators = new WeakMap();

function getRuntimeLoadScope(storage) {
  const resolvedStorage = storage === undefined ? globalThis?.localStorage : storage;

  return resolvedStorage && ["object", "function"].includes(typeof resolvedStorage)
    ? resolvedStorage
    : DEFAULT_RUNTIME_LOAD_SCOPE;
}

function beginRuntimeLoad(storage) {
  const scope = getRuntimeLoadScope(storage);
  const coordinator = runtimeLoadCoordinators.get(scope) || {
    latestRequestId: 0,
    latestState: null,
  };
  const requestId = coordinator.latestRequestId + 1;

  runtimeLoadCoordinators.set(scope, {
    ...coordinator,
    latestRequestId: requestId,
  });

  return { requestId, scope };
}

function isLatestRuntimeLoad({ requestId, scope }) {
  return runtimeLoadCoordinators.get(scope)?.latestRequestId === requestId;
}

function rememberLatestRuntimeState(load, state) {
  if (!isLatestRuntimeLoad(load)) return state;

  runtimeLoadCoordinators.set(load.scope, {
    latestRequestId: load.requestId,
    latestState: state,
  });
  return state;
}

function resolveSupersededRuntimeState(load, { storage, now }) {
  const latestState = runtimeLoadCoordinators.get(load.scope)?.latestState;
  if (latestState) return latestState;

  const payload = readRegionalOfficialAlertsCache({ storage, now });
  return createOfficialAlertsRuntimeState(payload, {
    fromCache: Boolean(payload),
    now,
    status: payload ? "cache" : "empty",
  });
}

function getErrorMessage(error) {
  if (error instanceof Error && error.message) return error.message;
  if (typeof error === "string" && error.trim()) return error.trim();
  return "Aggiornamento allerte ufficiali non riuscito";
}

export function createOfficialAlertsRuntimeState(
  payload,
  {
    error = null,
    fromCache = false,
    now = Date.now,
    retained = false,
    status,
  } = {},
) {
  const normalizedPayload = payload || null;
  const contract = classifyOfficialAlertState(normalizedPayload, { now });
  const resolvedStatus = status
    || (error
      ? normalizedPayload ? "retained" : "error"
      : retained
        ? "retained"
        : fromCache
          ? "cache"
          : normalizedPayload
            ? "fresh"
            : "empty");

  return {
    active: contract.active,
    alertState: contract.state,
    canShowBanner: contract.canShowBanner,
    contract,
    error: error ? getErrorMessage(error) : null,
    fromCache: Boolean(fromCache),
    payload: normalizedPayload,
    retained: Boolean(retained),
    status: resolvedStatus,
  };
}

export function readInitialOfficialAlertsRuntime({ storage, now = Date.now } = {}) {
  const payload = readRegionalOfficialAlertsCache({ storage, now });

  return createOfficialAlertsRuntimeState(payload, {
    fromCache: Boolean(payload),
    now,
    status: payload ? "cache" : "empty",
  });
}

export async function loadOfficialAlertsRuntime({
  alertsFetcher = fetchOfficialAlertsPayload,
  apiBase,
  fetchImpl = globalThis.fetch,
  force = false,
  now = Date.now,
  storage,
} = {}) {
  const load = beginRuntimeLoad(storage);
  const previousPayload = readRegionalOfficialAlertsCache({ storage, now });
  const previousContract = classifyOfficialAlertState(previousPayload, { now });

  try {
    const nextPayload = await alertsFetcher({ apiBase, fetchImpl, force, now });
    if (!isLatestRuntimeLoad(load)) {
      return resolveSupersededRuntimeState(load, { storage, now });
    }

    const nextContract = classifyOfficialAlertState(nextPayload, { now });
    const resolvedPayload = reconcileRegionalOfficialAlerts(
      nextPayload,
      previousPayload,
      { storage, now },
    );
    const retained = (
      !AUTHORITATIVE_ALERT_STATES.has(nextContract.state)
      && previousContract.state === OFFICIAL_ALERT_STATES.ACTIVE
    );

    return rememberLatestRuntimeState(load, createOfficialAlertsRuntimeState(resolvedPayload, {
      fromCache: retained,
      now,
      retained,
      status: retained
        ? "retained"
        : AUTHORITATIVE_ALERT_STATES.has(nextContract.state)
          ? "fresh"
          : "unavailable",
    }));
  } catch (error) {
    if (!isLatestRuntimeLoad(load)) {
      return resolveSupersededRuntimeState(load, { storage, now });
    }

    const retainedPayload = readRegionalOfficialAlertsCache({ storage, now }) || previousPayload;

    return rememberLatestRuntimeState(load, createOfficialAlertsRuntimeState(retainedPayload, {
      error,
      fromCache: Boolean(retainedPayload),
      now,
      retained: Boolean(retainedPayload),
      status: retainedPayload ? "retained" : "error",
    }));
  }
}
