import { defineConfig } from "vitest/config";

// Opt-in audit suite. These tests state the desired contracts for confirmed
// defects and intentionally remain outside the normal application test glob.
// A red result documents that the current implementation still violates the
// contract; do not turn these into skipped or expected-failure tests.
export default defineConfig({
  test: {
    include: ["src/diagnostics/structuralAudit.diagnostic.js"],
  },
});
