import { useEffect, useState, useSyncExternalStore } from "react";
import { createMarketsCatalogueStore, MARKETS_CATALOGUE_CACHE_PREFIX } from "../../services/marketsCatalogue";

export function useMarketsCatalogue({ enabled = false, refreshToken = 0 } = {}) {
  const [store] = useState(() => createMarketsCatalogueStore());
  const state = useSyncExternalStore(store.subscribe, store.getSnapshot, store.getSnapshot);
  useEffect(() => {
    const changed = event => {
      if (event.key?.startsWith(MARKETS_CATALOGUE_CACHE_PREFIX)) store.syncStorage();
    };
    window.addEventListener("storage", changed);
    return () => window.removeEventListener("storage", changed);
  }, [store]);
  useEffect(() => {
    if (!enabled) return undefined;
    let lastRefresh = 0;
    const resume = () => {
      if (document.visibilityState !== "hidden") {
        lastRefresh = Date.now();
        void store.refresh();
      }
    };
    resume();
    const timer = window.setInterval(() => {
      store.checkExpiry();
      if (Date.now() - lastRefresh >= 5 * 60000) resume();
    }, 60000);
    document.addEventListener("visibilitychange", resume);
    window.addEventListener("online", resume);
    return () => {
      window.clearInterval(timer);
      document.removeEventListener("visibilitychange", resume);
      window.removeEventListener("online", resume);
    };
  }, [store, enabled, refreshToken]);
  return state;
}
