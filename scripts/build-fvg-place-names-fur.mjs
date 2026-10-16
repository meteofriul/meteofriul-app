import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const scriptDirectory = path.dirname(fileURLToPath(import.meta.url));
const projectRoot = path.resolve(scriptDirectory, "..");
const sourcePath = path.join(
  projectRoot,
  "frontend",
  "src",
  "data",
  "discover",
  "municipalityProfiles.json",
);
const outputPath = path.join(
  projectRoot,
  "frontend",
  "src",
  "data",
  "fvgPlaceNamesFur.json",
);

const source = JSON.parse(fs.readFileSync(sourcePath, "utf8"));
const profiles = Array.isArray(source.profiles) ? source.profiles : [];

if (profiles.length !== 215) {
  throw new Error(`Expected 215 municipality profiles, found ${profiles.length}.`);
}

const names = profiles.map((profile) => {
  if (profile.languageStatus?.fur !== "approved") {
    throw new Error(`FUR is not approved for ${profile.municipality}.`);
  }

  const fur = String(profile.title?.fur || "").split(",", 1)[0].trim();
  if (!fur) {
    throw new Error(`Missing FUR display name for ${profile.municipality}.`);
  }

  return {
    istatCode: String(profile.istatCode || "").trim(),
    it: String(profile.municipality || "").trim(),
    fur,
  };
});

const istatCodes = new Set(names.map((item) => item.istatCode));
if (istatCodes.size !== names.length || istatCodes.has("")) {
  throw new Error("Municipality ISTAT codes must be present and unique.");
}

names.sort((first, second) => first.istatCode.localeCompare(second.istatCode, "it"));

const output = {
  schemaVersion: 1,
  generatedAt: new Date().toISOString().slice(0, 10),
  source: {
    catalog: "frontend/src/data/discover/municipalityProfiles.json",
    officialToponymy: "ARLeF - Comuni friulanofoni del Friuli-Venezia Giulia",
  },
  coverage: {
    municipalities: names.length,
    furApproved: names.length,
  },
  names,
};

fs.writeFileSync(outputPath, `${JSON.stringify(output, null, 2)}\n`, "utf8");
console.log(`Wrote ${names.length} FUR place names to ${outputPath}.`);
