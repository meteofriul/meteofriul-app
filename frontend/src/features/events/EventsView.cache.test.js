import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

const currentDir = dirname(fileURLToPath(import.meta.url));
const source = readFileSync(join(currentDir, "EventsView.jsx"), "utf8");

describe("EventsView cache ownership", () => {
  it("does not fetch or cache local events directly", () => {
    expect(source).not.toContain("/local/events");
    expect(source).not.toMatch(/\bfetch\s*\(/);
    expect(source).not.toContain("localStorage");
  });
});
