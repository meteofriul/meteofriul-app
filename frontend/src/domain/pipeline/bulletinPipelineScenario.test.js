import { describe, expect, it } from "vitest";

import activeYellowRegional from "../../tests/fixtures/officialAlerts/active-yellow-regional.json";
import diagnosticDpcNoActiveFvg from "../../tests/fixtures/officialAlerts/diagnostic-dpc-no-active-fvg.json";
import inactiveConfirmedRegional from "../../tests/fixtures/officialAlerts/inactive-confirmed-regional.json";
import unavailableFastFallback from "../../tests/fixtures/officialAlerts/unavailable-fast-fallback.json";
import normalizedFixture from "../../tests/fixtures/PW20260606.normalized.json";
import { OFFICIAL_ALERT_STATES } from "../alerts/officialAlerts";
import {
  OFFICIAL_ALERT_TRANSITION_ACTIONS,
  OFFICIAL_ALERT_TRANSITION_STATES,
  transitionOfficialAlertState,
} from "../alerts/officialAlertTransition";
import {
  OSMER_BULLETIN_TRANSITION_ACTIONS,
  OSMER_BULLETIN_TRANSITION_STATES,
  transitionOsmerBulletinState,
} from "../weather/osmerBulletinTransition";

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

function projectAppContract({ alertResult, bulletinResult }) {
  return {
    auditActions: [
      ...alertResult.actions,
      ...bulletinResult.actions,
    ],
    bulletin: {
      alertState: alertResult.finalState.state,
      canRenderNativeMap: bulletinResult.finalState.canRenderNativeMap,
      showAlertNotice: alertResult.finalState.canShowBulletinNotice,
      status: bulletinResult.finalState.status,
    },
    home: {
      canNotify: alertResult.finalState.canNotify,
      showFreshAlertBanner: alertResult.finalState.canShowFreshBanner,
      showHeldAlertBanner: Boolean(
        alertResult.finalState.canShowHomeBanner &&
        !alertResult.finalState.canShowFreshBanner,
      ),
      showHomeAlertBanner: alertResult.finalState.canShowHomeBanner,
    },
  };
}

