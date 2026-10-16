export function buildPilotCalendarSummary(calendar) {
  return {
    ...calendar,
    saint: {
      ...calendar.saint,
      biography: [],
      biographySource: "",
      sourceLabel: "",
      sourceUrl: "",
      otherSaints: (calendar.saint.otherSaints || []).filter(
        name => name !== calendar.saint.label.split(",")[0].trim(),
      ),
    },
  };
}
