import { describe, expect, it } from "vitest";
import { buildEventRecord, groupEventOccurrences, rankEventsForLocation } from "./eventsViewModel";

const now = new Date(2026, 8, 7);
const make = (patch = {}) => buildEventRecord({
  id: "a", title: "Festeggiamenti di S. Angelo", date: "12 settembre 2026",
  event_city: "Porcia", venue: "S. Angelo", url: "https://example.org/eventi/s-angelo",
  ...patch,
}, { now });

describe("event occurrence identity", () => {
  it("preserves distinct times and retains dates outside the selected tab in detail", () => {
    const first = make({ time: "18:00" });
    const second = make({ id: "b", time: "21:00" });
    const next = make({ id: "c", date: "13 settembre 2026", time: "18:00" });
    expect(rankEventsForLocation([first, second], { now })).toHaveLength(2);
    const groups = groupEventOccurrences([next], [first, second, next]);
    expect(groups).toHaveLength(1);
    expect(groups[0].occurrences).toHaveLength(3);
    expect(groups[0].visibleOccurrences).toEqual([next]);
  });
  it("groups dates with the same detail source and preserves both payloads", () => {
    const items = [make(), make({ id: "b", date: "13 settembre 2026", start_time: "18:00" })];
    const grouped = groupEventOccurrences(items);
    expect(grouped).toHaveLength(1);
    expect(grouped[0].occurrences).toEqual(items);
    expect(items[0].occurrences).toBeUndefined();
  });
  it("does not merge namesakes, different venues, or missing sources", () => {
    expect(groupEventOccurrences([make(), make({ event_city: "Udine" }), make({ venue: "Piazza" }), make({ url: "" }), make({ url: "https://example.org/another" })])).toHaveLength(5);
  });
  it("keeps namesakes in different towns during duplicate removal", () => {
    expect(rankEventsForLocation([make(), make({ event_city: "Udine" })], { now })).toHaveLength(2);
  });
});
