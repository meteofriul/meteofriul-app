import { describe, expect, it, vi } from "vitest";
import { EMPTY_EDITORIAL_ADVICE, fetchEditorialAdvice, normalizeEditorialAdvice } from "./editorialAdvice";

const item = { id: "draft_123", type: "message", title: "Un messaggio", message: "Testo pubblicato",
  enabled: true, startAt: "2026-11-08T08:00:00Z", endAt: "2026-11-09T08:00:00Z" };
const now = Date.parse("2026-11-08T09:00:00Z");

describe("Home editorial advice", () => {
  it("accepts only a published item valid at the current instant", () => {
    const payload = { schemaVersion: 1, item, nextChangeAt: item.endAt };
    expect(normalizeEditorialAdvice(payload, now).item?.message).toBe("Testo pubblicato");
    expect(normalizeEditorialAdvice(payload, Date.parse(item.endAt))).toEqual(EMPTY_EDITORIAL_ADVICE);
    expect(normalizeEditorialAdvice({ ...payload, item: { ...item, message: " " } }, now))
      .toEqual(EMPTY_EDITORIAL_ADVICE);
  });

  it("falls back to the automatic advice on an unavailable endpoint", async () => {
    const fetchImpl = vi.fn().mockResolvedValue({ ok: false, status: 503 });
    expect(await fetchEditorialAdvice({ apiBase: "/api", fetchImpl, now: () => now }))
      .toEqual(EMPTY_EDITORIAL_ADVICE);
    expect(fetchImpl.mock.calls[0][0]).toBe("/api/editorial/home-advice");
  });
});
