import { createHash } from "node:crypto";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import archive from "../../data/discover/localMemory.json";
import research from "../../data/discover/secondaryMemoryResearchWave01.json";
import institutionalArchive from "../../data/discover/institutionalArchive.json";
import archiveWave01 from "../../data/discover/archiveResearchWave01.json";
import archiveWave02 from "../../data/discover/archiveResearchWave02.json";
import municipalityProfiles from "../../data/discover/municipalityProfiles.json";
import ostermann from "../../data/ostermannCulturalDiscover.json";
import { DiscoverCard } from "../../features/discover/DiscoverView";
import { buildDiscoverViewModel } from "../../features/discover/discoverViewModel";
import { getLocalMemoryForDate, getLocalMemorySecondaryForDate } from "./localMemory";

const MINERVA_ID = "memory-secondary-0101-societa-minerva-1810";
const ICTP_ID = "memory-secondary-1005-ictp-inaugurazione-1964";
const PROMOTED_IDS = [MINERVA_ID, ICTP_ID];
const BASELINE_RECORDS = 579;
const BASELINE_DIGEST = "9aeff48310ed6744443568a1944821588000e4ec39e9d6870a2a27bf9e720dcd";
const PENDING_DIGEST = "56d96cbff0abf02c633d3a8f6610005477c01d4457b5efbd57c073e8f2cca125";
const baseline = { ...archive, records: archive.records.slice(0, BASELINE_RECORDS) };
const records = PROMOTED_IDS.map((id) => archive.records.find((record) => record.id === id));
const trieste = { city: "Trieste", province: "TS" };

function digest(value) {
  return createHash("sha256").update(JSON.stringify(value)).digest("hex");
}

function secondaryCards(date, language, location = trieste, source = archive) {
  return getLocalMemorySecondaryForDate({ date, language, location, source });
}

