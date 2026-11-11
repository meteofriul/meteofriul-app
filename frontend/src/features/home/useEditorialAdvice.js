import { useEffect, useState } from "react";
import { EMPTY_EDITORIAL_ADVICE, fetchEditorialAdvice } from "../../services/editorialAdvice";

export function useEditorialAdvice() {
  const enabled = import.meta.env.MODE !== "test"
    && import.meta.env.VITE_EDITORIAL_ADVICE_ENABLED === "true";
  const [snapshot, setSnapshot] = useState(EMPTY_EDITORIAL_ADVICE);

  useEffect(() => {
    if (!enabled) return undefined;
    let current = true;
    let boundaryTimer;
    let requestId = 0;
    const refresh = async () => {
      const selectedRequest = ++requestId;
      const result = await fetchEditorialAdvice();
      if (!current || selectedRequest !== requestId) return;
      setSnapshot(result);
      globalThis.clearTimeout(boundaryTimer);
      if (result.nextChangeAt) {
        boundaryTimer = globalThis.setTimeout(refresh,
          Math.max(1000, Math.min(result.nextChangeAt - Date.now() + 250, 2147483647)));
      }
    };
    const foreground = () => {
      if (globalThis.document?.visibilityState !== "hidden") void refresh();
    };
    void refresh();
    const interval = globalThis.setInterval(refresh, 60000);
    globalThis.addEventListener?.("focus", foreground);
    globalThis.document?.addEventListener?.("visibilitychange", foreground);
    return () => {
      current = false;
      globalThis.clearInterval(interval);
      globalThis.clearTimeout(boundaryTimer);
      globalThis.removeEventListener?.("focus", foreground);
      globalThis.document?.removeEventListener?.("visibilitychange", foreground);
    };
  }, [enabled]);

  return snapshot.item;
}
