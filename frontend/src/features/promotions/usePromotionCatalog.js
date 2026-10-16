import { useEffect, useState } from "react";

import {
  EMPTY_PROMOTION_CATALOG,
  PROMOTION_CATALOG_REFRESH_MS,
  fetchPromotionCatalog,
  readPromotionCatalogCache,
} from "../../services/promotionCatalog";

export function usePromotionCatalog(enabled = true) {
  const liveEnabled = enabled && import.meta.env.MODE !== "test";
  const [catalog, setCatalog] = useState(() => (
    liveEnabled ? readPromotionCatalogCache() : EMPTY_PROMOTION_CATALOG
  ));

  useEffect(() => {
    if (!liveEnabled) return undefined;
    let active = true;
    const refresh = () => fetchPromotionCatalog().then((nextCatalog) => {
      if (active) setCatalog(nextCatalog);
    });
    const onForeground = () => {
      if (!globalThis.document || globalThis.document.visibilityState !== "hidden") refresh();
    };

    refresh();
    const interval = globalThis.setInterval?.(refresh, PROMOTION_CATALOG_REFRESH_MS);
    globalThis.addEventListener?.("focus", onForeground);
    globalThis.document?.addEventListener?.("visibilitychange", onForeground);
    return () => {
      active = false;
      globalThis.clearInterval?.(interval);
      globalThis.removeEventListener?.("focus", onForeground);
      globalThis.document?.removeEventListener?.("visibilitychange", onForeground);
    };
  }, [liveEnabled]);

  return liveEnabled ? catalog : EMPTY_PROMOTION_CATALOG;
}
