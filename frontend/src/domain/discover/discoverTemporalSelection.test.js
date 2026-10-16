import { describe, expect, it } from "vitest";

import {
  getDiscoverRecordSeasons,
  getDiscoverSeason,
  getDiscoverSeasonForRecord,
  getDiscoverTemporalRank,
  getGregorianEasterDateKey,
  getGregorianEasterRelativeDateKey,
  matchesDiscoverMovableDate,
  matchesDiscoverMovableDateRange,
  matchesDiscoverNthWeekdayDate,
  pickDiscoverTemporalRecord,
} from "./discoverTemporalSelection";

describe("discover temporal selection", () => {
  it.each([
    [2026, "10-04"], [2027, "10-03"], [2028, "10-01"],
    [2029, "10-07"], [2030, "10-06"], [2031, "10-05"],
  ])("matches only the first October Sunday in %i", (year, expected) => {
    const record = { nthWeekdayDates: [{ month: 10, weekday: 0, ordinal: 1 }] };
    const matches = [];
    for (let day = 1; day <= 31; day += 1) {
      const date = `${year}-10-${String(day).padStart(2, "0")}`;
      if (getDiscoverTemporalRank(record, date) === 1) matches.push(date);
    }
    expect(matches).toEqual([`${year}-${expected}`]);
    expect(getDiscoverTemporalRank(record, `${year}-09-30`)).toBeNull();
    expect(getDiscoverTemporalRank(record, `${year}-11-01`)).toBeNull();
  });

  it("handles the fifth weekday only when present, including leap day", () => {
    const sunday = { nthWeekdayDates: [{ month: 2, weekday: 0, ordinal: 5 }] };
    expect(matchesDiscoverNthWeekdayDate(sunday, "2026-02-22")).toBe(false);
    expect(matchesDiscoverNthWeekdayDate(sunday, "2026-03-01")).toBe(false);
    expect(matchesDiscoverNthWeekdayDate(sunday, "2032-02-29")).toBe(true);
    const tuesday = { nthWeekdayDates: [{ month: 2, weekday: 2, ordinal: 5 }] };
    expect(getDiscoverTemporalRank(tuesday, "2028-02-29")).toBe(1);
    expect(getDiscoverTemporalRank(tuesday, "2027-02-29")).toBeNull();
    expect(getDiscoverTemporalRank(tuesday, "2028-03-07")).toBeNull();
  });

  it("validates ordinal fields as integers without coercion or generic fallback", () => {
    const good = { month: 10, weekday: 0, ordinal: 1 };
    const invalidRules = [
      null, [], {}, "first Sunday", [null], [{}],
      ...[0, 13, 1.5, "10", NaN].map((month) => [{ ...good, month }]),
      ...[-1, 7, 0.5, "0", null].map((weekday) => [{ ...good, weekday }]),
      ...[0, 6, 1.5, "1", undefined].map((ordinal) => [{ ...good, ordinal }]),
      [good, { ...good, month: 13 }],
    ];
    invalidRules.forEach((nthWeekdayDates) => {
      [undefined, "always", "seasonal"].forEach((recurrence) => {
        const record = { nthWeekdayDates, recurrence, months: [10], seasons: ["autunno"] };
        expect(matchesDiscoverNthWeekdayDate(record, "2028-10-01")).toBe(false);
        expect(getDiscoverTemporalRank(record, "2028-10-01")).toBeNull();
      });
    });
    expect(getDiscoverTemporalRank({ nthWeekdayDates: [good], recurrence: "always" }, "2028-10-02"))
      .toBeNull();
    ["not-a-date", "2028-10-32", "2028-13-01", new Date(NaN)].forEach((date) => {
      expect(matchesDiscoverNthWeekdayDate({ nthWeekdayDates: [good] }, date)).toBe(false);
    });
  });

  it("preserves fixed dates, Easter and ranges while ranking ordinal dates above intervals", () => {
    const ordinal = { id: "ordinal", nthWeekdayDates: [{ month: 4, weekday: 0, ordinal: 1 }] };
    expect(getDiscoverTemporalRank({ ...ordinal, dateAnchors: ["04-05"] }, "2026-04-05")).toBe(0);
    expect(getDiscoverTemporalRank({ ...ordinal, movableDates: ["easter"] }, "2027-03-28")).toBe(1);
    expect(getDiscoverTemporalRank({ ...ordinal, dateRanges: ["04-01..04-10"] }, "2026-04-06")).toBe(2);
    expect(getDiscoverTemporalRank(ordinal, "2026-04-05")).toBe(1);
    const broader = { id: "range", dateRanges: ["04-01..04-10"] };
    expect(pickDiscoverTemporalRecord([broader, ordinal], "2026-04-05", { blendBroader: true }))
      .toBe(ordinal);
    const exact = { id: "exact", dateAnchors: ["04-05"] };
    expect(pickDiscoverTemporalRecord([ordinal, broader, exact], "2026-04-05"))
      .toBe(exact);
  });

  it("supports multiple valid rules and leaves frozen input unchanged", () => {
    const rules = Object.freeze([
      Object.freeze({ month: 10, weekday: 0, ordinal: 1 }),
      Object.freeze({ month: 7, weekday: 0, ordinal: 1 }),
    ]);
    const record = Object.freeze({ nthWeekdayDates: rules });
    const date = new Date(2028, 9, 1, 12);
    const before = date.getTime();
    expect(matchesDiscoverNthWeekdayDate(record, date)).toBe(true);
    expect(matchesDiscoverNthWeekdayDate(record, "2028-07-02")).toBe(true);
    expect(date.getTime()).toBe(before);
    expect(record.nthWeekdayDates).toBe(rules);
  });

  it("calculates Easter and Palm Sunday for the selected year", () => {
    expect(getGregorianEasterDateKey(2026)).toBe("04-05");
    expect(matchesDiscoverMovableDate(
      { movableDates: ["easter"] },
      "2026-04-05",
    )).toBe(true);
    expect(matchesDiscoverMovableDate(
      { movableDates: ["easter_relative"] },
      "2026-03-29",
    )).toBe(true);
    expect(getGregorianEasterRelativeDateKey(2026, -52)).toBe("02-12");
  });

  it("matches movable periods without hard-coding Carnival or Holy Week dates", () => {
    const finalCarnivalDays = {
      movableDateRanges: [{
        anchor: "easter",
        startOffsetDays: -52,
        endOffsetDays: -47,
      }],
    };
    const holyTriduum = {
      movableDateRanges: [{
        anchor: "easter",
        startOffsetDays: -3,
        endOffsetDays: -1,
      }],
    };

    expect(matchesDiscoverMovableDateRange(finalCarnivalDays, "2026-02-12")).toBe(true);
    expect(matchesDiscoverMovableDateRange(finalCarnivalDays, "2026-02-17")).toBe(true);
    expect(matchesDiscoverMovableDateRange(finalCarnivalDays, "2026-02-18")).toBe(false);
    expect(matchesDiscoverMovableDateRange(holyTriduum, "2026-04-02")).toBe(true);
    expect(matchesDiscoverMovableDateRange(holyTriduum, "2026-04-04")).toBe(true);
    expect(matchesDiscoverMovableDateRange(holyTriduum, "2026-04-05")).toBe(false);
    expect(getDiscoverTemporalRank(finalCarnivalDays, "2026-02-14")).toBe(2);
  });

  it("ranks exact, movable, range, seasonal and evergreen records in order", () => {
    const date = "2026-04-05";

    expect(getDiscoverTemporalRank({ dateAnchors: ["04-05"] }, date)).toBe(0);
    expect(getDiscoverTemporalRank({ movableDates: ["easter"] }, date)).toBe(1);
    expect(getDiscoverTemporalRank({ dateRanges: ["04-01..04-10"] }, date)).toBe(2);
    expect(getDiscoverTemporalRank({ recurrence: "seasonal", seasons: ["primavera"] }, date)).toBe(3);
    expect(getDiscoverTemporalRank({ recurrence: "always" }, date)).toBe(4);
  });

  it("supports date ranges crossing the end of the year", () => {
    const record = { dateRanges: ["12-26..01-06"] };

    expect(getDiscoverTemporalRank(record, "2026-01-02")).toBe(2);
    expect(getDiscoverTemporalRank(record, "2026-07-02")).toBeNull();
  });

  it("does not rotate weather-bound or out-of-season records without context", () => {
    expect(getDiscoverTemporalRank(
      { recurrence: "weather", seasons: ["all"] },
      "2026-07-11",
    )).toBeNull();
    expect(getDiscoverTemporalRank(
      { recurrence: "seasonal", seasons: ["inverno"] },
      "2026-07-11",
    )).toBeNull();
    expect(getDiscoverSeason("2026-07-11")).toBe("estate");
  });

  it("uses declared months as a hard context after exact dates", () => {
    const record = {
      dateAnchors: ["01-02"],
      months: ["09"],
    };

    expect(getDiscoverTemporalRank(record, "2026-01-02")).toBe(0);
    expect(getDiscoverTemporalRank(record, "2026-09-10")).toBe(3);
    expect(getDiscoverTemporalRank(record, "2026-07-10")).toBeNull();
  });

  it("normalizes season aliases and ignores all when explicit seasons exist", () => {
    const record = {
      recurrence: "seasonal",
      seasons: ["spring", "summer", "all"],
    };

    expect(getDiscoverRecordSeasons(record)).toEqual(["primavera", "estate"]);
    expect(getDiscoverTemporalRank(record, "2026-07-11")).toBe(3);
    expect(getDiscoverTemporalRank(record, "2026-01-11")).toBeNull();
    expect(getDiscoverSeasonForRecord(record, "2026-07-11")).toBe("estate");
  });

  it("rotates exact-date conflicts deterministically across years", () => {
    const records = [
      { id: "first", dateAnchors: ["01-06"], priority: 1 },
      { id: "second", dateAnchors: ["01-06"], priority: 2 },
    ];

    expect(pickDiscoverTemporalRecord(records, "2028-01-06")?.id).toBe("first");
    expect(pickDiscoverTemporalRecord(records, "2029-01-06")?.id).toBe("second");
  });

  it("does not permanently hide candidates sharing the same short interval", () => {
    const records = ["first", "second", "third"].map((id, index) => ({
      id,
      dateRanges: ["06-23..06-24"],
      priority: index + 1,
    }));
    const selectedAcrossYears = new Set([2028, 2029, 2030].flatMap((year) => [
      pickDiscoverTemporalRecord(records, `${year}-06-23`)?.id,
      pickDiscoverTemporalRecord(records, `${year}-06-24`)?.id,
    ]));

    expect([...selectedAcrossYears].sort()).toEqual(["first", "second", "third"]);
  });

  it("blends broader material into long seasonal intervals without overriding exact dates", () => {
    const records = [
      { id: "seasonal", recurrence: "seasonal", seasons: ["estate"], priority: 1 },
      { id: "general-a", recurrence: "always", priority: 2 },
      { id: "general-b", recurrence: "always", priority: 3 },
      { id: "exact", dateAnchors: ["06-03"], priority: 4 },
    ];
    const selected = ["06-01", "06-02", "06-03", "06-04"].map((day) => (
      pickDiscoverTemporalRecord(records, `2028-${day}`, { blendBroader: true })?.id
    ));

    expect(selected[2]).toBe("exact");
    expect(selected).toContain("seasonal");
    expect(selected.some((id) => id.startsWith("general-"))).toBe(true);
  });

  it("changes the broad daily rotation across years while remaining deterministic", () => {
    const records = ["first", "second", "third"].map((id, index) => ({
      id,
      recurrence: "always",
      priority: index + 1,
    }));

    const firstRun = pickDiscoverTemporalRecord(records, "2028-05-10")?.id;
    const repeatedRun = pickDiscoverTemporalRecord(records, "2028-05-10")?.id;
    const followingYear = pickDiscoverTemporalRecord(records, "2029-05-10")?.id;

    expect(repeatedRun).toBe(firstRun);
    expect(followingYear).not.toBe(firstRun);
  });
});
