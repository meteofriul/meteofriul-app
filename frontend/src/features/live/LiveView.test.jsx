import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { getLiveViewCopy } from "../../copy/liveViewCopy";
import { buildBulletinRadarViewModel } from "../bulletin/bulletinRadarViewModel";
import {
  buildCommunityIdentity,
  buildPublicCommunityIdentitySnapshot,
  getCommunityIdentityPreview,
} from "../community/communityIdentity";
import { CommunityModerationDialog } from "./CommunityMap";
import {
  CommunityReportForm,
  LiveView,
  WebcamFailureActions,
  WebcamFailureCopy,
} from "./LiveView";
import { getReportFeedback } from "./liveReportFeedback";
import { buildLiveViewModel } from "./liveViewModel";
import { createWebcamMediaState, failWebcamMedia } from "./webcamMediaState";
import { getWebcamSnapshotBadgeLabel } from "./webcamSnapshotMetadata";

const radarNow = Date.parse("2026-08-30T09:25:00Z");

describe("webcam snapshot freshness label", () => {
  it("uses the verified source time without calling a snapshot live", () => {
    const copy = getLiveViewCopy("it");

    expect(getWebcamSnapshotBadgeLabel({
      copy,
      language: "it",
      now: new Date("2026-09-19T18:30:00+02:00"),
      updatedAt: "2026-09-19T16:27:53.000Z",
    })).toBe("Aggiornata alle 18:27");
  });

  it("includes the date for an older frame and never invents one when metadata is absent", () => {
    const copy = getLiveViewCopy("it");

    expect(getWebcamSnapshotBadgeLabel({
      copy,
      language: "it",
      now: new Date("2026-09-19T18:30:00+02:00"),
      updatedAt: "2026-09-18T16:27:53.000Z",
    })).toBe("Aggiornata il 18/09 alle 18:27");
    expect(getWebcamSnapshotBadgeLabel({
      copy,
      language: "it",
      now: new Date("2026-09-19T18:30:00+02:00"),
      updatedAt: "",
    })).toBe("Ultima immagine disponibile");
  });

  it("uses the Europe/Rome calendar when the UTC date is different", () => {
    const copy = getLiveViewCopy("it");

    expect(getWebcamSnapshotBadgeLabel({
      copy,
      language: "it",
      now: new Date("2026-09-20T23:30:00+02:00"),
      updatedAt: "2026-09-19T22:15:00.000Z",
    })).toBe("Aggiornata alle 00:15");
  });
});

function buildRadarModel(language = "it") {
  return buildBulletinRadarViewModel({
    status: "fresh",
    payload: {
      products: [{ id: "rain", product_type: "SRI", time: "2026-08-30T09:20:00Z", period_minutes: 5 }],
      tiles: { base_url: "https://tiles.example.test", tile_size: 256 },
    },
  }, { language, now: radarNow });
}

function buildModel() {
  return buildLiveViewModel({
    community: {
      payload: {
        map_groups: [{
          confirmations: { no: 0, yes: 1 },
          count: 1,
          createdAt: Date.now(),
          groupId: "group-rain:pordenone:1",
          id: "group-rain:pordenone:1",
          lat: 45.9567,
          lon: 12.6605,
          place: "Pordenone",
          sourceKeys: ["opaque-source-a"],
          typeId: "rain",
          x: 42,
          y: 61,
        }],
        reports: [{
          createdAt: Date.now(),
          expiresAt: Date.now() + 60_000,
          groupId: "group-rain:pordenone:1",
          id: "report-rain-1",
          lat: 45.9567,
          lon: 12.6605,
          place: "Pordenone",
          sourceKeys: ["opaque-source-a"],
          typeId: "rain",
        }],
      },
      status: "fresh",
    },
    webcams: {
      payload: {
        ok: true,
        webcams: [
          {
            area: "Sacile",
            group: "plain",
            health: "ok",
            id: "sacile",
            imageUrl: "https://images.example.test/sacile.jpg",
            mediaType: "video",
            name: "Sacile",
            playerUrl: "https://video.example.test/sacile.m3u8",
            provider: "Protezione Civile FVG",
            sourcePage: "https://www.osmer.fvg.it/webcam_img.php?ln=it",
          },
        ],
      },
      status: "fresh",
    },
  }, {
    location: { city: "Pordenone", lat: 45.9567, lon: 12.6605 },
  });
}

function buildWebcamModel(webcams, status = "fresh", language = "it") {
  return buildLiveViewModel({
    community: {
      payload: { map_groups: [], reports: [] },
      status: "fresh",
    },
    webcams: {
      payload: webcams ? { ok: true, webcams } : null,
      status,
    },
  }, {
    language,
    location: { city: "Pordenone", lat: 45.9567, lon: 12.6605 },
  });
}

