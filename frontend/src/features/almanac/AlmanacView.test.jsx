import { renderToStaticMarkup } from "react-dom/server";
import { expect, it } from "vitest";
import { AlmanacView } from "./AlmanacView";

it("keeps one sky card and adds a single day/night line", () => {
  const html = renderToStaticMarkup(<AlmanacView
    copy={{ placeholders: { almanacTitle: "Almanacco" } }}
    date={new Date("2026-09-06T10:00:00Z")}
    now={new Date("2026-09-06T10:00:00Z")}
  />);
  expect(html.match(/class="mf-almanac-sky-card"/g)).toHaveLength(1);
  expect(html.indexOf('class="mf-almanac-sky-card"')).toBeGreaterThan(html.indexOf('class="mf-almanac-date-strip"'));
  expect(html.indexOf('class="mf-almanac-sky-card"')).toBeLessThan(html.indexOf('class="mf-almanac-saint"'));
  expect(html).not.toContain('class="mf-almanac-sun-progress"');
  expect(html).not.toContain('class="mf-almanac-moon-progress"');
  expect(html.match(/role="progressbar"/g)).toHaveLength(1);
  expect(html).toContain('aria-label="Giorno"');
  const sky = html.slice(html.indexOf('class="mf-almanac-sky-card"'), html.indexOf('class="mf-almanac-saint"'));
  expect(sky).not.toContain("<details");
  expect(sky).not.toContain("<summary");
  expect(sky).toContain('class="mf-almanac-sun-orb"');
  expect(sky).toContain('class="mf-almanac-moon-orb"');
  expect(sky).toContain("Età lunare");
  expect(sky).toContain("Prossima:");
});

it("shows the night line in Friulian without confusing it with lunar age", () => {
  const html = renderToStaticMarkup(<AlmanacView copy={{ placeholders: { almanacTitle: "Almanac" } }} language="fur" date={new Date("2026-09-06T01:00:00Z")} now={new Date("2026-09-06T01:00:00Z")} />);
  expect(html).toContain('aria-label="Gnot"');
  expect(html).toContain('mf-almanac-cycle--night');
});
