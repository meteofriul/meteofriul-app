import { getPilotWhyContentById, getPilotWhyContentForDate } from "./pilotWhyContent";

export function createPilotWhyVisit(requestedId = "") {
  return { selectedId: String(requestedId || "").trim() };
}

export function getPilotWhyContentForVisit({ date = new Date(), language = "it", visit } = {}) {
  return getPilotWhyContentById(language, visit?.selectedId)
    || getPilotWhyContentForDate(language, date);
}
