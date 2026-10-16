const MODERATION_FOCUSABLE_SELECTOR = [
  "a[href]",
  "button:not([disabled])",
  "iframe",
  "input:not([disabled])",
  "select:not([disabled])",
  "summary",
  "textarea:not([disabled])",
  "[tabindex]:not([tabindex='-1'])",
].join(",");

export function trapCommunityModerationFocus(
  event,
  dialog,
  activeElement = globalThis.document?.activeElement,
) {
  if (event?.key !== "Tab" || !dialog) return false;

  const focusable = [...(dialog.querySelectorAll?.(MODERATION_FOCUSABLE_SELECTOR) || [])];
  if (!focusable.length) {
    event.preventDefault?.();
    return true;
  }

  const first = focusable[0];
  const last = focusable[focusable.length - 1];
  const activeInside = dialog.contains?.(activeElement);
  const activeIsDialog = activeElement === dialog;

  if (event.shiftKey && (!activeInside || activeIsDialog || activeElement === first)) {
    event.preventDefault?.();
    last.focus?.();
    return true;
  }
  if (!event.shiftKey && (!activeInside || activeIsDialog || activeElement === last)) {
    event.preventDefault?.();
    first.focus?.();
    return true;
  }

  return false;
}

export function isolateCommunityModalBackground(
  documentLike = globalThis.document,
  { includePortalLayers = true } = {},
) {
  const appRoot = documentLike?.getElementById?.("root");
  const portalLayers = includePortalLayers
    ? [...(documentLike?.querySelectorAll?.("[data-community-modal-background]") || [])]
    : [];
  const targets = [...new Set([appRoot, ...portalLayers].filter(Boolean))];
  if (!targets.length) return () => {};

  const previousState = targets.map((target) => ({
    ariaHidden: target.getAttribute?.("aria-hidden"),
    inert: Boolean(target.inert),
    target,
  }));

  previousState.forEach(({ target }) => {
    target.inert = true;
    target.setAttribute?.("aria-hidden", "true");
  });

  return () => {
    previousState.forEach(({ ariaHidden, inert, target }) => {
      target.inert = inert;
      if (ariaHidden == null) target.removeAttribute?.("aria-hidden");
      else target.setAttribute?.("aria-hidden", ariaHidden);
    });
  };
}
