import { describe, expect, it } from "vitest";
import { countIconFutureHours, selectIconFutureRows } from "./iconForecastWindow";

const HOUR = 3_600_000;
const START = Date.parse("2026-09-08T00:00:00Z");
const rows = Array.from({ length: 73 }, (_, i) => ({
  valid_at: new Date(START + i * HOUR).toISOString(), temperature_c: i,
}));

describe("pilot ICON real future window", () => {
  it.each([48, 37, 36, 24, 12, 11])("selects exactly %i real future rows", (count) => {
    const now = START + (73 - count) * HOUR;
    const selected = selectIconFutureRows(rows, now);
    expect(selected).toHaveLength(count);
    expect(countIconFutureHours(rows.at(-1).valid_at, now)).toBe(count);
    expect(selected.every(row => rows.includes(row) && Date.parse(row.valid_at) >= now)).toBe(true);
    expect(new Set(selected.map(row => row.valid_at)).size).toBe(count);
  });

  it("caps at 48, excluding a past sample even within the current clock hour", () => {
    const now = START + 30 * 60_000;
    const selected = selectIconFutureRows(rows, now);
    expect(selected).toHaveLength(48);
    expect(selected[0]).toBe(rows[1]);
  });

  it("crosses an hour without retaining or duplicating its past sample", () => {
    const boundary = START + 61 * HOUR;
    expect(selectIconFutureRows(rows, boundary - 1)).toHaveLength(12);
    expect(selectIconFutureRows(rows, boundary)).toHaveLength(12);
    expect(selectIconFutureRows(rows, boundary + 1)).toHaveLength(11);
  });

  it("rejects duplicates, gaps, invalid timestamps and non-hour samples without repair", () => {
    for (const damaged of [
      [rows[0], rows[0], ...rows.slice(1)],
      [rows[0], ...rows.slice(2)],
      [{ valid_at: "invalid" }, ...rows.slice(1)],
      [{ valid_at: new Date(START + 1).toISOString() }, ...rows.slice(1)],
    ]) expect(selectIconFutureRows(damaged, START)).toEqual([]);
  });
});
