import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import { fetchLocalEvents, PILOT_EVENTS_API } from "../../services/eventsApi";
import { getEventsViewCopy } from "../../copy/eventsViewCopy";
import { buildEventRecord, groupEventOccurrences } from "./eventsViewModel";
import { EventPreviewPanel } from "./EventsView";

const now = new Date(2026, 9, 15, 12);
const location = { city: "Udine", lat: 46.0635, lon: 13.2358 };

async function fromApi(fields) {
  const card = {
    title: "Evento", source: "TurismoFVG", event_city: "Udine",
    url: "https://www.turismofvg.it/eventi/prova", ...fields,
  };
  const fetchImpl = vi.fn(async () => ({ ok: true, json: async () => ({
    events: [card], total: 1, snapshot: "audit-schedule", next_offset: null,
  }) }));
  const response = await fetchLocalEvents(location, { apiBase: PILOT_EVENTS_API, fetchImpl });
  return buildEventRecord(response.events[0], { now });
}

function preview(event) {
  return renderToStaticMarkup(<EventPreviewPanel event={event}
    copy={getEventsViewCopy("it")} onClose={() => {}} />);
}

describe("event schedule contract, API to preview (EV-01/02/03)", () => {
  it.each([
    ["Barbacan", "2026-04-12", "2026-12-13", "TurismoFVG"],
    ["Julia", "2026-01-25", "2026-12-13", "TurismoFVG"],
    ["Aurisina", "2026-04-18", "2026-10-17", "TurismoFVG"],
    ["Polcenigo", "2026-09-26", "2026-10-18", "SagreFVG"],
  ])("does not claim today's opening from the %s period", async (title, start_date, end_date, source) => {
    const event = await fromApi({ title, start_date, end_date, source,
      schedule_kind: "period", opening_days_status: "unknown" });
    expect(event.timeCategory).toBe("next");
    expect(event.scheduleLabel).toBe("Giornate di apertura da verificare");
    expect(preview(event)).toContain("Giornate di apertura da verificare");
  });

  it.each(["TurismoFVG", "SagreFVG", "Galleria Spazzapan"])("handles older %s catalogues without a daily-opening claim", async (source) => {
    const event = await fromApi({ source, start_date: "2026-10-01", end_date: "2026-10-18",
      ...(source === "TurismoFVG" ? { schedule_kind: "period" } : {}) });
    expect(event.timeCategory).toBe("next");
  });

  it("keeps uncertainty for an older duplicate whose preferred source changed", async () => {
    const event = await fromApi({ source: "Paesi in Festa", alternate_sources: ["SagreFVG"],
      start_date: "2026-10-01", end_date: "2026-10-18" });
    expect(event.timeCategory).toBe("next");
    expect(preview(event)).toContain("Giornate di apertura da verificare");
  });

  it("uses explicit days in preference to the encompassing period", async () => {
    const event = await fromApi({ start_date: "2026-09-26", end_date: "2026-10-18",
      schedule_kind: "explicit_dates", occurrences: ["2026-09-26", "2026-10-17", "2026-10-18"] });
    expect(event.timeCategory).toBe("weekend");
    expect(buildEventRecord(event.raw, { now: new Date(2026, 9, 17, 12) }).timeCategory).toBe("today");
    expect(buildEventRecord(event.raw, { now: new Date(2026, 9, 19, 12) }).timeCategory).toBe("outside");
  });

  it("preserves verified daily openings and hides expired or distant unknown periods", async () => {
    const daily = await fromApi({ start_date: "2026-10-01", end_date: "2026-10-31",
      schedule_kind: "period", opening_days_status: "daily" });
    expect(daily.timeCategory).toBe("today");
    expect(daily.scheduleLabel).toBe("");
    for (const [start_date, end_date] of [["2026-09-01", "2026-10-14"], ["2027-01-01", "2027-01-31"]]) {
      const event = await fromApi({ start_date, end_date, schedule_kind: "period", opening_days_status: "unknown" });
      expect(event.timeCategory).toBe("outside");
    }
  });

  it("keeps uncertain opening information in Furlan without changing the dates", () => {
    const event = buildEventRecord({ title: "Mercjât", source: "TurismoFVG",
      date: "1 ottobre 2026 - 31 ottobre 2026", start_date: "2026-10-01",
      end_date: "2026-10-31", schedule_kind: "period", opening_days_status: "unknown",
    }, { now, language: "fur" });
    expect(event.timeCategory).toBe("next");
    expect(event.scheduleLabel).toBe("Zornadis di vierzidure di verificâ");
    expect(event.raw.start_date).toBe("2026-10-01");
  });

  it.each(["17:00", "20:30", "00:00"])("shows a single verified time %s", async (time) => {
    const event = await fromApi({ start_date: "2026-10-15", end_date: "2026-10-15", time });
    expect(preview(event)).toContain(`>${time}</span>`);
  });

  it("shows a verified time range without inventing an end or a missing start", async () => {
    const event = await fromApi({ start_date: "2026-10-15", time: "18:00", end_time: "21:00" });
    expect(preview(event)).toContain("18:00–21:00");
    for (const fields of [{}, { time: "invalid" }, { time: "25:30" }, { end_time: "21:00" }]) {
      const missing = await fromApi({ start_date: "2026-10-15", ...fields });
      expect(preview(missing)).not.toContain('data-testid="event-preview-time"');
    }
  });

  it("keeps each grouped performance time without an extra single time", () => {
    const events = ["18:00", "21:00"].map(time => buildEventRecord({
      title: "Spettacolo", date: "15 ottobre 2026", time,
      event_city: "Udine", venue: "Teatro",
      id: time, url: "https://www.azalea.it/eventi/prova/", source: "Azalea",
    }, { now }));
    const [grouped] = groupEventOccurrences(events);
    const html = preview(grouped);
    expect(html).toContain("18:00");
    expect(html).toContain("21:00");
    expect(html).not.toContain('data-testid="event-preview-time"');
  });

  it("keeps an end-only exhibition as a deadline through API adaptation", async () => {
    const event = await fromApi({ title: "Memorie riflesse", start_date: null,
      end_date: "2027-01-07", schedule_kind: "end_only", date_label: "Fino al 7 gennaio 2027" });
    expect(event.raw.start_date).toBeNull();
    expect(event.dateChip.start).toBeUndefined();
    expect(event.timeCategory).toBe("next");
    expect(preview(event)).toContain("Fino al 7 gennaio 2027");
  });
});
