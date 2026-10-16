// @vitest-environment jsdom
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, beforeEach, expect, it, vi } from "vitest";

import { getLiveViewCopy } from "../../copy/liveViewCopy";
import { CommunityReportForm, LiveView } from "./LiveView";
import { buildLiveViewModel } from "./liveViewModel";

let container;
let root;

const translatedCopy = [
  {
    language: "it",
    heading: "Stai segnalando da",
    gps: "Posizione rilevata dal GPS",
    simulated: "Posizione simulata per questa anteprima",
  },
  {
    language: "fur",
    heading: "Tu stâs segnalant di",
    gps: "Posizion rilevade dal GPS",
    simulated: "Posizion simulade par cheste anteprime",
  },
];

function readyLocation(place = "Pordenone", source = "browser_geolocation") {
  return {
    coords: { accuracyM: 80, lat: 45.9567, lon: 12.6605 },
    detectedPlace: place,
    maxDistanceKm: 5,
    nearbyPlaces: [{ distanceKm: 0, place }],
    ok: true,
    selectedPlace: place,
    source,
  };
}

async function renderForm({ language = "it", ...props } = {}) {
  const copy = getLiveViewCopy(language);
  await act(async () => {
    root.render(
      <CommunityReportForm
        copy={copy}
        locations={[]}
        maxDistanceKm={5}
        onClose={() => {}}
        onLocate={() => Promise.resolve(readyLocation())}
        onSubmit={() => Promise.resolve({ ok: true })}
        options={Object.entries(copy.reportTypes)
          .filter(([id]) => id !== "unknown")
          .map(([id, label]) => ({ id, label }))}
        pilotStyle
        {...props}
      />,
    );
  });
  return copy;
}

beforeEach(() => {
  vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT", true);
  vi.stubGlobal("IntersectionObserver", class {
    disconnect() {}
    observe() {}
  });
  vi.stubGlobal("requestAnimationFrame", (callback) => globalThis.setTimeout(callback, 0));
  vi.stubGlobal("cancelAnimationFrame", (frameId) => globalThis.clearTimeout(frameId));
  container = document.createElement("div");
  container.id = "root";
  document.body.appendChild(container);
  root = createRoot(container);
});

afterEach(async () => {
  await act(async () => root.unmount());
  container.remove();
  vi.unstubAllGlobals();
});

it.each(translatedCopy)("explains the GPS reporting location in $language", async ({ language, heading, gps }) => {
  const copy = await renderForm({ language });
  const locationCopy = container.querySelector(".mf-live-report-location__copy");

  expect(locationCopy.querySelector("strong")?.textContent).toBe(`${heading} Pordenone`);
  expect(locationCopy.querySelector(".mf-live-report-location__source")?.textContent).toBe(gps);
  expect(locationCopy.querySelector(".mf-live-report-location__rule")?.textContent)
    .toBe(copy.reportLocationRadius.replace("{distance}", "5"));
  expect([...locationCopy.children].map((child) => child.tagName)).toEqual([
    "STRONG", "SPAN", "SPAN",
  ]);
});

it("uses the location returned by GPS while the user is browsing Ancona", async () => {
  const model = buildLiveViewModel({
    community: { payload: { map_groups: [], reports: [] }, status: "fresh" },
  }, {
    language: "it",
    location: { city: "Ancona", lat: 43.6158, lon: 13.5189 },
    webcamsEnabled: false,
  });
  const onLocate = vi.fn().mockResolvedValue(readyLocation());
  expect(model.locationPlace).toBe("Ancona");

  await act(async () => root.render(
    <LiveView
      compactLayout
      model={model}
      onReportLocate={onLocate}
      onReportSubmit={() => Promise.resolve({ ok: true })}
      reportingEnabled
    />,
  ));
  await act(async () => container.querySelector(".mf-territory-map__report-action").click());

  const locationCopy = document.body.querySelector(".mf-live-report-location__copy");
  expect(onLocate).toHaveBeenCalledOnce();
  expect(locationCopy.querySelector("strong")?.textContent).toBe("Stai segnalando da Pordenone");
  expect(locationCopy.textContent).not.toContain("Ancona");
});

it("keeps a long detected place name complete in the heading", async () => {
  const place = "San Dorligo della Valle / Dolina";
  await renderForm({ onLocate: () => Promise.resolve(readyLocation(place)) });

  expect(container.querySelector(".mf-live-report-location__copy > strong")?.textContent)
    .toBe(`Stai segnalando da ${place}`);
});

it.each(translatedCopy.flatMap((translation) => [
  { ...translation, mode: "previewOnly", props: { previewOnly: true } },
  { ...translation, mode: "simulationOnly", props: { simulationOnly: true } },
  {
    ...translation,
    mode: "local_preview source",
    props: { onLocate: () => Promise.resolve(readyLocation("Pordenone", "local_preview")) },
  },
]))("labels $mode as simulated in $language", async ({ language, gps, simulated, props }) => {
  await renderForm({ language, ...props });
  const locationCopy = container.querySelector(".mf-live-report-location__copy");

  expect(locationCopy.querySelector(".mf-live-report-location__source")?.textContent).toBe(simulated);
  expect(locationCopy.textContent).not.toContain(gps);
});

it.each(translatedCopy)("preserves legacy location copy in $language", async ({ language, heading, gps }) => {
  const copy = await renderForm({ language, pilotStyle: false });
  const locationCopy = container.querySelector(".mf-live-report-location__copy");

  expect(locationCopy.querySelector("small")?.textContent).toBe(copy.reportLocation);
  expect(locationCopy.querySelector("strong")?.textContent).toBe("Pordenone");
  expect(locationCopy.querySelector(".mf-live-report-location__source")).toBeNull();
  expect(locationCopy.querySelector(".mf-live-report-location__rule")).toBeNull();
  expect(locationCopy.textContent).not.toContain(heading);
  expect(locationCopy.textContent).not.toContain(gps);
});

it.each(translatedCopy)("claims a location only after GPS succeeds in $language", async ({ language, heading, gps }) => {
  let resolveLocation;
  const pendingLocation = new Promise((resolve) => { resolveLocation = resolve; });
  const copy = await renderForm({ language, onLocate: () => pendingLocation });
  const locationCopy = container.querySelector(".mf-live-report-location__copy");

  expect(locationCopy.querySelector("strong")?.textContent).toBe(copy.reportGpsLoading);
  expect(locationCopy.querySelector(".mf-live-report-location__source")).toBeNull();
  expect(locationCopy.querySelector(".mf-live-report-location__rule")).toBeNull();
  expect(locationCopy.textContent).not.toContain(heading);
  expect(locationCopy.textContent).not.toContain(gps);

  await act(async () => resolveLocation({ ok: false, reason: "unavailable" }));

  expect(locationCopy.querySelector("strong")?.textContent).toBe(copy.reportGpsUnavailable);
  expect(locationCopy.querySelector(".mf-live-report-location__source")).toBeNull();
  expect(locationCopy.querySelector(".mf-live-report-location__rule")).toBeNull();
  expect(locationCopy.textContent).not.toContain(heading);
  expect(locationCopy.textContent).not.toContain(gps);
});
