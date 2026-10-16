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
} from "../alerts/officialAlertTransition";
import {
  OSMER_BULLETIN_TRANSITION_ACTIONS,
  OSMER_BULLETIN_TRANSITION_STATES,
} from "../weather/osmerBulletinTransition";
import {
  BACKEND_DATA_STATE_SCHEMA_VERSION,
  buildOfficialAlertObservationDocument,
  buildOfficialAlertStateDocument,
  buildOfficialAlertTransitionDocument,
  buildOsmerBulletinObservationDocument,
  buildOsmerBulletinStateDocument,
  buildOsmerBulletinTransitionDocument,
} from "./backendDataStateContract";

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

describe("backend data state contract simulator", () => {
  it("builds an official alert observation document without losing source authority", () => {
    const document = buildOfficialAlertObservationDocument(activeYellowRegional, {
      observedAt: "2026-06-24T10:00:00Z",
      observationId: "obs-active-yellow",
    });

    expect(document).toMatchObject({
      active: true,
      count: 1,
      fetch_status: "success",
      observation_id: "obs-active-yellow",
      observed_at: "2026-06-24T10:00:00Z",
      parser_status: "success",
      schema_version: BACKEND_DATA_STATE_SCHEMA_VERSION,
      source_authority: "regional_fvg",
      source_mode: "github_actions_official_page",
    });
    expect(document.alerts).toHaveLength(1);
  });

  it("produces an official alert state document that can notify only for a new active alert", () => {
    const state = buildOfficialAlertStateDocument(null, activeYellowRegional, {
      now: "2026-06-24T10:05:00+02:00",
    });

    expect(state).toMatchObject({
      active: true,
      can_clear_previous_alert: false,
      can_notify: true,
      can_show_bulletin_notice: true,
      can_show_home_banner: true,
      confidence: "high",
      count: 1,
      previous_state: "",
      schema_version: BACKEND_DATA_STATE_SCHEMA_VERSION,
      source_authority: "regional_fvg",
      source_mode: "github_actions_official_page",
      state: OFFICIAL_ALERT_STATES.ACTIVE,
      state_id: "official-alert-state-current",
      transition_actions: [
        OFFICIAL_ALERT_TRANSITION_ACTIONS.NOTIFY_NEW_OFFICIAL_ALERT,
      ],
    });
    expect(state.alert_signature).toContain("pc fvg yellow storm 20260624");
  });

  it("keeps a repeated active official alert visible but not notifiable", () => {
    const previousState = buildOfficialAlertStateDocument(null, activeYellowRegional, {
      now: "2026-06-24T10:05:00+02:00",
    });
    const state = buildOfficialAlertStateDocument(previousState, activeYellowRegional, {
      now: "2026-06-24T10:15:00+02:00",
    });

    expect(state).toMatchObject({
      active: true,
      can_notify: false,
      can_show_home_banner: true,
      previous_state: OFFICIAL_ALERT_STATES.ACTIVE,
      state: OFFICIAL_ALERT_STATES.ACTIVE,
      transition_actions: [
        OFFICIAL_ALERT_TRANSITION_ACTIONS.SUPPRESS_DUPLICATE_NOTIFICATION,
      ],
    });
  });

  it("holds a recent regional alert when DPC no-active is only diagnostic", () => {
    const previousState = buildOfficialAlertStateDocument(null, activeYellowRegional, {
      now: "2026-06-24T10:05:00+02:00",
    });
    const held = buildOfficialAlertStateDocument(previousState, diagnosticDpcNoActiveFvg, {
      holdActiveMs: 3 * 60 * 60 * 1000,
      now: "2026-06-24T10:30:00+02:00",
    });

    expect(held).toMatchObject({
      active: false,
      can_clear_previous_alert: false,
      can_notify: false,
      can_show_bulletin_notice: true,
      can_show_home_banner: true,
      source_authority: "national_dpc",
      state: OFFICIAL_ALERT_TRANSITION_STATES.STALE_HELD_ACTIVE,
      transition_actions: [
        OFFICIAL_ALERT_TRANSITION_ACTIONS.DISABLE_NEW_NOTIFICATIONS,
        OFFICIAL_ALERT_TRANSITION_ACTIONS.KEEP_BULLETIN_NOTICE,
        OFFICIAL_ALERT_TRANSITION_ACTIONS.LOG_DIAGNOSTIC_ALERT,
      ],
    });
    expect(held.alerts).toHaveLength(1);
  });

  it("marks expired without network as not confirmed green and clears only after regional no-alert", () => {
    const expired = buildOfficialAlertStateDocument(
      {
        alerts: [{ id: "regional-yellow", level: "gialla", valid_to: "2026-06-24T23:59:00Z" }],
        expires_at: "2026-06-24T23:59:00Z",
        fetched_at: "2026-06-24T22:00:00Z",
        state: OFFICIAL_ALERT_STATES.ACTIVE,
      },
      unavailableFastFallback,
      { now: "2026-06-25T00:05:00Z" },
    );

    expect(expired).toMatchObject({
      can_clear_previous_alert: false,
      can_notify: false,
      can_show_home_banner: false,
      state: OFFICIAL_ALERT_STATES.EXPIRED,
      transition_actions: [
        OFFICIAL_ALERT_TRANSITION_ACTIONS.HIDE_BANNER_FROM_HOME,
        OFFICIAL_ALERT_TRANSITION_ACTIONS.RETAIN_DB_CRITICALITY,
      ],
    });

    const cleared = buildOfficialAlertStateDocument(expired, inactiveConfirmedRegional, {
      now: "2026-06-25T01:00:00Z",
    });

    expect(cleared).toMatchObject({
      can_clear_previous_alert: true,
      can_notify: false,
      state: OFFICIAL_ALERT_STATES.INACTIVE_CONFIRMED,
      transition_actions: [
        OFFICIAL_ALERT_TRANSITION_ACTIONS.CLEAR_ALL_ALERTS_AND_BANNERS,
        OFFICIAL_ALERT_TRANSITION_ACTIONS.RESET_STATE_ENGINE,
      ],
    });
  });

  it("builds an official alert transition audit document from state actions", () => {
    const transition = buildOfficialAlertTransitionDocument(null, activeYellowRegional, {
      computedAt: "2026-06-24T10:00:05Z",
      now: "2026-06-24T10:00:05Z",
      observationId: "obs-active-yellow",
      transitionId: "transition-active-yellow",
    });

    expect(transition).toMatchObject({
      actions: [OFFICIAL_ALERT_TRANSITION_ACTIONS.NOTIFY_NEW_OFFICIAL_ALERT],
      computed_at: "2026-06-24T10:00:05Z",
      dry_run: true,
      from_state: "",
      observation_id: "obs-active-yellow",
      schema_version: BACKEND_DATA_STATE_SCHEMA_VERSION,
      to_state: OFFICIAL_ALERT_STATES.ACTIVE,
      transition_id: "transition-active-yellow",
    });
  });

  it("builds an OSMER observation document from the normalized XML fixture", () => {
    const observation = buildOsmerBulletinObservationDocument(normalizedFixture, {
      language: "it",
      observationId: "obs-osmer-normalized",
      observedAt: "2026-06-24T10:00:00Z",
    });

    expect(observation).toMatchObject({
      id_emissione: normalizedFixture.id_emissione,
      language: "it",
      observation_id: "obs-osmer-normalized",
      observed_at: "2026-06-24T10:00:00Z",
      schema_version: BACKEND_DATA_STATE_SCHEMA_VERSION,
      source_kind: "structured_xml",
      source_status: normalizedFixture.source_status,
    });
    expect(observation.days).toHaveLength(normalizedFixture.days.length);
  });

  it("uses a lookback OSMER snapshot as current only with explicit warning and action", () => {
    const previousSnapshot = fixtureWithSingleDay("2026-06-25", "2026-06-24");
    const unavailableObservation = {
      days: [],
      fonte: "structured_xml",
      source_status: "source_404",
    };

    const state = buildOsmerBulletinStateDocument(
      { snapshot: previousSnapshot },
      { snapshot: unavailableObservation },
      {
        lookbackMs: 36 * 60 * 60 * 1000,
        now: "2026-06-25T00:05:00Z",
        requestedDate: "2026-06-25",
      },
    );

    expect(state).toMatchObject({
      can_render_native_map: true,
      can_use_as_current: true,
      source_kind: "structured_xml",
      state: OSMER_BULLETIN_TRANSITION_STATES.STALE_FROM_CACHE,
      transition_actions: [
        OSMER_BULLETIN_TRANSITION_ACTIONS.USE_LOOKBACK_SNAPSHOT,
        OSMER_BULLETIN_TRANSITION_ACTIONS.LOG_OSMER_SOURCE_GAP,
      ],
      valid_dates: ["2026-06-25"],
      warnings: ["osmer_lookback_snapshot_used"],
    });
  });

  it("marks healed OSMER merges as mixed source state", () => {
    const previousSnapshot = fixtureWithSingleDay("2026-06-26", "2026-06-24");
    const currentSnapshot = fixtureWithSingleDay("2026-06-26", "2026-06-25", "2026-06-25T10:00:00Z");
    delete currentSnapshot.days[0].areas9.A9;

    const state = buildOsmerBulletinStateDocument(
      { snapshot: previousSnapshot },
      { snapshot: currentSnapshot },
      {
        now: "2026-06-25T10:05:00Z",
        requestedDate: "2026-06-26",
      },
    );

    expect(state).toMatchObject({
      can_render_native_map: true,
      can_use_as_current: true,
      confidence: "medium",
      healed_manifest: {
        "2026-06-26": ["A9"],
      },
      source_kind: "mixed",
      source_mix: true,
      state: OSMER_BULLETIN_TRANSITION_STATES.PARTIAL_HEALED,
      transition_actions: [
        OSMER_BULLETIN_TRANSITION_ACTIONS.HEAL_MISSING_AREAS_FROM_PREVIOUS,
        OSMER_BULLETIN_TRANSITION_ACTIONS.LOG_OSMER_HEALED_MERGE,
      ],
      warnings: ["osmer_source_mix_healed"],
    });
  });

  it("builds an OSMER transition audit document from state actions", () => {
    const previousSnapshot = fixtureWithSingleDay("2026-06-25", "2026-06-24");
    const unavailableObservation = {
      days: [],
      fonte: "structured_xml",
      source_status: "source_404",
    };
    const transition = buildOsmerBulletinTransitionDocument(
      { snapshot: previousSnapshot },
      { snapshot: unavailableObservation },
      {
        computedAt: "2026-06-25T00:05:05Z",
        now: "2026-06-25T00:05:05Z",
        observationId: "obs-osmer-gap",
        requestedDate: "2026-06-25",
        transitionId: "transition-osmer-gap",
      },
    );

    expect(transition).toMatchObject({
      actions: [
        OSMER_BULLETIN_TRANSITION_ACTIONS.USE_LOOKBACK_SNAPSHOT,
        OSMER_BULLETIN_TRANSITION_ACTIONS.LOG_OSMER_SOURCE_GAP,
      ],
      computed_at: "2026-06-25T00:05:05Z",
      observation_id: "obs-osmer-gap",
      schema_version: BACKEND_DATA_STATE_SCHEMA_VERSION,
      source_mix: false,
      to_state: OSMER_BULLETIN_TRANSITION_STATES.STALE_FROM_CACHE,
      transition_id: "transition-osmer-gap",
    });
  });
});
