import { describe, expect, it } from "vitest";

import {
  OFFICIAL_ALERT_STATES,
  buildOfficialAlertSummary,
  classifyOfficialAlertState,
  formatOfficialAlertText,
  formatOfficialAlertContent,
  getActionableOfficialAlerts,
  getHighestOfficialAlertSeverityKey,
  getNextOfficialAlertExpiryAt,
  getOfficialAlertRecords,
  isActionableOfficialAlert,
} from "./officialAlerts";

const COPY = {
  alertsLabel: "Avvisi ufficiali",
  officialAlertMultipleLabel: "allerte ufficiali",
  officialAlertPhenomenonLabels: {
    rain: "Allerta pioggia",
    storm: "Allerta temporali",
    wind: "Allerta vento",
  },
  officialAlertSeverityLabels: {
    yellow: "Allerta gialla",
    orange: "Allerta arancione",
    red: "Allerta rossa",
  },
  officialAlertSingleLabel: "Allerta ufficiale",
};

describe("official alerts domain", () => {
  it("accepts both backend official_alerts payloads and plain alert arrays", () => {
    const alert = { id: "alert-1", level: "gialla" };

    expect(getOfficialAlertRecords({ active: true, alerts: [alert] })).toEqual([alert]);
    expect(getOfficialAlertRecords([alert])).toEqual([alert]);
    expect(getOfficialAlertRecords(null)).toEqual([]);
  });

  it("excludes green official states from actionable alerts", () => {
    expect(isActionableOfficialAlert({ id: "green", level: "verde", title: "Nessuna allerta" })).toBe(false);
    expect(isActionableOfficialAlert({ id: "yellow", level: "gialla" })).toBe(true);
    expect(isActionableOfficialAlert({ id: "fallback-official-alert" })).toBe(true);
    expect(getActionableOfficialAlerts({
      alerts: [
        { id: "green", level: "verde" },
        { id: "orange", level: "arancione" },
      ],
    })).toEqual([{ id: "orange", level: "arancione" }]);
  });

  it("returns the highest official alert severity", () => {
    expect(getHighestOfficialAlertSeverityKey([
      { id: "yellow", level: "gialla" },
      { id: "red", severity: "rossa" },
      { id: "orange", color: "orange" },
    ])).toBe("red");
  });

  it("classifies active regional alerts as displayable and notifiable", () => {
    expect(classifyOfficialAlertState({
      active: true,
      alerts: [{ id: "yellow", level: "gialla" }],
      fetched_at: "2026-06-24T10:00:00Z",
      source_mode: "github_actions_official_page",
    })).toMatchObject({
      active: true,
      canClearPreviousAlert: false,
      canNotify: true,
      canShowBanner: true,
      confidence: "high",
      count: 1,
      freshness: "fresh",
      sourceAuthority: "regional_fvg",
      sourceMode: "github_actions_official_page",
      state: OFFICIAL_ALERT_STATES.ACTIVE,
    });
  });

  it("ignores an expired record when another alert in the snapshot is still active", () => {
    const payload = {
      active: true,
      alerts: [
        {
          id: "expired-red",
          level: "rossa",
          valid_to: "2026-08-14T11:59:00Z",
        },
        {
          id: "active-yellow",
          level: "gialla",
          valid_to: "2026-08-14T18:00:00Z",
        },
      ],
      expires_at: "2026-08-14T18:00:00Z",
      fetched_at: "2026-08-14T11:55:00Z",
      source_mode: "official_telegram_pdf_verified",
    };

    const state = classifyOfficialAlertState(payload, {
      now: new Date("2026-08-14T12:00:00Z"),
    });
    const summary = buildOfficialAlertSummary(payload, COPY, {
      now: new Date("2026-08-14T12:00:00Z"),
    });

    expect(state).toMatchObject({
      active: true,
      count: 1,
      state: OFFICIAL_ALERT_STATES.ACTIVE,
    });
    expect(state.actionableAlerts.map((alert) => alert.id)).toEqual(["active-yellow"]);
    expect(summary).toMatchObject({ count: 1, label: "Allerta gialla", level: "yellow" });
  });

  it("schedules each exact validity transition when alerts expire in sequence", () => {
    const payload = {
      active: true,
      alerts: [
        {
          id: "red-first",
          level: "rossa",
          valid_to: "2026-08-14T10:00:00Z",
        },
        {
          id: "yellow-second",
          level: "gialla",
          valid_to: "2026-08-14T12:00:00Z",
        },
      ],
      expires_at: "2026-08-14T12:00:00Z",
      source_mode: "official_widget",
    };

    expect(getNextOfficialAlertExpiryAt(payload, {
      now: new Date("2026-08-14T09:00:00Z"),
    })).toBe(new Date("2026-08-14T10:00:00Z").getTime());
    expect(getNextOfficialAlertExpiryAt(payload, {
      now: new Date("2026-08-14T10:00:00Z"),
    })).toBe(new Date("2026-08-14T12:00:00Z").getTime());
    expect(getNextOfficialAlertExpiryAt(payload, {
      now: new Date("2026-08-14T12:00:00Z"),
    })).toBeNull();
  });

  it("recognizes reconciled Telegram alerts as high-confidence regional alerts", () => {
    expect(classifyOfficialAlertState({
      active: true,
      alerts: [{ id: "telegram-yellow", level: "gialla" }],
      fetched_at: "2026-06-24T10:00:00Z",
      source_mode: "official_telegram_pdf_verified",
    })).toMatchObject({
      active: true,
      canClearPreviousAlert: false,
      canNotify: true,
      canShowBanner: true,
      confidence: "high",
      sourceAuthority: "regional_fvg",
      state: OFFICIAL_ALERT_STATES.ACTIVE,
    });
  });

  it("never treats absence on the positive-only Telegram feed as a clearance", () => {
    expect(classifyOfficialAlertState({
      active: false,
      alerts: [],
      fetched_at: "2026-06-24T10:00:00Z",
      source_mode: "official_telegram_positive_only",
    })).toMatchObject({
      active: false,
      canClearPreviousAlert: false,
      canNotify: false,
      canShowBanner: false,
      confidence: "low",
      sourceAuthority: "regional_fvg",
      state: OFFICIAL_ALERT_STATES.UNAVAILABLE,
    });
  });

  it("accepts the ARPA PCR mirror as a confirmed regional clearance", () => {
    expect(classifyOfficialAlertState({
      active: false,
      alerts: [],
      fetched_at: "2026-06-24T10:00:00Z",
      source_mode: "arpa_pcr_mirror",
    })).toMatchObject({
      active: false,
      canClearPreviousAlert: true,
      canNotify: false,
      canShowBanner: false,
      confidence: "high",
      sourceAuthority: "regional_fvg",
      state: OFFICIAL_ALERT_STATES.INACTIVE_CONFIRMED,
    });
  });

  it("accepts the official validity deadline as a confirmed clearance", () => {
    expect(classifyOfficialAlertState({
      active: false,
      alerts: [],
      fetched_at: "2026-06-24T10:00:00Z",
      source_mode: "official_validity_expired",
    })).toMatchObject({
      active: false,
      canClearPreviousAlert: true,
      confidence: "high",
      sourceAuthority: "regional_fvg",
      state: OFFICIAL_ALERT_STATES.INACTIVE_CONFIRMED,
    });
  });

  it("classifies confirmed green/no-alert regional reads without treating them as unavailable", () => {
    expect(classifyOfficialAlertState({
      active: false,
      alerts: [{ id: "green", level: "verde", title: "Nessuna allerta" }],
      fetched_at: "2026-06-24T10:00:00Z",
      source_mode: "github_actions_official_widget",
    })).toMatchObject({
      active: false,
      canClearPreviousAlert: true,
      canNotify: false,
      canShowBanner: false,
      confidence: "high",
      count: 0,
      freshness: "fresh",
      sourceAuthority: "regional_fvg",
      state: OFFICIAL_ALERT_STATES.INACTIVE_CONFIRMED,
    });
  });

  it("does not clear alerts when the source was not actually read", () => {
    expect(classifyOfficialAlertState({
      active: false,
      alerts: [],
      cache: { status: "unavailable", reason: "direct_fetch_deferred" },
      error: "official_alerts_unavailable",
      source_mode: "official_alerts_unavailable_fast_fallback",
    })).toMatchObject({
      active: false,
      cacheStatus: "unavailable",
      canClearPreviousAlert: false,
      canNotify: false,
      canShowBanner: false,
      confidence: "low",
      error: "official_alerts_unavailable",
      sourceAuthority: "backend_fallback",
      state: OFFICIAL_ALERT_STATES.UNAVAILABLE,
    });
  });

  it("keeps stale or expired alert payloads out of active UI states", () => {
    expect(classifyOfficialAlertState({
      active: true,
      alerts: [{ id: "old-yellow", level: "gialla" }],
      cache: { status: "stale" },
      source_mode: "github_actions_official_page",
    })).toMatchObject({
      active: false,
      canNotify: false,
      canShowBanner: false,
      freshness: "stale",
      state: OFFICIAL_ALERT_STATES.STALE,
    });

    expect(classifyOfficialAlertState({
      active: true,
      alerts: [{ id: "expired-red", level: "rossa" }],
      expires_at: "2026-06-24T08:00:00Z",
      source_mode: "github_actions_official_page",
    }, { now: "2026-06-24T10:00:00Z" })).toMatchObject({
      active: false,
      canNotify: false,
      canShowBanner: false,
      freshness: "stale",
      state: OFFICIAL_ALERT_STATES.EXPIRED,
    });
  });

  it("marks national no-active fallback as diagnostic, not confirmed green", () => {
    expect(classifyOfficialAlertState({
      active: false,
      alerts: [],
      source_mode: "github_actions_dpc_national_criticity_no_active_fvg_unverified",
      warning: "Fonte regionale non raggiungibile",
    })).toMatchObject({
      active: false,
      canClearPreviousAlert: false,
      canNotify: false,
      canShowBanner: false,
      confidence: "low",
      sourceAuthority: "national_dpc",
      state: OFFICIAL_ALERT_STATES.DIAGNOSTIC,
    });
  });

  it("builds compact labels for Home and future bulletin anchors", () => {
    expect(buildOfficialAlertSummary({ alerts: [{ id: "yellow", level: "gialla" }] }, COPY)).toMatchObject({
      action: { anchor: "official-alerts", tab: "bulletin" },
      count: 1,
      label: "Allerta gialla",
      level: "yellow",
      tone: "yellow",
    });

    expect(buildOfficialAlertSummary([{ id: "storm", official_text: "ALLERTA PER TEMPORALI" }], COPY)).toMatchObject({
      count: 1,
      label: "Allerta temporali",
      level: null,
      tone: "neutral",
    });

    expect(buildOfficialAlertSummary({ active: true, alerts: [{ id: "fallback" }] }, COPY)).toMatchObject({
      count: 1,
      label: "Allerta ufficiale",
      level: null,
      tone: "neutral",
    });
  });

  it("does not build UI labels for unavailable or stale official alert states", () => {
    expect(buildOfficialAlertSummary({
      active: false,
      alerts: [],
      cache: { status: "unavailable" },
      source_mode: "official_alerts_unavailable_fast_fallback",
    }, COPY)).toBeNull();

    expect(buildOfficialAlertSummary({
      active: true,
      alerts: [{ id: "stale-yellow", level: "gialla" }],
      cache: { status: "stale" },
      source_mode: "github_actions_official_page",
    }, COPY)).toBeNull();
  });

  it("formats official alert text without changing source meaning", () => {
    expect(formatOfficialAlertText({
      official_text: "DALLE ORE 12:00 DEL 24/06 ALLE ORE 23:59 DEL 24/06 ALLERTA GIALLA PER TEMPORALI SU TUTTA LA REGIONE",
    })).toBe(
      "Dalle ore 12:00 del 24/06 alle ore 23:59 del 24/06: allerta gialla per temporali su tutta la regione.",
    );

    expect(formatOfficialAlertText({ push_body: "Allerta gialla per temporali." })).toBe("Allerta gialla per temporali.");
  });

  it("cleans the exact official text of regional alert 24", () => {
    expect(formatOfficialAlertContent({
      official_text: "#AllertameteoFVG - ALLERTA REGIONALE 24 DEL 2026 DALLE ORE 18:00 DI GIOVEDI' 20/08/26 ALLE ORE 24:00 DI VENERDI’ 21/08/26 ALLERTA ARANCIONE PER TEMPORALI FORTI E CRITICITA' IDROGEOLOGICA SU TUTTA LA REGIONE. LA FASE ACUTA DELL'EVENTO E' PREVISTA DALLE ORE 18:00 ALLE ORE 24:00 DEL 20 AGOSTO E DALLE ORE 12:00 ALLE 24:00 DEL 21 AGOSTO 2026. Maggiori informazioni su: https://bit.ly/3lcJsoh Documento di allerta: https://cfd.protezionecivile.fvg.it/docs/alerts/2026/Allerta_regionale_24-2026_20082026-11_36.pdf",
    })).toEqual({
      includesValidity: true,
      paragraphs: [
        "Allerta regionale 24 del 2026 dalle ore 18:00 di giovedì 20/08/26 alle ore 24:00 di venerdì 21/08/26: allerta arancione per temporali forti e criticità idrogeologica su tutta la regione.",
        "La fase acuta dell'evento è prevista dalle ore 18:00 alle ore 24:00 del 20 agosto e dalle ore 12:00 alle 24:00 del 21 agosto 2026.",
      ],
      text: "Allerta regionale 24 del 2026 dalle ore 18:00 di giovedì 20/08/26 alle ore 24:00 di venerdì 21/08/26: allerta arancione per temporali forti e criticità idrogeologica su tutta la regione.",
    });
  });

  it("cleans the exact official text of regional alert 23", () => {
    expect(formatOfficialAlertContent({
      official_text: "#AllertameteoFVG - ALLERTA REGIONALE 23 DEL 2026 DALLE ORE 12:00 DI GIOVEDI' 20/08/26 ALLE ORE 24:00 DI VENERDI’ 21/08/26 ALLERTA GIALLA PER TEMPORALI FORTI E CRITICITA' IDROGEOLOGICA SU TUTTA LA REGIONE. Maggiori informazioni su: https://bit.ly/3lcJsoh Documento di allerta: https://cfd.protezionecivile.fvg.it/docs/alerts/2026/Allerta_regionale_23-2026_19082026-14_57.pdf",
    })).toEqual({
      includesValidity: true,
      paragraphs: [
        "Allerta regionale 23 del 2026 dalle ore 12:00 di giovedì 20/08/26 alle ore 24:00 di venerdì 21/08/26: allerta gialla per temporali forti e criticità idrogeologica su tutta la regione.",
      ],
      text: "Allerta regionale 23 del 2026 dalle ore 12:00 di giovedì 20/08/26 alle ore 24:00 di venerdì 21/08/26: allerta gialla per temporali forti e criticità idrogeologica su tutta la regione.",
    });
  });

  it("applies the same cleanup when links are reversed and the alert has one sentence", () => {
    expect(formatOfficialAlertContent({
      official_text: "#AllertameteoFVG - ALLERTA REGIONALE 26 DEL 2026 DALLE ORE 12:00 DI GIOVEDI' 20/08/26 ALLE ORE 24:00 DI VENERDI' 21/08/26 ALLERTA GIALLA PER TEMPORALI FORTI SU TUTTA LA REGIONE. Documento di allerta: https://example.test/26.pdf Maggiori informazioni su: https://example.test/allerte",
    })).toEqual({
      includesValidity: true,
      paragraphs: [
        "Allerta regionale 26 del 2026 dalle ore 12:00 di giovedì 20/08/26 alle ore 24:00 di venerdì 21/08/26: allerta gialla per temporali forti su tutta la regione.",
      ],
      text: "Allerta regionale 26 del 2026 dalle ore 12:00 di giovedì 20/08/26 alle ore 24:00 di venerdì 21/08/26: allerta gialla per temporali forti su tutta la regione.",
    });
  });

  it("preserves three meaningful official sentences as three paragraphs", () => {
    expect(formatOfficialAlertContent({
      official_text: "#AllertameteoFVG - ALLERTA REGIONALE 25 DEL 2026 DALLE ORE 08:00 DEL 22/08/26 ALLE ORE 18:00 DEL 22/08/26 ALLERTA ROSSA PER TEMPORALI SU TUTTO FVG. PRESTARE ATTENZIONE NELLE ZONE ESPOSTE. SEGUIRE GLI AGGIORNAMENTI UFFICIALI. Maggiori informazioni su: https://example.test/allerte",
    }).paragraphs).toEqual([
      "Allerta regionale 25 del 2026 dalle ore 08:00 del 22/08/26 alle ore 18:00 del 22/08/26: allerta rossa per temporali su tutto FVG.",
      "Prestare attenzione nelle zone esposte.",
      "Seguire gli aggiornamenti ufficiali.",
    ]);
  });

  it("keeps the safe fallback for concise non-regional alert text", () => {
    expect(formatOfficialAlertContent({ push_body: "Allerta gialla per temporali." })).toEqual({
      includesValidity: false,
      paragraphs: ["Allerta gialla per temporali."],
      text: "Allerta gialla per temporali.",
    });
  });
});
