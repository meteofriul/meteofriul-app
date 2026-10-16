// @vitest-environment jsdom
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, beforeEach, expect, it, vi } from "vitest";

import { getLiveViewCopy } from "../../copy/liveViewCopy";
import {
  buildCommunityIdentity,
  buildPublicCommunityIdentitySnapshot,
  getCommunityIdentityPreview,
} from "../community/communityIdentity";
import { CommunityReportForm, LiveView } from "./LiveView";
import {
  hasCommunityGuidelinesConsent,
  rememberCommunityGuidelinesConsent,
} from "./communityGuidelinesConsent";
import { hasReportLocationNoticeConsent } from "./reportLocationNoticeConsent";
import { COMMUNITY_GUIDELINES_POLICY_VERSION } from "./liveReportPolicy";
import { buildLiveViewModel } from "./liveViewModel";

let container;
let root;
let originalIntersectionObserver;
let originalScrollIntoView;
let originalRequestAnimationFrame;
let originalCancelAnimationFrame;
let originalNavigatorShareDescriptor;
let originalNavigatorClipboardDescriptor;

function buildModel({
  community = { map_groups: [], reports: [] },
  communityStatus = "fresh",
  webcamsEnabled = true,
  webcams = [
    {
      area: "Sacile",
      fallbackImageUrl: "/municipalities/photos/093037-photo.webp",
      group: "plain",
      id: "sacile",
      lat: 45.9541,
      lon: 12.5027,
      name: "Sacile",
    },
    {
      area: "Maniago",
      fallbackImageUrl: "/municipalities/photos/093025-photo.webp",
      group: "plain",
      id: "maniago",
      lat: 46.1706,
      lon: 12.7078,
      name: "Maniago",
    },
  ],
} = {}) {
  return buildLiveViewModel({
    community: {
      payload: community,
      status: communityStatus,
    },
    webcams: {
      payload: {
        ok: true,
        webcams,
      },
      status: "fresh",
    },
  }, {
    language: "it",
    location: { city: "Pordenone", lat: 45.9567, lon: 12.6605 },
    webcamsEnabled,
  });
}

function buildCommunityModel() {
  const now = Date.now();
  const report = {
    confirmations: { no: 0, yes: 2 },
    count: 1,
    createdAt: now - 4 * 60_000,
    expiresAt: now + 56 * 60_000,
    groupId: "rain:pordenone:test",
    id: "rain:pordenone:test",
    lat: 45.9567,
    lon: 12.6605,
    place: "Pordenone",
    reportIds: ["report-rain-test"],
    sourceKeys: ["source-test"],
    typeId: "rain",
  };

  return buildModel({
    community: {
      generated_at: new Date(now).toISOString(),
      map_groups: [report],
      reports: [{ ...report, id: "report-rain-test" }],
    },
  });
}

function createMemoryStorage() {
  const values = new Map();
  return {
    getItem: (key) => values.get(key) ?? null,
    removeItem: (key) => values.delete(key),
    setItem: (key, value) => values.set(key, String(value)),
  };
}

function buildReadyReportLocation() {
  return {
    coords: { accuracyM: 80, lat: 45.9567, lon: 12.6605 },
    detectedPlace: "Pordenone",
    maxDistanceKm: 5,
    nearbyPlaces: [
      { distanceKm: 0, place: "Pordenone" },
      { distanceKm: 4.2, place: "Cordenons" },
    ],
    ok: true,
    selectedPlace: "Pordenone",
    source: "browser_geolocation",
  };
}

beforeEach(() => {
  originalIntersectionObserver = globalThis.IntersectionObserver;
  originalScrollIntoView = Element.prototype.scrollIntoView;
  originalRequestAnimationFrame = globalThis.requestAnimationFrame;
  originalCancelAnimationFrame = globalThis.cancelAnimationFrame;
  originalNavigatorShareDescriptor = Object.getOwnPropertyDescriptor(
    globalThis.navigator,
    "share",
  );
  originalNavigatorClipboardDescriptor = Object.getOwnPropertyDescriptor(
    globalThis.navigator,
    "clipboard",
  );
  globalThis.IntersectionObserver = class IntersectionObserverMock {
    disconnect() {}

    observe() {}
  };
  Element.prototype.scrollIntoView = vi.fn();
  globalThis.requestAnimationFrame = (callback) => globalThis.setTimeout(
    () => callback(globalThis.performance?.now?.() || 0),
    0,
  );
  globalThis.cancelAnimationFrame = (frameId) => globalThis.clearTimeout(frameId);
  globalThis.IS_REACT_ACT_ENVIRONMENT = true;
  container = document.createElement("div");
  container.id = "root";
  document.body.appendChild(container);
  root = createRoot(container);
});

afterEach(async () => {
  await act(async () => root.unmount());
  container.remove();
  globalThis.IntersectionObserver = originalIntersectionObserver;
  Element.prototype.scrollIntoView = originalScrollIntoView;
  globalThis.requestAnimationFrame = originalRequestAnimationFrame;
  globalThis.cancelAnimationFrame = originalCancelAnimationFrame;
  if (originalNavigatorShareDescriptor) {
    Object.defineProperty(
      globalThis.navigator,
      "share",
      originalNavigatorShareDescriptor,
    );
  } else {
    delete globalThis.navigator.share;
  }
  if (originalNavigatorClipboardDescriptor) {
    Object.defineProperty(
      globalThis.navigator,
      "clipboard",
      originalNavigatorClipboardDescriptor,
    );
  } else {
    delete globalThis.navigator.clipboard;
  }
  document.documentElement.classList.remove("mf-community-report-open");
  delete globalThis.IS_REACT_ACT_ENVIRONMENT;
  vi.useRealTimers();
});

async function flushAnimationFrame() {
  await act(async () => {
    await new Promise((resolve) => globalThis.setTimeout(resolve, 0));
  });
}

