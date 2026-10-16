import { describe, expect, it } from "vitest";

import {
  getOstermannArchiveIssues,
  getOstermannArchiveSummary,
  getOstermannCuratedLinkRecords,
  getOstermannCuratedRecords,
  getOstermannDiscoverQueue,
  getOstermannExtractRecords,
  getOstermannSourceCatalogRecords,
} from "./ostermannArchive";

describe("ostermann archive", () => {
  it("keeps the new Ostermann work as editorial backlog, not UI content", () => {
    const summary = getOstermannArchiveSummary();

    expect(summary.catalogSourcePages).toBe(63);
    expect(summary.highPriorityPages).toBe(63);
    expect(summary.curatedRecoveredRecords).toBe(63);
    expect(summary.curatedRecoveredPages).toBe(58);
    expect(summary.curatedFurApprovedRecords).toBe(63);
    expect(summary.curatedFurShortReadyRecords).toBe(0);
    expect(summary.curatedReadyItRecords).toBe(62);
    expect(summary.recoveredLinkedCatalogRecords).toBe(18);
    expect(summary.curatedPagesMissingFromCatalog).toBe(0);
    expect(summary.curatedPagesMissingFromGranular).toBe(0);
    expect(summary.curatedRecoveredExtracts).toBe(18);
    expect(summary.curatedRecoveredExtractsWithFurReviewRequired).toBe(0);
    expect(summary.curatedLinkRecords).toBe(45);
    expect(summary.curatedLinkedExtracts).toBe(45);
    expect(summary.curatedLinkedRecordRefs).toBe(50);
    expect(summary.editoriallyClosedExtracts).toBe(1);
    expect(summary.unresolvedEditorialExtracts).toBe(0);
    expect(summary.granularExtracts).toBe(64);
    expect(summary.extractedSourcePages).toBe(62);
    expect(summary.discoverPrimaryExtracts).toBe(64);
    expect(summary.almanacBridgeExtracts).toBe(43);
    expect(summary.archiveContextExtracts).toBe(16);
    expect(summary.cleanPageCheckedExtracts).toBe(8);
    expect(summary.inconclusiveSourceChecks).toBe(0);
    expect(summary.remainingNeedsSourceCheck).toBe(0);
    expect(summary.pendingFurReviewExtracts).toBe(45);
    expect(summary.itDraftTranslations).toBe(45);
    expect(summary.readyForUiExtracts).toBe(0);
  });

  it("keeps source catalog and extract records internally consistent", () => {
    const issues = getOstermannArchiveIssues();

    expect(issues.duplicateCatalogPages).toEqual([]);
    expect(issues.duplicateExtractIds).toEqual([]);
    expect(issues.duplicateCuratedLinkExtractIds).toEqual([]);
    expect(issues.unknownSourcePageReferences).toEqual([]);
    expect(issues.missingSourcePath).toEqual([]);
    expect(issues.missingItDraft).toEqual([]);
    expect(issues.unresolvedSourceChecks).toEqual([]);
    expect(issues.recoveredPagesMissingFromCatalog).toEqual([]);
    expect(issues.catalogExtractIdsMissing).toEqual([]);
    expect(issues.recoveredExtractsMissingCuratedRecord).toEqual([]);
    expect(issues.curatedLinksMissingExtract).toEqual([]);
    expect(issues.curatedLinksMissingCuratedRecord).toEqual([]);
    expect(issues.readyWithoutFurReview).toEqual([]);
  });

  it("exposes catalog and extracts without coupling them to presentation components", () => {
    const catalogRecords = getOstermannSourceCatalogRecords();
    const extractRecords = getOstermannExtractRecords();
    const curatedRecords = getOstermannCuratedRecords();
    const curatedLinkRecords = getOstermannCuratedLinkRecords();

    expect(catalogRecords.every((record) => record.recommendedUse?.includes("discover") || record.recommendedUse?.includes("proverb_candidates"))).toBe(true);
    expect(extractRecords.every((record) => record.uiReadiness === "not_ready")).toBe(true);
    expect(curatedRecords.some((record) => record.languageStatus?.fur === "approved")).toBe(true);
    expect(extractRecords.some((record) => record.editorialStatus === "archive_context")).toBe(true);
    expect(curatedLinkRecords).toHaveLength(45);
    expect(curatedLinkRecords.every((record) => (
      Boolean(record.extractId) &&
      Array.isArray(record.curatedRecordIds) &&
      record.curatedRecordIds.length > 0
    ))).toBe(true);
  });

  it("keeps archive stories human instead of forcing them into daily cards", () => {
    const curatedRecords = getOstermannCuratedRecords();
    const sanBarnaba = curatedRecords.find((record) => record.id === "ost-0051-san-barnaba-vite");
    const santErmacora = curatedRecords.find((record) => record.id === "ost-0052-sant-ermacora-grandini-bufere");
    const animalSigns = curatedRecords.find((record) => record.id === "ost-0021-segni-animali-vento");
    const mountainCap = curatedRecords.find((record) => record.id === "ost-0024-monti-col-cappello");
    const hoursOfDay = curatedRecords.find((record) => record.id === "ost-0060-ore-del-giorno");
    const saintDays = curatedRecords.find((record) => record.id === "ost-0061-giornate-dei-santi");
    const fogLanguage = curatedRecords.find((record) => record.id === "ost-0062-nebbia-linguaggio-tempo");
    const herbNames = curatedRecords.find((record) => record.id === "ost-0063-erbe-nomi-buona-stagione");

    expect(sanBarnaba).toMatchObject({
      candidateId: "ost-discover-608-san-barnaba-viti",
      section: "archivio_tradizioni",
      editorialStatus: "ready_it",
      languageStatus: { fur: "approved" },
      sourceStatus: "controllato",
    });
    expect(sanBarnaba.title.it).toBe("Ostermann raccontava San Barnaba");
    expect(sanBarnaba.text.it).toContain("Ostermann raccontava");
    expect(sanBarnaba.text.it).toContain("l'uva era a rischio");

    expect(santErmacora).toMatchObject({
      candidateId: "ost-discover-609-sant-ermacora-bufere",
      section: "archivio_tradizioni",
      editorialStatus: "ready_it",
      languageStatus: { fur: "approved" },
      sourceStatus: "controllato",
    });
    expect(santErmacora.title.it).toBe("Sant'Ermacora e il cielo di luglio");
    expect(santErmacora.text.it).toContain("Ostermann raccontava");
    expect(santErmacora.text.it).not.toContain("settimana delle disgrazie");

    expect(animalSigns).toMatchObject({
      section: "archivio_tradizioni",
      editorialStatus: "ready_it",
      languageStatus: { fur: "approved" },
      sourceStatus: "controllato",
    });
    expect(animalSigns.title.it).toBe("Animali, vento e cielo");
    expect(animalSigns.text.it).toContain("Ostermann raccoglieva");
    expect(animalSigns.text.it).toContain("Non erano previsioni");

    expect(mountainCap).toMatchObject({
      section: "archivio_tradizioni",
      editorialStatus: "ready_it",
      languageStatus: { fur: "approved" },
      sourceStatus: "controllato",
    });
    expect(mountainCap.title.it).toBe("Quando i monti mettono il cappello");
    expect(mountainCap.text.it).toContain("Ostermann raccoglieva");
    expect(mountainCap.text.it).toContain("Non era una previsione");

    expect(hoursOfDay).toMatchObject({
      candidateId: "ost-extract-087-feste-ore-giorno",
      section: "archivio_tradizioni",
      editorialStatus: "ready_it",
      languageStatus: { fur: "approved" },
      sourceStatus: "controllato",
    });
    expect(hoursOfDay.title.it).toBe("Le ore del giorno");
    expect(hoursOfDay.text.it).toContain("Ostermann annotava");
    expect(hoursOfDay.appShort.it).toContain("parole della tradizione");

    expect(saintDays).toMatchObject({
      candidateId: "ost-extract-057-giornate-santi",
      section: "archivio_tradizioni",
      editorialStatus: "ready_it",
      languageStatus: { fur: "approved" },
      sourceStatus: "controllato",
    });
    expect(saintDays.title.it).toBe("Le giornate dei santi");
    expect(saintDays.text.it).toContain("San Tomas");
    expect(saintDays.text.it).toContain("Natale ed Epifania");

    expect(fogLanguage).toMatchObject({
      candidateId: "ost-discover-099-nebbia-pronostici",
      section: "archivio_tradizioni",
      editorialStatus: "ready_it",
      languageStatus: { fur: "approved" },
      sourceStatus: "controllato",
    });
    expect(fogLanguage.text.it).not.toContain("malattie");

    expect(herbNames).toMatchObject({
      candidateId: "ost-discover-234-erbe-buona-stagione",
      section: "archivio_tradizioni",
      editorialStatus: "ready_it",
      languageStatus: { fur: "approved" },
      sourceStatus: "controllato",
    });
    expect(herbNames.text.it).not.toContain("medic");
  });

  it("keeps new FUR drafts visible to editors but blocked from UI approval", () => {
    const extractRecords = getOstermannExtractRecords();
    const fogArchive = extractRecords.find((record) => record.id === "ost-extract-099-nebbia-pronostici");
    const herbsArchive = extractRecords.find((record) => record.id === "ost-extract-234-erbe-buona-stagione");

    expect(fogArchive).toMatchObject({
      title: { fur: "pending_review" },
      review: { furReviewRequired: true },
      uiReadiness: "not_ready",
    });
    expect(fogArchive.translation.furDraft).toContain("la fumate");
    expect(fogArchive.translation.furDraft).toContain("No je une prevision");

    expect(herbsArchive).toMatchObject({
      title: { fur: "pending_review" },
      review: { furReviewRequired: true },
      uiReadiness: "not_ready",
    });
    expect(herbsArchive.translation.furDraft).toContain("Il lessic des jerbis");
    expect(herbsArchive.translation.furDraft).toContain("no come indicazions medichis");
  });

  it("splits Ostermann extracts into explicit editorial queues for Scopri and Almanacco", () => {
    const queue = getOstermannDiscoverQueue();

    expect(queue.total).toBe(64);
    expect(queue.counts).toEqual({
      already_curated_link: 63,
      editorially_closed: 1,
      daily_or_saying_candidate: 0,
      seasonal_context_candidate: 0,
      discover_topic_candidate: 0,
      archive_story_candidate: 0,
    });

    expect(queue.buckets.already_curated_link.map((record) => record.id)).toContain("ost-extract-067-epifania-fuochi");
    expect(queue.buckets.already_curated_link.find((record) => record.id === "ost-extract-608-san-giorgio-barnaba")?.curatedRecordIds).toEqual([
      "ost-0050-san-giorgio-primavera",
      "ost-0051-san-barnaba-vite",
    ]);
    expect(queue.buckets.already_curated_link.find((record) => record.id === "ost-extract-609-ermacora-bufere")?.curatedRecordIds).toEqual([
      "ost-0052-sant-ermacora-grandini-bufere",
    ]);
    expect(queue.buckets.already_curated_link.find((record) => record.id === "ost-extract-087-feste-ore-giorno")?.curatedRecordIds).toEqual([
      "ost-0060-ore-del-giorno",
    ]);
    expect(queue.buckets.already_curated_link.find((record) => record.id === "ost-extract-057-giornate-santi")?.curatedRecordIds).toEqual([
      "ost-0061-giornate-dei-santi",
    ]);
    expect(queue.buckets.already_curated_link.find((record) => record.id === "ost-extract-146-aloni-lunari")?.curatedRecordIds).toEqual([
      "ost-0059-pareli-aloni-lunari",
    ]);
    expect(queue.buckets.already_curated_link.find((record) => record.id === "ost-extract-107-pioggia-sole-streghe")?.curatedRecordIds).toEqual([
      "ost-0026-pioggia-grandine-streghe",
    ]);
    expect(queue.buckets.already_curated_link.find((record) => record.id === "ost-extract-538-streghe-meteo-archive")?.curatedRecordIds).toEqual([
      "ost-0026-pioggia-grandine-streghe",
    ]);
    expect(queue.buckets.daily_or_saying_candidate).toEqual([]);
    expect(queue.buckets.editorially_closed.map((record) => record.id)).toEqual([
      "ost-extract-058-inverno-estate-stagioni",
    ]);
    expect(queue.buckets.seasonal_context_candidate).toEqual([]);
    expect(queue.buckets.discover_topic_candidate).toEqual([]);
    expect(queue.buckets.archive_story_candidate).toEqual([]);
    expect(
      Object.values(queue.buckets).flat().every((record) => record.uiReadiness === "not_ready"),
    ).toBe(true);
  });

  it("reports archive problems if future records skip the review workflow", () => {
    const issues = getOstermannArchiveIssues({
      catalog: {
        records: [
          { pdfPage: 100 },
          { pdfPage: 100 },
        ],
      },
      extracts: {
        records: [
          {
            id: "duplicate",
            sourcePage: 999,
            uiReadiness: "ready_for_ui",
            translation: {},
            source: {},
            review: { furReviewRequired: true },
          },
          {
            id: "duplicate",
            sourcePage: 100,
            uiReadiness: "not_ready",
            translation: { itDraft: "Bozza" },
            source: { sourcePath: "normalized-pages/page-100.txt" },
          },
        ],
      },
      curatedLinks: {
        records: [
          {
            extractId: "missing-extract",
            curatedRecordIds: ["missing-curated"],
          },
          {
            extractId: "missing-extract",
            curatedRecordIds: ["ost-0001-nubi-pioggia"],
          },
        ],
      },
    });

    expect(issues.duplicateCatalogPages).toEqual([100]);
    expect(issues.duplicateExtractIds).toEqual(["duplicate"]);
    expect(issues.duplicateCuratedLinkExtractIds).toEqual(["missing-extract"]);
    expect(issues.unknownSourcePageReferences).toEqual([{ id: "duplicate", sourcePage: 999 }]);
    expect(issues.missingSourcePath).toEqual(["duplicate", "duplicate"]);
    expect(issues.missingItDraft).toEqual(["duplicate"]);
    expect(issues.unresolvedSourceChecks).toEqual([]);
    expect(issues.curatedLinksMissingExtract).toEqual(["missing-extract", "missing-extract"]);
    expect(issues.curatedLinksMissingCuratedRecord).toEqual([
      { extractId: "missing-extract", curatedRecordId: "missing-curated" },
    ]);
    expect(issues.readyWithoutFurReview).toEqual(["duplicate"]);
  });

  it("reports unresolved source checks when an extract is still blocked without an inconclusive audit", () => {
    const issues = getOstermannArchiveIssues({
      catalog: {
        records: [{ pdfPage: 44 }],
      },
      extracts: {
        records: [
          {
            id: "blocked",
            sourcePage: 44,
            editorialStatus: "needs_source_check",
            uiReadiness: "not_ready",
            translation: { itDraft: "Bozza" },
            source: {
              sourcePath: "normalized-pages/page-044.txt",
              verifiedAgainst: "pages/page-044.txt",
              auditStatus: "needs_clean_page_check",
            },
          },
        ],
      },
      curatedLinks: {
        records: [],
      },
    });

    expect(issues.unresolvedSourceChecks).toEqual(["blocked"]);
  });
});
