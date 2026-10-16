import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

import {
  FIXED_FVG_PLACES,
  FVG_PLACES_SOURCE,
} from "../frontend/src/data/fvgPlaces.js";

const scriptDirectory = path.dirname(fileURLToPath(import.meta.url));
const workspaceRoot = path.resolve(scriptDirectory, "..");
const outputPath = path.join(
  workspaceRoot,
  "backend",
  "app",
  "data",
  "fvg_municipalities.json",
);

const municipalities = Object.entries(FIXED_FVG_PLACES)
  .map(([slug, place]) => ({
    slug,
    name: String(place.name || "").trim(),
    admin1: String(place.admin1 || "Friuli Venezia Giulia").trim(),
    province: String(place.province || "").trim(),
    provinceName: String(place.provinceName || "").trim(),
    istatCode: String(place.istatCode || "").trim(),
    latitude: Number(place.latitude),
    longitude: Number(place.longitude),
  }))
  .sort((first, second) => first.istatCode.localeCompare(second.istatCode));

if (municipalities.length !== FVG_PLACES_SOURCE.count) {
  throw new Error(
    `Catalogo Comuni incoerente: attesi ${FVG_PLACES_SOURCE.count}, trovati ${municipalities.length}`,
  );
}

for (const municipality of municipalities) {
  if (
    !municipality.name ||
    !municipality.province ||
    !municipality.istatCode ||
    !Number.isFinite(municipality.latitude) ||
    !Number.isFinite(municipality.longitude)
  ) {
    throw new Error(`Comune non esportabile: ${JSON.stringify(municipality)}`);
  }
}

const payload = {
  schemaVersion: 1,
  generatedFrom: "frontend/src/data/fvgPlaces.js",
  source: FVG_PLACES_SOURCE,
  municipalities,
};

await mkdir(path.dirname(outputPath), { recursive: true });
await writeFile(outputPath, `${JSON.stringify(payload, null, 2)}\n`, "utf8");

console.log(`Esportati ${municipalities.length} Comuni in ${outputPath}`);
