import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";

const root = join(dirname(fileURLToPath(import.meta.url)), "..", "android", "app", "src");
const read = path => readFileSync(join(root, path), "utf8");

test("retired private enrollment plugin is absent from every Android source set", () => {
  const main = JSON.parse(read("main/assets/capacitor.plugins.json"));
  const pilot = JSON.parse(read("localPilot/assets/capacitor.plugins.json"));
  assert.equal(main.some(item => item.classpath.includes("PilotCommunityAuth")), false);
  assert.equal(pilot.some(item => item.classpath.includes("PilotCommunityAuth")), false);
  assert.doesNotMatch(read("main/java/com/meteofriul/app/MainActivity.java"), /PilotCommunityAuth/);
  for (const relative of [
    "localPilot/java/com/meteofriul/app/pilot/PilotCommunityAuthCore.java",
    "localPilot/java/com/meteofriul/app/pilot/PilotCommunityAuthPlugin.java",
    "testLocalPilot/java/com/meteofriul/app/pilot/PilotCommunityAuthCoreTest.java",
    "testLocalPilot/java/com/meteofriul/app/pilot/PilotCommunityAuthUnitTest.java",
  ]) assert.equal(existsSync(join(root, relative)), false);
});
