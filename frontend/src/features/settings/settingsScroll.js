export function resetAppMainScroll(documentRef = globalThis.document) {
  const appMain = documentRef?.querySelector?.(".mf-app-main");
  if (!appMain) return false;

  appMain.scrollTop = 0;
  return true;
}
