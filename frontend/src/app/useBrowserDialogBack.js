import { Capacitor } from "@capacitor/core";
import { useEffect, useRef } from "react";

const DIALOG_ENTRY = "__mfBrowserDialog";
let pendingReturn = Promise.resolve();
let nextEntry = 0;
const activeEntries = new Set();

// A close button must consume the same entry as browser Back. Wait for that
// asynchronous traversal before registering a newly opened dialog.
function returnFromDialog() {
  pendingReturn = new Promise((resolve) => {
    window.addEventListener("popstate", () => resolve(), { once: true });
    window.history.back();
  });
}

/** Browser-only history entry for a dialog or an enabled temporary screen. */
export function useBrowserDialogBack(onBack, enabled = true) {
  const callbackRef = useRef(onBack);
  useEffect(() => { callbackRef.current = onBack; }, [onBack]);
  useEffect(() => {
    if (!enabled || typeof window === "undefined" || Capacitor.isNativePlatform()) return undefined;
    let active = true;
    let entry = null;
    const handlePopState = (event) => {
      if (event.state?.[DIALOG_ENTRY] === entry) return;
      activeEntries.delete(entry);
      entry = null;
      callbackRef.current?.();
    };

    // StrictMode's setup/cleanup rehearsal must not create a history entry.
    queueMicrotask(async () => {
      await pendingReturn;
      if (!active) return;
      entry = `${Date.now()}-${++nextEntry}`;
      const previous = window.history.state;
      const state = { ...previous, [DIALOG_ENTRY]: entry };
      // A reload can preserve an entry whose dialog no longer exists.
      // An active entry belongs to a parent screen/dialog and must be preserved.
      if (previous?.[DIALOG_ENTRY] && !activeEntries.has(previous[DIALOG_ENTRY])) window.history.replaceState(state, "");
      else window.history.pushState(state, "");
      activeEntries.add(entry);
      window.addEventListener("popstate", handlePopState);
    });

    return () => {
      active = false;
      window.removeEventListener("popstate", handlePopState);
      activeEntries.delete(entry);
      if (entry && window.history.state?.[DIALOG_ENTRY] === entry) {
        returnFromDialog();
      }
    };
  }, [enabled]);
}
