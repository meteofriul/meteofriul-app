import { describe, expect, it } from "vitest";

import {
  getOstermannDiscoverBacklogRecords,
  getOstermannDiscoverBacklogSummary,
} from "./ostermannDiscoverBacklog";

describe("ostermann discover backlog", () => {
  it("keeps Ostermann extraction oriented to Scopri before Almanacco promotion", () => {
    const summary = getOstermannDiscoverBacklogSummary();

    expect(summary.totalRecords).toBe(29);
    expect(summary.sourcePages).toBe(29);
    expect(summary.discoverRecords).toBe(29);
    expect(summary.almanacBridgeRecords).toBeGreaterThan(10);
    expect(summary.pendingFurRecords).toBe(29);
    expect(summary.readyForUiRecords).toBe(0);
  });

  it("keeps backlog records out of the UI until editorial review", () => {
    const records = getOstermannDiscoverBacklogRecords();
    const readyForCopyRecords = records.filter((record) => (
      record.editorialStatus === "ready_for_editorial_copy"
    ));

    expect(readyForCopyRecords.map((record) => record.id)).toEqual([
      "ost-discover-099-nebbia-pronostici",
    ]);
    expect(records.every((record) => (
      record.editorialStatus === "backlog_extracted" ||
      record.editorialStatus === "ready_for_editorial_copy"
    ))).toBe(true);
    expect(records.every((record) => record.primaryUse === "discover")).toBe(true);
    expect(records.every((record) => record.source?.pdfPage === record.sourcePage)).toBe(true);
    expect(records.every((record) => record.readyForUi !== true)).toBe(true);
  });
});
