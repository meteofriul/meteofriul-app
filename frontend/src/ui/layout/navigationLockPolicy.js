export function isPullRefreshDisabled({ navigationLocked, onRuntimeRefresh }) {
  return Boolean(navigationLocked || !onRuntimeRefresh);
}