it("renders webcam area filters without a compact webcam card", async () => {
  const model = buildCommunityModel();

  await act(async () => {
    root.render(
      <LiveView
        compactLayout
        model={model}
        onReportLocate={() => Promise.resolve(buildReadyReportLocation())}
        onReportSubmit={() => Promise.resolve({ ok: true })}
        reportingEnabled
      />,
    );
  });

  const workspace = container.querySelector(".mf-live-territory-workspace");
  const inlineMap = workspace?.querySelector(".mf-territory-map--inline");
  const navigation = workspace?.querySelector(".mf-territory-map__navigation");
  const reportButton = workspace?.querySelector(".mf-territory-map__report-action");

  expect(workspace).not.toBeNull();
  expect(inlineMap).not.toBeNull();
  expect(container.querySelectorAll(".mf-live-card--community")).toHaveLength(0);
  expect(container.querySelector(".mf-live-webcam-carousel")).toBeNull();
  expect(document.body.querySelector(
    '.mf-live-community-map-layer--pilot[role="dialog"][aria-modal="true"]',
  )).toBeNull();
  expect(navigation.compareDocumentPosition(reportButton) & Node.DOCUMENT_POSITION_FOLLOWING)
    .toBeTruthy();

  const navigationButtons = [...navigation.querySelectorAll("button")];
  expect(navigationButtons.map((button) => button.textContent.trim())).toEqual([
    "Mappa",
    "Segnalazioni",
    "Webcam",
  ]);
  expect(reportButton.textContent).toContain("Segnala meteo");
  expect(reportButton.getAttribute("aria-haspopup")).toBe("dialog");
  expect(reportButton.getAttribute("aria-expanded")).toBe("false");

  await act(async () => navigationButtons[2].click());
  await flushAnimationFrame();

  const webcamView = workspace.querySelector(".mf-territory-map__browse-sheet");
  expect(webcamView.textContent).toContain("Webcam sul territorio");
  expect([...webcamView.querySelectorAll(".mf-territory-map__webcam-groups button")]
    .map((button) => button.textContent.replace(/\d+/g, "").trim()))
    .toEqual(["Vicino", "Pianura"]);
  expect(webcamView.textContent).not.toContain("Sacile");
  expect(webcamView.textContent).not.toContain("Maniago");
  const viewAllWebcams = [...webcamView.querySelectorAll("button")]
    .find((button) => button.textContent.includes("Vedi tutte"));
  expect(viewAllWebcams).toBeTruthy();
  expect(webcamView.querySelector(".mf-territory-map__browse-list")?.hidden).toBe(true);
  expect(webcamView.querySelectorAll(".mf-territory-map__browse-list > button")).toHaveLength(0);

  await act(async () => viewAllWebcams.click());
  await flushAnimationFrame();

  expect(webcamView.textContent).toContain("Sacile");
  expect(webcamView.textContent).toContain("Maniago");
  expect(webcamView.textContent).toContain("Mostra meno");
  expect(workspace.querySelector(".mf-territory-map__report-action")).toBeNull();

  await act(async () => navigationButtons[0].click());
  await flushAnimationFrame();

  const activeReportButton = workspace.querySelector(".mf-territory-map__report-action");
  expect(activeReportButton).not.toBeNull();
  expect(workspace.querySelector(".mf-territory-map__dock")?.lastElementChild)
    .toBe(activeReportButton);
  expect(workspace.querySelector(".mf-territory-map--inline")).toBe(inlineMap);

  await act(async () => activeReportButton.click());
  await flushAnimationFrame();

  const reportDialog = document.body.querySelector(".mf-live-report-form--sheet");
  expect(reportDialog).not.toBeNull();
  expect(reportDialog.classList.contains("mf-live-report-form--pilot")).toBe(true);
  expect(reportDialog.querySelector(".mf-live-report-submit")?.classList.contains("mf-button--primary"))
    .toBe(true);
  expect(activeReportButton.getAttribute("aria-expanded")).toBe("true");
  expect(document.body.textContent).toContain(model.copy.reportQuestion);
  expect(reportDialog.querySelector(".mf-live-report-location__rule")?.textContent)
    .toBe("Puoi segnalare solo se ti trovi entro 5 km dalla località indicata.");
  expect(reportDialog.querySelector(".mf-live-report-location__copy > small")).toBeNull();
  expect(reportDialog.querySelector(".mf-live-report-location__copy > strong")?.textContent)
    .toBe("Stai segnalando da Pordenone");
  expect(reportDialog.querySelector(`button[aria-label="${model.copy.reportLocationChange}"]`))
    .toBeNull();
  expect(reportDialog.querySelector(".mf-live-report-location__selector")).toBeNull();
  expect(reportDialog.querySelector(".mf-live-report-duration")?.textContent)
    .toBe(model.copy.reportExpires);
  expect(reportDialog.querySelector(".mf-live-report-meta")).toBeNull();
  const submit = reportDialog.querySelector(".mf-live-report-submit");
  const safety = reportDialog.querySelector(".mf-live-report-safety");
  expect(safety?.textContent).toBe(model.copy.reportSafety);
  expect(submit.compareDocumentPosition(safety) & Node.DOCUMENT_POSITION_FOLLOWING)
    .toBeTruthy();
});

it("shows one clustered Cividale entry and changes its three views by button or swipe", async () => {
  globalThis.IntersectionObserver = undefined;
  const sourcePage = "https://www.meteo.fvg.it/webcam_img.php?ln=it";
  const shared = {
    attribution: "ARPA FVG - OSMER e GRN",
    attributionUrl: "https://www.meteo.fvg.it/",
    fallbackImageUrl: "/municipalities/photos/030026-photo.webp",
    group: "plain",
    mapClusterId: "cividale-del-friuli",
    mapClusterLabel: "Cividale del Friuli",
    mediaType: "snapshot",
    municipality: "Cividale del Friuli",
    provider: "ARPA FVG - OSMER e GRN",
    sourcePage,
  };
  const model = buildModel({
    webcams: [
      {
        ...shared,
        area: "Campanile ex Monastero Maggiore",
        id: "cividale-campanile-ex-monastero",
        imageUrl: "https://www.meteo.fvg.it/campanile.jpg",
        name: "Cividale del Friuli - Veduta dal campanile",
        sortOrder: 20,
      },
      {
        ...shared,
        area: "Piazza Duomo",
        id: "cividale-piazza-duomo",
        imageUrl: "https://www.meteo.fvg.it/duomo.jpg",
        name: "Cividale del Friuli - Piazza Duomo",
        sortOrder: 21,
      },
      {
        ...shared,
        area: "Piazza Paolo Diacono",
        id: "cividale-piazza-paolo-diacono",
        imageUrl: "https://www.meteo.fvg.it/diacono.jpg",
        name: "Cividale del Friuli - Piazza Paolo Diacono",
        sortOrder: 22,
      },
    ],
  });

  await act(async () => {
    root.render(<LiveView compactLayout model={model} />);
  });

  const workspace = container.querySelector(".mf-live-territory-workspace");
  const webcamTab = [...workspace.querySelectorAll(".mf-territory-map__navigation button")]
    .find((button) => button.textContent.trim() === "Webcam");
  await act(async () => webcamTab.click());
  await flushAnimationFrame();

  const viewAll = workspace.querySelector(".mf-territory-map__browse-toggle");
  await act(async () => viewAll.click());
  await flushAnimationFrame();

  const clusteredEntry = workspace.querySelector(
    ".mf-territory-map__browse-item--webcam",
  );
  expect(workspace.querySelectorAll(".mf-territory-map__browse-item--webcam")).toHaveLength(1);
  expect(clusteredEntry.textContent).toContain("Cividale del Friuli · 3 webcam");

  await act(async () => clusteredEntry.click());
  await flushAnimationFrame();

  let detail = workspace.querySelector(".mf-territory-map__webcam-detail");
  expect(detail.querySelector(".mf-live-community-map__detail-heading strong").textContent)
    .toBe("Veduta dal campanile");
  expect(detail.querySelector(".mf-territory-map__webcam-switcher").textContent)
    .toContain("1 di 3");
  expect(detail.querySelector(
    ".mf-live-webcam-preview__media > .mf-territory-map__webcam-switcher",
  )).not.toBeNull();
  expect(detail.querySelector(".mf-live-webcam-preview__media img").src)
    .toContain("campanile.jpg");

  const nextButton = detail.querySelector('button[aria-label="Webcam successiva"]');
  await act(async () => nextButton.click());

  detail = workspace.querySelector(".mf-territory-map__webcam-detail");
  expect(detail.querySelector(".mf-live-community-map__detail-heading strong").textContent)
    .toBe("Piazza Duomo");
  expect(detail.querySelector(".mf-territory-map__webcam-switcher").textContent)
    .toContain("2 di 3");

  const swipeSurface = detail.querySelector(".mf-territory-map__webcam-swipe");
  await act(async () => {
    swipeSurface.dispatchEvent(new MouseEvent("pointerdown", {
      bubbles: true,
      clientX: 240,
      clientY: 100,
    }));
    swipeSurface.dispatchEvent(new MouseEvent("pointerup", {
      bubbles: true,
      clientX: 140,
      clientY: 104,
    }));
  });

  detail = workspace.querySelector(".mf-territory-map__webcam-detail");
  expect(detail.querySelector(".mf-live-community-map__detail-heading strong").textContent)
    .toBe("Piazza Paolo Diacono");
  expect(detail.querySelector(".mf-territory-map__webcam-switcher").textContent)
    .toContain("3 di 3");
});

