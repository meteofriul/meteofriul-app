import { describe, expect, it } from "vitest";

import {
  REPORT_LOCATION_NOTICE_CONSENT_KEY,
  REPORT_LOCATION_NOTICE_VERSION,
  hasReportLocationNoticeConsent,
  rememberReportLocationNoticeConsent,
} from "./reportLocationNoticeConsent";

function createStorage() {
  const values = new Map();
  return {
    getItem: (key) => values.get(key) ?? null,
    setItem: (key, value) => values.set(key, value),
    values,
  };
}

describe("reportLocationNoticeConsent", () => {
  it("requires the new local notice even if older community guidelines were accepted", () => {
    const storage = createStorage();

    expect(hasReportLocationNoticeConsent({ storage })).toBe(false);
    expect(rememberReportLocationNoticeConsent({ storage })).toBe(true);
    expect(hasReportLocationNoticeConsent({ storage })).toBe(true);
    expect(storage.values.get(REPORT_LOCATION_NOTICE_CONSENT_KEY))
      .toBe(REPORT_LOCATION_NOTICE_VERSION);
  });

  it("fails closed when storage is unavailable", () => {
    const storage = { getItem: () => { throw new Error("blocked"); }, setItem: () => { throw new Error("blocked"); } };

    expect(hasReportLocationNoticeConsent({ storage })).toBe(false);
    expect(rememberReportLocationNoticeConsent({ storage })).toBe(false);
    expect(rememberReportLocationNoticeConsent({ storage: null })).toBe(false);
  });
});
