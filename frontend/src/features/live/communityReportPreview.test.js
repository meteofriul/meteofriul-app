import { describe, expect, it } from "vitest";

import { normalizePublicCommunityIdentitySnapshot } from "../community/communityIdentity";
import {
  COMMUNITY_REPORT_PREVIEW_MODE_ACTIVE,
  COMMUNITY_REPORT_PREVIEW_MODE_INTERACTIVE,
  applyCommunityReportSimulationConfirmation,
  applyCommunityReportSimulationOverlay,
  applyCommunityReportSimulationSubmission,
  applyCommunityReportSimulationUndo,
  blockCommunityReportPreviewSubmission,
  createCommunityReportActivePreviewState,
  createCommunityReportPreviewLocation,
  createCommunityReportPreviewMemoryStorage,
  createCommunityReportSimulationOverlay,
  getLocalCommunityReportPreviewMode,
  isLocalCommunityReportPreviewEnabled,
  simulateCommunityReportConfirmation,
  simulateCommunityReportSubmission,
  simulateCommunityReportUndo,
} from "./communityReportPreview";
import { buildLiveViewModel } from "./liveViewModel";

describe("community report local preview", () => {
  it("requires both a development build and the explicit query flag", () => {
    expect(isLocalCommunityReportPreviewEnabled({
      dev: true,
      search: "?tab=live&communityReportQa=preview",
    })).toBe(true);
    expect(getLocalCommunityReportPreviewMode({
      dev: true,
      search: "?tab=live&communityReportQa=active",
    })).toBe(COMMUNITY_REPORT_PREVIEW_MODE_ACTIVE);
    expect(isLocalCommunityReportPreviewEnabled({
      dev: true,
      search: "?tab=live&communityReportQa=active",
    })).toBe(true);
    expect(getLocalCommunityReportPreviewMode({
      dev: true,
      search: "?tab=live&communityReportQa=interactive",
    })).toBe(COMMUNITY_REPORT_PREVIEW_MODE_INTERACTIVE);
    expect(isLocalCommunityReportPreviewEnabled({
      dev: true,
      search: "?tab=live",
    })).toBe(false);
    expect(isLocalCommunityReportPreviewEnabled({
      dev: false,
      search: "?tab=live&communityReportQa=active",
    })).toBe(false);
    expect(isLocalCommunityReportPreviewEnabled({
      dev: false,
      search: "?tab=live&communityReportQa=interactive",
    })).toBe(false);
  });

  it("builds three local active reports without changing webcam data", () => {
    const now = Date.parse("2026-08-29T18:00:00Z");
    const webcams = { payload: { webcams: [{ id: "sacile" }] }, status: "fresh" };
    const state = createCommunityReportActivePreviewState(
      { community: { payload: { report_locations: [] } }, webcams },
      { now },
    );
    const model = buildLiveViewModel(state, {
      location: { city: "Pordenone", lat: 45.9567, lon: 12.6605 },
      now: new Date(now),
    });

    expect(state.webcams).toBe(webcams);
    expect(state.community.payload.map_groups).toHaveLength(3);
    expect(state.community.payload.reports).toHaveLength(3);
    expect(state.community.payload.map_groups.map((group) => group.sourceKeys.length))
      .toEqual([3, 2, 1]);
    expect(state.community.payload.map_groups.map((group) => group.identities.length))
      .toEqual([3, 2, 1]);
    expect(state.community.payload.map_groups[0].identities.map(({ identity }) => identity.alias))
      .toEqual([
        "Clâf de Mont",
        "Acuile dal Vint",
        "Cjan de Mont",
      ]);
    expect(state.community.payload.reports.every((report) => report.sourceKey)).toBe(true);
    expect(state.community.payload.reports.every((report) => report.identity)).toBe(true);
    expect(model.community.items.map((item) => item.typeId)).toEqual([
      "rain",
      "wind",
      "quiet",
    ]);
    expect(model.community.markers).toHaveLength(3);
  });

  it("builds a local location with only the two nearest visible options", () => {
    expect(createCommunityReportPreviewLocation({
      locations: [
        { lat: 46.063, lon: 13.235, place: "Udine" },
        { lat: 45.957, lon: 12.661, place: "Pordenone" },
        { lat: 45.9836, lon: 12.7004, place: "Cordenons" },
        { lat: 45.9509, lon: 12.5022, place: "Sacile" },
      ],
      preferredPlace: "Pordenone",
    })).toMatchObject({
      coords: { accuracyM: 0, lat: 45.957, lon: 12.661 },
      nearbyPlaces: [
        { place: "Pordenone" },
        { place: "Cordenons" },
      ],
      ok: true,
      selectedPlace: "Pordenone",
      source: "local_preview",
    });
  });

  it("never uses an alphabetical neighbour outside the allowed radius", () => {
    const result = createCommunityReportPreviewLocation({
      locations: [
        { lat: 45.87276, lon: 13.36038, place: "Aiello del Friuli" },
        { lat: 46.37367, lon: 13.09368, place: "Amaro" },
        { lat: 45.89194, lon: 13.34861, place: "Visco" },
      ],
      preferredPlace: "Aiello del Friuli",
    });

    expect(result.nearbyPlaces.map((item) => item.place)).toEqual([
      "Aiello del Friuli",
      "Visco",
    ]);
  });

  it("blocks submission without calling any service", async () => {
    await expect(blockCommunityReportPreviewSubmission()).resolves.toEqual({
      ok: false,
      reason: "preview_only",
    });
  });

  it("simulates the complete mutation flow without a backend", async () => {
    const now = Date.parse("2026-08-29T18:00:00Z");
    const identity = {
      alias: "Cevron di Pordenon",
      avatar: {
        angle: 90,
        paletteId: "cobalt",
        patternId: "halo",
        variant: 1,
      },
      subjectId: "cevron",
      version: 1,
    };
    const location = {
      coords: { lat: 45.9567, lon: 12.6605 },
      selectedPlace: "Pordenone",
    };

    await expect(simulateCommunityReportSubmission(
      "snow",
      location,
      { identity, now: () => now },
    )).resolves.toMatchObject({
      ok: true,
      report: {
        expiresAt: now + 60 * 60_000,
        identity,
        place: "Pordenone",
        typeId: "snow",
      },
      undoUntil: now + 60_000,
    });
    await expect(simulateCommunityReportConfirmation(
      "qa-rain-pordenone",
      "yes",
    )).resolves.toEqual({
      groupId: "qa-rain-pordenone",
      ok: true,
      vote: "yes",
    });
    await expect(simulateCommunityReportUndo("qa-report-1")).resolves.toEqual({
      ok: true,
      reportId: "qa-report-1",
    });
  });

  it("fails closed for invalid simulated mutations", async () => {
    await expect(simulateCommunityReportSubmission("", null))
      .resolves.toEqual({ ok: false, reason: "preview_invalid" });
    await expect(simulateCommunityReportConfirmation("group", "maybe"))
      .resolves.toEqual({ ok: false, reason: "preview_invalid" });
    await expect(simulateCommunityReportUndo(""))
      .resolves.toEqual({ ok: false, reason: "preview_invalid" });
  });

  it("keeps QA personal state in an isolated memory storage", () => {
    const storage = createCommunityReportPreviewMemoryStorage({ existing: 7 });

    expect(storage.length).toBe(1);
    expect(storage.getItem("existing")).toBe("7");
    storage.setItem("vote", "yes");
    expect(storage.length).toBe(2);
    expect(storage.key(1)).toBe("vote");
    expect(storage.getItem("vote")).toBe("yes");
    storage.removeItem("existing");
    expect(storage.getItem("existing")).toBeNull();
    storage.clear();
    expect(storage.length).toBe(0);
  });

  it("adds a simulated report to both the feed and map overlay", () => {
    const now = Date.parse("2026-08-29T18:00:00Z");
    const identityInput = {
      alias: "Acuile di Pordenon",
      avatar: {
        angle: 135,
        palette_id: "night",
        pattern_id: "orbit",
        variant: 3,
      },
      subject_id: "acuile",
      version: 1,
    };
    const expectedIdentity = normalizePublicCommunityIdentitySnapshot(identityInput);
    const baseState = {
      community: { payload: { report_locations: [{ place: "Pordenone" }] } },
      webcams: { payload: { webcams: [{ id: "sacile" }] }, status: "fresh" },
    };
    const initialOverlay = createCommunityReportSimulationOverlay(baseState, { now });
    const mutation = applyCommunityReportSimulationSubmission(
      initialOverlay,
      "snow",
      {
        coords: { lat: 45.9567, lon: 12.6605 },
        selectedPlace: "Pordenone",
      },
      { identity: identityInput, now: () => now + 1_000 },
    );
    identityInput.alias = "Ors di Udin";
    identityInput.avatar.palette_id = "gold";
    const nextState = applyCommunityReportSimulationOverlay(baseState, mutation.overlay);
    const model = buildLiveViewModel(nextState, {
      location: { city: "Pordenone", lat: 45.9567, lon: 12.6605 },
      now: new Date(now + 1_000),
    });

    expect(mutation.result).toMatchObject({
      ok: true,
      report: {
        groupId: "qa-local-snow-pordenone",
        identity: expectedIdentity,
        typeId: "snow",
      },
      undoUntil: now + 61_000,
    });
    expect(mutation.overlay.reports).toHaveLength(4);
    expect(mutation.overlay.mapGroups).toHaveLength(4);
    expect(mutation.overlay.ownedReportIds).toEqual([mutation.result.report.id]);
    expect(mutation.overlay.mapGroups.at(-1).sourceKeys)
      .toEqual([mutation.result.report.sourceKey]);
    expect(mutation.overlay.mapGroups.at(-1).identities).toEqual([{
      identity: expectedIdentity,
      sourceKey: mutation.result.report.sourceKey,
    }]);
    expect(mutation.overlay.mapGroups.at(-1).identity).toEqual(expectedIdentity);
    expect(Object.isFrozen(mutation.result.report.identity)).toBe(true);
    expect(Object.isFrozen(mutation.result.report.identity.avatar)).toBe(true);
    expect(model.community.items.find((item) => item.typeId === "snow")?.identities)
      .toEqual([{
        identity: expectedIdentity,
        sourceKey: mutation.result.report.sourceKey,
      }]);
    expect(model.community.items.some((item) => item.typeId === "snow")).toBe(true);
    expect(model.community.markers.flatMap((marker) => marker.phenomena || [marker]))
      .toEqual(expect.arrayContaining([
        expect.objectContaining({ groupId: "qa-local-snow-pordenone" }),
      ]));
    expect(nextState.webcams).toBe(baseState.webcams);
    expect(nextState.community.payload.report_locations).toEqual([{ place: "Pordenone" }]);
  });

  it("keeps old report snapshots while a regenerated alias replaces the same source in its group", () => {
    const now = Date.parse("2026-08-29T18:00:00Z");
    const location = {
      coords: { lat: 45.9567, lon: 12.6605 },
      selectedPlace: "Pordenone",
    };
    const claf = {
      alias: "Clâf di Pordenon",
      avatar: { angle: 45, paletteId: "sky", patternId: "split", variant: 0 },
      subjectId: "claf",
      version: 1,
    };
    const ors = {
      alias: "Ors di Pordenon",
      avatar: { angle: 90, paletteId: "gold", patternId: "halo", variant: 2 },
      subjectId: "ors",
      version: 1,
    };
    const initial = createCommunityReportSimulationOverlay({}, { now });
    const first = applyCommunityReportSimulationSubmission(
      initial,
      "rain",
      location,
      { identity: claf, now: () => now + 1_000 },
    );
    const second = applyCommunityReportSimulationSubmission(
      first.overlay,
      "rain",
      location,
      { identity: ors, now: () => now + 2_000 },
    );
    const group = second.overlay.mapGroups.find(
      (entry) => entry.groupId === "qa-local-rain-pordenone",
    );
    const ownedReports = second.overlay.reports.filter(
      (entry) => second.overlay.ownedReportIds.includes(entry.id),
    );

    expect(ownedReports.map((report) => report.identity.alias)).toEqual([
      "Clâf di Pordenon",
      "Ors di Pordenon",
    ]);
    expect(group.count).toBe(2);
    expect(group.identities).toHaveLength(1);
    expect(group.identities[0]).toMatchObject({
      identity: { alias: "Ors di Pordenon" },
      sourceKey: "qa-local-preview",
    });
    expect(group.identity.alias).toBe("Ors di Pordenon");
  });

  it("keeps confirmations idempotent and moves the count when the vote changes", () => {
    const now = Date.parse("2026-08-29T18:00:00Z");
    const initial = createCommunityReportSimulationOverlay({}, { now });
    const first = applyCommunityReportSimulationConfirmation(
      initial,
      "qa-rain-pordenone",
      "yes",
      { now: () => now + 1_000 },
    );
    const repeated = applyCommunityReportSimulationConfirmation(
      first.overlay,
      "qa-rain-pordenone",
      "yes",
      { now: () => now + 2_000 },
    );
    const toggled = applyCommunityReportSimulationConfirmation(
      repeated.overlay,
      "qa-rain-pordenone",
      "no",
      { now: () => now + 3_000 },
    );

    expect(first.result.confirmations).toEqual({ no: 0, yes: 5 });
    expect(repeated.overlay).toBe(first.overlay);
    expect(repeated.result.confirmations).toEqual({ no: 0, yes: 5 });
    expect(toggled.result.confirmations).toEqual({ no: 1, yes: 4 });
    expect(toggled.overlay.votes["qa-rain-pordenone"]).toBe("no");
  });

  it("removes only a report created by the current QA simulation", () => {
    const now = Date.parse("2026-08-29T18:00:00Z");
    const initial = createCommunityReportSimulationOverlay({}, { now });
    const submitted = applyCommunityReportSimulationSubmission(
      initial,
      "snow",
      {
        coords: { lat: 45.9567, lon: 12.6605 },
        selectedPlace: "Pordenone",
      },
      { now: () => now + 1_000 },
    );
    const removed = applyCommunityReportSimulationUndo(
      submitted.overlay,
      submitted.result.report.id,
      { now: () => now + 2_000 },
    );
    const fixtureRemoval = applyCommunityReportSimulationUndo(
      removed.overlay,
      "qa-rain-pordenone-1",
      { now: () => now + 3_000 },
    );

    expect(removed.result).toEqual({
      ok: true,
      reportId: submitted.result.report.id,
    });
    expect(removed.overlay.reports).toHaveLength(3);
    expect(removed.overlay.mapGroups).toHaveLength(3);
    expect(removed.overlay.mapGroups.some(
      (group) => group.groupId === "qa-local-snow-pordenone",
    )).toBe(false);
    expect(fixtureRemoval.result).toEqual({
      ok: false,
      reason: "preview_not_found",
      status: 404,
    });
    expect(fixtureRemoval.overlay).toBe(removed.overlay);
  });
});
