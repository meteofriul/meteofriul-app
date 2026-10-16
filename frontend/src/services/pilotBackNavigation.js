import { App } from "@capacitor/app";
import { Capacitor } from "@capacitor/core";

import { isAndroidCapacitorRuntime } from "./apiConfig";
import { isDefinitiveAppExperience } from "./localWeatherPilot";

/** One native listener, owned by the definitive Android app while it has a Back action. */
export function createPilotBackNavigation({
  app = App,
  capacitor = Capacitor,
  enabled = isDefinitiveAppExperience,
  history = () => globalThis.history,
} = {}) {
  const overlays = [];
  let page = null;
  let listener = null;
  let transition = null;
  let revision = 0;

  const allowed = () => (typeof enabled === "function" ? enabled() : enabled) === true
    && isAndroidCapacitorRuntime(capacitor)
    && typeof app?.addListener === "function";
  const activeOverlay = () => overlays.findLast((entry) => entry.isActive());
  const wantsListener = () => allowed() && Boolean(activeOverlay() || page);

  function handleBack(event = {}) {
    const action = allowed() ? (activeOverlay()?.onBack || page?.onBack) : null;
    if (action) {
      // An active overlay owns this press even when busy or its close is refused.
      // Never fall through to the page after closing a dialog with the same press.
      action();
      return;
    }

    // Removal crosses the asynchronous native bridge. A press already queued
    // during cleanup must retain AppPlugin's default: go back only if possible.
    if (event.canGoBack) history()?.back?.();
  }

  function reconcile() {
    revision += 1;
    if (transition) return transition;
    let observedRevision = revision;

    // Serialize add/remove so closing before addListener resolves, or reopening
    // during remove(), cannot leave duplicate or orphaned native listeners.
    transition = Promise.resolve().then(async () => {
      while (true) {
        observedRevision = revision;
        if (wantsListener() && !listener) {
          listener = await app.addListener("backButton", handleBack);
          if (typeof listener?.remove !== "function") throw new Error("pilot_back_listener_unavailable");
        } else if (!wantsListener() && listener) {
          const previous = listener;
          await previous.remove();
          listener = null;
        } else {
          return;
        }
      }
    }).catch(() => {
      // Failure must not produce an unhandled rejection; on-screen close and
      // navigation controls remain available. A later registration retries.
    }).finally(() => {
      transition = null;
      if (observedRevision !== revision) void reconcile();
    });
    return transition;
  }

  return {
    registerOverlay(onBack, { isActive = () => true } = {}) {
      if (!allowed() || typeof onBack !== "function") return () => {};
      const entry = { onBack, isActive };
      overlays.push(entry);
      void reconcile();
      return () => {
        const index = overlays.indexOf(entry);
        if (index < 0) return;
        overlays.splice(index, 1);
        void reconcile();
      };
    },
    setPageHandler(onBack) {
      if (!allowed()) return () => {};
      const entry = typeof onBack === "function" ? { onBack } : null;
      page = entry;
      void reconcile();
      return () => {
        if (page !== entry) return;
        page = null;
        void reconcile();
      };
    },
    async whenSettled() {
      while (transition) await transition;
    },
  };
}

const pilotBackNavigation = createPilotBackNavigation();

export function registerPilotBackHandler(onBack, options) {
  return pilotBackNavigation.registerOverlay(onBack, options);
}

export function setPilotBackPageHandler(onBack) {
  return pilotBackNavigation.setPageHandler(onBack);
}