it("uses the longer timeout only for a live snapshot, not its fallback", async () => {
  globalThis.IntersectionObserver = undefined;
  vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout"] });
  const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue({
    headers: { get: () => null },
    ok: false,
  });
  const imageUrl = "https://anemometro.comune.monfalcone.go.it/monfalcone-cam-marinaJulia2.php";
  const fallbackImageUrl = "/municipalities/photos/031012-photo.webp";
  const model = buildModel({
    webcams: [{
      area: "Marina Julia",
      fallbackImageUrl,
      group: "coast",
      id: "monfalcone-marina-julia-2",
      imageUrl,
      lat: 45.77274,
      lon: 13.52759,
      mediaType: "snapshot",
      name: "Monfalcone - Marina Julia 2",
      provider: "Comune di Monfalcone",
      sourcePage: "https://www.comune.monfalcone.go.it/it/novita-220905/notizie-220906/condizioni-del-vento-marina-julia-21786",
    }],
  });

  try {
    await act(async () => {
      root.render(<LiveView model={model} />);
    });

    let image = container.querySelector(".mf-live-card--webcam .mf-live-webcam-preview__media img");
    expect(image.src).toContain(`${imageUrl}?mf_snapshot=`);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(6_500);
    });
    image = container.querySelector(".mf-live-card--webcam .mf-live-webcam-preview__media img");
    expect(image.src).toContain(`${imageUrl}?mf_snapshot=`);
    expect(image.closest(".mf-live-webcam-preview__media")?.dataset.source).toBe("live");
    expect(container.querySelector(".mf-live-webcam-preview__fallback-notice")).toBeNull();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(8_500);
    });
    image = container.querySelector(".mf-live-card--webcam .mf-live-webcam-preview__media img");
    expect(image.src).toBe(new URL(fallbackImageUrl, globalThis.location.href).href);
    expect(image.closest(".mf-live-webcam-preview__media")?.dataset.source).toBe("static");
    expect(container.querySelector(".mf-live-webcam-preview__fallback-notice")).not.toBeNull();
    expect(fetchMock).not.toHaveBeenCalled();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(6_500);
    });
    const failedFallback = container.querySelector(
      ".mf-live-card--webcam .mf-live-webcam-preview__media",
    );
    expect(failedFallback?.dataset.source).toBe("static");
    expect(failedFallback?.dataset.state).toBe("error");
  } finally {
    fetchMock.mockRestore();
  }
});

it("accepts a valid snapshot that finishes loading after nine seconds", async () => {
  globalThis.IntersectionObserver = undefined;
  vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout"] });
  const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue({
    headers: { get: () => null },
    ok: false,
  });
  const imageUrl = "https://anemometro.comune.monfalcone.go.it/monfalcone-cam-marinaJulia2.php";
  const model = buildModel({
    webcams: [{
      area: "Marina Julia",
      fallbackImageUrl: "/municipalities/photos/031012-photo.webp",
      group: "coast",
      id: "monfalcone-marina-julia-2",
      imageUrl,
      lat: 45.77274,
      lon: 13.52759,
      mediaType: "snapshot",
      name: "Monfalcone - Marina Julia 2",
      provider: "Comune di Monfalcone",
      sourcePage: "https://www.comune.monfalcone.go.it/it/novita-220905/notizie-220906/condizioni-del-vento-marina-julia-21786",
    }],
  });

  try {
    await act(async () => {
      root.render(<LiveView model={model} />);
    });

    await act(async () => {
      await vi.advanceTimersByTimeAsync(9_000);
    });
    let image = container.querySelector(".mf-live-card--webcam .mf-live-webcam-preview__media img");
    expect(image.src).toContain(`${imageUrl}?mf_snapshot=`);
    expect(image.closest(".mf-live-webcam-preview__media")?.dataset.state).toBe("loading");
    expect(fetchMock).not.toHaveBeenCalled();

    await act(async () => {
      image.dispatchEvent(new Event("load"));
    });
    image = container.querySelector(".mf-live-card--webcam .mf-live-webcam-preview__media img");
    expect(image.closest(".mf-live-webcam-preview__media")?.dataset.source).toBe("live");
    expect(image.closest(".mf-live-webcam-preview__media")?.dataset.state).toBe("loaded");
    expect(fetchMock).toHaveBeenCalledOnce();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(6_000);
    });
    image = container.querySelector(".mf-live-card--webcam .mf-live-webcam-preview__media img");
    expect(image.closest(".mf-live-webcam-preview__media")?.dataset.source).toBe("live");
    expect(image.closest(".mf-live-webcam-preview__media")?.dataset.state).toBe("loaded");
    expect(container.querySelector(".mf-live-webcam-preview__fallback-notice")).toBeNull();
  } finally {
    fetchMock.mockRestore();
  }
});

it.each([
  ["own", { reports: [{ groupId: "rain:pordenone:nearby" }], votes: [] }],
  ["voted", { reports: [], votes: [{ groupId: "rain:pordenone:nearby", vote: "yes" }] }],
])("omits the pilot safety footer after a nearby report is already %s", async (state, personalState) => {
  const model = buildModel();
  const now = Date.now();

  await act(async () => {
    root.render(
      <CommunityReportForm
        activeGroups={[{
          confirmations: { no: 0, yes: 1 },
          count: 1,
          createdAt: now - 60_000,
          expiresAt: now + 60 * 60_000,
          groupId: "rain:pordenone:nearby",
          lat: 45.9567,
          lon: 12.6605,
          place: "Pordenone",
          typeId: "rain",
        }]}
        copy={model.copy}
        locations={model.community.reportLocations}
        maxDistanceKm={model.community.maxDistanceKm}
        onClose={() => {}}
        onLocate={() => Promise.resolve(buildReadyReportLocation())}
        onSubmit={() => Promise.resolve({ ok: true })}
        options={model.community.reportOptions}
        personalState={personalState}
        pilotStyle
      />,
    );
  });
  await flushAnimationFrame();
  await act(async () => container.querySelector(".mf-live-report-option--rain").click());

  expect(container.querySelector(`.mf-live-report-match--${state}`)).not.toBeNull();
  expect(container.querySelector(".mf-live-report-map-action")).not.toBeNull();
  expect(container.querySelector(".mf-live-report-safety")).toBeNull();
});