describe("secondary memory research wave 01", () => {
  it("appends only the two reviewed records and preserves all 579 earlier records", () => {
    expect(archive.records.slice(BASELINE_RECORDS, BASELINE_RECORDS + 2).map((record) => record.id))
      .toEqual(PROMOTED_IDS);
    expect(digest(baseline.records)).toBe(BASELINE_DIGEST);
    expect(new Set(archive.records.map((record) => record.id)).size).toBe(archive.records.length);
    expect(research.baseline.records).toBe(BASELINE_RECORDS);
    expect(research.baseline.recordsSha256).toBe(BASELINE_DIGEST);
  });

  it("keeps the 14 pending drafts complete, excluded and outside the assisted exception", () => {
    const pending = archive.records.filter((record) => record.readyForUi !== true);
    expect(pending).toHaveLength(14);
    expect(digest(pending)).toBe(PENDING_DIGEST);
    expect(research.baseline.pendingRecordsSha256).toBe(PENDING_DIGEST);
    const exception = archive.assistedEditorialReviewExceptions.find((review) => (
      review.recordIds.includes(MINERVA_ID)
    ));
    expect(exception.recordIds).toEqual(PROMOTED_IDS);
    expect(pending.some((record) => exception.recordIds.includes(record.id))).toBe(false);
  });

  it("documents a scoped assisted decision without claiming independent human review", () => {
    expect(archive.rules.join(" ")).toContain("assistedEditorialReviewExceptions");
    expect(archive.rules.join(" ")).toContain("14 bozze precedenti");
    const exception = archive.assistedEditorialReviewExceptions.find((review) => (
      review.recordIds.includes(MINERVA_ID)
    ));
    const decision = {
      approvalBasis: "user_delegated_assisted_editorial_review",
      reviewer: "assistant",
      independentHumanReview: false,
    };
    expect(exception).toMatchObject(decision);
    expect(research.editorialDecision).toMatchObject({ ...decision, recordIds: PROMOTED_IDS });
    records.forEach((record) => {
      expect(record.editorialReview).toMatchObject(decision);
      expect(record.editorialReview.researchManifest).toBe(exception.researchManifest);
      expect(record.editorialReview.note).toContain("non certificazione ARLeF");
    });
  });

  it("retains a compact hidden manifest with exact dates and directly read primary HTML", () => {
    expect(research).toMatchObject({
      schemaVersion: 1,
      readyForUi: false,
      runtimeCatalog: "frontend/src/data/discover/localMemory.json",
    });
    expect(research.records.map((candidate) => candidate.promotedRecordId)).toEqual(PROMOTED_IDS);
    expect(research.records.map((candidate) => candidate.eventDate)).toEqual(["1810-01-01", "1964-10-05"]);
    research.records.forEach((candidate) => {
      const record = records.find((item) => item.id === candidate.promotedRecordId);
      expect(candidate).toMatchObject({
        rubric: "memorie_secondarie", reviewStatus: "promoted", readyForUi: false,
        geographicScope: ["trieste", "ts"],
      });
      expect(candidate).not.toHaveProperty("draftCopy");
      expect(candidate).not.toHaveProperty("summary");
      expect(candidate.dateAnchors).toEqual([candidate.eventDate.slice(5)]);
      expect(candidate.source).toMatchObject({
        accessMethod: "direct_html", checkedAt: "2026-08-31", url: record.source.url,
      });
      expect(candidate.supportingSources.every((source) => (
        source.accessMethod === "direct_html" && !source.url.endsWith(".pdf")
      ))).toBe(true);
      expect(record).toMatchObject({
        candidateId: candidate.id,
        primaryUse: "discover",
        recommendedSurface: "discover",
        dailyRole: "secondary",
        dateAnchors: candidate.dateAnchors,
        areas: candidate.geographicScope,
        editorialStatus: "ready_for_discover",
        languageStatus: { it: "approved", fur: "approved" },
        readyForUi: true,
      });
      expect(record).not.toHaveProperty("localityFocus");
      expect(record).not.toHaveProperty("milestones");
      expect(record.source.type).toBe("verified_source");
      expect(record.summary.it.split(/\s+/).length).toBeGreaterThanOrEqual(25);
      expect(record.summary.it.split(/\s+/).length).toBeLessThanOrEqual(45);
      expect(record.summary.fur.split(/\s+/).length).toBeLessThanOrEqual(45);
    });
  });

  it("records ARLeF evidence as direct lexical HTML, not certification of the copy", () => {
    research.records.forEach((candidate) => {
      expect(candidate.languageReview).toMatchObject({
        approvalBasis: "user_delegated_assisted_editorial_review",
        reviewer: "assistant",
        independentHumanReview: false,
        method: "assisted_standard_reference_review",
        accessMethod: "public_html_via_powershell_Invoke-WebRequest",
      });
      expect(candidate.languageReview.references.length).toBeGreaterThanOrEqual(4);
      candidate.languageReview.references.forEach((reference) => {
        expect(new URL(reference.url).hostname).toBe("superdizionari.arlef.it");
        expect(reference.attestation).toBeTruthy();
      });
    });
    expect(records[0].summary.fur).toContain("Società di Minerva");
    expect(records[0].summary.fur).toContain("Archeografo Triestino");
    expect(records[1].summary.fur).toContain("benvignût");
    expect(records[1].summary.fur).toContain("sienziâts");
  });

  it("keeps the founding dates distinct from publication and campus dates", () => {
    expect(records[0].summary.it).toContain("1° gennaio 1810");
    expect(records[0].summary.it).toContain("Nel 1829 nasce l'Archeografo");
    expect(records[1].summary.it).toContain("5 ottobre 1964");
    expect(records[1].summary.it).toContain("Hotel Jolly");
    expect(records[1].summary.it).not.toContain("1968");
    expect(records[1].source.note).toContain("distinta dalla sede completata nel 1968");
  });

  it("adds distinct subjects without copying earlier archive or municipal material", () => {
    const earlier = JSON.stringify([
      baseline.records, archiveWave01, archiveWave02, institutionalArchive, municipalityProfiles, ostermann,
    ]);
    expect(earlier).not.toMatch(/Società di Minerva|Archeografo Triestino|\bICTP\b|Abdus Salam/);
    research.records.forEach((candidate) => {
      expect(candidate.duplicateReview.status).toBe("distinct");
      expect(candidate.duplicateReview.comparedCatalogs).toEqual([
        "localMemory", "archiveResearchWave01", "archiveResearchWave02", "municipalityProfiles",
        "ostermannCulturalDiscover", "institutionalArchive",
      ]);
      expect(archive.records.filter((record) => record.candidateId === candidate.id)).toHaveLength(1);
    });
  });

  it.each(["it", "fur"])("preserves both primary cards and the existing secondaries in %s", (language) => {
    research.records.forEach((candidate) => {
      const date = `2026-${candidate.dateAnchors[0]}`;
      const oldPrimary = getLocalMemoryForDate({ date, language, source: baseline });
      const currentPrimary = getLocalMemoryForDate({ date, language });
      expect(oldPrimary.id).toBe(candidate.preservedPrimaryId);
      expect(currentPrimary).toEqual(oldPrimary);
      const oldSecondary = secondaryCards(date, language, trieste, baseline);
      const newSecondary = secondaryCards(date, language);
      expect(oldSecondary).toHaveLength(candidate.existingReadySecondaryCount);
      expect(newSecondary.filter((card) => card.id !== candidate.promotedRecordId)).toEqual(oldSecondary);
      expect(newSecondary).toHaveLength(candidate.existingReadySecondaryCount + 1);
      expect(newSecondary.length).toBeLessThanOrEqual(3);
    });
  });

  it.each([2026, 2027, 2028])("uses exact dates only and excludes adjacent days in %s", (year) => {
    ["it", "fur"].forEach((language) => {
      const cases = [
        { id: MINERVA_ID, date: `${year}-01-01`, before: `${year - 1}-12-31`, after: `${year}-01-02` },
        { id: ICTP_ID, date: `${year}-10-05`, before: `${year}-10-04`, after: `${year}-10-06` },
      ];
      cases.forEach(({ id, date, before, after }) => {
        expect(secondaryCards(date, language).some((card) => card.id === id)).toBe(true);
        [before, after].forEach((otherDate) => {
          expect(secondaryCards(otherDate, language).some((card) => card.id === id)).toBe(false);
        });
      });
    });
  });

  it.each(["it", "fur"])("matches Trieste or its province without unrelated localities in %s", (language) => {
    research.records.forEach((candidate) => {
      const date = `2026-${candidate.dateAnchors[0]}`;
      expect(secondaryCards(date, language, { province: "TS" }).map((card) => card.id))
        .toContain(candidate.promotedRecordId);
      [
        { city: "Udine", province: "UD" },
        { city: "Pordenone", province: "PN" },
        { city: "Gorizia", province: "GO" },
      ].forEach((location) => {
        expect(secondaryCards(date, language, location).map((card) => card.id))
          .not.toContain(candidate.promotedRecordId);
      });
    });
  });

  it("retains the existing default limit of three even with more matching candidates", () => {
    const source = {
      ...archive,
      records: Array.from({ length: 5 }, (_, index) => ({ ...records[0], id: `fixture-secondary-${index}` })),
    };
    expect(secondaryCards("2026-01-01", "it", trieste, source)).toHaveLength(3);
    expect(getLocalMemorySecondaryForDate({
      date: "2026-01-01", language: "fur", location: trieste, source, limit: null,
    })).toHaveLength(5);
  });

  it.each(["it", "fur"])("renders both new cards only in the secondary section in %s", (language) => {
    research.records.forEach((candidate) => {
      const date = `2026-${candidate.dateAnchors[0]}`;
      const model = buildDiscoverViewModel({ today: date, language, location: trieste });
      const section = model.sections.find((item) => item.id === "local-memory-secondary");
      const record = records.find((item) => item.id === candidate.promotedRecordId);
      const card = section.cards.find((item) => item.id === record.id);
      expect(card).toMatchObject({
        title: record.title[language], text: record.summary[language], dailyRole: "secondary",
        selectionKind: "exact_date_secondary", isFurPending: false,
        sourceLabel: record.source.label, sourceNote: record.source.url,
      });
      expect(model.sections.flatMap((item) => item.cards).filter((item) => item.id === record.id))
        .toHaveLength(1);
      const markup = renderToStaticMarkup(createElement(DiscoverCard, { card, language }));
      expect(markup).toContain(`<small>${record.source.label.split(" · ")[0]}`);
      expect(markup).toContain(language === "it" ? "Trieste" : "Triest");
      expect(markup).not.toMatch(/pending_review|human_review_needed|source_needed/);
    });
  });
});
