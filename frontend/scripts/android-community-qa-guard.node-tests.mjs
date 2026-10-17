import assert from "node:assert/strict";
import { mkdtempSync, readFileSync, readdirSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import test from "node:test";
import config from "../vite.community-qa.config.js";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");

test("QA rejects serving, wrong modes and unmarked builds", () => {
  const before = process.env.METEO_COMMUNITY_QA_BUILD;
  try {
    delete process.env.METEO_COMMUNITY_QA_BUILD;
    assert.throws(() => config({ command: "build", mode: "android-community-qa" }), /guard_required/);
    process.env.METEO_COMMUNITY_QA_BUILD = "1";
    assert.throws(() => config({ command: "serve", mode: "android-community-qa" }), /guard_required/);
    for (const mode of ["android", "production", "local-pilot", "development"]) {
      assert.throws(() => config({ command: "build", mode }), /guard_required/);
    }
  } finally {
    if (before === undefined) delete process.env.METEO_COMMUNITY_QA_BUILD;
    else process.env.METEO_COMMUNITY_QA_BUILD = before;
  }
});

test("the actual QA Web bundle isolates environment, Firebase and network destinations", { timeout: 90000 }, () => {
  const directory = mkdtempSync(join(tmpdir(), "meteofriul-community-qa-guard-"));
  const sentinel = "qa-environment-contamination-sentinel";
  const env = { ...process.env };
  for (const name of Object.keys(env)) {
    if (name.startsWith("VITE_") || name.startsWith("METEO_PLAY_")) delete env[name];
  }
  Object.assign(env, {
    METEO_COMMUNITY_QA_BUILD: "1",
    VITE_API_BASE: `https://${sentinel}.invalid/api`,
    VITE_ANDROID_API_BASE: `https://${sentinel}.invalid/api`,
    VITE_COMMUNITY_API_BASE: `https://${sentinel}.invalid/api`,
    VITE_FIREBASE_API_KEY: sentinel,
  });
  try {
    const result = spawnSync(process.execPath, [
      join(root, "node_modules/vite/bin/vite.js"), "build", "--mode", "android-community-qa",
      "--config", "vite.community-qa.config.js", "--configLoader", "native", "--outDir", directory,
    ], { cwd: root, env, encoding: "utf8", timeout: 80000 });
    assert.equal(result.status, 0, "isolated QA Web build must succeed");
    const html = readFileSync(join(directory, "qa/community/index.html"), "utf8");
    assert.match(html, /connect-src http:\/\/127\.0\.0\.1:8788;/);
    assert.match(html, /viewport-fit=cover/);
    const assets = readdirSync(join(directory, "assets"));
    const scripts = assets.filter(name => name.endsWith(".js")).map(name => readFileSync(join(directory, "assets", name), "utf8")).join("\n");
    assert.ok(scripts.length > 1000);
    for (const forbidden of [sentinel, "49007668366", "AIza", "meteofriul-community-"]) {
      assert.equal(scripts.includes(forbidden), false, "production or injected configuration reached QA assets");
    }
    assert.ok(scripts.includes("http://127.0.0.1:8788"));
    assert.equal(assets.some(name => name.endsWith(".map")), false);
  } finally {
    // Only the unique directory created by this test can be removed.
    assert.equal(dirname(directory), tmpdir());
    assert.ok(directory.startsWith(join(tmpdir(), "meteofriul-community-qa-guard-")));
    rmSync(directory, { recursive: true, force: true });
  }
});
