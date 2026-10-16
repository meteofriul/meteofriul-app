import { defineConfig } from "vitest/config";

// Opt-in audit suite. These deliberately red contract tests stay outside the
// normal Vitest filename glob and must be invoked with this config explicitly.
export default defineConfig({
  test: {
    include: ["src/diagnostics/ordinaryWeatherContract.diagnostic.jsx"],
  },
});
