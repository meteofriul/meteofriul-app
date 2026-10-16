import {
  OSMER_SOURCE_KINDS,
  classifyOsmerStructuredSnapshot,
} from "./osmerStructuredContract";

export const OSMER_BULLETIN_TRANSITION_STATES = Object.freeze({
  PARTIAL_HEALED: "partial_healed",
  READY: "ready",
  STALE_FROM_CACHE: "stale_from_cache",
  UNAVAILABLE: "unavailable",
});

export const OSMER_BULLETIN_TRANSITION_ACTIONS = Object.freeze({
  HEAL_MISSING_AREAS_FROM_PREVIOUS: "HEAL_MISSING_AREAS_FROM_PREVIOUS",
  LOG_OSMER_HEALED_MERGE: "LOG_OSMER_HEALED_MERGE",
  LOG_OSMER_SOURCE_GAP: "LOG_OSMER_SOURCE_GAP",
  USE_LOOKBACK_SNAPSHOT: "USE_LOOKBACK_SNAPSHOT",
});

const DEFAULT_LOOKBACK_MS = 36 * 60 * 60 * 1000;
const REQUIRED_AREA_IDS = ["A1", "A2", "A3", "A4", "A5", "A6", "A7", "A8", "A9"];

function clone(value) {
  return JSON.parse(JSON.stringify(value));
}

function getTimestamp(value) {
  if (!value) return null;
  const date = new Date(value);
  const time = date.getTime();
  return Number.isFinite(time) ? time : null;
}

function getNowTimestamp(now) {
  const value = typeof now === "function" ? now() : now;
  if (value === undefined || value === null) return Date.now();
  if (Number.isFinite(Number(value))) return Number(value);
  return getTimestamp(value) ?? Date.now();
}

function getSnapshotTime(snapshot = {}) {
  return getTimestamp(snapshot.updated_at || snapshot.updatedAt || snapshot.data_emissione || snapshot.published_at);
}

function isWithinLookback(snapshot = {}, { lookbackMs = DEFAULT_LOOKBACK_MS, now } = {}) {
  const snapshotTime = getSnapshotTime(snapshot);
  if (snapshotTime === null) return false;

  return getNowTimestamp(now) - snapshotTime <= lookbackMs;
}

function getDaysByValidDate(snapshot = {}) {
  return new Map(
    (snapshot.days || [])
      .filter((day) => day?.valid_date)
      .map((day) => [day.valid_date, day]),
  );
}

function getRequestedDay(snapshot = {}, requestedDate = "") {
  return (snapshot.days || []).find((day) => day?.valid_date === requestedDate) || null;
}

function canUseLookbackSnapshot(snapshot = {}, context = {}) {
  if (!snapshot?.days?.length || !context.requestedDate) return false;
  if (!isWithinLookback(snapshot, context)) return false;

  return Boolean(getRequestedDay(snapshot, context.requestedDate));
}

function markHealedDay(day, {
  fallbackSourceDate = "",
  healedMissingAreas = [],
  primarySourceDate = "",
} = {}) {
  return {
    ...day,
    healed_missing_areas: healedMissingAreas,
    primary_source_date: primarySourceDate,
    fallback_source_date: fallbackSourceDate,
    quality: {
      ...(day.quality || {}),
      all_nodes_present: true,
      confidence: "medium",
      healed_missing_areas: healedMissingAreas,
      source_mix: true,
    },
    source_mix: true,
  };
}

function healMissingAreas(primaryDay = {}, fallbackDay = null, {
  fallbackSourceDate = "",
  primarySourceDate = "",
} = {}) {
  if (!fallbackDay?.areas9) {
    return { day: primaryDay, healedMissingAreas: [] };
  }

  const nextAreas = { ...(primaryDay.areas9 || {}) };
  const healedMissingAreas = [];

  for (const areaId of REQUIRED_AREA_IDS) {
    if (!nextAreas[areaId] && fallbackDay.areas9[areaId]) {
      nextAreas[areaId] = {
        ...fallbackDay.areas9[areaId],
        healed_from_previous_snapshot: true,
      };
      healedMissingAreas.push(areaId);
    }
  }

  if (!healedMissingAreas.length) return { day: primaryDay, healedMissingAreas };

  return {
    day: markHealedDay({
      ...primaryDay,
      areas9: nextAreas,
    }, {
      fallbackSourceDate,
      healedMissingAreas,
      primarySourceDate,
    }),
    healedMissingAreas,
  };
}

