import { useEffect, useRef } from "react";

import { registerPilotBackHandler } from "../services/pilotBackNavigation";

// Keep the original stack position when an open panel re-renders.
// The bridge itself is inert outside the definitive native Android app.
export function usePilotBackHandler(onBack, enabled = true) {
  const callbackRef = useRef(onBack);
  useEffect(() => { callbackRef.current = onBack; }, [onBack]);
  useEffect(() => {
    if (!enabled) return undefined;
    return registerPilotBackHandler(() => callbackRef.current?.());
  }, [enabled]);
}
