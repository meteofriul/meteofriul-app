export const UI_V3_QUERY_PARAM = "uiV3";
export const UI_V3_STORAGE_KEY = "uiV3Lab";

export function readBooleanFlag(value) {
  if (value == null) return null;
  const normalized = String(value).trim().toLowerCase();
  if (["1", "true", "yes", "on"].includes(normalized)) return true;
  if (["0", "false", "no", "off"].includes(normalized)) return false;
  return null;
}

export function readUiV3LabFlag(search = window.location.search, storage = window.localStorage) {
  const params = new URLSearchParams(search);
  const queryFlag = readBooleanFlag(params.get(UI_V3_QUERY_PARAM));
  if (queryFlag != null) return queryFlag;

  try {
    const storedFlag = readBooleanFlag(storage?.getItem(UI_V3_STORAGE_KEY));
    if (storedFlag != null) return storedFlag;
  } catch {
    return true;
  }

  return false;
}