it("keeps the pilot nearby-confirmation success on the legacy layout", async () => {
  const model = buildModel();
  const now = Date.now();
  const onConfirmNearby = vi.fn().mockResolvedValue({ ok: true });

  await act(async () => {
    root.render(
      <CommunityReportForm
        activeGroups={[{
          confirmations: { no: 0, yes: 1 },
          count: 1,
          createdAt: now - 60_000,
          expiresAt: now + 55 * 60_000,
          groupId: "rain:pordenone:nearby-confirm",
          lat: 45.9567,
          lon: 12.6605,
          place: "Pordenone",
          typeId: "rain",
        }]}
        copy={model.copy}
        locations={model.community.reportLocations}
        maxDistanceKm={model.community.maxDistanceKm}
        onClose={() => {}}
        onConfirmNearby={onConfirmNearby}
        onLocate={() => Promise.resolve(buildReadyReportLocation())}
        onSubmit={() => Promise.resolve({ ok: true })}
        options={model.community.reportOptions}
        personalStorage={createMemoryStorage()}
        pilotStyle
      />,
    );
  });
  await flushAnimationFrame();

  await act(async () => container.querySelector(".mf-live-report-option--rain").click());
  await act(async () => container.querySelector(".mf-live-report-terms input").click());
  await act(async () => container.querySelector(".mf-live-report-submit").click());
  await flushAnimationFrame();

  const success = container.querySelector(".mf-live-report-success");
  expect(onConfirmNearby).toHaveBeenCalledWith(expect.objectContaining({
    groupId: "rain:pordenone:nearby-confirm",
    vote: "yes",
  }));
  expect(success?.classList.contains("mf-live-report-success--pilot-receipt")).toBe(false);
  expect(success?.querySelector(":scope > strong")?.textContent)
    .toBe(model.copy.reportSuccessConfirmation);
  expect(success?.querySelector(".mf-live-report-success__summary")).toBeNull();
  expect(container.querySelector(".mf-live-report-form--receipt")).toBeNull();
  expect(container.querySelector(".mf-live-report-form__header strong")?.textContent)
    .toBe(model.copy.reportSuccessTitle);
  expect(container.querySelector(".mf-live-report-form__header span")?.textContent)
    .toBe(model.copy.reportSuccessBody);
});

it("removes FVG webcam controls from compact Territory when the source is out of scope", async () => {
  const model = buildModel({ webcamsEnabled: false });

  await act(async () => {
    root.render(
      <LiveView
        compactLayout
        model={model}
        reportingEnabled={false}
        reportingUnavailableText="Le segnalazioni non sono ancora attive in questa regione."
      />,
    );
  });

  const workspace = container.querySelector(".mf-live-territory-workspace");
  const navigationButtons = [...workspace.querySelectorAll(
    ".mf-territory-map__navigation button",
  )];

  expect(navigationButtons.map((button) => button.textContent.trim())).toEqual([
    "Mappa",
    "Segnalazioni",
  ]);
  expect(workspace.querySelector(".mf-territory-map__navigation").style.gridTemplateColumns)
    .toBe("repeat(2, minmax(0, 1fr))");
  expect(workspace.querySelector(".mf-territory-map__control--webcam")).toBeNull();
  expect(workspace.textContent).not.toContain("Sacile");
  expect(workspace.textContent).not.toContain("Maniago");
});

it("explains the FVG webcam boundary in the regular Territory layout", async () => {
  const model = buildModel({ webcamsEnabled: false });

  await act(async () => {
    root.render(<LiveView model={model} />);
  });

  const webcamPanel = container.querySelector(".mf-live-card--webcam");
  expect(webcamPanel.textContent).toContain("Webcam non disponibili in quest’area");
  expect(webcamPanel.textContent).toContain(
    "Le webcam editoriali sono disponibili soltanto in Friuli Venezia Giulia.",
  );
  expect(webcamPanel.textContent).not.toContain("Sacile");
});

it("keeps location correction available outside the pilot report composer", async () => {
  const model = buildModel();

  await act(async () => {
    root.render(
      <CommunityReportForm
        copy={model.copy}
        locations={model.community.reportLocations}
        maxDistanceKm={model.community.maxDistanceKm}
        onClose={() => {}}
        onLocate={() => Promise.resolve(buildReadyReportLocation())}
        onSubmit={() => Promise.resolve({ ok: true })}
        options={model.community.reportOptions}
      />,
    );
  });
  await flushAnimationFrame();

  const editButton = container.querySelector(
    `button[aria-label="${model.copy.reportLocationChange}"]`,
  );
  expect(editButton).not.toBeNull();
  expect(container.querySelector(".mf-live-report-location__rule")).toBeNull();

  await act(async () => editButton.click());

  expect(container.querySelector(".mf-live-report-location__selector")).not.toBeNull();
});

it("remembers community guidelines acceptance and omits it from later report forms", async () => {
  const model = buildModel();
  const personalStorage = createMemoryStorage();
  const renderReportForm = () => (
    <CommunityReportForm
      copy={model.copy}
      locations={model.community.reportLocations}
      maxDistanceKm={model.community.maxDistanceKm}
      onClose={() => {}}
      onLocate={() => Promise.resolve(buildReadyReportLocation())}
      onSubmit={() => Promise.resolve({ ok: true })}
      options={model.community.reportOptions}
      personalStorage={personalStorage}
    />
  );

  await act(async () => root.render(renderReportForm()));
  await flushAnimationFrame();

  const termsCheckbox = container.querySelector(".mf-live-report-terms input");
  expect(termsCheckbox).not.toBeNull();
  expect(container.querySelector(".mf-live-report-location-privacy")?.textContent)
    .toBe(model.copy.reportPreciseLocationNotice);
  expect(hasCommunityGuidelinesConsent(
    COMMUNITY_GUIDELINES_POLICY_VERSION,
    { storage: personalStorage },
  )).toBe(false);

  await act(async () => termsCheckbox.click());

  expect(container.querySelector(".mf-live-report-terms")).toBeNull();
  expect(hasCommunityGuidelinesConsent(
    COMMUNITY_GUIDELINES_POLICY_VERSION,
    { storage: personalStorage },
  )).toBe(true);
  expect(hasReportLocationNoticeConsent({ storage: personalStorage })).toBe(true);

  await act(async () => root.render(null));
  await act(async () => root.render(renderReportForm()));
  await flushAnimationFrame();

  expect(container.querySelector(".mf-live-report-terms")).toBeNull();
  expect(container.querySelector(".mf-live-report-location-privacy")?.textContent)
    .toBe(model.copy.reportPreciseLocationNotice);
});

it("asks prior guidelines acceptors to acknowledge the precise-location notice before reporting", async () => {
  const model = buildModel();
  const personalStorage = createMemoryStorage();
  rememberCommunityGuidelinesConsent(
    COMMUNITY_GUIDELINES_POLICY_VERSION,
    { storage: personalStorage },
  );

  await act(async () => {
    root.render(
      <CommunityReportForm
        copy={model.copy}
        locations={model.community.reportLocations}
        maxDistanceKm={model.community.maxDistanceKm}
        onClose={() => {}}
        onLocate={() => Promise.resolve(buildReadyReportLocation())}
        onSubmit={() => Promise.resolve({ ok: true })}
        options={model.community.reportOptions}
        personalStorage={personalStorage}
      />,
    );
  });
  await flushAnimationFrame();

  const checkbox = container.querySelector(".mf-live-report-terms input");
  expect(checkbox).not.toBeNull();
  expect(container.querySelector(".mf-live-report-location-privacy")?.textContent)
    .toBe(model.copy.reportPreciseLocationNotice);
  expect(hasReportLocationNoticeConsent({ storage: personalStorage })).toBe(false);
  expect(container.querySelector(".mf-live-report-submit")?.disabled).toBe(true);

  await act(async () => checkbox.click());

  expect(hasReportLocationNoticeConsent({ storage: personalStorage })).toBe(true);
  expect(container.querySelector(".mf-live-report-terms")).toBeNull();
});

