import { defineConfig } from "vitest/config";

// Opt-in structural audit. This diagnostic is deliberately outside Vitest's
// normal *.test.* / *.spec.* discovery and remains red until the local-pilot
// UI capability gate agrees with the App Check capability actually available.
export default defineConfig({
  test: {
    include: ["src/diagnostics/pilotCapabilityMismatch.diagnostic.js"],
  },
});