function mergeWithPreviousSnapshot(primarySnapshot = {}, previousSnapshot = {}) {
  const fallbackDaysByDate = getDaysByValidDate(previousSnapshot);
  const healedAreasByDate = {};
  const mergedDays = (primarySnapshot.days || []).map((day) => {
    const fallbackDay = fallbackDaysByDate.get(day.valid_date);
    const { day: mergedDay, healedMissingAreas } = healMissingAreas(day, fallbackDay, {
      fallbackSourceDate: previousSnapshot.source_date || "",
      primarySourceDate: primarySnapshot.source_date || "",
    });

    if (healedMissingAreas.length) {
      healedAreasByDate[day.valid_date] = healedMissingAreas;
    }

    return mergedDay;
  });

  return {
    healedAreasByDate,
    snapshot: {
      ...primarySnapshot,
      days: mergedDays,
      quality: Object.keys(healedAreasByDate).length
        ? {
            ...(primarySnapshot.quality || {}),
            confidence: "medium",
            healed_missing_areas_by_date: healedAreasByDate,
            source_mix: true,
          }
        : primarySnapshot.quality,
      source_mix: Object.keys(healedAreasByDate).length || Boolean(primarySnapshot.source_mix),
    },
  };
}

function buildFinalState(status, snapshot, overrides = {}) {
  const contract = classifyOsmerStructuredSnapshot(snapshot);

  return {
    canRenderNativeMap: contract.canRenderNativeMap,
    canUseAsCurrent: status === OSMER_BULLETIN_TRANSITION_STATES.READY,
    contract,
    snapshot,
    status,
    ...overrides,
  };
}

export function transitionOsmerBulletinState(previousState = null, newObservation = null, context = {}) {
  const previousSnapshot = previousState?.snapshot || previousState || null;
  const observedSnapshot = newObservation?.snapshot || newObservation || null;
  const observedContract = classifyOsmerStructuredSnapshot(observedSnapshot);

  if (
    observedContract.state === "unavailable" &&
    canUseLookbackSnapshot(previousSnapshot || {}, context)
  ) {
    return {
      actions: [
        OSMER_BULLETIN_TRANSITION_ACTIONS.USE_LOOKBACK_SNAPSHOT,
        OSMER_BULLETIN_TRANSITION_ACTIONS.LOG_OSMER_SOURCE_GAP,
      ],
      finalState: buildFinalState(
        OSMER_BULLETIN_TRANSITION_STATES.STALE_FROM_CACHE,
        previousSnapshot,
        {
          canUseAsCurrent: true,
          requestedDate: context.requestedDate || "",
          usedLookback: true,
        },
      ),
      observation: observedContract,
    };
  }

  if (observedSnapshot?.days?.length && previousSnapshot?.days?.length) {
    const { healedAreasByDate, snapshot } = mergeWithPreviousSnapshot(clone(observedSnapshot), previousSnapshot);
    const healedDates = Object.keys(healedAreasByDate);

    if (healedDates.length) {
      return {
        actions: [
          OSMER_BULLETIN_TRANSITION_ACTIONS.HEAL_MISSING_AREAS_FROM_PREVIOUS,
          OSMER_BULLETIN_TRANSITION_ACTIONS.LOG_OSMER_HEALED_MERGE,
        ],
        finalState: buildFinalState(
          OSMER_BULLETIN_TRANSITION_STATES.PARTIAL_HEALED,
          snapshot,
          {
            canUseAsCurrent: true,
            confidence: "medium",
            healedAreasByDate,
            sourceKind: OSMER_SOURCE_KINDS.MIXED,
          },
        ),
        observation: observedContract,
      };
    }
  }

  if (observedContract.state === "unavailable") {
    return {
      actions: [OSMER_BULLETIN_TRANSITION_ACTIONS.LOG_OSMER_SOURCE_GAP],
      finalState: buildFinalState(OSMER_BULLETIN_TRANSITION_STATES.UNAVAILABLE, observedSnapshot, {
        canRenderNativeMap: false,
        canUseAsCurrent: false,
      }),
      observation: observedContract,
    };
  }

  return {
    actions: [],
    finalState: buildFinalState(OSMER_BULLETIN_TRANSITION_STATES.READY, observedSnapshot),
    observation: observedContract,
  };
}