it("does not persist guidelines acceptance from a preview-only report form", async () => {
  const model = buildModel();
  const personalStorage = createMemoryStorage();

  await act(async () => {
    root.render(
      <CommunityReportForm
        copy={model.copy}
        locations={model.community.reportLocations}
        maxDistanceKm={model.community.maxDistanceKm}
        onClose={() => {}}
        onLocate={() => Promise.resolve(buildReadyReportLocation())}
        onSubmit={() => Promise.resolve({ ok: true })}
        options={model.community.reportOptions}
        personalStorage={personalStorage}
        previewOnly
      />,
    );
  });
  await flushAnimationFrame();

  await act(async () => container.querySelector(".mf-live-report-terms input").click());

  expect(hasCommunityGuidelinesConsent(
    COMMUNITY_GUIDELINES_POLICY_VERSION,
    { storage: personalStorage },
  )).toBe(false);
  expect(hasReportLocationNoticeConsent({ storage: personalStorage })).toBe(false);
  expect(container.querySelector(".mf-live-report-submit")?.disabled).toBe(true);
});

it("shows a compact pilot receipt and lets its author undo the submitted report", async () => {
  const model = buildModel();
  const personalStorage = createMemoryStorage();
  const now = Date.now();
  const identity = buildPublicCommunityIdentitySnapshot(buildCommunityIdentity({
    placeName: "Pordenone",
    revision: 4,
    subjectId: "acuile",
  }));
  const onUndo = vi.fn().mockResolvedValue({ ok: true });
  const onSubmit = vi.fn().mockResolvedValue({
    ok: true,
    report: {
      expiresAt: now + (60 * 60_000) + 30_000,
      groupId: "rain:pordenone:identity",
      id: "report-identity",
      identity,
      place: "Pordenone",
      sourceKey: "private-source-key",
      typeId: "rain",
      typeLabel: "Pioggia",
    },
    undoUntil: now + 60_000,
  });

  await act(async () => {
    root.render(
      <CommunityReportForm
        copy={model.copy}
        locations={model.community.reportLocations}
        maxDistanceKm={model.community.maxDistanceKm}
        onClose={() => {}}
        onLocate={() => Promise.resolve(buildReadyReportLocation())}
        onSubmit={onSubmit}
        onUndo={onUndo}
        options={model.community.reportOptions}
        personalStorage={personalStorage}
        pilotStyle
      />,
    );
  });
  await flushAnimationFrame();

  await act(async () => container.querySelector(".mf-live-report-option--rain").click());
  await act(async () => container.querySelector(".mf-live-report-terms input").click());
  await act(async () => container.querySelector(".mf-live-report-submit").click());
  await flushAnimationFrame();

  const success = container.querySelector(".mf-live-report-success");
  expect(onSubmit).toHaveBeenCalledTimes(1);
  expect(success).not.toBeNull();
  expect(success.classList.contains("mf-live-report-success--pilot-receipt")).toBe(true);
  expect(success.querySelector(".mf-live-report-success__title")?.textContent)
    .toBe("Segnalazione inviata!");
  expect(success.querySelector(".mf-live-report-success__description")?.textContent)
    .toBe(model.copy.reportSuccessBody);
  expect(container.querySelector(".mf-live-report-form--receipt")).not.toBeNull();
  expect(container.querySelector(".mf-live-report-form__header strong")).toBeNull();
  const summary = success.querySelector(".mf-live-report-success__summary");
  expect(summary).not.toBeNull();
  expect(summary.hasAttribute("aria-label")).toBe(false);
  expect(summary.textContent).toContain("Pioggia");
  expect(summary.querySelector('svg[aria-hidden="true"]')).not.toBeNull();
  expect(summary.querySelector(".mf-live-report-success__summary-row")?.textContent)
    .toContain("Scade tra 60 min");
  expect(summary.querySelector(".mf-live-report-success__place")?.textContent)
    .toBe("Pordenone");
  expect(success.querySelector(".mf-live-report-success__identity-label")?.textContent)
    .toBe("Inviata come:");
  const identityInline = success.querySelector(".mf-live-report-success__identity-inline");
  expect(identityInline?.textContent).toContain(identity.alias);
  expect(identityInline?.querySelector('.mf-community-avatar[data-subject="acuile"]'))
    .not.toBeNull();
  expect(success.querySelector(".mf-live-report-success__identity-pill")).toBeNull();
  expect(success.textContent).not.toContain("private-source-key");
  expect(container.querySelector(".mf-live-report-safety")).toBeNull();

  const mapAction = container.querySelector(".mf-live-report-map-action");
  const undoAction = container.querySelector(".mf-live-report-undo");
  expect(mapAction).not.toBeNull();
  expect(undoAction).not.toBeNull();
  expect(mapAction.compareDocumentPosition(undoAction) & Node.DOCUMENT_POSITION_FOLLOWING)
    .toBeTruthy();

  await act(async () => undoAction.click());
  await flushAnimationFrame();

  expect(onUndo).toHaveBeenCalledWith("report-identity");
  expect(container.querySelector(".mf-live-report-success")).toBeNull();
  expect(container.querySelector(".mf-live-report-options")).not.toBeNull();
  expect(container.querySelector(".mf-live-report-feedback")?.textContent)
    .toContain(model.copy.reportUndoSuccess);
});

