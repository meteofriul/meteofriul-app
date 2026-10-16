import { describe, expect, it } from "vitest";

import activeOrangeDpcFallback from "../../tests/fixtures/officialAlerts/active-orange-dpc-fallback.json";
import activeYellowRegional from "../../tests/fixtures/officialAlerts/active-yellow-regional.json";
import diagnosticDpcNoActiveFvg from "../../tests/fixtures/officialAlerts/diagnostic-dpc-no-active-fvg.json";
import expiredRegionalAlert from "../../tests/fixtures/officialAlerts/expired-regional-alert.json";
import inactiveConfirmedRegional from "../../tests/fixtures/officialAlerts/inactive-confirmed-regional.json";
import staleRegionalCache from "../../tests/fixtures/officialAlerts/stale-regional-cache.json";
import unavailableFastFallback from "../../tests/fixtures/officialAlerts/unavailable-fast-fallback.json";
import {
  OFFICIAL_ALERT_STATES,
  buildOfficialAlertSummary,
  classifyOfficialAlertState,
} from "./officialAlerts";

const COPY = {
  alertsLabel: "Avvisi ufficiali",
  officialAlertMultipleLabel: "allerte ufficiali",
  officialAlertSeverityLabels: {
    orange: "Allerta arancione",
    red: "Allerta rossa",
    yellow: "Allerta gialla",
  },
  officialAlertSingleLabel: "Allerta ufficiale",
};

const NOW = "2026-06-24T10:00:00+02:00";

const CONTRACT_CASES = [
  {
    expected: {
      canClearPreviousAlert: false,
      canNotify: true,
      canShowBanner: true,
      confidence: "high",
      count: 1,
      label: "Allerta gialla",
      sourceAuthority: "regional_fvg",
      state: OFFICIAL_ALERT_STATES.ACTIVE,
    },
    name: "regional yellow alert",
    payload: activeYellowRegional,
  },
  {
    expected: {
      canClearPreviousAlert: true,
      canNotify: false,
      canShowBanner: false,
      confidence: "high",
      count: 0,
      label: "",
      sourceAuthority: "regional_fvg",
      state: OFFICIAL_ALERT_STATES.INACTIVE_CONFIRMED,
    },
    name: "confirmed regional green/no-alert",
    payload: inactiveConfirmedRegional,
  },
  {
    expected: {
      canClearPreviousAlert: false,
      canNotify: false,
      canShowBanner: false,
      confidence: "low",
      count: 0,
      label: "",
      sourceAuthority: "backend_fallback",
      state: OFFICIAL_ALERT_STATES.UNAVAILABLE,
    },
    name: "unavailable backend fallback",
    payload: unavailableFastFallback,
  },
  {
    expected: {
      canClearPreviousAlert: false,
      canNotify: false,
      canShowBanner: false,
      confidence: "low",
      count: 1,
      label: "",
      sourceAuthority: "regional_fvg",
      state: OFFICIAL_ALERT_STATES.STALE,
    },
    name: "stale regional cache",
    payload: staleRegionalCache,
  },
  {
    expected: {
      canClearPreviousAlert: false,
      canNotify: false,
      canShowBanner: false,
      confidence: "low",
      count: 0,
      label: "",
      sourceAuthority: "regional_fvg",
      state: OFFICIAL_ALERT_STATES.EXPIRED,
    },
    name: "expired regional alert",
    payload: expiredRegionalAlert,
  },
  {
    expected: {
      canClearPreviousAlert: false,
      canNotify: false,
      canShowBanner: false,
      confidence: "low",
      count: 0,
      label: "",
      sourceAuthority: "national_dpc",
      state: OFFICIAL_ALERT_STATES.DIAGNOSTIC,
    },
    name: "DPC diagnostic no-active fallback",
    payload: diagnosticDpcNoActiveFvg,
  },
  {
    expected: {
      canClearPreviousAlert: false,
      canNotify: false,
      canShowBanner: false,
      confidence: "low",
      count: 1,
      label: "",
      sourceAuthority: "national_dpc",
      state: OFFICIAL_ALERT_STATES.DIAGNOSTIC,
    },
    name: "DPC active fallback stays diagnostic",
    payload: activeOrangeDpcFallback,
  },
];

describe("official alert fixture contract", () => {
  it.each(CONTRACT_CASES)("classifies $name", ({ expected, payload }) => {
    const state = classifyOfficialAlertState(payload, { now: NOW });
    const summary = buildOfficialAlertSummary(payload, COPY, { now: NOW });

    expect(state).toMatchObject({
      canClearPreviousAlert: expected.canClearPreviousAlert,
      canNotify: expected.canNotify,
      canShowBanner: expected.canShowBanner,
      confidence: expected.confidence,
      count: expected.count,
      sourceAuthority: expected.sourceAuthority,
      state: expected.state,
    });

    expect(summary?.label || "").toBe(expected.label);
  });
});
