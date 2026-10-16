import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import viteConfig from "../vite.config.js";

const read = (path) => readFileSync(new URL(path, import.meta.url), "utf8");
const APP_NAME = "Meteo Friûl";

test("pilot browser title and installable name match the Android launcher", () => {
  const html = read("../index.html");
  const config = viteConfig({ command: "serve", mode: "local-pilot" });
  const branded = config.plugins.find((plugin) => plugin.name === "pilot-brand-head").transformIndexHtml(html);
  assert.ok(branded.includes(`<title>${APP_NAME}</title>`));
  assert.ok(branded.includes(`name="apple-mobile-web-app-title" content="${APP_NAME}"`));
  assert.ok(branded.includes('href="/manifest.webmanifest"'));
  assert.ok(branded.includes('href="/apple-touch-icon-mf-r5-20260927.png"'));
  assert.ok(!branded.includes("pilot-text"));
  assert.ok(!branded.includes("Meteo Eventi"));

  const manifest = JSON.parse(read("../public/manifest.webmanifest"));
  assert.equal(manifest.name, APP_NAME);
  assert.equal(manifest.short_name, APP_NAME);
  const android = read("../android/app/src/localPilot/res/values/strings.xml");
  assert.ok(android.includes(`<string name="app_name">${APP_NAME}</string>`));
  assert.ok(android.includes(`<string name="title_activity_main">${APP_NAME}</string>`));
});
