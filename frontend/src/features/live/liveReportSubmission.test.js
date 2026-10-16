import { describe, expect, it, vi } from "vitest";

import {
  runLiveReportSubmission,
  runPersistentLiveReportSubmission,
} from "./liveReportSubmission";

function deferred() {
  let resolve;
  let reject;
  const promise = new Promise((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });

  return { promise, reject, resolve };
}

describe("live report submission guard", () => {
  it("keeps one submission in flight and unlocks after success", async () => {
    const pending = deferred();
    const inFlightRef = { current: false };
    const onStateChange = vi.fn();
    const operation = vi.fn(() => pending.promise);
    const first = runLiveReportSubmission({ inFlightRef, onStateChange, operation });

    await expect(runLiveReportSubmission({ inFlightRef, onStateChange, operation }))
      .resolves.toEqual({ result: null, started: false });
    expect(operation).toHaveBeenCalledTimes(1);
    expect(inFlightRef.current).toBe(true);

    pending.resolve({ ok: true });
    await expect(first).resolves.toEqual({ result: { ok: true }, started: true });
    expect(inFlightRef.current).toBe(false);
    expect(onStateChange.mock.calls).toEqual([[true], [false]]);
  });

  it("always unlocks when submission rejects", async () => {
    const inFlightRef = { current: false };
    const onStateChange = vi.fn();

    await expect(runLiveReportSubmission({
      inFlightRef,
      onStateChange,
      operation: () => Promise.reject(new Error("offline")),
    })).rejects.toThrow("offline");

    expect(inFlightRef.current).toBe(false);
    expect(onStateChange.mock.calls).toEqual([[true], [false]]);
  });

  it("survives a route remount and publishes undo before unlocking", async () => {
    const pending = deferred();
    const promiseRef = { current: null };
    const onStateChange = vi.fn();
    const onSuccess = vi.fn();
    const operation = vi.fn(() => pending.promise);

    const beforeLocationChange = runPersistentLiveReportSubmission({
      onStateChange,
      onSuccess,
      operation,
      promiseRef,
    });
    const afterLocationRemount = runPersistentLiveReportSubmission({
      onStateChange,
      onSuccess,
      operation,
      promiseRef,
    });

    expect(afterLocationRemount).toBe(beforeLocationChange);
    expect(onStateChange).toHaveBeenCalledTimes(1);
    await Promise.resolve();
    expect(operation).toHaveBeenCalledTimes(1);

    pending.resolve({
      ok: true,
      report: { id: "report-after-location-change" },
      undoUntil: 61_000,
    });
    await expect(afterLocationRemount).resolves.toMatchObject({ ok: true });
    expect(onSuccess).toHaveBeenCalledWith(expect.objectContaining({
      report: { id: "report-after-location-change" },
      undoUntil: 61_000,
    }));
    expect(onStateChange.mock.calls).toEqual([[true], [false]]);
    expect(promiseRef.current).toBeNull();
  });
});
