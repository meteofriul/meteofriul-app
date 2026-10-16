import { defineConfig } from "vite";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";

const rootDir = fileURLToPath(new URL(".", import.meta.url));

export default defineConfig({
  build: {
    emptyOutDir: false,
    outDir: resolve(rootDir, "dist"),
    rollupOptions: {
      input: resolve(rootDir, "src/firebase-messaging-sw.js"),
      output: {
        codeSplitting: false,
        entryFileNames: "firebase-messaging-sw.js",
      },
    },
  },
});