it.each([
  { scenario: "new report", language: "it", correction: false, expired: false },
  { scenario: "new report in Friulian", language: "fur", correction: false, expired: false },
  { scenario: "corrected report", language: "it", correction: true, expired: false },
  { scenario: "expired reconciled report", language: "it", correction: false, expired: true },
  { scenario: "expired reconciled correction", language: "it", correction: true, expired: true },
])("keeps a centered pilot sheet receipt accessible for $scenario without adding undo", async ({ language, correction, expired }) => {
  const model = buildModel();
  const copy = getLiveViewCopy(language);
  const now = Date.now();
  const identity = buildPublicCommunityIdentitySnapshot(buildCommunityIdentity({
    placeName: "Pordenone",
    revision: 4,
    subjectId: "acuile",
  }));
  const report = {
    expiresAt: expired ? now - 60_000 : now + 3_600_000,
    groupId: "rain:pordenone:receipt-sheet",
    id: "report-receipt-sheet",
    identity,
    place: "Pordenone",
    typeId: "rain",
    typeLabel: copy.reportTypes.rain,
  };
  const onClose = vi.fn();
  const onViewMap = vi.fn();
  const onUndo = vi.fn();
  const onSubmit = vi.fn().mockResolvedValue({ expired, ok: true, report });

  await act(async () => {
    root.render(
      <CommunityReportForm
        copy={copy}
        correctionReport={correction ? { ...report, reportId: report.id } : null}
        dialogId="receipt-sheet-test"
        locations={model.community.reportLocations}
        maxDistanceKm={model.community.maxDistanceKm}
        onClose={onClose}
        onLocate={() => Promise.resolve(buildReadyReportLocation())}
        onSubmit={onSubmit}
        onUndo={onUndo}
        onViewMap={onViewMap}
        options={model.community.reportOptions}
        personalStorage={createMemoryStorage()}
        pilotStyle
        sheet
      />,
    );
  });
  await flushAnimationFrame();
  const dialog = document.body.querySelector("#receipt-sheet-test");
  expect(dialog?.getAttribute("role")).toBe("dialog");
  await act(async () => dialog.querySelector(".mf-live-report-option--rain").click());
  await act(async () => dialog.querySelector(".mf-live-report-terms input").click());
  await act(async () => dialog.querySelector(".mf-live-report-submit").click());
  await flushAnimationFrame();

  const success = dialog.querySelector(".mf-live-report-success");
  const title = success?.querySelector(".mf-live-report-success__title");
  const description = success?.querySelector(".mf-live-report-success__description");
  expect(onSubmit).toHaveBeenCalledOnce();
  expect(dialog.classList.contains("mf-live-report-form--receipt")).toBe(true);
  expect(success?.querySelectorAll(".mf-live-report-success__title")).toHaveLength(1);
  expect(success?.querySelectorAll(".mf-live-report-success__description")).toHaveLength(1);
  expect(title?.textContent).toBe(correction ? "Osservazione corretta" : copy.reportSuccessReceipt);
  expect(description?.tagName).toBe("P");
  expect(description?.textContent).toBe(expired
    ? "L’operazione era riuscita, ma questa osservazione è già scaduta."
    : correction
      ? "Correzione salvata. La scadenza resta invariata."
      : copy.reportSuccessBody);
  expect(dialog.getAttribute("aria-labelledby")).toBe(title?.id);
  expect(dialog.getAttribute("aria-describedby")).toBe(description?.id);
  expect(document.querySelectorAll("#receipt-sheet-test-title")).toHaveLength(1);
  expect(document.querySelectorAll("#receipt-sheet-test-description")).toHaveLength(1);
  const header = dialog.querySelector(".mf-live-report-form__header");
  expect(header.textContent).toBe("");
  expect(header.querySelectorAll("button")).toHaveLength(1);
  expect(header.querySelector("button")?.getAttribute("aria-label")).toBe(copy.reportClose);
  expect(success.querySelector(".mf-live-report-success__identity-label")?.textContent)
    .toBe(language === "fur" ? "Inviade come:" : "Inviata come:");
  expect(success.querySelector(".mf-live-report-success__identity-inline")?.textContent)
    .toContain(identity.alias);
  expect(success.querySelector(".mf-live-report-success__place")?.textContent)
    .toBe("Pordenone");
  expect(dialog.querySelector(".mf-live-report-undo")).toBeNull();
  const mapAction = dialog.querySelector(".mf-live-report-map-action");
  expect(mapAction?.textContent).toBe(copy.reportSuccessMap);
  await act(async () => mapAction.click());
  expect(onViewMap).toHaveBeenCalledOnce();
  expect(onClose).not.toHaveBeenCalled();
  await act(async () => header.querySelector("button").click());
  expect(onClose).toHaveBeenCalledOnce();
  expect(onUndo).not.toHaveBeenCalled();
});

it("keeps the ordinary success card and its uncapped countdown unchanged", async () => {
  const model = buildModel();
  const personalStorage = createMemoryStorage();
  const now = Date.now();
  const identity = buildPublicCommunityIdentitySnapshot(buildCommunityIdentity({
    placeName: "Pordenone",
    revision: 4,
    subjectId: "acuile",
  }));

  await act(async () => {
    root.render(
      <CommunityReportForm
        copy={model.copy}
        locations={model.community.reportLocations}
        maxDistanceKm={model.community.maxDistanceKm}
        onClose={() => {}}
        onLocate={() => Promise.resolve(buildReadyReportLocation())}
        onSubmit={() => Promise.resolve({
          ok: true,
          report: {
            expiresAt: now + (60 * 60_000) + 30_000,
            groupId: "rain:pordenone:legacy",
            id: "report-legacy",
            identity,
            place: "Pordenone",
            typeId: "rain",
            typeLabel: "Pioggia",
          },
        })}
        options={model.community.reportOptions}
        personalStorage={personalStorage}
      />,
    );
  });
  await flushAnimationFrame();

  await act(async () => container.querySelector(".mf-live-report-option--rain").click());
  await act(async () => container.querySelector(".mf-live-report-terms input").click());
  await act(async () => container.querySelector(".mf-live-report-submit").click());
  await flushAnimationFrame();

  const success = container.querySelector(".mf-live-report-success");
  expect(success?.querySelector(":scope > strong")?.textContent)
    .toBe(model.copy.ownReportLabel);
  expect(success?.textContent).toContain("Scade tra 61 min");
  expect(success?.classList.contains("mf-live-report-success--pilot-receipt")).toBe(false);
  expect(success?.querySelector(".mf-live-report-success__summary")).toBeNull();
  expect(success?.querySelector(".mf-live-report-success__identity-inline")).toBeNull();
  expect(success?.querySelector(".mf-live-report-success__description")).toBeNull();
  expect(container.querySelector(".mf-live-report-form--receipt")).toBeNull();
  expect(container.querySelector(".mf-live-report-form__header strong")?.textContent)
    .toBe(model.copy.reportSuccessTitle);
  expect(container.querySelector(".mf-live-report-form__header span")?.textContent)
    .toBe(model.copy.reportSuccessBody);
});

