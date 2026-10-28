import { marketDay } from "./marketsCatalog";

// The catalogue follows Rome even when the device is travelling in another zone.
export function subscribeToMarketsDayClock(onDayChange, {
  documentRef = typeof document === "undefined" ? null : document,
  now = () => new Date(),
  timerApi = globalThis,
} = {}) {
  let disposed = false;
  let timer;
  let day = marketDay(now());
  onDayChange(now());
  const sync = () => {
    if (disposed) return;
    const date = now();
    const nextDay = marketDay(date);
    if (nextDay !== day) {
      day = nextDay;
      onDayChange(date);
    }
    timerApi.clearTimeout(timer);
    // Rome midnight is always a minute boundary, including daylight saving changes.
    timer = timerApi.setTimeout(sync, 60000 - date.getTime() % 60000);
  };
  sync();
  documentRef?.addEventListener("visibilitychange", sync);
  return () => {
    disposed = true;
    timerApi.clearTimeout(timer);
    documentRef?.removeEventListener("visibilitychange", sync);
  };
}
