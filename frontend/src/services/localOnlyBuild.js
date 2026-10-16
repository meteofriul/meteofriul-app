// Compile-time boundary for the guarded Android build connected to PC services.
// Public endpoint fallbacks must not be embedded in this particular TEST APK.
export const ANDROID_LOOPBACK_ONLY_BUILD = import.meta.env.MODE === "android-local-pilot"
  && import.meta.env.VITE_LOCAL_WEATHER_PILOT_API_BASE === "http://127.0.0.1:8781";
