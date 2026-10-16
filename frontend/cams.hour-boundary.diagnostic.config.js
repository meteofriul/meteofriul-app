import { defineConfig } from "vitest/config";

// Explicit temporal-regression suite kept separate from the normal test glob.
// Assertions are ordinary failures: no skip or expected-failure masking.
export default defineConfig({
  test: { include: ["src/services/camsHourBoundaryDiagnostic.diagnostic.js"] },
});
