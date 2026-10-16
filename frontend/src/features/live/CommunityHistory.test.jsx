// @vitest-environment jsdom
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
vi.mock("../../services/liveApi", () => ({
  fetchCommunityHistory: vi.fn(), getPersistentLiveReportClientId: () => "test-client",
}));
import { fetchCommunityHistory } from "../../services/liveApi";
import { CommunityHistory } from "./CommunityHistory";
import { getLiveViewCopy } from "../../copy/liveViewCopy";
let root, container;
beforeEach(() => {
  globalThis.IS_REACT_ACT_ENVIRONMENT = true;
  container = document.createElement("div"); document.body.appendChild(container);
  root = createRoot(container); vi.clearAllMocks();
});
afterEach(async () => {
  await act(async () => root.unmount()); container.remove();
  delete globalThis.IS_REACT_ACT_ENVIRONMENT;
});
it("shows read-only history and loads the next page without duplicating reports", async () => {
  const first = { id: "one", typeId: "rain", place: "Pordenone", createdAt: Date.now(), status: "replaced", mine: true, point: true };
  vi.mocked(fetchCommunityHistory).mockResolvedValueOnce({ reports: [first], next_offset: 50 })
    .mockResolvedValueOnce({ reports: [first, { ...first, id: "two", mine: false, status: "expired" }], next_offset: null });
  const copy = getLiveViewCopy("it");
  await act(async () => root.render(<CommunityHistory location={{ istatCode: "093033" }} copy={copy} />));
  expect(container.textContent).toContain("Sostituita");
  expect(container.textContent).toContain(copy.historyPoint);
  expect(container.querySelectorAll("button")).toHaveLength(1);
  await act(async () => container.querySelector("button").click());
  expect(fetchCommunityHistory).toHaveBeenLastCalledWith(expect.objectContaining({ offset: 50, location: { istatCode: "093033" } }), expect.any(Object));
  expect(container.querySelectorAll("article")).toHaveLength(2);
  expect(container.querySelectorAll("button")).toHaveLength(0);
});