describe("bulletin data pipeline scenario", () => {
  it("survives the official alert lifecycle without flapping or false green", () => {
    const active = transitionOfficialAlertState(null, activeYellowRegional, {
      now: "2026-06-24T10:05:00+02:00",
    });
    let app = projectAppContract({
      alertResult: active,
      bulletinResult: { actions: [], finalState: { canRenderNativeMap: false, status: "not-tested" } },
    });

    expect(app.home).toMatchObject({
      canNotify: true,
      showFreshAlertBanner: true,
      showHeldAlertBanner: false,
      showHomeAlertBanner: true,
    });
    expect(active.finalState.state).toBe(OFFICIAL_ALERT_STATES.ACTIVE);

    const held = transitionOfficialAlertState(
      {
        ...active.finalState,
        expires_at: "2026-06-25T23:59:00Z",
        fetched_at: "2026-06-24T22:00:00Z",
        state: OFFICIAL_ALERT_STATES.ACTIVE,
      },
      diagnosticDpcNoActiveFvg,
      {
        holdActiveMs: 3 * 60 * 60 * 1000,
        now: "2026-06-24T22:30:00Z",
      },
    );
    app = projectAppContract({
      alertResult: held,
      bulletinResult: { actions: [], finalState: { canRenderNativeMap: false, status: "not-tested" } },
    });

    expect(held.finalState.state).toBe(OFFICIAL_ALERT_TRANSITION_STATES.STALE_HELD_ACTIVE);
    expect(app.home).toMatchObject({
      canNotify: false,
      showFreshAlertBanner: false,
      showHeldAlertBanner: true,
      showHomeAlertBanner: true,
    });
    expect(app.bulletin.showAlertNotice).toBe(true);
    expect(app.auditActions).toContain(OFFICIAL_ALERT_TRANSITION_ACTIONS.LOG_DIAGNOSTIC_ALERT);

    const expired = transitionOfficialAlertState(
      {
        alerts: [{ id: "regional-yellow", level: "gialla", valid_to: "2026-06-24T23:59:00Z" }],
        expires_at: "2026-06-24T23:59:00Z",
        fetched_at: "2026-06-24T22:00:00Z",
        state: OFFICIAL_ALERT_STATES.ACTIVE,
      },
      unavailableFastFallback,
      { now: "2026-06-25T00:05:00Z" },
    );
    app = projectAppContract({
      alertResult: expired,
      bulletinResult: { actions: [], finalState: { canRenderNativeMap: false, status: "not-tested" } },
    });

    expect(expired.finalState.state).toBe(OFFICIAL_ALERT_STATES.EXPIRED);
    expect(app.home).toMatchObject({
      canNotify: false,
      showHomeAlertBanner: false,
    });
    expect(app.bulletin.showAlertNotice).toBe(true);
    expect(app.auditActions).toContain(OFFICIAL_ALERT_TRANSITION_ACTIONS.RETAIN_DB_CRITICALITY);

    const cleared = transitionOfficialAlertState(expired.finalState, inactiveConfirmedRegional, {
      now: "2026-06-25T01:00:00Z",
    });

    expect(cleared.finalState).toMatchObject({
      canClearPreviousAlert: true,
      canNotify: false,
      state: OFFICIAL_ALERT_STATES.INACTIVE_CONFIRMED,
    });
    expect(cleared.actions).toEqual([
      OFFICIAL_ALERT_TRANSITION_ACTIONS.CLEAR_ALL_ALERTS_AND_BANNERS,
      OFFICIAL_ALERT_TRANSITION_ACTIONS.RESET_STATE_ENGINE,
    ]);
  });

  it("survives OSMER midnight gaps and healed merges without hiding data provenance", () => {
    const lookbackSnapshot = fixtureWithSingleDay("2026-06-25", "2026-06-24");
    const missingCurrentXml = {
      days: [],
      fonte: "structured_xml",
      source_status: "source_404",
    };

    const lookback = transitionOsmerBulletinState(
      { snapshot: lookbackSnapshot },
      { snapshot: missingCurrentXml },
      {
        lookbackMs: 36 * 60 * 60 * 1000,
        now: "2026-06-25T00:05:00Z",
        requestedDate: "2026-06-25",
      },
    );
    let app = projectAppContract({
      alertResult: { actions: [], finalState: { canNotify: false, canShowBulletinNotice: false, canShowFreshBanner: false, canShowHomeBanner: false, state: "not-tested" } },
      bulletinResult: lookback,
    });

    expect(app.bulletin).toMatchObject({
      canRenderNativeMap: true,
      status: OSMER_BULLETIN_TRANSITION_STATES.STALE_FROM_CACHE,
    });
    expect(app.auditActions).toEqual([
      OSMER_BULLETIN_TRANSITION_ACTIONS.USE_LOOKBACK_SNAPSHOT,
      OSMER_BULLETIN_TRANSITION_ACTIONS.LOG_OSMER_SOURCE_GAP,
    ]);

    const previousSnapshot = fixtureWithSingleDay("2026-06-26", "2026-06-24");
    const currentSnapshot = fixtureWithSingleDay("2026-06-26", "2026-06-25", "2026-06-25T10:00:00Z");
    delete currentSnapshot.days[0].areas9.A9;

    const healed = transitionOsmerBulletinState(
      { snapshot: previousSnapshot },
      { snapshot: currentSnapshot },
      {
        now: "2026-06-25T10:05:00Z",
        requestedDate: "2026-06-26",
      },
    );
    app = projectAppContract({
      alertResult: { actions: [], finalState: { canNotify: false, canShowBulletinNotice: false, canShowFreshBanner: false, canShowHomeBanner: false, state: "not-tested" } },
      bulletinResult: healed,
    });

    expect(app.bulletin).toMatchObject({
      canRenderNativeMap: true,
      status: OSMER_BULLETIN_TRANSITION_STATES.PARTIAL_HEALED,
    });
    expect(healed.finalState).toMatchObject({
      confidence: "medium",
      healedAreasByDate: {
        "2026-06-26": ["A9"],
      },
      sourceKind: "mixed",
    });
    expect(healed.finalState.snapshot.days[0]).toMatchObject({
      fallback_source_date: "2026-06-24",
      healed_missing_areas: ["A9"],
      primary_source_date: "2026-06-25",
      source_mix: true,
    });
    expect(app.auditActions).toEqual([
      OSMER_BULLETIN_TRANSITION_ACTIONS.HEAL_MISSING_AREAS_FROM_PREVIOUS,
      OSMER_BULLETIN_TRANSITION_ACTIONS.LOG_OSMER_HEALED_MERGE,
    ]);
  });
});
