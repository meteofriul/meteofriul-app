import { defineConfig } from "vitest/config";

// Run explicitly with:
// npx vitest --configLoader native --config social-geo-structural-audit.diagnostic.config.js run
// These tests describe desired contracts for confirmed open defects and are
// intentionally excluded from the ordinary application suite.
export default defineConfig({
  test: {
    include: ["src/diagnostics/socialGeoStructuralAudit.diagnostic.js"],
  },
});
