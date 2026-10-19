// @vitest-environment jsdom
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

vi.mock("../../services/localCommunityPilot", async (importOriginal) => ({
  ...await importOriginal(),
  isLocalCommunityPilot: vi.fn(() => true),
}));

import { CommunityReportForm, LiveView } from "./LiveView";
import { buildLiveViewModel } from "./liveViewModel";

function buildModel(language = "it") {
  return buildLiveViewModel({
    community: { status: "fresh", payload: { map_groups: [], reports: [] } },
    webcams: { status: "disabled", payload: null },
  }, {
    language,
    location: { city: "Urbino", istatCode: "041067", lat: 43.7265, lon: 12.6365 },
    webcamsEnabled: false,
  });
}

function render(markup) {
  const container = document.createElement("div");
  container.innerHTML = renderToStaticMarkup(markup);
  return container;
}

describe("national pilot compact map layout", () => {
  it("keeps the map workspace as the only grid child when the route owns the location header", () => {
    const container = render(
      <LiveView compactLayout model={buildModel()} showLocationContext={false} reportingEnabled />,
    );
    const grid = container.querySelector(".mf-live-view--compact-territory");
    expect(grid).not.toBeNull();
    expect(grid.children).toHaveLength(1);
    expect(grid.firstElementChild.classList.contains("mf-live-territory-workspace")).toBe(true);
    expect(grid.querySelectorAll(".mf-territory-map--inline")).toHaveLength(1);
    // Any extra direct child creates another grid row and halves map height.
    expect(grid.querySelector(":scope > p")).toBeNull();
    expect(container.querySelector(".mf-live-pilot-note")).toBeNull();
  });

  it.each([
    [
      "it",
      "Segnala il meteo attuale nella tua zona.",
      "Posizione approssimata a tutela della tua privacy.",
      "Rimarrà visibile sulla mappa per 60 minuti.",
      "In caso di situazioni critiche o pericoli immediati, contatta il 112.",
    ],
    [
      "fur",
      "Segnale il timp atuâl te tô zone.",
      "Posizion aproximade a tutele de tô riservatece.",
      "E restarà visibile su la mape par 60 minûts.",
      "In câs di situazions critichis o pericui imediâts, clame il 112.",
    ],
  ])("keeps the concise reporting guidance inside the %s pilot form", (
    language,
    body,
    privacy,
    expires,
    safety,
  ) => {
    const model = buildModel(language);
    const container = render(
      <CommunityReportForm
        copy={model.copy}
        locations={model.community.reportLocations}
        maxDistanceKm={model.community.maxDistanceKm}
        onClose={() => {}}
        onLocate={() => Promise.resolve({ ok: false, reason: "permission_denied" })}
        onSubmit={() => Promise.resolve({ ok: true })}
        options={model.community.reportOptions}
        pilotStyle
      />,
    );
    expect(container.querySelector(".mf-live-report-form--pilot").textContent).toContain(body);
    expect(model.copy).toMatchObject({
      reportBody: body,
      reportExpires: expires,
      reportLocationRadius: privacy,
      reportSafety: safety,
    });
    expect(container.textContent).not.toContain("Prova locale");
    expect(container.textContent).not.toContain("Prove locâl");
    expect(container.querySelector(".mf-live-pilot-note")).toBeNull();
  });
});
