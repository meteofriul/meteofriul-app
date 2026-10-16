const DAY_MS = 24 * 60 * 60 * 1000;
const MIN_TIMER_DELAY_MS = 1000;

export function getLocalDayKey(value = new Date()) {
  const date = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(date.getTime())) return "";

  return [
    date.getFullYear(),
    String(date.getMonth() + 1).padStart(2, "0"),
    String(date.getDate()).padStart(2, "0"),
  ].join("-");
}

export function getMillisecondsUntilNextLocalDay(value = new Date()) {
  const date = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(date.getTime())) return DAY_MS;

  const nextDay = new Date(date);
  nextDay.setHours(24, 0, 0, 0);

  return Math.max(MIN_TIMER_DELAY_MS, nextDay.getTime() - date.getTime());
}

export function subscribeToDiscoverDayClock(
  onDayChange,
  {
    documentRef = typeof document === "undefined" ? null : document,
    now = () => new Date(),
    timerApi = globalThis,
  } = {},
) {
  let timeoutId;
  let isDisposed = false;
  let currentDayKey = getLocalDayKey(now());

  const scheduleNextDay = () => {
    const currentTime = now();
    timeoutId = timerApi.setTimeout(
      syncDay,
      getMillisecondsUntilNextLocalDay(currentTime),
    );
  };

  const syncDay = () => {
    if (isDisposed) return;

    const currentTime = now();
    const nextDayKey = getLocalDayKey(currentTime);
    if (nextDayKey && nextDayKey !== currentDayKey) {
      currentDayKey = nextDayKey;
      onDayChange(currentTime);
    }

    timerApi.clearTimeout(timeoutId);
    scheduleNextDay();
  };

  scheduleNextDay();
  documentRef?.addEventListener("visibilitychange", syncDay);

  return () => {
    isDisposed = true;
    timerApi.clearTimeout(timeoutId);
    documentRef?.removeEventListener("visibilitychange", syncDay);
  };
}
