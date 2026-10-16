import { defineConfig } from "vitest/config";

// Opt-in structural audit. This file is deliberately outside Vitest's normal
// *.test.* / *.spec.* discovery. A red result records the current defect.
export default defineConfig({
  test: {
    include: ["src/diagnostics/weatherRefreshLifecycle.diagnostic.jsx"],
  },
});
