export function getDefinitiveBrandMark(environment = import.meta.env) {
  return environment.MODE === "android-local-pilot"
    ? "/brand/pilot-test-orange-v1/mark.svg"
    : "/brand/pilot-r4/meteo-eventi-friul-mark-192.png";
}
