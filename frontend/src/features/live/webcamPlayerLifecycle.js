export function subscribeToWebcamPlayerBackgroundClose({
  documentRef = globalThis.document,
  onClose,
  windowRef = globalThis.window,
} = {}) {
  if (!documentRef?.addEventListener || typeof onClose !== "function") {
    return () => {};
  }

  let closed = false;
  const closeOnce = () => {
    if (closed) return;
    closed = true;
    onClose();
  };
  const handleVisibilityChange = () => {
    if (documentRef.visibilityState === "hidden") closeOnce();
  };

  documentRef.addEventListener("visibilitychange", handleVisibilityChange);
  windowRef?.addEventListener?.("pagehide", closeOnce);

  return () => {
    documentRef.removeEventListener("visibilitychange", handleVisibilityChange);
    windowRef?.removeEventListener?.("pagehide", closeOnce);
  };
}
