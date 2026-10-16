import { describe, expect, it } from "vitest";

import normalizedFixture from "../../tests/fixtures/PW20260606.normalized.json";
import {
  OSMER_BULLETIN_TRANSITION_ACTIONS,
  OSMER_BULLETIN_TRANSITION_STATES,
  transitionOsmerBulletinState,
} from "./osmerBulletinTransition";

function clone(value) {
  return JSON.parse(JSON.stringify(value));
}

function fixtureWithSingleDay(validDate, sourceDate, updatedAt = "2026-06-24T22:00:00Z") {
  const snapshot = clone(normalizedFixture);
  snapshot.days = [snapshot.days[0]];
  snapshot.days[0].valid_date = validDate;
  snapshot.source_date = sourceDate;
  snapshot.updated_at = updatedAt;
  return snapshot;
}

describe("OSMER bulletin transition engine", () => {
  it("uses a lookback snapshot across midnight when the current XML is not available yet", () => {
    const previousSnapshot = fixtureWithSingleDay("2026-06-25", "2026-06-24");
    const unavailableObservation = {
      days: [],
      fonte: "structured_xml",
      source_status: "source_404",
    };

    const result = transitionOsmerBulletinState(
      { snapshot: previousSnapshot },
      { snapshot: unavailableObservation },
      {
        lookbackMs: 36 * 60 * 60 * 1000,
        now: "2026-06-25T00:05:00Z",
        requestedDate: "2026-06-25",
      },
    );

    expect(result.finalState).toMatchObject({
      canRenderNativeMap: true,
      canUseAsCurrent: true,
      requestedDate: "2026-06-25",
      status: OSMER_BULLETIN_TRANSITION_STATES.STALE_FROM_CACHE,
      usedLookback: true,
    });
    expect(result.finalState.snapshot.days[0].valid_date).toBe("2026-06-25");
    expect(result.actions).toEqual([
      OSMER_BULLETIN_TRANSITION_ACTIONS.USE_LOOKBACK_SNAPSHOT,
      OSMER_BULLETIN_TRANSITION_ACTIONS.LOG_OSMER_SOURCE_GAP,
    ]);
  });

  it("heals a missing A9 area from the previous snapshot without hiding the source mix", () => {
    const previousSnapshot = fixtureWithSingleDay("2026-06-26", "2026-06-24");
    const currentSnapshot = fixtureWithSingleDay("2026-06-26", "2026-06-25", "2026-06-25T10:00:00Z");
    delete currentSnapshot.days[0].areas9.A9;
    currentSnapshot.days[0].quality = {
      all_fasce_present: true,
      all_nodes_present: false,
      confidence: "bassa",
      missing_fasce: [],
      missing_nodes: ["A9"],
    };

    const result = transitionOsmerBulletinState(
      { snapshot: previousSnapshot },
      { snapshot: currentSnapshot },
      {
        now: "2026-06-25T10:05:00Z",
        requestedDate: "2026-06-26",
      },
    );
    const healedDay = result.finalState.snapshot.days[0];

    expect(result.finalState).toMatchObject({
      canRenderNativeMap: true,
      canUseAsCurrent: true,
      confidence: "medium",
      healedAreasByDate: {
        "2026-06-26": ["A9"],
      },
      sourceKind: "mixed",
      status: OSMER_BULLETIN_TRANSITION_STATES.PARTIAL_HEALED,
    });
    expect(healedDay.areas9.A9).toMatchObject({
      healed_from_previous_snapshot: true,
      id: "A9",
    });
    expect(healedDay).toMatchObject({
      fallback_source_date: "2026-06-24",
      healed_missing_areas: ["A9"],
      primary_source_date: "2026-06-25",
      source_mix: true,
    });
    expect(healedDay.quality).toMatchObject({
      confidence: "medium",
      healed_missing_areas: ["A9"],
      source_mix: true,
    });
    expect(result.actions).toEqual([
      OSMER_BULLETIN_TRANSITION_ACTIONS.HEAL_MISSING_AREAS_FROM_PREVIOUS,
      OSMER_BULLETIN_TRANSITION_ACTIONS.LOG_OSMER_HEALED_MERGE,
    ]);
  });
});
