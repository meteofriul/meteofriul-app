// Requires the backend Python dependencies as well as npm ci.
// Standalone integration check: no listener, collection or cloud calls.
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { after, before, describe, it } from "node:test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { createServer } from "vite";

let server, payloads, fetchLocalEvents, PILOT_EVENTS_API, buildEventRecord, EventPreviewPanel, getEventsViewCopy;
before(async () => {
  const root = fileURLToPath(new URL("../", import.meta.url));
  const backend = fileURLToPath(new URL("../../backend/", import.meta.url));
  payloads = JSON.parse(execFileSync(process.env.PYTHON || "python", ["-X", "utf8", "-B", "tests/test_pilot_opening_days.py", "--http-fixtures"], {
    cwd: backend, env: { ...process.env, PYTHONPATH: backend, PYTHONDONTWRITEBYTECODE: "1" },
    encoding: "utf8", timeout: 20000,
  }));
  server = await createServer({ root, configFile: root + "vite.config.js", configLoader: "native",
    server: { middlewareMode: true, watch: null }, appType: "custom", logLevel: "error" });
  ({ fetchLocalEvents, PILOT_EVENTS_API } = await server.ssrLoadModule("/src/services/eventsApi.js"));
  ({ buildEventRecord } = await server.ssrLoadModule("/src/features/events/eventsViewModel.js"));
  ({ EventPreviewPanel } = await server.ssrLoadModule("/src/features/events/EventsView.jsx"));
  ({ getEventsViewCopy } = await server.ssrLoadModule("/src/copy/eventsViewCopy.js"));
});
after(async () => { await server?.close(); });

describe("EV-01 source → catalogue → dedup → HTTP → preview", () => {
  for (const order of ["official_first", "regional_first"]) {
    it(`keeps opening evidence with ${order}`, async () => {
      for (const kind of ["unknown", "legacy_official", "daily", "explicit_days"]) {
        const payload = payloads[`${kind}_${order}`];
        assert.equal(payload.total, 1);
        const response = await fetchLocalEvents({ city: "Gradisca d'Isonzo", lat: 45.89, lon: 13.5 }, {
          apiBase: PILOT_EVENTS_API, fetchImpl: async () => ({ ok: true, json: async () => payload }),
        });
        const event = buildEventRecord(response.events[0], { now: new Date(2026, 9, 19, 12) });
        assert.equal(event.raw.source, "Galleria Spazzapan");
        const html = renderToStaticMarkup(createElement(EventPreviewPanel, {
          event, copy: getEventsViewCopy("it"), onClose() {},
        }));
        if (["unknown", "legacy_official"].includes(kind)) {
          assert.equal(event.timeCategory, "next");
          assert.match(html, /Giornate di apertura da verificare/);
        } else if (kind === "daily") {
          assert.equal(event.timeCategory, "today");
          assert.equal(event.scheduleLabel, "");
        } else {
          assert.notEqual(event.timeCategory, "today");
          assert.equal(buildEventRecord(response.events[0], { now: new Date(2026, 9, 21, 12) }).timeCategory, "today");
        }
      }
    });
  }
});
