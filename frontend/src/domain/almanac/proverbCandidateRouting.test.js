import { describe, expect, it } from "vitest";

import { getProverbCandidateRoutingSummary } from "./proverbCandidateRouting";

function ids(records) {
  return records.map((record) => record.id);
}

describe("proverb candidate routing", () => {
  it("confirms all extracted Ostermann candidates have an editorial route", () => {
    const summary = getProverbCandidateRoutingSummary();

    expect(summary.totalCandidates).toBe(122);
    expect(summary.reviewedCandidates).toBe(122);
    expect(summary.unreviewedCandidates).toBe(0);
    expect(summary.unreviewedSourceChecked).toBe(0);
    expect(summary.unreviewedCandidateStatus).toBe(0);
    expect(summary.queueCounts).toEqual({
      almanacReview: 0,
      needsContextOrHold: 0,
      discoverArchive: 0,
    });
    expect(summary.duplicateRoutedIds).toEqual([]);
  });

  it("keeps the Almanac review queue empty after the final review pass", () => {
    const summary = getProverbCandidateRoutingSummary();
    const almanacIds = ids(summary.queues.almanacReview);

    expect(almanacIds).toEqual([]);
    expect(almanacIds).not.toContain("ostermann-054-epifanie-fred");
    expect(almanacIds).not.toContain("ostermann-060-san-bortolomio-bon-timp");
    expect(almanacIds).not.toContain("ostermann-061-san-simon-unviar");
    expect(almanacIds).not.toContain("ostermann-061-fueis-tardis");
    expect(almanacIds).not.toContain("ostermann-192-san-barnaba-vin");
    expect(almanacIds).not.toContain("ostermann-192-assunte-vin");
    expect(almanacIds).not.toContain("ostermann-126-tone-ploe-tempieste");
    expect(almanacIds).not.toContain("ostermann-126-mai-tempieste");
    expect(almanacIds).not.toContain("ostermann-130-sot-nev-pan");
    expect(almanacIds).not.toContain("ostermann-104-monts-chapiel");
    expect(almanacIds).not.toContain("ostermann-104-cil-lane");
    expect(almanacIds).not.toContain("ostermann-049-prin-martars-lune-pluv");
    expect(almanacIds).not.toContain("ostermann-049-lune-brume");
    expect(almanacIds).not.toContain("ostermann-096-garbin-timp");
    expect(almanacIds).not.toContain("ostermann-097-rosadis-marz-bueris-avril");
    expect(almanacIds).not.toContain("ostermann-099-tre-fumatis-ploe");
    expect(almanacIds).not.toContain("ostermann-102-cuch-ploe-sut");
    expect(almanacIds).not.toContain("ostermann-058-san-pauli-scur");
    expect(almanacIds).not.toContain("ostermann-087-sante-luzie-nadal");
  });

  it("leaves no contextual candidates in the automatic routing queue", () => {
    const summary = getProverbCandidateRoutingSummary();
    const contextIds = ids(summary.queues.needsContextOrHold);

    expect(contextIds).toEqual([]);
  });

  it("leaves no prose or no-FUR candidates in the automatic routing queue", () => {
    const summary = getProverbCandidateRoutingSummary();
    const discoverIds = ids(summary.queues.discoverArchive);

    expect(discoverIds).toEqual([]);
  });
});
