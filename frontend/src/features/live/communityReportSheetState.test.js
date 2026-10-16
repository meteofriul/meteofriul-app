import { describe, expect, it, vi } from "vitest";

import {
  COMMUNITY_REPORT_SHEET_OPEN_CLASS,
  lockCommunityReportSheetScroll,
} from "./communityReportSheetState";

function createDocumentClassList(initiallyLocked = false) {
  const classes = new Set(
    initiallyLocked ? [COMMUNITY_REPORT_SHEET_OPEN_CLASS] : [],
  );
  return {
    classes,
    documentLike: {
      documentElement: {
        classList: {
          add: vi.fn((name) => classes.add(name)),
          contains: vi.fn((name) => classes.has(name)),
          remove: vi.fn((name) => classes.delete(name)),
        },
      },
    },
  };
}

describe("community report sheet scroll lock", () => {
  it("locks and restores the app scroll container", () => {
    const { classes, documentLike } = createDocumentClassList();
    const release = lockCommunityReportSheetScroll(documentLike);

    expect(classes.has(COMMUNITY_REPORT_SHEET_OPEN_CLASS)).toBe(true);
    release();
    expect(classes.has(COMMUNITY_REPORT_SHEET_OPEN_CLASS)).toBe(false);
  });

  it("preserves a lock owned by another open layer", () => {
    const { classes, documentLike } = createDocumentClassList(true);
    const release = lockCommunityReportSheetScroll(documentLike);

    release();
    expect(classes.has(COMMUNITY_REPORT_SHEET_OPEN_CLASS)).toBe(true);
  });
});
