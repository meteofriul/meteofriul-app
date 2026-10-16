import institutionalArchive from "../../data/discover/institutionalArchive.json";
import institutionalRituals from "../../data/discover/institutionalRituals.json";
import ostermannCulturalRecords from "../../data/ostermannCulturalDiscover.json";
import { applyDiscoverWeatherEditorialPolicy } from "./discoverWeatherEditorialPolicy";

export const discoverCulturalRecords = [
  ...applyDiscoverWeatherEditorialPolicy(ostermannCulturalRecords),
  ...institutionalRituals,
  ...institutionalArchive,
];

export function getDiscoverCulturalRecords() {
  return discoverCulturalRecords;
}

export function getInstitutionalRitualRecords() {
  return institutionalRituals;
}

export function getInstitutionalArchiveRecords() {
  return institutionalArchive;
}

export function getOstermannCulturalRecords() {
  return ostermannCulturalRecords;
}

export default discoverCulturalRecords;
