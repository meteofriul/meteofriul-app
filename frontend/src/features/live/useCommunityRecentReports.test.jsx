// @vitest-environment jsdom
import { act, useEffect } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { useCommunityRecentReports } from "./useCommunityRecentReports";
import { fetchCommunityHistory } from "../../services/liveApi";
vi.mock("../../services/liveApi", () => ({ fetchCommunityHistory: vi.fn(),
  getPersistentLiveReportClientId: () => "test-reader" }));
let root, container, value;
const pn = { istatCode: "093033" };
function Harness(props) {
  const current = useCommunityRecentReports(props);
  useEffect(() => { value = current; }, [current]);
  return <span>{current.reports.map((r) => r.id).join(",")}</span>;
}
async function render(props = {}) {
  await act(async () => root.render(<Harness enabled location={pn} refreshKey="one" {...props} />));
}
beforeEach(() => {
  globalThis.IS_REACT_ACT_ENVIRONMENT = true;
  container = document.createElement("div"); document.body.append(container);
  root = createRoot(container); vi.clearAllMocks();
});
afterEach(async () => {
  await act(async () => root.unmount()); container.remove(); delete globalThis.IS_REACT_ACT_ENVIRONMENT;
});
it("loads only when enabled and appends pages with a stable cursor, without duplicates", async () => {
  const cursor = { createdAt: 1234, id: "first" };
  fetchCommunityHistory.mockResolvedValueOnce({ reports: [{ id: "first" }], next_cursor: cursor })
    .mockResolvedValueOnce({ reports: [{ id: "first" }, { id: "second" }], next_cursor: null });
  await render({ enabled: false }); expect(fetchCommunityHistory).not.toHaveBeenCalled();
  await render();
  await act(async () => { value.loadMore(); value.loadMore(); });
  expect(fetchCommunityHistory).toHaveBeenCalledTimes(2);
  expect(fetchCommunityHistory.mock.calls[1][0]).toMatchObject({ cursor, location: pn, grouped: true });
  expect(value.reports.map((r) => r.id)).toEqual(["first", "second"]);
});
it("aborts an old locality and never displays its late result in the new locality", async () => {
  let finish;
  fetchCommunityHistory.mockImplementationOnce(() => new Promise((resolve) => { finish = resolve; }))
    .mockResolvedValueOnce({ reports: [{ id: "trieste" }], next_cursor: null });
  await render(); const signal = fetchCommunityHistory.mock.calls[0][1].signal;
  await render({ location: { istatCode: "032006" } });
  expect(signal.aborted).toBe(true);
  await act(async () => finish({ reports: [{ id: "pordenone" }], next_cursor: null }));
  expect(container.textContent).toBe("trieste");
});
it("retries a failed page using the same cursor and refreshes after a changed live feed", async () => {
  const cursor = { createdAt: 1234, id: "first" };
  fetchCommunityHistory.mockResolvedValueOnce({ reports: [{ id: "first" }], next_cursor: cursor })
    .mockRejectedValueOnce(new Error("offline"))
    .mockResolvedValueOnce({ reports: [{ id: "second" }], next_cursor: null })
    .mockResolvedValueOnce({ reports: [{ id: "new" }], next_cursor: null });
  await render(); await act(async () => value.loadMore());
  expect(value.status).toBe("error"); expect(value.reports).toHaveLength(1);
  await act(async () => value.retry());
  expect(fetchCommunityHistory.mock.calls[2][0].cursor).toEqual(cursor);
  expect(value.reports).toHaveLength(2);
  await render({ refreshKey: "changed" });
  expect(value.reports.map((r) => r.id)).toEqual(["new"]);
});
