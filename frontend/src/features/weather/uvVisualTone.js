import { uvLevel } from "./uvLevels";

export function getUvVisualTone(model) {
  return uvLevel(model?.current?.value)?.tone || "unavailable";
}
