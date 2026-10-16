import { writeFile } from "node:fs/promises";
import { resolve } from "node:path";

import { FIXED_FVG_PLACES } from "../frontend/src/data/fvgPlaces.js";

const outputPath = resolve(process.argv[2] || "tmp/community-report-locations.json");
const bounds = {
  latMax: 46.72,
  latMin: 45.52,
  lonMax: 14.08,
  lonMin: 12.24,
};
const clamp = (value) => Math.min(100, Math.max(0, value));
const locations = Object.values(FIXED_FVG_PLACES)
  .map((place) => {
    const lat = Number(place.latitude);
    const lon = Number(place.longitude);

    return {
      place: place.name,
      lat,
      lon,
      x: Number(clamp(((lon - bounds.lonMin) / (bounds.lonMax - bounds.lonMin)) * 100).toFixed(2)),
      y: Number(clamp(((bounds.latMax - lat) / (bounds.latMax - bounds.latMin)) * 100).toFixed(2)),
    };
  })
  .filter((location) => location.place && Number.isFinite(location.lat) && Number.isFinite(location.lon))
  .sort((first, second) => first.place.localeCompare(second.place, "it"));

await writeFile(outputPath, `${JSON.stringify(locations, null, 2)}\n`, "utf8");
console.log(`Esportate ${locations.length} localita in ${outputPath}`);
