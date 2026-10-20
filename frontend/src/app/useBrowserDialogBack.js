import { Capacitor } from "@capacitor/core";
import { useEffect, useRef } from "react";

const DIALOG_ENTRY = "__mfBrowserDialog";
let pendingReturn = Promise.resolve();
let nextEntry = 0;

// A close button must consume the same entry as browser Back. Wait for that
// asynchronous traversal before registering a newly opened dialog.
function returnFromDialog() {
  pendingReturn = new Promise((resolve) => {
    window.addEventListener("popstate", () => resolve(), { once: true });
    window.history.back();
  });
}

/** Browser-only history entry, scoped to the lifetime of one open dialog. */
export function useBrowserDialogBack(onBack) {
  const callbackRef = useRef(onBack);
  useEffect(() => { callbackRef.current = onBack; }, [onBack]);
  useEffect(() => {
    if (typeof window === "undefined" || Capacitor.isNativePlatform()) return undefined;
    let active = true;
    let entry = null;
    const handlePopState = (event) => {
      if (event.state?.[DIALOG_ENTRY] === entry) return;
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
      if (previous?.[DIALOG_ENTRY]) window.history.replaceState(state, "");
      else window.history.pushState(state, "");
      window.addEventListener("popstate", handlePopState);
    });

    return () => {
      active = false;
      window.removeEventListener("popstate", handlePopState);
      if (entry && window.history.state?.[DIALOG_ENTRY] === entry) {
        returnFromDialog();
      }
    };
  }, []);
}
