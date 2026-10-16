import { describe, expect, it } from "vitest";

import activeYellowRegional from "../../tests/fixtures/officialAlerts/active-yellow-regional.json";
import diagnosticDpcNoActiveFvg from "../../tests/fixtures/officialAlerts/diagnostic-dpc-no-active-fvg.json";
import inactiveConfirmedRegional from "../../tests/fixtures/officialAlerts/inactive-confirmed-regional.json";
import unavailableFastFallback from "../../tests/fixtures/officialAlerts/unavailable-fast-fallback.json";
import {
  OFFICIAL_ALERT_TRANSITION_ACTIONS,
  OFFICIAL_ALERT_TRANSITION_STATES,
  transitionOfficialAlertState,
} from "./officialAlertTransition";
import { OFFICIAL_ALERT_STATES } from "./officialAlerts";

describe("official alert transition engine", () => {
  it("emits a notification action only when an active alert is new", () => {
    const result = transitionOfficialAlertState(null, activeYellowRegional, {
      now: "2026-06-24T10:05:00+02:00",
    });

    expect(result.finalState).toMatchObject({
      active: true,
      canNotify: true,
      canShowHomeBanner: true,
      state: OFFICIAL_ALERT_STATES.ACTIVE,
    });
    expect(result.finalState.alertSignature).toContain("pc fvg yellow storm 20260624");
    expect(result.actions).toEqual([
      OFFICIAL_ALERT_TRANSITION_ACTIONS.NOTIFY_NEW_OFFICIAL_ALERT,
    ]);
  });

  it("keeps the banner but suppresses notification when the same active alert is confirmed again", () => {
    const previousResult = transitionOfficialAlertState(null, activeYellowRegional, {
      now: "2026-06-24T10:05:00+02:00",
    });

    const result = transitionOfficialAlertState(previousResult.finalState, activeYellowRegional, {
      now: "2026-06-24T10:15:00+02:00",
    });

    expect(result.finalState).toMatchObject({
      active: true,
      canNotify: false,
      canShowHomeBanner: true,
      state: OFFICIAL_ALERT_STATES.ACTIVE,
    });
    expect(result.actions).toEqual([
      OFFICIAL_ALERT_TRANSITION_ACTIONS.SUPPRESS_DUPLICATE_NOTIFICATION,
    ]);
  });

  it("emits a notification action when the active alert signature changes", () => {
    const previousResult = transitionOfficialAlertState(null, activeYellowRegional, {
      now: "2026-06-24T10:05:00+02:00",
    });
    const changedObservation = {
      ...activeYellowRegional,
      alerts: [
        {
          ...activeYellowRegional.alerts[0],
          id: "pc-fvg-orange-storm-20260624",
          level: "arancione",
          title: "Allerta regionale arancione",
        },
      ],
    };

    const result = transitionOfficialAlertState(previousResult.finalState, changedObservation, {
      now: "2026-06-24T11:05:00+02:00",
    });

    expect(result.finalState).toMatchObject({
      active: true,
      canNotify: true,
      state: OFFICIAL_ALERT_STATES.ACTIVE,
    });
    expect(result.actions).toEqual([
      OFFICIAL_ALERT_TRANSITION_ACTIONS.NOTIFY_NEW_OFFICIAL_ALERT,
    ]);
  });

  it("holds a recent regional alert when DPC no-active is only diagnostic", () => {
    const previousState = {
      alerts: [{ id: "regional-yellow", level: "gialla" }],
      count: 1,
      fetched_at: "2026-06-24T22:00:00Z",
      state: OFFICIAL_ALERT_STATES.ACTIVE,
    };

    const result = transitionOfficialAlertState(previousState, diagnosticDpcNoActiveFvg, {
      holdActiveMs: 3 * 60 * 60 * 1000,
      now: "2026-06-24T22:30:00Z",
    });

    expect(result.finalState).toMatchObject({
      active: false,
      canClearPreviousAlert: false,
      canNotify: false,
      canShowBulletinNotice: true,
      canShowFreshBanner: false,
      canShowHomeBanner: true,
      count: 1,
      freshness: "stale",
      state: OFFICIAL_ALERT_TRANSITION_STATES.STALE_HELD_ACTIVE,
    });
    expect(result.finalState.alerts).toEqual(previousState.alerts);
    expect(result.actions).toEqual([
      OFFICIAL_ALERT_TRANSITION_ACTIONS.DISABLE_NEW_NOTIFICATIONS,
      OFFICIAL_ALERT_TRANSITION_ACTIONS.KEEP_BULLETIN_NOTICE,
      OFFICIAL_ALERT_TRANSITION_ACTIONS.LOG_DIAGNOSTIC_ALERT,
    ]);
  });

  it("moves an expired alert to expired, not confirmed green, when sources are unavailable", () => {
    const previousState = {
      alerts: [{ id: "regional-yellow", level: "gialla", valid_to: "2026-06-24T23:59:00Z" }],
      expires_at: "2026-06-24T23:59:00Z",
      fetched_at: "2026-06-24T21:00:00Z",
      state: OFFICIAL_ALERT_STATES.ACTIVE,
    };

    const result = transitionOfficialAlertState(previousState, unavailableFastFallback, {
      now: "2026-06-25T00:05:00Z",
    });

    expect(result.finalState).toMatchObject({
      active: false,
      canClearPreviousAlert: false,
      canNotify: false,
      canShowBulletinNotice: true,
      canShowFreshBanner: false,
      canShowHomeBanner: false,
      freshness: "stale",
      state: OFFICIAL_ALERT_STATES.EXPIRED,
    });
    expect(result.actions).toEqual([
      OFFICIAL_ALERT_TRANSITION_ACTIONS.HIDE_BANNER_FROM_HOME,
      OFFICIAL_ALERT_TRANSITION_ACTIONS.RETAIN_DB_CRITICALITY,
    ]);
  });

  it("clears held or expired alerts only after a confirmed regional no-alert read", () => {
    const previousState = {
      fetched_at: "2026-06-24T22:00:00Z",
      state: OFFICIAL_ALERT_TRANSITION_STATES.STALE_HELD_ACTIVE,
    };

    const result = transitionOfficialAlertState(previousState, inactiveConfirmedRegional, {
      now: "2026-06-25T01:00:00Z",
    });

    expect(result.finalState).toMatchObject({
      active: false,
      canClearPreviousAlert: true,
      canNotify: false,
      canShowHomeBanner: false,
      state: OFFICIAL_ALERT_STATES.INACTIVE_CONFIRMED,
    });
    expect(result.actions).toEqual([
      OFFICIAL_ALERT_TRANSITION_ACTIONS.CLEAR_ALL_ALERTS_AND_BANNERS,
      OFFICIAL_ALERT_TRANSITION_ACTIONS.RESET_STATE_ENGINE,
    ]);
  });
});
