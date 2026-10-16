const PRIMARY_MEMORY_ROLES = new Set(["exact-date-memory", "rotation-memory"]);

function getFirstCard(section) {
  return Array.isArray(section?.cards) ? section.cards.find(Boolean) || null : null;
}

export function selectHomeDiscoverPreview(discoverModel) {
  const sections = Array.isArray(discoverModel?.sections) ? discoverModel.sections : [];
  const memorySection = sections.find((section) => (
    PRIMARY_MEMORY_ROLES.has(section?.role) && getFirstCard(section)
  ));
  const fallbackSection = sections.find((section) => section?.id === "archive")
    || sections.find((section) => getFirstCard(section));
  const section = memorySection || fallbackSection;
  const card = getFirstCard(section);

  if (!card) return null;

  return {
    ...card,
    heading: String(section?.title || "").trim(),
  };
}