it("keeps pilot report cards focused on voting, share and close without moderation", async () => {
  const model = buildCommunityModel();
  const share = vi.fn().mockResolvedValue(undefined);
  const writeText = vi.fn().mockResolvedValue(undefined);
  Object.defineProperty(globalThis.navigator, "share", {
    configurable: true,
    value: share,
  });
  Object.defineProperty(globalThis.navigator, "clipboard", {
    configurable: true,
    value: { writeText },
  });

  await act(async () => {
    root.render(
      <LiveView
        compactLayout
        model={model}
        onReportConfirm={vi.fn().mockResolvedValue({ ok: true })}
        onReportFlag={vi.fn().mockResolvedValue({ ok: true })}
        reportingEnabled
      />,
    );
  });

  const workspace = container.querySelector(".mf-live-territory-workspace");
  const inlineMap = workspace.querySelector(".mf-territory-map--inline");
  const marker = inlineMap.querySelector(".mf-live-community-map__marker");
  expect(marker).not.toBeNull();

  await act(async () => marker.click());
  await flushAnimationFrame();

  const detail = workspace.querySelector(".mf-territory-map__report-detail");
  const primaryHeading = detail.querySelector(".mf-territory-map__report-primary-heading");
  const headingCopy = detail.querySelector(".mf-territory-map__report-heading-copy");
  const communityStatus = detail.querySelector(".mf-territory-map__report-community-status");
  const expectedIdentity = getCommunityIdentityPreview({
    placeName: "Pordenone",
    sourceKeys: ["source-test"],
  }).identities[0];
  const phenomenon = detail.querySelector(".mf-live-community-map__phenomenon");
  const confirmationActions = phenomenon.querySelector(".mf-live-community-map__confirm-actions");
  const confirmButton = confirmationActions.querySelector(
    ".mf-live-community-map__confirm-button--yes",
  );
  const denyButton = confirmationActions.querySelector(
    ".mf-live-community-map__confirm-button--no",
  );
  const headingActions = primaryHeading.querySelector(
    ".mf-territory-map__report-heading-actions",
  );
  const manageButton = headingActions.querySelector(".mf-territory-map__report-manage");
  const closeDetailButton = headingActions.querySelector(".mf-territory-map__report-close");
  const shareButton = headingActions.querySelector(".mf-territory-map__share-action");
  expect(detail).not.toBeNull();
  expect(detail.getAttribute("role")).toBe("dialog");
  expect(detail.getAttribute("aria-modal")).toBe("true");
  expect(primaryHeading.textContent).toContain("Pioggia");
  expect(headingCopy.textContent).toContain("Pordenone · Segnalata");
  expect(primaryHeading.lastElementChild).toBe(headingActions);
  expect([...headingActions.children]).toEqual([
    shareButton,
    closeDetailButton,
    headingActions.querySelector(".mf-territory-map__share-status"),
  ]);
  expect(manageButton).toBeNull();
  expect(headingActions.querySelector(".lucide-ellipsis")).toBeNull();
  expect(detail.querySelector('[aria-label="Gestisci contenuto"]')).toBeNull();
  expect(closeDetailButton).not.toBeNull();
  expect(closeDetailButton.getAttribute("aria-label")).toBe("Chiudi dettaglio segnalazione");
  expect(closeDetailButton.textContent.trim()).toBe("");
  expect(closeDetailButton.querySelector('svg[aria-hidden="true"]')).not.toBeNull();
  expect(communityStatus.textContent).toContain("1 segnalazione recente");
  expect(communityStatus.textContent).toContain("Riferito al Comune");
  expect(communityStatus.textContent).toContain(expectedIdentity.alias);
  expect(communityStatus.textContent).not.toContain("source-test");
  expect(communityStatus.querySelector(
    `.mf-community-avatar[data-subject="${expectedIdentity.subjectId}"] svg`,
  )).not.toBeNull();
  expect(detail.textContent).toContain("Pordenone");
  expect(detail.textContent).not.toContain("Zona indicativa del Comune, non la posizione esatta.");
  expect(detail.textContent).not.toContain(model.copy.denialExplanation);
  expect(detail.querySelector(".mf-live-community-map__confirmation-summary")).toBeNull();
  expect(detail.querySelector(".mf-live-community-map__denial-status")).toBeNull();
  expect(confirmButton.querySelector(".mf-live-community-map__confirm-label")?.textContent)
    .toBe("Confermo");
  expect(confirmButton.querySelector(".mf-live-community-map__confirm-count")?.textContent)
    .toBe("2");
  expect(confirmButton.getAttribute("aria-label")).toBe("Confermo. Conferme: 2");
  expect(confirmButton.querySelector(".lucide-thumbs-up")).not.toBeNull();
  expect(confirmButton.getAttribute("aria-pressed")).toBe("false");
  expect(denyButton.querySelector(".mf-live-community-map__confirm-label")?.textContent)
    .toBe("Non c’è più");
  expect(denyButton.querySelector(".mf-live-community-map__confirm-count")?.textContent)
    .toBe("0");
  expect(denyButton.getAttribute("aria-label")).toBe("Non c’è più. Non c’è più: 0");
  expect(denyButton.querySelector(".lucide-thumbs-down")).not.toBeNull();
  expect(denyButton.getAttribute("aria-pressed")).toBe("false");
  expect([...confirmationActions.children]).toEqual([confirmButton, denyButton]);
  expect(phenomenon.querySelector(".mf-live-community-map__flag-action")).toBeNull();
  expect(document.body.querySelector(".mf-live-moderation-dialog")).toBeNull();
  expect(document.body.textContent).not.toContain(model.copy.reportFlagTitle);
  expect(detail.textContent).not.toContain("Lo vedo anch’io");
  expect(shareButton.getAttribute("aria-label")).toBe("Condividi");
  expect(detail.textContent).not.toContain("Chiudi");
  expect(detail.textContent).not.toMatch(/45[,.]9567|12[,.]6605/);
  expect(detail.textContent).not.toMatch(/confermat[ao].*radar/iu);
  expect(document.activeElement).toBe(detail);
  expect(workspace.querySelector(".mf-territory-map--inline")).toBe(inlineMap);
  expect(primaryHeading.compareDocumentPosition(communityStatus) & Node.DOCUMENT_POSITION_FOLLOWING)
    .toBeTruthy();
  expect(communityStatus.compareDocumentPosition(phenomenon) & Node.DOCUMENT_POSITION_FOLLOWING)
    .toBeTruthy();
  expect(detail.querySelector(".mf-territory-map__report-detail-actions")).toBeNull();
  expect(detail.lastElementChild).toBe(phenomenon.parentElement);
  expect(headingActions.querySelectorAll("button")).toHaveLength(2);

  expect(shareButton).not.toBeNull();
  expect(shareButton.textContent.trim()).toBe("");
  expect(shareButton.querySelector('svg[aria-hidden="true"].lucide-share-2')).not.toBeNull();
  await act(async () => shareButton.click());

  expect(share).not.toHaveBeenCalled();
  expect(writeText).toHaveBeenCalledTimes(1);
  const sharedText = writeText.mock.calls[0][0];
  expect(sharedText).toContain("Pioggia");
  expect(sharedText).toContain("Pordenone");
  expect(sharedText).toContain(
    "https://meteofriul.it/?segnalazione=rain%3Apordenone%3Atest",
  );
  expect(sharedText).not.toMatch(
    /45[,.]9567|12[,.]6605|source-test|confermat[ao].*radar/iu,
  );
  expect(sharedText).not.toMatch(/127\.0\.0\.1|localhost|communityReportQa/u);
  expect(shareButton.getAttribute("aria-label")).toBe("Link copiato");
  expect(shareButton.classList.contains("is-success")).toBe(true);
  expect(shareButton.querySelector('svg[aria-hidden="true"].lucide-check')).not.toBeNull();
  const shareStatus = headingActions.querySelector(".mf-territory-map__share-status");
  expect(shareStatus).not.toBeNull();
  expect(shareStatus.getAttribute("role")).toBe("status");
  expect(shareStatus.getAttribute("aria-live")).toBe("polite");
  expect(shareStatus.getAttribute("aria-atomic")).toBe("true");
  expect(shareStatus.textContent).toBe("Link copiato");

  await act(async () => {
    document.dispatchEvent(new KeyboardEvent("keydown", { bubbles: true, key: "Escape" }));
  });
  await flushAnimationFrame();

  expect(workspace.querySelector(".mf-territory-map__report-detail")).toBeNull();
  expect(workspace.querySelector(".mf-territory-map--inline")).toBe(inlineMap);
  expect(document.activeElement).toBe(marker);

  await act(async () => marker.click());
  await flushAnimationFrame();

  const reopenedDetail = workspace.querySelector(".mf-territory-map__report-detail");
  const reopenedCloseDetailButton = reopenedDetail.querySelector(
    ".mf-territory-map__report-close",
  );
  expect(reopenedCloseDetailButton).not.toBeNull();
  expect(reopenedCloseDetailButton.getAttribute("aria-label"))
    .toBe("Chiudi dettaglio segnalazione");
  await act(async () => reopenedCloseDetailButton.click());

  expect(workspace.querySelector(".mf-territory-map__report-detail")).toBeNull();
  expect(workspace.querySelector(".mf-territory-map--inline")).toBe(inlineMap);
});

it("opens the exact recent report received from a shared link", async () => {
  const model = buildCommunityModel();

  await act(async () => {
    root.render(
      <LiveView
        compactLayout
        model={model}
        reportingEnabled
        sharedReportId="rain:pordenone:test"
        sharedReportLoadSettled
      />,
    );
  });
  await flushAnimationFrame();

  const detail = container.querySelector(".mf-territory-map__report-detail");
  expect(detail).not.toBeNull();
  expect(detail.textContent).toContain("Pioggia");
  expect(detail.textContent).toContain("Pordenone");
});

