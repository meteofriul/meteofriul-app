import { defineConfig } from "vitest/config";

// Focused B01 regression diagnostic. It stays available as an opt-in proof of
// the original cross-layer failure; the ordinary suite carries the broader
// durability and isolation matrix.
export default defineConfig({
  test: {
    include: ["src/diagnostics/camsFamilyRevocation.diagnostic.js"],
  },
});
