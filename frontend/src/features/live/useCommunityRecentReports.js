import { useCallback, useEffect, useRef, useState } from "react";
import { fetchCommunityHistory, getPersistentLiveReportClientId } from "../../services/liveApi";

const EMPTY = Object.freeze({ reports: [], status: "loading", next: null });

export function useCommunityRecentReports({ enabled, location, refreshKey }) {
  const scope = JSON.stringify({ istatCode: location?.istatCode || location?.municipality?.istatCode,
    lat: location?.lat, lon: location?.lon });
  const [page, setPage] = useState(EMPTY);
  const [now, setNow] = useState(() => Date.now());
  const activeRequest = useRef(null);
  const generation = useRef(0);
  const currentPage = useRef(EMPTY);

  const load = useCallback(async (cursor = null) => {
    if (activeRequest.current) return;
    const controller = new AbortController();
    activeRequest.current = controller;
    const requestGeneration = generation.current;
    const update = (next) => { currentPage.current = next; setPage(next); };
    update({ ...(currentPage.current.scope === scope ? currentPage.current : EMPTY),
      scope, status: "loading", requestedCursor: cursor });
    try {
      const result = await fetchCommunityHistory({ location: JSON.parse(scope),
        clientId: getPersistentLiveReportClientId(), cursor, grouped: true }, { signal: controller.signal });
      if (controller.signal.aborted || requestGeneration !== generation.current) return;
      const rows = cursor ? [...currentPage.current.reports, ...result.reports] : result.reports;
      update({ scope, reports: [...new Map(rows.map((row) => [row.id, row])).values()],
        status: "ready", next: result.next_cursor || null, requestedCursor: cursor });
      setNow(Date.now());
    } catch {
      if (!controller.signal.aborted && requestGeneration === generation.current) {
        update({ ...currentPage.current, status: "error" });
      }
    } finally {
      if (activeRequest.current === controller) activeRequest.current = null;
    }
  }, [scope]);

  useEffect(() => {
    if (!enabled) return;
    // Defer so cleanup can cancel a superseded locality before any request starts.
    let alive = true;
    Promise.resolve().then(() => { if (alive) void load(); });
    const refresh = () => { if (document.visibilityState !== "hidden") void load(); };
    window.addEventListener("focus", refresh);
    const timer = window.setInterval(() => setNow(Date.now()), 30_000);
    return () => {
      alive = false;
      generation.current += 1;
      activeRequest.current?.abort();
      activeRequest.current = null;
      window.removeEventListener("focus", refresh);
      window.clearInterval(timer);
    };
  }, [enabled, load, refreshKey]);

  const visible = page.scope === scope ? page : EMPTY;
  return { ...visible, now,
    loadMore: () => {
      if (enabled && visible.status === "ready" && visible.next) void load(visible.next);
    },
    retry: () => { if (enabled) void load(visible.requestedCursor || null); },
  };
}
