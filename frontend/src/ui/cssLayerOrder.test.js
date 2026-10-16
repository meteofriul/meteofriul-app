import { readFileSync } from "node:fs";

import { describe, expect, it } from "vitest";

const readSource = (path) => readFileSync(new URL(path, import.meta.url), "utf8");

describe("application CSS layer order", () => {
  it("loads the CSS entry before App can import component styles", () => {
    const main = readSource("../main.jsx");
    const cssImport = main.indexOf('import "./ui/index.css";');
    const appImport = main.indexOf('import App from "./app/App.jsx";');

    expect(cssImport).toBeGreaterThanOrEqual(0);
    expect(appImport).toBeGreaterThan(cssImport);
  });

  it("declares the layer order before importing any stylesheet", () => {
    const css = readSource("./index.css");

    expect(css.trimStart()).toMatch(
      /^@layer reset, tokens, base, layout, components, features, utilities;/,
    );
  });

  it("registers webcam styles once in the existing features layer", () => {
    const css = readSource("./index.css");
    const imports = css.match(/@import\s+"[^"\n]*webcamPlayer\.css"[^;]*;/g);

    expect(imports).toEqual([
      '@import "../features/live/webcamPlayer.css" layer(features);',
    ]);
    expect(readSource("../features/live/webcamPlayer.css")).not.toMatch(/@layer\b/);
  });

  it("does not let the webcam component register features before the CSS entry", () => {
    const dialog = readSource("../features/live/WebcamPlayerDialog.jsx");

    expect(dialog).not.toMatch(/import\s+["'][^"']+\.css["']/);
  });
});
