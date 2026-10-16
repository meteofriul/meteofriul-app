import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("../../services/localCommunityPilot", async (importOriginal) => ({
  ...await importOriginal(),
  isLocalCommunityPilot: vi.fn(() => true),
}));

import { isLocalCommunityPilot } from "../../services/localCommunityPilot";
import { buildLiveViewModel } from "./liveViewModel";

const now = new Date("2026-09-20T12:00:00Z");
const bergamo = { istatCode: "016065", regionId: "IT-25", provinceCode: "BG", lat: 45.8, lon: 10.07 };
const lecce = { istatCode: "075096", regionId: "IT-75", provinceCode: "LE", lat: 40, lon: 18.4 };

function group(id, identity, extra = {}) {
  return {
    id, groupId: id, place: "Castro", typeId: "rain", count: 1,
    createdAt: now.getTime()-1000, expiresAt: now.getTime()+3599000,
    confirmations: { yes: 0, no: 0 },
    ...identity, ...extra,
  };
}

function model(mapGroups, reports = []) {
  return buildLiveViewModel({ community: { payload: { map_groups: mapGroups, reports } } }, { now }).community;
}

afterEach(() => vi.mocked(isLocalCommunityPilot).mockReturnValue(true));

describe("pilot municipality marker identity", () => {
  it("describes national test reporting without changing ordinary FVG copy", () => {
    expect(buildLiveViewModel({}, { now }).copy).toMatchObject({
      reportBody: "Segnala il meteo attuale nella tua zona.",
      reportExpires: "Rimarrà visibile sulla mappa per 60 minuti",
      reportLocationRadius: "Posizione approssimata a tutela della tua privacy.",
      reportSafety: "In caso di situazioni critiche o pericoli immediati contatta il 112.",
    });
    vi.mocked(isLocalCommunityPilot).mockReturnValue(false);
    expect(buildLiveViewModel({}, { now }).copy).toMatchObject({
      reportBody: "Solo con GPS in Friuli Venezia Giulia.",
      reportExpires: "Visibile per 60 min",
      reportLocationRadius: "Puoi segnalare solo se ti trovi entro {distance} km dalla località indicata.",
      reportSafety: "Per emergenze usa sempre i numeri ufficiali.",
    });
  });

  it("keeps same-name municipalities separate and preserves identity in markers, phenomena and list items", () => {
    const community = model([group("rain-bg", bergamo), group("rain-le", lecce)]);
    expect(community.markers.map((item) => item.id)).toEqual(["place:istat:016065", "place:istat:075096"]);
    for (const identity of [bergamo, lecce]) {
      const marker = community.markers.find((item) => item.istatCode === identity.istatCode);
      expect(marker).toMatchObject(identity);
      expect(marker.phenomena[0]).toMatchObject(identity);
      expect(community.items.find((item) => item.istatCode === identity.istatCode)).toMatchObject({
        istatCode: identity.istatCode, regionId: identity.regionId, provinceCode: identity.provinceCode,
      });
    }
  });

  it("combines different phenomena in the same ISTAT municipality even when the label differs", () => {
    const community = model([
      group("rain-bg", bergamo),
      group("wind-bg", bergamo, { place: "Castro (BG)", typeId: "wind" }),
    ]);
    expect(community.markers).toHaveLength(1);
    expect(community.markers[0]).toMatchObject({ istatCode: "016065", count: 2, typeId: "multiple" });
    expect(community.markers[0].phenomena).toHaveLength(2);
  });

  it("uses public coordinates for legacy groups without ISTAT, never just the name", () => {
    const community = model([
      group("legacy-bg", { lat: bergamo.lat, lon: bergamo.lon }),
      group("legacy-le", { lat: lecce.lat, lon: lecce.lon }),
      group("legacy-wind-bg", { lat: bergamo.lat, lon: bergamo.lon }, { typeId: "wind" }),
    ]);
    expect(community.markers).toHaveLength(2);
    expect(community.markers.find((item) => item.id === "place:point:45.8:10.07").count).toBe(2);
    expect(community.markers.find((item) => item.id === "place:point:40:18.4").count).toBe(1);
  });

  it("does not invent zero coordinates or merge unidentified legacy groups", () => {
    const community = model([group("missing-first", { lat: null, lon: null }), group("missing-second", {})]);
    expect(community.markers).toHaveLength(2);
    expect(community.markers.map((item) => item.lat)).toEqual([null, null]);
    expect(community.markers.map((item) => item.id)).toEqual(["place:group:missing-first", "place:group:missing-second"]);
  });

  it("keeps reports and contributions distinct when a legacy feed omits precomputed groups", () => {
    const reports = [
      group("report-bg", bergamo, { groupId: undefined }),
      group("report-le", lecce, { groupId: undefined }),
    ];
    const community = model([], reports);
    expect(community.markers).toHaveLength(2);
    expect(community.items).toHaveLength(2);
    expect(community.items.every((item) => item.count === 1 && item.contributions.length === 1)).toBe(true);
  });

  it("preserves the ordinary FVG marker shape and grouping outside pilot mode", () => {
    vi.mocked(isLocalCommunityPilot).mockReturnValue(false);
    const community = model([group("rain-bg", bergamo), group("rain-le", lecce)]);
    expect(community.markers).toHaveLength(1);
    expect(community.markers[0]).toMatchObject({ id: "place:castro", count: 2 });
    expect(community.markers[0]).not.toHaveProperty("istatCode");
    expect(community.items[0]).not.toHaveProperty("istatCode");
  });
});
