const DISCOVER_CARD_ANCHOR_PREFIX = "discover-card-";

export function getDiscoverCardAnchor(cardId) {
  const normalizedId = String(cardId || "").trim();
  return normalizedId ? `${DISCOVER_CARD_ANCHOR_PREFIX}${normalizedId}` : undefined;
}