describe("LiveView", () => {
  it("places the compact official alert before radar and Live content", () => {
    const markup = renderToStaticMarkup(
      <LiveView
        model={buildModel()}
        officialAlert={{
          label: "Allerta arancione",
          meta: "Protezione Civile FVG",
          tone: "orange",
          validityLabel: "Valida fino alle 18:00",
        }}
        onOfficialAlertOpen={() => {}}
        radarModel={buildRadarModel()}
      />,
    );
    const alertIndex = markup.indexOf("mf-official-alert-compact");
    const locationIndex = markup.indexOf('class="mf-live-location-context"');

    expect(locationIndex).toBeGreaterThanOrEqual(0);
    expect(alertIndex).toBeGreaterThan(locationIndex);
    expect(alertIndex).toBeLessThan(markup.indexOf("mf-bulletin-radar-card"));
    expect(markup).toContain("Allerta arancione");
    expect(markup).toContain("Valida fino alle 18:00");
  });

  it("can delegate the route location without emptying the inline Territorio workspace", () => {
    const markup = renderToStaticMarkup(
      <LiveView
        compactLayout
        model={buildModel()}
        radarModel={buildRadarModel()}
        showLocationContext={false}
      />,
    );

    expect(markup).not.toContain('class="mf-live-location-context"');
    expect(markup.match(/class="[^"]*mf-live-territory-workspace/g)).toHaveLength(1);
    expect(markup.match(/class="mf-live-community-map /g)).toHaveLength(1);
    expect(markup).toContain("mf-territory-map--inline");
    expect(markup).not.toContain("mf-official-alert-compact");
    expect(markup).not.toContain("mf-bulletin-radar-card");
    expect(markup).not.toContain("mf-live-card--webcam");
    expect(markup).not.toContain("mf-live-card--community");
    expect(markup).not.toContain("mf-live-territory-sources");
  });

  it("requires explicit community guidelines consent before report submission", () => {
    const model = buildModel();
    const markup = renderToStaticMarkup(
      <CommunityReportForm
        copy={model.copy}
        locations={model.community.reportLocations}
        maxDistanceKm={model.community.maxDistanceKm}
        onClose={() => {}}
        onLocate={() => Promise.resolve({ ok: false, reason: "permission_denied" })}
        onSubmit={() => Promise.resolve({ ok: true })}
        options={model.community.reportOptions}
      />,
    );

    expect(markup).toContain(model.copy.reportTermsTitle);
    expect(markup).toContain(model.copy.reportTermsBody);
    expect(markup).toContain(model.copy.reportTermsAccept);
    expect(markup).toContain(model.copy.reportSafety);
    expect(markup).toContain(model.copy.reportExpires);
    expect(markup).toContain('class="mf-live-report-meta"');
    expect(markup).not.toContain("mf-live-report-duration");
    expect(markup).not.toContain("mf-live-report-safety");
    expect(markup).toContain('type="checkbox"');
    expect(markup).toContain('disabled=""');
  });

  it("renders a fail-closed local preview without an active submit action", () => {
    const model = buildModel();
    const markup = renderToStaticMarkup(
      <CommunityReportForm
        copy={model.copy}
        locations={model.community.reportLocations}
        maxDistanceKm={model.community.maxDistanceKm}
        onClose={() => {}}
        onLocate={() => Promise.resolve({ ok: true })}
        onSubmit={() => Promise.resolve({ ok: true })}
        options={model.community.reportOptions}
        previewOnly
      />,
    );

    expect(markup).toContain(model.copy.reportPreviewOnly);
    expect(markup).toContain(model.copy.reportPreviewSubmit);
    expect(markup).toContain('class="mf-button mf-button--primary mf-live-report-submit" disabled=""');
  });

  it("presents the report composer as a labelled three-zone dialog", () => {
    const model = buildModel();
    const markup = renderToStaticMarkup(
      <CommunityReportForm
        copy={model.copy}
        dialogId="community-report-test"
        locations={model.community.reportLocations}
        maxDistanceKm={model.community.maxDistanceKm}
        onClose={() => {}}
        onLocate={() => Promise.resolve({ ok: false, reason: "permission_denied" })}
        onSubmit={() => Promise.resolve({ ok: true })}
        options={model.community.reportOptions}
        previewOnly
        sheet
      />,
    );

    expect(markup).toContain('class="mf-live-report-layer"');
    expect(markup).toContain('aria-hidden="true" class="mf-live-report-layer__backdrop"');
    expect(markup).toContain('role="dialog"');
    expect(markup).toContain('aria-modal="true"');
    expect(markup).toContain('aria-labelledby="community-report-test-title"');
    expect(markup).toContain('class="mf-live-report-form mf-live-report-form--sheet"');
    expect(markup).not.toContain("mf-live-report-form--pilot");
    expect(markup).toContain('class="mf-live-report-form__body"');
    expect(markup).toContain('class="mf-live-report-form__footer"');
    expect(markup).toContain(model.copy.reportTermsRead);
  });

  it("enables only the report-form entry point in local preview mode", () => {
    const markup = renderToStaticMarkup(
      <LiveView model={buildModel()} reportingPreview />,
    );

    expect(markup).toContain("Segnala cosa vedi");
    expect(markup).toContain("mf-button--secondary mf-live-report-open");
    expect(markup).toContain('aria-haspopup="dialog"');
    expect(markup).toContain('aria-expanded="false"');
    expect(markup).not.toContain("L’invio delle segnalazioni non è configurato");
    expect(markup).not.toContain(">Confermo<");
  });

  it("shows the remaining cooldown instead of a generic submission error", () => {
    const copy = buildModel().copy;

    expect(getReportFeedback(copy, {
      ok: false,
      reason: "cooldown",
      retryAfterSeconds: 119,
    })).toBe(`${copy.reportCooldown} 2 min.`);
  });

  it("shows the explicit regional rollout reason", () => {
    const copy = buildModel().copy;

    expect(getReportFeedback(copy, {
      ok: false,
      reason: "community_region_not_enabled",
      detail: {
        message: "Le segnalazioni partecipative non sono ancora attive in questa regione.",
      },
    })).toBe("Le segnalazioni partecipative non sono ancora attive in questa regione.");
  });

  it("restores the undo action from the active session window", () => {
    const model = buildModel();
    const markup = renderToStaticMarkup(
      <CommunityReportForm
        copy={model.copy}
        locations={model.community.reportLocations}
        maxDistanceKm={model.community.maxDistanceKm}
        onClose={() => {}}
        onLocate={() => Promise.resolve({ ok: false, reason: "permission_denied" })}
        onSubmit={() => Promise.resolve({ ok: true })}
        onUndo={() => Promise.resolve({ ok: true })}
        options={model.community.reportOptions}
        pendingReportUndo={{
          reportId: "report-1",
          undoUntil: Date.now() + 60_000,
        }}
        ttlLabel={model.community.ttlLabel}
      />,
    );

    expect(markup).toContain(model.copy.reportUndo);
    expect(markup).toContain(model.copy.reportSafety);
    expect(markup).toContain(model.community.ttlLabel);
  });

  it("renders real webcam media, location context, social map and community action", () => {
    const model = buildModel();
    const legacyIdentity = getCommunityIdentityPreview({
      placeName: "Pordenone",
      sourceKeys: ["opaque-source-a"],
    }).identities[0];
    const markup = renderToStaticMarkup(
      <LiveView
        model={model}
        onChangeLocation={() => {}}
        onReportConfirm={() => Promise.resolve({ ok: true })}
        onReportFlag={() => Promise.resolve({ ok: true })}
        onReportLocate={() => Promise.resolve({ ok: false, reason: "permission_denied" })}
        onReportSubmit={() => Promise.resolve({ ok: true })}
        radarModel={buildRadarModel()}
        reportingEnabled
      />,
    );

    expect(markup).not.toContain(">Vicino a</span>");
    expect(markup).toContain("Pordenone");
    expect(markup).toContain('src="https://images.example.test/sacile.jpg"');
    expect(markup).toContain("Protezione Civile FVG");
    expect(markup).toContain("Scegli una zona");
    expect(markup).toContain("Scegli una webcam");
    expect(markup).toContain("Distanze da Pordenone");
    expect(markup).toContain("Vicino, 1 webcam");
    expect(markup).toContain('aria-expanded="false"');
    expect(markup).toContain('aria-controls="live-webcam-options-nearby"');
    expect(markup).toContain('class="mf-live-webcam-picker__options" hidden=""');
    expect(markup).not.toContain("mf-live-webcam-strip");
    expect(markup).toContain(
      'aria-label="Apri la fonte di Sacile in una nuova scheda"',
    );
    expect(markup).toContain('role="tabpanel"');
    expect(markup).toContain('aria-controls="live-webcam-panel"');
    expect(markup).not.toContain("mf-live-webcam-eyebrow");
    expect(markup).not.toContain("Immagini e funzionamento dipendono dalle fonti esterne.");
    expect(markup).toContain("Radar precipitazioni");
    expect(markup).toContain("mf-bulletin-radar-timeline__range");
    expect(markup).toContain("Mappa sociale delle segnalazioni");
    expect(markup).toContain("1 segnalazione");
    expect(markup.indexOf("mf-bulletin-radar-card")).toBeLessThan(
      markup.indexOf("mf-live-card--community"),
    );
    expect(markup.indexOf("mf-live-card--webcam")).toBeLessThan(
      markup.indexOf("mf-live-card--community"),
    );
    expect(markup.indexOf("mf-live-community-feed")).toBeLessThan(
      markup.indexOf("mf-live-community-map"),
    );
    expect(markup).not.toContain("Fonte attiva");
    expect(markup).toContain("Pioggia · Pordenone");
    expect(markup).toContain("Segnala cosa vedi");
    expect(markup).toContain("1 osservazione recente");
    expect(markup).toContain("Ultime segnalazioni");
    expect(markup).toContain("1 conferma recente");
    expect(markup).toContain("mf-live-community-item__deny");
    expect(markup).toContain("Smentisci");
    expect(markup).toContain(
      "La nascondi dalla tua mappa. Con 3 smentite viene rimossa dalla mappa per tutti.",
    );
    expect(markup).not.toContain('aria-label="Gestisci contenuto"');
    expect(markup).not.toContain("mf-live-community-item__flag");
    expect(markup).toContain(legacyIdentity.alias);
    expect(markup).toContain(`data-subject="${legacyIdentity.subjectId}"`);
    expect(markup).not.toContain("opaque-source-a");
    expect(markup).not.toContain("Apri pannello OSMER");
    expect(markup).not.toContain("Video live");
  });

  it("keeps webcam and radar controls inside the compact pilot workspace", () => {
    const model = buildWebcamModel([
      {
        area: "Sacile",
        group: "plain",
        id: "sacile",
        imageUrl: "https://images.example.test/sacile.jpg",
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
      {
        area: "Tarvisio",
        fallbackImageUrl: "/municipalities/photos/030117-photo.webp",
        group: "mountain",
        id: "tarvisio",
        lat: 46.5057,
        lon: 13.5784,
        name: "Tarvisio",
      },
    ]);
    const cameras = new Map(
      model.webcams.groups.flatMap((group) => group.cameras.map((camera) => [camera.id, camera])),
    );
    model.webcams.groups = [
      {
        cameras: [cameras.get("sacile"), cameras.get("maniago")],
        count: 2,
        id: "nearby",
        label: "Vicino",
      },
      {
        cameras: [cameras.get("tarvisio")],
        count: 1,
        id: "mountain",
        label: "Montagna",
      },
    ];

    const markup = renderToStaticMarkup(
      <LiveView compactLayout model={model} radarModel={buildRadarModel()} />,
    );

    expect(markup).toContain("mf-live-view--compact-territory");
    expect(markup.match(/class="[^"]*mf-live-territory-workspace/g)).toHaveLength(1);
    expect(markup.match(/class="mf-live-community-map /g)).toHaveLength(1);
    expect(markup).toContain('aria-label="Radar"');
    expect(markup).toContain('aria-label="Webcam sulla mappa · 2"');
    expect(markup).toContain("<span>Webcam</span>");
    expect(markup).not.toContain("<em>3</em>");
    expect(markup).not.toContain('class="mf-live-webcam-carousel"');
    expect(markup).not.toContain("mf-live-webcam-picker");
    expect(markup).not.toContain("Scegli una webcam");
    expect(markup).not.toContain("mf-bulletin-radar-card");
    expect(markup).not.toContain("mf-live-card--webcam");
  });

  it("renders one compact pilot workspace with navigation before the report action", () => {
    const markup = renderToStaticMarkup(
      <LiveView
        compactLayout
        model={buildModel()}
        officialAlert={{
          label: "Allerta arancione",
          meta: "Protezione Civile FVG",
          tone: "orange",
          validityLabel: "Valida fino alle 18:00",
        }}
        onOfficialAlertOpen={() => {}}
        onReportConfirm={() => Promise.resolve({ ok: true })}
        onReportFlag={() => Promise.resolve({ ok: true })}
        onReportLocate={() => Promise.resolve({ ok: false, reason: "permission_denied" })}
        onReportSubmit={() => Promise.resolve({ ok: true })}
        radarModel={buildRadarModel()}
        reportingEnabled
      />,
    );

    const locationIndex = markup.indexOf('class="mf-live-location-context"');
    const workspaceIndex = markup.indexOf("mf-live-territory-workspace");
    const navigationIndex = markup.indexOf('class="mf-territory-map__navigation"');
    const navigationEndIndex = markup.indexOf("</nav>", navigationIndex);
    const navigationMarkup = markup.slice(navigationIndex, navigationEndIndex);
    const reportIndex = markup.indexOf('class="mf-territory-map__report-action"');

    expect(locationIndex).toBeGreaterThanOrEqual(0);
    expect(workspaceIndex).toBeGreaterThan(locationIndex);
    expect(markup.match(/class="[^"]*mf-live-territory-workspace/g)).toHaveLength(1);
    expect(markup.match(/class="mf-live-community-map /g)).toHaveLength(1);
    expect(navigationIndex).toBeGreaterThan(workspaceIndex);
    expect(navigationMarkup.indexOf("Mappa")).toBeGreaterThanOrEqual(0);
    expect(navigationMarkup.indexOf("Segnalazioni")).toBeGreaterThan(
      navigationMarkup.indexOf("Mappa"),
    );
    expect(navigationMarkup.indexOf("Webcam")).toBeGreaterThan(
      navigationMarkup.indexOf("Segnalazioni"),
    );
    expect(reportIndex).toBeGreaterThan(navigationEndIndex);
    expect(markup).toContain("Segnala meteo");
    expect(markup).toContain('aria-haspopup="dialog"');

    expect(markup).not.toContain("mf-live-card--community");
    expect(markup).not.toContain("mf-official-alert-compact");
    expect(markup).not.toContain("mf-bulletin-radar-card");
    expect(markup).not.toContain("mf-live-card--webcam");
    expect(markup).not.toContain("mf-live-territory-sources");
  });

  it("keeps the ordinary Territorio hierarchy and expanded community map unchanged", () => {
    const markup = renderToStaticMarkup(
      <LiveView
        model={buildModel()}
        officialAlert={{
          label: "Allerta arancione",
          meta: "Protezione Civile FVG",
          tone: "orange",
          validityLabel: "Valida fino alle 18:00",
        }}
        onOfficialAlertOpen={() => {}}
        radarModel={buildRadarModel()}
      />,
    );

    const alertIndex = markup.indexOf("mf-official-alert-compact");
    const radarIndex = markup.indexOf("mf-bulletin-radar-card");
    const webcamIndex = markup.indexOf("mf-live-card--webcam");
    const communityIndex = markup.indexOf("mf-live-card--community");

    expect(alertIndex).toBeGreaterThanOrEqual(0);
    expect(radarIndex).toBeGreaterThan(alertIndex);
    expect(webcamIndex).toBeGreaterThan(radarIndex);
    expect(communityIndex).toBeGreaterThan(webcamIndex);
    expect(markup).toContain('class="mf-live-community-map"');
    expect(markup).not.toContain("mf-live-community-map-toggle");
    expect(markup).not.toContain("mf-live-territory-sources");
  });

  it("describes an empty compact community as missing reports, not proof of calm weather", () => {
    const model = buildWebcamModel([{
      area: "Sacile",
      fallbackImageUrl: "/municipalities/photos/093037-photo.webp",
      group: "plain",
      id: "sacile",
      name: "Sacile",
    }]);
    const markup = renderToStaticMarkup(
      <LiveView
        compactLayout
        model={model}
        officialAlert={{
          label: "Allerta arancione",
          meta: "Protezione Civile FVG",
          tone: "orange",
          validityLabel: "Valida fino alle 18:00",
        }}
        onOfficialAlertOpen={() => {}}
        radarModel={buildRadarModel()}
        reportingPreview
      />,
    );

    expect(markup).toContain("Pordenone");
    expect(markup).toContain("Nessuna segnalazione recente sulla mappa.");
    expect(markup).not.toContain("Nessun fenomeno grave");
    expect(markup).not.toContain("Tutto tranquillo?");
    expect(markup).toContain("Segnala meteo");
    expect(markup.match(/class="[^"]*mf-live-territory-workspace/g)).toHaveLength(1);
    expect(markup.match(/class="mf-live-community-map /g)).toHaveLength(1);
    expect(markup).toContain("mf-live-community-map-layer--inline");
    expect(markup).not.toContain("mf-live-card--community");
    expect(markup).not.toContain("mf-official-alert-compact");
    expect(markup).not.toContain("mf-bulletin-radar-card");
    expect(markup).not.toContain("mf-live-card--webcam");
    expect(markup).not.toContain("mf-live-territory-sources");
  });

  it("keeps the radar card optional while Live data is loading", () => {
    const markup = renderToStaticMarkup(<LiveView model={buildModel()} />);

    expect(markup).not.toContain("mf-bulletin-radar-card");
    expect(markup).toContain("mf-live-card--community");
    expect(markup).toContain("mf-live-card--webcam");
  });

  it("keeps the community activity list to the three most recent entries", () => {
    const model = buildModel();
    const template = model.community.items[0];
    model.community.items = [0, 1, 2, 3].map((index) => ({
      ...template,
      createdAt: Date.now() - index * 60_000,
      groupId: `group-${index}`,
      id: `group-${index}`,
      place: `Località ${index}`,
    }));
    const markup = renderToStaticMarkup(<LiveView model={model} />);

    expect(markup.match(/class="mf-live-community-item /g)).toHaveLength(3);
    expect(markup).not.toContain(model.copy.reportShowAll);
    expect(markup).not.toContain("Località 3");
  });

  it("uses each specific webcam name in the picker, including distinct Trieste views", () => {
    const model = buildWebcamModel([
      {
        area: "Trieste",
        group: "coast",
        id: "trieste-miramare",
        imageUrl: "https://images.example.test/miramare.jpg",
        name: "Trieste - Parco di Miramare",
      },
      {
        area: "Trieste",
        group: "coast",
        id: "trieste-piazza-borsa",
        imageUrl: "https://images.example.test/borsa.jpg",
        name: "Trieste - Piazza della Borsa",
      },
    ]);
    const markup = renderToStaticMarkup(<LiveView model={model} />);

    expect(markup).toContain(
      'class="mf-live-webcam-picker__option-name">Trieste - Parco di Miramare</span>',
    );
    expect(markup).toContain(
      'class="mf-live-webcam-picker__option-name">Trieste - Piazza della Borsa</span>',
    );
  });

  it("keeps an empty community compact and does not mount an unused map", () => {
    const model = buildWebcamModel([{
      area: "Sacile",
      fallbackImageUrl: "/municipalities/photos/093037-photo.webp",
      group: "plain",
      id: "sacile",
      name: "Sacile",
    }]);
    const markup = renderToStaticMarkup(
      <LiveView model={model} reportingPreview />,
    );

    expect(markup).toContain(model.copy.liveMapEmptyBody);
    expect(markup).toContain("mf-live-community-state--empty");
    expect(markup).not.toContain("mf-live-community-map");
    expect(markup.indexOf("mf-live-card--webcam")).toBeLessThan(
      markup.indexOf("mf-live-card--community"),
    );
  });

  it.each(["it", "fur"])("keeps the territorial photo alt and adds an external preview action in %s", (language) => {
    const model = buildWebcamModel([{
      area: "Piazza Italia",
      fallbackImageUrl: "/municipalities/photos/093025-photo.webp",
      group: "plain",
      id: "maniago-centro",
      lat: 46.1706,
      lon: 12.7078,
      municipality: "Maniago",
      name: "Maniago - Piazza Italia",
      provider: "Foto territoriale",
      sourcePage: "https://example.test/webcam/maniago",
    }], "fresh", language);
    const markup = renderToStaticMarkup(<LiveView model={model} />);
    const copy = model.copy;
    const externalAction = markup.match(
      /<a\b[^>]*class="mf-live-webcam-preview__external-trigger"[^>]*>[\s\S]*?<\/a>/,
    )?.[0];

    expect(markup).toContain('src="/municipalities/photos/093025-photo.webp"');
    expect(markup).toContain(`alt="${copy.webcamStaticImage}: Maniago - Piazza Italia"`);
    expect(markup).not.toContain("mf-live-webcam-preview__static-label");
    expect(markup).not.toContain(`>${copy.webcamStaticImage}<`);
    expect(markup).toContain("<strong>Maniago - Piazza Italia</strong>");
    expect(markup).not.toContain("Maniago - Piazza Italia · Maniago · Piazza Italia");
    expect(markup).toContain(`class="mf-live-webcam-preview__source-label">${copy.webcamSourceLabel}:</span>`);
    expect(markup).toContain('class="mf-live-webcam-preview__provider">Foto territoriale</span>');
    expect(externalAction).toContain(`<strong>${copy.webcamOpenExternal}</strong>`);
    expect(externalAction).toContain(
      `aria-label="${copy.webcamOpenExternalNewTab.replace("{camera}", "Maniago - Piazza Italia")}"`,
    );
    expect(externalAction).toContain('href="https://example.test/webcam/maniago"');
    expect(externalAction).toContain('target="_blank"');
    expect(externalAction).toContain('rel="noopener noreferrer"');
    expect(externalAction).toContain("lucide-external-link");
    expect(markup.match(/href="https:\/\/example\.test\/webcam\/maniago"/g)).toHaveLength(1);
    expect(markup).not.toContain("mf-live-webcam-preview__live-trigger");
    expect(markup).not.toContain("mf-live-webcam-picker__live-icon");
    expect(markup).not.toContain("lucide-play");
    expect(markup).not.toContain("<iframe");
    expect(markup).not.toContain("autoplay");
  });

  it.each(["it", "fur"])("does not create a preview action without a source URL in %s", (language) => {
    const model = buildWebcamModel([{
      fallbackImageUrl: "/municipalities/photos/093037-photo.webp",
      group: "plain",
      id: "sacile",
      name: "Sacile",
    }], "fresh", language);
    const markup = renderToStaticMarkup(<LiveView model={model} />);

    expect(markup).not.toContain("mf-live-webcam-preview__external-trigger");
    expect(markup).not.toContain("mf-live-webcam-preview__live-trigger");
    expect(markup).not.toContain(model.copy.webcamOpenExternal);
    expect(markup).not.toContain("<iframe");
  });

  it.each(["it", "fur"])("keeps a snapshot unobstructed with author and source in %s", (language) => {
    const model = buildWebcamModel([{
      id: "sacile",
      name: "Sacile",
      group: "plain",
      imageUrl: "https://sacilemeteo.altervista.org/hik/webcam_r.jpg",
      fallbackImageUrl: "/municipalities/photos/093037-photo.webp",
      mediaType: "snapshot",
      provider: "SacileMeteo",
      attribution: "© Luigi Carbonera",
      attributionUrl: "https://sacilemeteo.altervista.org/hik/webcam_hik.html",
      sourcePage: "https://sacilemeteo.altervista.org/hik/webcam_hik.html",
    }], "fresh", language);
    const markup = renderToStaticMarkup(<LiveView model={model} />);

    expect(markup).toContain('data-kind="snapshot"');
    expect(markup).toContain('data-source="live"');
    expect(markup).toContain(`alt="${model.copy.webcamSnapshotImage}: Sacile"`);
    expect(markup).toContain('referrerPolicy="no-referrer"');
    expect(markup).toContain("© Luigi Carbonera");
    expect(markup).toContain("SacileMeteo");
    expect(markup).toContain(model.copy.webcamOpenSource);
    expect(markup.match(/href="https:\/\/sacilemeteo\.altervista\.org\/hik\/webcam_hik\.html"/g)).toHaveLength(1);
    expect(markup).toContain('target="_blank"');
    expect(markup).toContain('rel="noopener noreferrer"');
    expect(markup).not.toContain("mf-live-webcam-preview__external-trigger");
    expect(markup).not.toContain("mf-live-webcam-preview__live-trigger");
    expect(markup).not.toContain("<iframe");
    expect(markup).not.toContain("<video");
    expect(markup).not.toContain("CC BY-SA");
    // No request during SSR: the visibility observer initiates the JPEG in the browser.
    expect(markup).not.toContain('src="https://sacilemeteo.altervista.org/hik/webcam_r.jpg');
  });

  it("shows an identical provider and attribution only once", () => {
    const model = buildWebcamModel([{
      id: "lignano-punta-faro",
      name: "Lignano Sabbiadoro - Punta Faro",
      group: "coast",
      imageUrl: "https://www.lignanosabbiadoro.com/images/webcam6.jpg",
      mediaType: "snapshot",
      provider: "LignanoSabbiadoro.com",
      attribution: "LignanoSabbiadoro.com",
      attributionUrl: "https://www.lignanosabbiadoro.com/webcam/webcam-spiaggia-punta-faro",
      sourcePage: "https://www.lignanosabbiadoro.com/webcam/webcam-spiaggia-punta-faro",
    }], "fresh", "it");
    const markup = renderToStaticMarkup(<LiveView model={model} />);
    const sourceAction = markup.match(
      /<a\b[^>]*aria-label="Apri la fonte di Lignano Sabbiadoro - Punta Faro in una nuova scheda"[^>]*>[\s\S]*?<\/a>/,
    )?.[0];

    expect(markup).toContain('class="mf-live-webcam-preview__provider">LignanoSabbiadoro.com</span>');
    expect(markup).not.toContain("mf-live-webcam-preview__attribution");
    expect(sourceAction).toContain('href="https://www.lignanosabbiadoro.com/webcam/webcam-spiaggia-punta-faro"');
    expect(sourceAction).toContain('class="mf-live-webcam-preview__source-action"');
    expect(sourceAction).toContain('target="_blank"');
    expect(sourceAction).toContain('rel="noopener noreferrer"');
    expect(sourceAction).not.toContain("mf-live-webcam-preview__action-label");
    expect(sourceAction).toContain("lucide-external-link");
  });

  it("keeps a distinct attribution destination without repeating its label", () => {
    const model = buildWebcamModel([{
      id: "same-credit-different-link",
      name: "Camera campione",
      group: "plain",
      imageUrl: "https://images.example.test/webcam.jpg",
      provider: "Ente ufficiale",
      attribution: "Ente ufficiale",
      attributionUrl: "https://example.test/crediti",
      sourcePage: "https://example.test/webcam",
    }], "fresh", "it");
    const markup = renderToStaticMarkup(<LiveView model={model} />);
    const attributionLink = markup.match(
      /<a\b[^>]*class="mf-live-webcam-preview__attribution"[^>]*>[\s\S]*?<\/a>/,
    )?.[0];

    expect(attributionLink).toContain('href="https://example.test/crediti"');
    expect(attributionLink).toContain('class="mf-live-webcam-preview__provider">Ente ufficiale</span>');
    expect(markup.match(/>Ente ufficiale</g)).toHaveLength(1);
  });

  it("does not misattribute a territorial fallback photo to the webcam author", () => {
    const model = buildWebcamModel([{
      id: "sacile",
      name: "Sacile",
      group: "plain",
      fallbackImageUrl: "/municipalities/photos/093037-photo.webp",
      attribution: "© Webcam author",
      attributionUrl: "https://example.test/credits",
      sourcePage: "https://example.test/webcam",
    }]);
    const markup = renderToStaticMarkup(<LiveView model={model} />);

    expect(markup).toContain('data-source="static"');
    expect(markup).not.toContain("© Webcam author");
    expect(markup).not.toContain("https://example.test/credits");
    expect(markup).toContain('href="https://example.test/webcam"');
  });

  it("renders a separate safe attribution link but rejects unsafe attribution URLs", () => {
    const record = {
      id: "sacile",
      name: "Sacile",
      group: "plain",
      imageUrl: "https://example.test/snapshot.jpg",
      mediaType: "snapshot",
      attribution: "Webcam author",
      attributionUrl: "https://example.test/credits",
      sourcePage: "https://example.test/webcam",
    };
    const markup = renderToStaticMarkup(<LiveView model={buildWebcamModel([record])} />);

    expect(markup).toContain('href="https://example.test/credits"');
    expect(markup).toContain('href="https://example.test/webcam"');
    const unsafeMarkup = renderToStaticMarkup(<LiveView model={buildWebcamModel([{
      ...record,
      attributionUrl: "javascript:alert(1)",
    }])} />);
    expect(unsafeMarkup).toContain("Webcam author");
    expect(unsafeMarkup).not.toContain("javascript:");
  });

  it.each(["it", "fur"])("does not describe a failed territorial photo as an unavailable stream in %s", (language) => {
    const camera = { fallbackImageUrl: "/municipalities/photos/093037-photo.webp" };
    const copy = buildWebcamModel([], "fresh", language).copy;
    const media = failWebcamMedia(camera, createWebcamMediaState(camera));
    const markup = renderToStaticMarkup(<WebcamFailureCopy copy={copy} media={media} autoRetryScheduled />);

    expect(markup).toContain(`<strong>${copy.webcamImageUnavailable}</strong>`);
    expect(markup).toContain(copy.webcamAutomaticRetry);
    expect(markup).not.toContain(copy.webcamTemporaryUnavailable);
    expect(markup).not.toContain(copy.webcamStaticFallback);
  });

  it.each(["it", "fur"])("keeps the live failure message for a real webcam image failure in %s", (language) => {
    const camera = { imageUrl: "https://images.example.test/sacile.jpg" };
    const copy = buildWebcamModel([], "fresh", language).copy;
    const media = failWebcamMedia(camera, createWebcamMediaState(camera));
    const markup = renderToStaticMarkup(<WebcamFailureCopy copy={copy} media={media} />);

    expect(markup).toContain(`<strong>${copy.webcamTemporaryUnavailable}</strong>`);
    expect(markup).toContain(copy.webcamTryAnother);

    const cameraWithFallback = { ...camera, fallbackImageUrl: "/municipalities/photos/093037-photo.webp" };
    const failedLive = failWebcamMedia(cameraWithFallback, createWebcamMediaState(cameraWithFallback));
    const failedFallback = failWebcamMedia(cameraWithFallback, failedLive);
    const failedFallbackMarkup = renderToStaticMarkup(<WebcamFailureCopy copy={copy} media={failedFallback} />);

    expect(failedFallbackMarkup).toContain(`<strong>${copy.webcamTemporaryUnavailable}</strong>`);
  });

  it.each(["it", "fur"])("keeps the external caption link and next action when no preview image is available in %s", (language) => {
    const model = buildWebcamModel([
      { id: "sacile", name: "Sacile", group: "plain", fallbackImageUrl: "/sacile.webp", sourcePage: "https://example.test/webcam/sacile" },
      { id: "maniago", name: "Maniago", group: "plain", fallbackImageUrl: "/maniago.webp" },
    ], "fresh", language);
    model.webcams.groups = model.webcams.groups.filter((group) => group.id === "plain");
    model.webcams.groups.forEach((group) => {
      group.cameras.forEach((camera) => {
        camera.imageUrl = "";
        camera.fallbackImageUrl = "";
      });
    });
    const markup = renderToStaticMarkup(<LiveView model={model} />);

    expect(markup).toContain(`<strong>${model.copy.webcamImageUnavailable}</strong>`);
    expect(markup).toContain('href="https://example.test/webcam/sacile"');
    expect(markup).toContain(model.copy.webcamNext);
    expect(markup).not.toContain(model.copy.webcamTemporaryUnavailable);
    expect(markup).not.toContain("<iframe");
  });

  it("offers an in-app player only for a reviewed Panomax camera", () => {
    const model = buildWebcamModel([{
      area: "Centro",
      fallbackImageUrl: "/municipalities/photos/030099-photo.webp",
      group: "plain",
      id: "san-daniele-centro",
      mediaType: "iframe",
      municipality: "San Daniele del Friuli",
      name: "San Daniele del Friuli - Centro",
      playerUrl: "https://sandanieledelfriuli.panomax.com/",
      provider: "Panomax / PromoTurismoFVG",
      sourcePage: "https://sandanieledelfriuli.panomax.com/",
    }]);
    const markup = renderToStaticMarkup(<LiveView model={model} />);

    expect(markup).toContain('class="mf-live-webcam-preview__live-trigger"');
    expect(markup).toContain(
      'aria-label="Apri la webcam live di San Daniele del Friuli - Centro"',
    );
    expect(markup).toContain("Apri la webcam live");
    expect(markup).toContain('class="mf-live-webcam-picker__live-icon"');
    expect(markup).toContain('aria-label="Webcam live"');
    expect(markup).not.toContain("mf-live-webcam-preview__external-trigger");
    expect(markup).not.toContain("<iframe");
  });

  it("does not expose an unreviewed iframe host", () => {
    const model = buildWebcamModel([{
      fallbackImageUrl: "/municipalities/photos/093037-photo.webp",
      group: "plain",
      id: "sacile",
      mediaType: "iframe",
      name: "Sacile",
      playerUrl: "https://video.example.test/embed/sacile",
    }]);
    const markup = renderToStaticMarkup(<LiveView model={model} />);

    expect(markup).not.toContain("mf-live-webcam-preview__live-trigger");
    expect(markup).not.toContain("mf-live-webcam-picker__live-icon");
    expect(markup).not.toContain("video.example.test");
  });

  it("does not repeat the webcam name as its location", () => {
    const model = buildWebcamModel([{
      area: "Sacile",
      fallbackImageUrl: "/municipalities/photos/093037-photo.webp",
      group: "plain",
      id: "sacile-centro",
      lat: 45.9541,
      lon: 12.5027,
      municipality: "Sacile",
      name: "Sacile",
      provider: "Protezione Civile FVG",
      sourcePage: "https://example.test/webcam/sacile",
    }]);
    const markup = renderToStaticMarkup(<LiveView model={model} />);

    expect(markup).not.toContain("Sacile · Sacile");
    expect(markup).toContain('class="mf-live-webcam-preview__provider">Protezione Civile FVG</span>');
  });

  it("reserves the webcam viewer during the first catalog load", () => {
    const markup = renderToStaticMarkup(
      <LiveView model={buildWebcamModel(null, "loading")} />,
    );

    expect(markup).toContain("mf-live-webcam-skeleton");
    expect(markup).toContain('aria-label="Caricamento webcam"');
    expect(markup).not.toContain("Webcam non disponibili");
  });

  it("announces an unavailable catalog and relies on automatic recovery", () => {
    const markup = renderToStaticMarkup(
      <LiveView model={buildWebcamModel(null, "failed")} />,
    );

    expect(markup).toContain('class="mf-live-empty" role="status"');
    expect(markup).toContain(
      "Webcam momentaneamente non disponibili. Riproveremo automaticamente.",
    );
    expect(markup).not.toContain(">Riprova<");
  });

  it("offers a light next-camera action without a manual retry", () => {
    const copy = buildModel().copy;
    const markup = renderToStaticMarkup(
      <WebcamFailureActions copy={copy} onNext={() => {}} />,
    );

    expect(markup).not.toContain("Riprova");
    expect(markup).toContain(">Guarda la prossima<");
    expect(markup).toContain("lucide-arrow-right");
  });

  it("renders a distinct accessible moderation dialog with three fixed reasons", () => {
    const model = buildModel();
    const markup = renderToStaticMarkup(
      <CommunityModerationDialog
        copy={model.copy}
        onClose={() => {}}
        onFlag={() => Promise.resolve({ ok: true })}
        onHideSources={() => {}}
        phenomenon={{
          groupId: "group-rain:pordenone:1",
          sourceKeys: ["opaque-source-a", "opaque-source-b"],
        }}
      />,
    );

    expect(markup).toContain('role="dialog"');
    expect(markup).toContain(model.copy.reportFlagTitle);
    expect(markup).toContain(model.copy.reportFlagReasons.inaccurate);
    expect(markup).toContain(model.copy.reportFlagReasons.duplicate);
    expect(markup).toContain(model.copy.reportFlagReasons.misuse);
    expect(markup).toContain("Fonti anonime · 2");
    expect(markup).toContain("mf-live-moderation-dialog__hide-source");
    expect(markup).toContain(model.copy.reportHideSources);
    expect(markup).not.toContain("opaque-source-a");
    expect(markup).not.toContain(model.copy.confirmNo);

    const singleSourceMarkup = renderToStaticMarkup(
      <CommunityModerationDialog
        copy={model.copy}
        onClose={() => {}}
        onFlag={() => Promise.resolve({ ok: true })}
        onHideSources={() => {}}
        phenomenon={{
          groupId: "group-rain:pordenone:1",
          sourceKeys: ["opaque-source-a"],
        }}
      />,
    );
    expect(singleSourceMarkup).toContain(model.copy.reportHideSource);
  });

  it("keeps the community feed readable when reporting is not configured", () => {
    const markup = renderToStaticMarkup(
      <LiveView
        model={buildModel()}
        onReportConfirm={() => Promise.resolve({ ok: true })}
        onReportLocate={() => Promise.resolve({ ok: false, reason: "permission_denied" })}
        onReportSubmit={() => Promise.resolve({ ok: true })}
      />,
    );

    expect(markup).toContain("Mappa sociale delle segnalazioni");
    expect(markup).toContain('aria-label="Pioggia · Pordenone');
    expect(markup).toContain("L’invio delle segnalazioni non è configurato per questa versione.");
    expect(markup).not.toContain("mf-live-report-open");
  });

  it("explains a regional rollout gate in the compact territory dock", () => {
    const message = "Le segnalazioni partecipative non sono ancora attive in questa regione.";
    const markup = renderToStaticMarkup(
      <LiveView
        compactLayout
        model={buildModel()}
        onReportSubmit={() => Promise.resolve({ ok: true })}
        reportingEnabled={false}
        reportingUnavailableText={message}
      />,
    );

    expect(markup).toContain(message);
    expect(markup).toContain("mf-territory-map__report-unavailable");
    expect(markup).toContain('class="mf-territory-map__report-action" disabled=""');
  });

  it("shows at most three immutable community identities in feed cards", () => {
    const model = buildModel();
    const identities = ["acuile", "ors", "claf", "lof"].map((subjectId, index) => ({
      identity: buildPublicCommunityIdentitySnapshot(buildCommunityIdentity({
        placeName: "Pordenone",
        revision: index,
        subjectId,
      })),
      sourceKey: `opaque-source-${index}`,
    }));
    model.community = {
      ...model.community,
      items: model.community.items.map((item, index) => index === 0 ? {
        ...item,
        identities,
        identity: identities[0].identity,
        sourceKeys: identities.map(({ sourceKey }) => sourceKey),
      } : item),
    };

    const markup = renderToStaticMarkup(<LiveView model={model} />);

    expect(markup).toContain('class="mf-community-avatar');
    expect(markup).toContain('data-subject="acuile"');
    expect(markup).toContain(identities[0].identity.alias);
    expect(markup).toContain(identities[1].identity.alias);
    expect(markup).toContain(identities[2].identity.alias);
    expect(markup).not.toContain(identities[3].identity.alias);
    expect(markup).toContain('class="mf-live-community-identity__more"> +1</span>');
    expect(markup).not.toContain("opaque-source-");
  });

  it("derives an avatar identity for legacy feed sources without exposing their keys", () => {
    const model = buildModel();
    const sourceKey = "legacy-private-source";
    const expected = getCommunityIdentityPreview({
      placeName: "Pordenone",
      sourceKeys: [sourceKey],
    }).identities[0];
    model.community = {
      ...model.community,
      items: model.community.items.map((item, index) => index === 0 ? {
        ...item,
        identities: [],
        identity: null,
        sourceKeys: [sourceKey],
      } : item),
    };

    const markup = renderToStaticMarkup(<LiveView model={model} />);

    expect(markup).toContain(expected.alias);
    expect(markup).toContain(`data-subject="${expected.subjectId}"`);
    expect(markup).not.toContain(sourceKey);
  });

  it("does not present a failed community load as a true empty state", () => {
    const model = buildModel();
    model.community = {
      ...model.community,
      items: [],
      markers: [],
      status: { id: "error", label: "Fonte non raggiungibile", tone: "offline" },
    };
    const markup = renderToStaticMarkup(<LiveView model={model} />);

    expect(markup).not.toContain(model.copy.communityErrorTitle);
    expect(markup).toContain(model.copy.communityErrorBody);
    expect(markup).not.toContain(model.copy.liveMapEmptyTitle);
  });
});
