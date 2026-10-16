import { defineConfig } from "vitest/config";

// Explicit diagnostic suite, separate from the normal application test glob.
// Known failures remain failures: no skipped tests or expected-failure masking.
export default defineConfig({
  test: {
    include: ["src/services/camsRecoveryDiagnostic.diagnostic.js"],
  },
});
