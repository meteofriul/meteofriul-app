import { afterEach, describe, expect, it, vi } from "vitest";

import {
  fetchWebcamSnapshotUpdatedAt,
  isWebcamSnapshotRecent,
  WEBCAM_SNAPSHOT_METADATA_TIMEOUT_MS,
  WEBCAM_SNAPSHOT_RECENT_MAX_AGE_MS,
} from "./webcamSnapshotMetadata";

function successfulHead(lastModified = "Sat, 19 Sep 2026 16:20:00 GMT") {
  return {
    ok: true,
    headers: new Headers(lastModified ? { "Last-Modified": lastModified } : {}),
  };
}

afterEach(() => {
  vi.useRealTimers();
});

describe("webcam snapshot metadata", () => {
  it("marks only verified, genuinely recent frames as recent", () => {
    const now = new Date("2026-09-19T17:00:00.000Z");

    expect(isWebcamSnapshotRecent({ now, updatedAt: "2026-09-19T16:30:00.000Z" })).toBe(true);
    expect(isWebcamSnapshotRecent({ now, updatedAt: "2026-09-19T16:29:59.999Z" })).toBe(false);
    expect(isWebcamSnapshotRecent({ now, updatedAt: "2026-09-19T17:02:00.000Z" })).toBe(true);
    expect(isWebcamSnapshotRecent({ now, updatedAt: "2026-09-19T17:02:00.001Z" })).toBe(false);
    expect(isWebcamSnapshotRecent({ now, updatedAt: "" })).toBe(false);
    expect(WEBCAM_SNAPSHOT_RECENT_MAX_AGE_MS).toBe(30 * 60 * 1000);
  });

  it("reads and normalizes Last-Modified with a private, uncached CORS HEAD request", async () => {
    const fetchImpl = vi.fn().mockResolvedValue(successfulHead());

    await expect(fetchWebcamSnapshotUpdatedAt(
      "  https://images.example.test/latest.jpg?camera=2#frame  ",
      { fetchImpl },
    )).resolves.toBe("2026-09-19T16:20:00.000Z");

    expect(fetchImpl).toHaveBeenCalledOnce();
    expect(fetchImpl).toHaveBeenCalledWith(
      "https://images.example.test/latest.jpg?camera=2#frame",
      expect.objectContaining({
        method: "HEAD",
        mode: "cors",
        credentials: "omit",
        referrerPolicy: "no-referrer",
        cache: "no-store",
        signal: expect.any(AbortSignal),
      }),
    );
  });

  it.each([
    "",
    "not a URL",
    "/latest.jpg",
    "//images.example.test/latest.jpg",
    "http://images.example.test/latest.jpg",
    "data:image/jpeg;base64,example",
    "javascript:alert(1)",
    "https:images.example.test/latest.jpg",
    "https://",
    "https://bad host/latest.jpg",
    "https://user@images.example.test/latest.jpg",
    "https://user:password@images.example.test/latest.jpg",
    null,
    undefined,
  ])("does not request unsafe or malformed snapshot URLs: %s", async (imageUrl) => {
    const fetchImpl = vi.fn();

    await expect(fetchWebcamSnapshotUpdatedAt(imageUrl, { fetchImpl })).resolves.toBe("");
    expect(fetchImpl).not.toHaveBeenCalled();
  });

  it.each([
    ["a missing Last-Modified header", successfulHead("")],
    ["an invalid Last-Modified header", successfulHead("not a date")],
    ["a failed HTTP response", { ...successfulHead(), ok: false }],
    ["an unusable response", null],
  ])("returns no source time for %s", async (_label, response) => {
    const fetchImpl = vi.fn().mockResolvedValue(response);

    await expect(fetchWebcamSnapshotUpdatedAt(
      "https://images.example.test/latest.jpg",
      { fetchImpl },
    )).resolves.toBe("");
  });

  it("returns no source time when the request or header access fails", async () => {
    const rejectedFetch = vi.fn().mockRejectedValue(new TypeError("CORS blocked"));
    const throwingHeadersFetch = vi.fn().mockResolvedValue({
      ok: true,
      headers: { get: () => { throw new Error("unreadable header"); } },
    });

    await expect(fetchWebcamSnapshotUpdatedAt(
      "https://images.example.test/latest.jpg",
      { fetchImpl: rejectedFetch },
    )).resolves.toBe("");
    await expect(fetchWebcamSnapshotUpdatedAt(
      "https://images.example.test/latest.jpg",
      { fetchImpl: throwingHeadersFetch },
    )).resolves.toBe("");
  });

  it("returns no source time when abort setup is unavailable", async () => {
    class BrokenAbortController {
      constructor() {
        throw new Error("AbortController unavailable");
      }
    }
    const fetchImpl = vi.fn();

    await expect(fetchWebcamSnapshotUpdatedAt(
      "https://images.example.test/latest.jpg",
      { fetchImpl, AbortControllerClass: BrokenAbortController },
    )).resolves.toBe("");
    expect(fetchImpl).not.toHaveBeenCalled();
  });

  it("aborts a stalled request after the metadata timeout and returns no fabricated time", async () => {
    vi.useFakeTimers();
    let requestSignal;
    const fetchImpl = vi.fn((_url, { signal }) => {
      requestSignal = signal;
      return new Promise((_resolve, reject) => {
        signal.addEventListener("abort", () => reject(new DOMException("Aborted", "AbortError")));
      });
    });

    const result = fetchWebcamSnapshotUpdatedAt(
      "https://images.example.test/latest.jpg",
      { fetchImpl, timeoutMs: 25 },
    );
    expect(requestSignal.aborted).toBe(false);

    await vi.advanceTimersByTimeAsync(25);
    await expect(result).resolves.toBe("");
    expect(requestSignal.aborted).toBe(true);
  });

  it("clears the default timeout after a successful request", async () => {
    vi.useFakeTimers();
    const fetchImpl = vi.fn().mockResolvedValue(successfulHead());

    await expect(fetchWebcamSnapshotUpdatedAt(
      "https://images.example.test/latest.jpg",
      { fetchImpl },
    )).resolves.toBe("2026-09-19T16:20:00.000Z");

    expect(WEBCAM_SNAPSHOT_METADATA_TIMEOUT_MS).toBe(8000);
    expect(vi.getTimerCount()).toBe(0);
  });
});
