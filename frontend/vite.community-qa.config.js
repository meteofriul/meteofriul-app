import process from "node:process";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { fileURLToPath } from "node:url";
const root = fileURLToPath(new URL(".", import.meta.url));
export default defineConfig(({ command, mode }) => {
  if (command !== "build" || mode !== "android-community-qa" || process.env.METEO_COMMUNITY_QA_BUILD !== "1") throw new Error("community_qa_guard_required");
  return {
    root, envDir: false, envPrefix: [], publicDir: false, plugins: [react()],
    resolve: { alias: [{ find: /^.*\/firebaseWebConfig(?:\.js)?$/, replacement: fileURLToPath(new URL("./qa/community/firebaseWebDisabled.js", import.meta.url)) }] },
    define: {
      "import.meta.env.VITE_ANDROID_API_BASE": JSON.stringify("https://community-qa.invalid/api"),
      "import.meta.env.VITE_API_BASE": JSON.stringify("https://community-qa.invalid/api"),
      "import.meta.env.VITE_COMMUNITY_API_BASE": JSON.stringify("http://127.0.0.1:8788/api"),
      "import.meta.env.VITE_COMMUNITY_V2_ENABLED": JSON.stringify("1"),
      "import.meta.env.VITE_DEFINITIVE_APP_EXPERIENCE": JSON.stringify("1"),
      "import.meta.env.VITE_LOCAL_COMMUNITY_PILOT_ENABLED": JSON.stringify("0"),
      "import.meta.env.VITE_LOCAL_WEATHER_PILOT": JSON.stringify("0"),
      "import.meta.env.VITE_OFFICIAL_APP_RELEASE": JSON.stringify("0"),
    },
    build: { sourcemap: false, rollupOptions: { input: fileURLToPath(new URL("./qa/community/index.html", import.meta.url)) } },
  };
});
