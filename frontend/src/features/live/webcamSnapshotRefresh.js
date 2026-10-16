export const WEBCAM_SNAPSHOT_REFRESH_MS = 10 * 60 * 1000;

export function buildWebcamSnapshotUrl(imageUrl, requestedAt) {
  if (!Number.isFinite(requestedAt) || requestedAt <= 0) return "";
  if (typeof imageUrl !== "string" || !/^https:\/\//i.test(imageUrl.trim())) return "";

  try {
    const url = new URL(imageUrl.trim());
    if (url.protocol !== "https:" || !url.hostname || url.username || url.password) return "";
    url.searchParams.set("mf_snapshot", String(requestedAt));
    return url.href;
  } catch {
    return "";
  }
}

export function watchWebcamSnapshot({
  element,
  onRefresh,
  now = Date.now,
  documentRef = globalThis.document,
  windowRef = globalThis.window,
  IntersectionObserverClass = globalThis.IntersectionObserver,
} = {}) {
  if (!element || !documentRef || !windowRef || typeof onRefresh !== "function") {
    return () => {};
  }

  let disposed = false;
  let timerId = null;
  // Null, rather than zero, also supports clocks starting at the Unix epoch.
  let lastRequestedAt = null;
  let isIntersecting = typeof IntersectionObserverClass !== "function";
  let observer = null;

  function cancelTimer() {
    if (timerId === null) return;
    windowRef.clearTimeout(timerId);
    timerId = null;
  }

  function isVisible() {
    return !disposed && isIntersecting && documentRef.visibilityState === "visible";
  }

  function updateRefresh() {
    cancelTimer();
    if (!isVisible()) return;

    const requestedAt = now();
    if (lastRequestedAt === null || requestedAt - lastRequestedAt >= WEBCAM_SNAPSHOT_REFRESH_MS) {
      lastRequestedAt = requestedAt;
      onRefresh(requestedAt);
    }

    if (!isVisible()) return;
    // A refresh callback can synchronously change visibility and reschedule.
    cancelTimer();
    const remainingMs = Math.max(0, WEBCAM_SNAPSHOT_REFRESH_MS - (now() - lastRequestedAt));
    timerId = windowRef.setTimeout(updateRefresh, remainingMs);
  }

  documentRef.addEventListener("visibilitychange", updateRefresh);
  if (typeof IntersectionObserverClass === "function") {
    observer = new IntersectionObserverClass((entries) => {
      if (disposed) return;
      const entry = entries.filter((candidate) => candidate.target === element).at(-1);
      if (!entry) return;
      isIntersecting = entry.isIntersecting;
      updateRefresh();
    });
    observer.observe(element);
  }
  updateRefresh();

  return () => {
    disposed = true;
    cancelTimer();
    documentRef.removeEventListener("visibilitychange", updateRefresh);
    observer?.disconnect();
  };
}
