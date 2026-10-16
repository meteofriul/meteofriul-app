import { WEATHER_SECTION_IDS } from "./weatherSectionNavCopy";

export function weatherSwipeTarget(activeId, dx, dy, elapsed) {
  const index = WEATHER_SECTION_IDS.indexOf(activeId);
  if (index < 0 || Math.abs(dx) < 70 || Math.abs(dx) < Math.abs(dy) * 2 || elapsed > 700) {
    return null;
  }
  return WEATHER_SECTION_IDS[index + (dx < 0 ? 1 : -1)] || null;
}
