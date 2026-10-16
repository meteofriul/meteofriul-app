import { describe, expect, it } from "vitest";

import normalizedFixture from "../../tests/fixtures/PW20260606.normalized.json";
import {
  OSMER_SOURCE_KINDS,
  OSMER_STRUCTURED_STATES,
  classifyOsmerStructuredDay,
  classifyOsmerStructuredSnapshot,
} from "./osmerStructuredContract";

function clone(value) {
  return JSON.parse(JSON.stringify(value));
}

function completeProjectedDay() {
  const day = clone(normalizedFixture.days[0]);

  for (const area of Object.values(day.areas9)) {
    area.source_kind = OSMER_SOURCE_KINDS.OFFICIAL_PROJECTED;
    area.projected_condition = "poco nuvoloso";
  }

  return {
    ...day,
    source_kind: OSMER_SOURCE_KINDS.OFFICIAL_PROJECTED,
  };
}

describe("OSMER structured contract", () => {
  it("accepts the real normalized XML fixture as native and complete", () => {
    const snapshot = classifyOsmerStructuredSnapshot(normalizedFixture);
    const firstDay = snapshot.dayContracts[0];

    expect(snapshot).toMatchObject({
      canRenderNativeMap: true,
      canUseAsCurrent: true,
      confidence: "alta",
      daysCount: 2,
      isStale: false,
      sourceKind: OSMER_SOURCE_KINDS.STRUCTURED_XML,
      state: OSMER_STRUCTURED_STATES.READY,
    });
    expect(firstDay).toMatchObject({
      areaCount: 9,
      canRenderMap: true,
      canRenderNativeMap: true,
      canRenderProjectedMap: false,
      canUseFullBulletin: true,
      fasceCount: 4,
      hasCompleteAreas: true,
      hasCompleteFasce: true,
      sourceKind: OSMER_SOURCE_KINDS.STRUCTURED_XML,
      state: OSMER_STRUCTURED_STATES.READY,
      validDate: "2026-06-07",
    });
  });

  it("marks a day without all A1-A9 areas as partial and not renderable as a map", () => {
    const fixture = clone(normalizedFixture);
    delete fixture.days[0].areas9.A9;

    const snapshot = classifyOsmerStructuredSnapshot(fixture);
    const firstDay = snapshot.dayContracts[0];

    expect(snapshot.state).toBe(OSMER_STRUCTURED_STATES.PARTIAL);
    expect(firstDay).toMatchObject({
      areaCount: 8,
      canRenderMap: false,
      canRenderNativeMap: false,
      hasCompleteAreas: false,
      missingAreas: ["A9"],
      state: OSMER_STRUCTURED_STATES.PARTIAL,
    });
  });

  it("marks missing F1-F4 bands as partial without blocking the native map geometry", () => {
    const fixture = clone(normalizedFixture);
    delete fixture.days[0].fasce4.F4;

    const firstDay = classifyOsmerStructuredDay(fixture.days[0], { snapshot: fixture });

    expect(firstDay).toMatchObject({
      canRenderNativeMap: true,
      canUseFullBulletin: false,
      fasceCount: 3,
      hasCompleteAreas: true,
      hasCompleteFasce: false,
      missingFasce: ["F4"],
      state: OSMER_STRUCTURED_STATES.PARTIAL,
    });
  });

  it("keeps stale structured data out of current native map rendering", () => {
    const fixture = clone(normalizedFixture);
    fixture.is_stale = true;
    fixture.source_status = "source_unavailable";
    fixture.stale_reason = "source_404";

    const snapshot = classifyOsmerStructuredSnapshot(fixture);
    const firstDay = snapshot.dayContracts[0];

    expect(snapshot).toMatchObject({
      canRenderNativeMap: false,
      canUseAsCurrent: false,
      isStale: true,
      state: OSMER_STRUCTURED_STATES.STALE,
    });
    expect(firstDay).toMatchObject({
      canRenderMap: false,
      canRenderNativeMap: false,
      state: OSMER_STRUCTURED_STATES.STALE,
    });
  });

  it("classifies an unavailable source without days as unavailable", () => {
    expect(classifyOsmerStructuredSnapshot({
      days: [],
      fonte: OSMER_SOURCE_KINDS.STRUCTURED_XML,
      source_status: "source_unavailable",
    })).toMatchObject({
      canRenderNativeMap: false,
      canUseAsCurrent: false,
      daysCount: 0,
      state: OSMER_STRUCTURED_STATES.UNAVAILABLE,
    });
  });

  it("keeps official projected maps distinct from native XML maps", () => {
    const snapshot = {
      days: [completeProjectedDay()],
      fonte: OSMER_SOURCE_KINDS.OFFICIAL_PROJECTED,
      quality: { confidence: "media" },
      source_status: "official_projected",
    };
    const firstDay = classifyOsmerStructuredSnapshot(snapshot).dayContracts[0];

    expect(firstDay).toMatchObject({
      canRenderMap: true,
      canRenderNativeMap: false,
      canRenderProjectedMap: true,
      canUseFullBulletin: false,
      sourceKind: OSMER_SOURCE_KINDS.OFFICIAL_PROJECTED,
      state: OSMER_STRUCTURED_STATES.READY,
    });
  });
});
