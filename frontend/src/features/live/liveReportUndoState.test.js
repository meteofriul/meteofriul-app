import { describe, expect, it, vi } from "vitest";

import {
  LIVE_REPORT_UNDO_STATE_KEY,
  clearLiveReportUndoState,
  readLiveReportUndoState,
  writeLiveReportUndoState,
} from "./liveReportUndoState";

function createStorage() {
  const values = new Map();

  return {
    getItem: vi.fn((key) => values.get(key) || null),
    removeItem: vi.fn((key) => values.delete(key)),
    setItem: vi.fn((key, value) => values.set(key, value)),
  };
}

describe("live report undo state", () => {
  it("persists a valid undo window for the browser session", () => {
    const memoryState = { value: null };
    const storage = createStorage();
    const state = { reportId: "report-1", undoUntil: 61_000 };

    expect(writeLiveReportUndoState(state, { memoryState, now: 1_000, storage }))
      .toEqual(state);
    expect(storage.setItem).toHaveBeenCalledWith(
      LIVE_REPORT_UNDO_STATE_KEY,
      JSON.stringify(state),
    );
    expect(readLiveReportUndoState({ memoryState: { value: null }, now: 2_000, storage }))
      .toEqual(state);
  });

  it("keeps undo in module memory when sessionStorage is unavailable", () => {
    const memoryState = { value: null };
    const storage = {
      getItem: vi.fn(() => { throw new Error("blocked"); }),
      removeItem: vi.fn(() => { throw new Error("blocked"); }),
      setItem: vi.fn(() => { throw new Error("blocked"); }),
    };
    const state = { reportId: "report-2", undoUntil: 70_000 };

    expect(writeLiveReportUndoState(state, { memoryState, now: 1_000, storage }))
      .toEqual(state);
    expect(readLiveReportUndoState({ memoryState, now: 2_000, storage }))
      .toEqual(state);
  });

  it("cleans expired or explicitly cleared undo state", () => {
    const memoryState = { value: null };
    const storage = createStorage();
    writeLiveReportUndoState(
      { reportId: "report-3", undoUntil: 2_000 },
      { memoryState, now: 1_000, storage },
    );

    expect(readLiveReportUndoState({ memoryState, now: 2_001, storage })).toBeNull();
    expect(memoryState.value).toBeNull();
    expect(storage.removeItem).toHaveBeenCalledWith(LIVE_REPORT_UNDO_STATE_KEY);

    writeLiveReportUndoState(
      { reportId: "report-4", undoUntil: 4_000 },
      { memoryState, now: 3_000, storage },
    );
    clearLiveReportUndoState({ memoryState, storage });
    expect(readLiveReportUndoState({ memoryState, now: 3_100, storage })).toBeNull();
  });
});
