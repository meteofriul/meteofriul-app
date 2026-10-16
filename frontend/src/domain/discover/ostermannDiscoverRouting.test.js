import { describe, expect, it } from "vitest";

import {
  getOstermannDiscoverRouting,
  getOstermannDiscoverRoutingSummary,
} from "./ostermannDiscoverRouting";

describe("Ostermann discover backlog routing", () => {
  it("classifies the current backlog without publishing records", () => {
    const summary = getOstermannDiscoverRoutingSummary();

    expect(summary.totalRecords).toBe(29);
    expect(summary.publishedInScopriRecords).toBe(8);
    expect(summary.coveredByCuratedArchiveRecords).toBe(18);
    expect(summary.coveredByAlmanacProverbRecords).toBe(3);
    expect(summary.pendingCopyRecords).toBe(0);
    expect(summary.counts).toEqual({
      almanac_proverb_source_candidate: 3,
      discover_archive_candidate: 20,
      local_memory_candidate: 2,
      traditional_saying_candidate: 4,
    });
    expect(summary.pendingCounts).toEqual({});
    expect(summary.unclassifiedRecords).toEqual([]);
  });

  it("resolves saint-territory exact-date records as archive stories when daily memory is unclear", () => {
    const routes = getOstermannDiscoverRouting();

    expect(routes.find((record) => record.id === "ost-discover-608-san-barnaba-viti")).toMatchObject({
      route: { target: "local_memory_candidate" },
      publicationStatus: "published_in_scopri",
      dateAnchors: ["06-11"],
    });
    expect(routes.find((record) => record.id === "ost-discover-609-sant-ermacora-bufere")).toMatchObject({
      route: { target: "local_memory_candidate" },
      publicationStatus: "published_in_scopri",
      dateAnchors: ["07-12"],
    });
  });

  it("routes short isolated weather sayings to Si diceva che", () => {
    const routes = getOstermannDiscoverRouting();
    const sayingIds = routes
      .filter((record) => record.route.target === "traditional_saying_candidate")
      .map((record) => record.id)
      .sort();

    expect(sayingIds).toEqual([
      "ost-discover-130-neve-pane-pioggia-fame",
      "ost-discover-140-arcobaleno-annata",
      "ost-discover-141-arcobaleno-tempo",
      "ost-discover-193-pasqua-fieno",
    ]);
    expect(routes.find((record) => record.id === "ost-discover-130-neve-pane-pioggia-fame")).toMatchObject({
      publicationStatus: "published_in_scopri",
    });
    expect(routes.find((record) => record.id === "ost-discover-140-arcobaleno-annata")).toMatchObject({
      publicationStatus: "published_in_scopri",
    });
    expect(routes.find((record) => record.id === "ost-discover-141-arcobaleno-tempo")).toMatchObject({
      publicationStatus: "published_in_scopri",
    });
    expect(routes.find((record) => record.id === "ost-discover-193-pasqua-fieno")).toMatchObject({
      publicationStatus: "published_in_scopri",
    });
  });

  it("keeps broad or multi-detto pages as Scopri archive material", () => {
    const routes = getOstermannDiscoverRouting();

    expect(routes.find((record) => record.id === "ost-discover-049-luna-pioggia")).toMatchObject({
      route: { target: "discover_archive_candidate" },
      publicationStatus: "covered_by_curated_archive",
      curatedRecordIds: ["ost-0014-proverbi-lunari-pioggia"],
      sourceLineCount: 3,
    });
    expect(routes.find((record) => record.id === "ost-discover-094-lessico-venti")).toMatchObject({
      route: { target: "discover_archive_candidate" },
      publicationStatus: "covered_by_curated_archive",
      curatedRecordIds: ["ost-0005-lessico-venti"],
      type: "lessico_popolare",
    });
  });

  it("closes the last broad pages as curated Scopri archive stories", () => {
    const routes = getOstermannDiscoverRouting();

    expect(routes.find((record) => record.id === "ost-discover-099-nebbia-pronostici")).toMatchObject({
      publicationStatus: "published_in_scopri",
      curatedRecordIds: ["ost-0062-nebbia-linguaggio-tempo"],
    });
    expect(routes.find((record) => record.id === "ost-discover-234-erbe-buona-stagione")).toMatchObject({
      publicationStatus: "published_in_scopri",
      curatedRecordIds: ["ost-0063-erbe-nomi-buona-stagione"],
    });
  });

  it("tracks proverb bundle pages as already covered by Almanacco extraction", () => {
    const coveredIds = getOstermannDiscoverRouting()
      .filter((record) => (
        record.publicationStatus === "covered_by_almanac_proverbs" &&
        record.route.target === "almanac_proverb_source_candidate"
      ))
      .map((record) => ({
        id: record.id,
        almanacProverbCount: record.almanacProverbIds.length,
      }))
      .sort((first, second) => first.id.localeCompare(second.id));

    expect(coveredIds).toEqual([
      {
        id: "ost-discover-103-proverbi-generali-tempo",
        almanacProverbCount: 8,
      },
      {
        id: "ost-discover-105-proverbi-meteo-brevi",
        almanacProverbCount: 4,
      },
      {
        id: "ost-discover-190-marzo-aprile-annata",
        almanacProverbCount: 7,
      },
    ]);
  });

  it("does not treat an explicitly blocked curated record as published", () => {
    const backlog = {
      records: [{
        id: "candidate-blocked",
        type: "vita_popolare",
        title: { it: "Bozza" },
        sourceLines: ["riga uno", "riga due", "riga tre"],
      }],
    };
    const blockedPublishedSource = [{
      id: "curated-blocked",
      candidateId: "candidate-blocked",
      editorialStatus: "ready_it",
      languageStatus: { fur: "approved" },
      readyForUi: false,
    }];

    const [route] = getOstermannDiscoverRouting(backlog, [blockedPublishedSource]);

    expect(route.publicationStatus).toBe("pending_copy");
  });
});
