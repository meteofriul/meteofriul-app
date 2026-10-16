import { readFileSync, readdirSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

const uiRoot = path.dirname(fileURLToPath(import.meta.url));
const sourceRoot = path.dirname(uiRoot);

function cssFiles(directory) {
  return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const absolute = path.join(directory, entry.name);
    if (entry.isDirectory()) return cssFiles(absolute);
    return entry.isFile() && entry.name.endsWith(".css") ? [absolute] : [];
  });
}

describe("edge-to-edge safe areas", () => {
  it("provides browser fallbacks for every native inset", () => {
    const base = readFileSync(path.join(uiRoot, "base.css"), "utf8");

    for (const edge of ["top", "right", "bottom", "left"]) {
      expect(base).toContain(
        `--mf-safe-area-inset-${edge}: var(--safe-area-inset-${edge}, env(safe-area-inset-${edge}, 0px))`,
      );
    }
  });

  it("routes application safe-area geometry through the native-compatible aliases", () => {
    const offenders = cssFiles(sourceRoot)
      .filter((file) => path.basename(file) !== "base.css")
      .filter((file) => /env\(safe-area-inset-(?:top|right|bottom|left)\)/.test(
        readFileSync(file, "utf8"),
      ))
      .map((file) => path.relative(sourceRoot, file));

    expect(offenders).toEqual([]);
  });
});