it("updates the visible confirmation count from the authoritative vote response", async () => {
  const model = buildCommunityModel();
  const personalStorage = createMemoryStorage();
  const onReportConfirm = vi.fn()
    .mockResolvedValueOnce({
      confirmations: { no: 0, yes: 3 },
      ok: true,
      vote: "yes",
    })
    .mockResolvedValueOnce({
      confirmations: { no: 1, yes: 2 },
      ok: true,
      vote: "no",
    });
  rememberCommunityGuidelinesConsent(
    COMMUNITY_GUIDELINES_POLICY_VERSION,
    { storage: personalStorage },
  );

  await act(async () => {
    root.render(
      <LiveView
        compactLayout
        model={model}
        onReportConfirm={onReportConfirm}
        personalStorage={personalStorage}
        reportingEnabled
      />,
    );
  });

  const workspace = container.querySelector(".mf-live-territory-workspace");
  await act(async () => workspace.querySelector(".mf-live-community-map__marker").click());
  await flushAnimationFrame();

  const confirmButton = workspace.querySelector(
    ".mf-live-community-map__confirm-button--yes",
  );
  expect(confirmButton.querySelector(".mf-live-community-map__confirm-count")?.textContent)
    .toBe("2");

  await act(async () => confirmButton.click());

  expect(onReportConfirm).toHaveBeenCalledTimes(1);
  expect(confirmButton.querySelector(".mf-live-community-map__confirm-count")?.textContent)
    .toBe("3");
  expect(confirmButton.getAttribute("aria-label")).toBe("Confermo. Conferme: 3");
  expect(confirmButton.getAttribute("aria-pressed")).toBe("true");

  const denyButton = workspace.querySelector(
    ".mf-live-community-map__confirm-button--no",
  );
  expect(denyButton.disabled).toBe(false);
  await act(async () => denyButton.click());

  expect(onReportConfirm).toHaveBeenCalledTimes(2);
  expect(onReportConfirm.mock.calls[1].slice(0, 2))
    .toEqual(["rain:pordenone:test", "no"]);
  expect(workspace.querySelector(".mf-territory-map__report-detail")).toBeNull();
  expect(workspace.querySelector(".mf-live-community-map__marker")).toBeNull();
});

it("keeps the inline map mounted when the last community report disappears", async () => {
  await act(async () => {
    root.render(<LiveView compactLayout model={buildCommunityModel()} />);
  });

  const workspace = container.querySelector(".mf-live-territory-workspace");
  const inlineMap = workspace.querySelector(".mf-territory-map--inline");
  expect(inlineMap.querySelector(".mf-live-community-map__marker")).not.toBeNull();

  await act(async () => {
    root.render(<LiveView compactLayout model={buildModel()} />);
  });

  expect(container.querySelector(".mf-territory-map--inline")).toBe(inlineMap);
  expect(inlineMap.querySelector(".mf-live-community-map__marker")).toBeNull();

  const reportsButton = [...inlineMap.querySelectorAll(".mf-territory-map__navigation button")]
    .find((button) => button.textContent.includes("Segnalazioni"));
  await act(async () => reportsButton.click());
  await flushAnimationFrame();

  expect(inlineMap.querySelector(".mf-territory-map__browse-sheet")?.textContent)
    .toContain("Nessuna segnalazione recente sulla mappa.");
  expect(container.querySelector(".mf-territory-map--inline")).toBe(inlineMap);
  expect(container.inert).not.toBe(true);
  expect(container.hasAttribute("aria-hidden")).toBe(false);
});

it("distinguishes community loading and errors from a verified empty result", async () => {
  const loadingModel = buildModel({ communityStatus: "loading" });

  await act(async () => {
    root.render(<LiveView compactLayout model={loadingModel} />);
  });

  let note = container.querySelector(".mf-territory-map__service-note");
  expect(note.classList.contains("mf-territory-map__service-note--loading")).toBe(true);
  expect(note.textContent).toContain(loadingModel.copy.communityLoadingTitle);
  expect(note.textContent).toContain(loadingModel.copy.communityLoadingBody);
  expect(note.textContent).not.toContain("Nessuna segnalazione recente sulla mappa");

  const errorModel = buildModel({ communityStatus: "error" });
  await act(async () => {
    root.render(<LiveView compactLayout model={errorModel} />);
  });

  note = container.querySelector(".mf-territory-map__service-note");
  expect(note.classList.contains("mf-territory-map__service-note--error")).toBe(true);
  expect(note.textContent).toContain(errorModel.copy.communityErrorTitle);
  expect(note.textContent).toContain(errorModel.copy.communityErrorBody);
  expect(note.textContent).not.toContain("Nessuna segnalazione recente sulla mappa");
});

it("restores focus inside the inline map after closing nested confirmation consent", async () => {
  const model = buildCommunityModel();
  const personalStorage = createMemoryStorage();

  await act(async () => {
    root.render(
      <LiveView
        compactLayout
        model={model}
        onReportConfirm={vi.fn().mockResolvedValue({ ok: true, vote: "yes" })}
        personalStorage={personalStorage}
        reportingEnabled
      />,
    );
  });

  const workspace = container.querySelector(".mf-live-territory-workspace");
  const inlineMap = workspace.querySelector(".mf-territory-map--inline");
  const marker = inlineMap.querySelector(".mf-live-community-map__marker");
  await act(async () => marker.click());
  await flushAnimationFrame();

  const confirmationButton = workspace.querySelector(
    ".mf-live-community-map__confirm-button--yes",
  );
  expect(confirmationButton).toBeTruthy();
  await act(async () => confirmationButton.click());

  const consent = document.body.querySelector(".mf-live-consent-dialog");
  expect(consent).not.toBeNull();
  expect(container.inert).toBe(true);
  expect(container.getAttribute("aria-hidden")).toBe("true");

  const closeConsentButton = consent.querySelector(
    `button[aria-label="${model.copy.reportFlagClose}"]`,
  );
  await act(async () => closeConsentButton.click());
  await flushAnimationFrame();

  expect(document.body.querySelector(".mf-live-consent-dialog")).toBeNull();
  expect(container.inert).toBe(false);
  expect(container.hasAttribute("aria-hidden")).toBe(false);
  expect(container.querySelector(".mf-territory-map--inline")).toBe(inlineMap);
  expect(document.activeElement).toBe(confirmationButton);
});

it("keeps the ordinary non-pilot community map inline and unchanged", async () => {
  const model = buildCommunityModel();

  await act(async () => {
    root.render(<LiveView model={model} />);
  });

  const communityCard = container.querySelector(".mf-live-card--community");
  expect(communityCard.querySelector(".mf-live-community-intro")).not.toBeNull();
  expect(communityCard.querySelector(".mf-live-community-feed > h3")).not.toBeNull();
  expect(communityCard.querySelector(".mf-live-community-map")).not.toBeNull();
  expect(communityCard.querySelector(".mf-live-community-map-toggle")).toBeNull();
  expect(document.body.querySelector(".mf-live-community-map-layer--pilot")).toBeNull();

  const ordinaryMarker = communityCard.querySelector(".mf-live-community-map__marker");
  await act(async () => ordinaryMarker.click());
  expect(communityCard.querySelector(".mf-live-community-map__detail")?.hasAttribute("role"))
    .toBe(false);
});
