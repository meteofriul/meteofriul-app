import test from "node:test";
import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";

const root = new URL("../", import.meta.url);
const html = readFileSync(new URL("index.html", root), "utf8");
const head = html.match(/<head>([\s\S]*?)<\/head>/)?.[1] ?? "";
const meta = (name) => {
  const matches = [...head.matchAll(/<meta (?:name|property)="([^"]+)" content="([^"]*)"\s*\/>/g)]
    .filter((match) => match[1] === name);
  assert.equal(matches.length, 1, `Exactly one static ${name} tag`);
  return matches[0][2];
};

test("social crawlers receive web-app metadata without executing JavaScript", () => {
  assert.equal(meta("og:type"), "website");
  assert.equal(meta("og:locale"), "it_IT");
  assert.equal(meta("og:site_name"), "Meteo Friûl");
  assert.equal(meta("og:url"), "https://meteofriul.app/");
  assert.equal(meta("og:title"), "Meteo Friûl — Meteo ed Eventi per il tempo libero");
  assert.equal(meta("twitter:title"), meta("og:title"));
  assert.match(meta("og:description"), /^Apri la web app:/);
  assert.equal(meta("twitter:description"), meta("og:description"));
  assert.equal(meta("twitter:card"), "summary_large_image");
});

test("OG and Twitter use the same versioned, local 1200×630 opaque PNG", () => {
  const imageUrl = new URL(meta("og:image"));
  assert.equal(imageUrl.href, "https://meteofriul.app/social-preview.png?v=20261021");
  assert.equal(meta("twitter:image"), imageUrl.href);
  assert.equal(meta("og:image:type"), "image/png");
  assert.equal(meta("og:image:width"), "1200");
  assert.equal(meta("og:image:height"), "630");
  assert.equal(meta("twitter:image:alt"), meta("og:image:alt"));
  assert.match(meta("og:image:alt"), /meteofriul\.app/);

  const png = readFileSync(new URL(`public${imageUrl.pathname}`, root));
  assert.equal(png.subarray(0, 8).toString("hex"), "89504e470d0a1a0a");
  assert.equal(png.readUInt32BE(16), 1200);
  assert.equal(png.readUInt32BE(20), 630);
  assert.equal(png[25], 2, "RGB PNG without an alpha channel");
});

test("editable source has a full-bleed background and reuses official artwork", () => {
  const svg = readFileSync(new URL("public/social-preview.svg", root), "utf8");
  assert.match(svg, /<rect width="1200" height="630" fill="url\(#background\)"\/>/);
  assert.match(svg, />meteofriul\.app<\/text>/);
  const icon = svg.match(/<image xlink:href="([^"]+)"/)?.[1];
  assert.equal(icon, "branding/icon_launcher_any_mf-r5-20260927-512.png");
  assert.ok(existsSync(new URL(`public/${icon}`, root)));
});
