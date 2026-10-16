// @vitest-environment jsdom

import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { getLiveViewCopy } from "../../copy/liveViewCopy";
import { CommunityMapPhenomenon, CommunityModerationDialog } from "./CommunityMap";
import {
  expireCommunityReport,
  getCommunityContributionCount,
  readCommunityPersonalState,
  releaseCommunityReportReceipt,
  rememberCommunityReport,
} from "./communityPersonalState";
import {
  CommunityPendingUpdateRecovery,
  LiveView,
} from "./LiveView";
import { buildLiveViewModel } from "./liveViewModel";

function storage() {
  const values = new Map();
  return {
    getItem: (key) => values.get(key) || null,
    setItem: (key, value) => values.set(key, value),
  };
}

function buildOwnedReportModel(now = Date.now()) {
  return buildLiveViewModel({
    community: {
      payload: {
        map_groups: [{
          confirmations: { no: 0, yes: 0 },
          count: 1,
          createdAt: now,
          expiresAt: now + 60_000,
          groupId: "group-rain",
          id: "group-rain",
          lat: 45.9567,
          lon: 12.6605,
          place: "Pordenone",
          reportIds: ["report-rain"],
          sourceKeys: ["opaque-source-a"],
          typeId: "rain",
          x: 42,
          y: 61,
        }],
        reports: [{
          createdAt: now,
          expiresAt: now + 60_000,
          groupId: "group-rain",
          id: "report-rain",
          lat: 45.9567,
          lon: 12.6605,
          place: "Pordenone",
          revision: 1,
          sourceKeys: ["opaque-source-a"],
          typeId: "rain",
        }],
      },
      status: "fresh",
    },
    webcams: { payload: null, status: "disabled" },
  }, {
    location: { city: "Pordenone", lat: 45.9567, lon: 12.6605 },
    now: new Date(now),
    webcamsEnabled: false,
  });
}

describe("community moderation dialog interactions", () => {
  let container;
  let root;

  beforeEach(() => {
    globalThis.IS_REACT_ACT_ENVIRONMENT = true;
    container = document.createElement("div");
    container.id = "root";
    document.body.appendChild(container);
    root = createRoot(container);
    vi.stubGlobal("requestAnimationFrame", (callback) => globalThis.setTimeout(callback, 0));
    vi.stubGlobal("cancelAnimationFrame", (handle) => globalThis.clearTimeout(handle));
  });

  afterEach(async () => {
    await act(async () => root.unmount());
    document.body.replaceChildren();
    vi.useRealTimers();
    delete globalThis.IS_REACT_ACT_ENVIRONMENT;
    vi.unstubAllGlobals();
  });

  it("keeps the flag submit disabled until a radio card is selected", async () => {
    const copy = getLiveViewCopy("it");

    await act(async () => {
      root.render(
        <CommunityModerationDialog
          copy={copy}
          onClose={vi.fn()}
          onFlag={vi.fn().mockResolvedValue({ ok: true })}
          phenomenon={{
            groupId: "group-rain",
            sourceKeys: ["opaque-source-a"],
          }}
        />,
      );
    });

    const dialog = document.body.querySelector(".mf-live-moderation-dialog");
    const reason = dialog.querySelector('input[value="inaccurate"]');
    const reasonCard = reason.closest("label");
    const submit = dialog.querySelector(".mf-live-moderation-dialog__submit--flag");

    expect(reason.checked).toBe(false);
    expect(reasonCard.querySelector("input:checked")).toBeNull();
    expect(submit.disabled).toBe(true);
    expect(submit.querySelector('svg[aria-hidden="true"][fill="currentColor"]')).not.toBeNull();

    await act(async () => reason.click());

    expect(reason.checked).toBe(true);
    expect(reasonCard.querySelector("input:checked")).toBe(reason);
    expect(submit.disabled).toBe(false);
  });

  it("requires confirmation before withdrawing the exact owned report", async () => {
    const copy = getLiveViewCopy("it");
    const onWithdraw = vi.fn().mockResolvedValue({ ok: true });

    await act(async () => {
      root.render(
        <CommunityMapPhenomenon
          copy={copy}
          onWithdraw={onWithdraw}
          ownReport={{
            expiresAt: Date.now() + 120_000,
            groupId: "group-rain",
            reportId: "report-rain",
          }}
          phenomenon={{
            confirmations: { no: 0, yes: 0 },
            countLabel: copy.reportCountOne,
            groupId: "group-rain",
            sourceKeys: ["opaque-source-a"],
            timeLabel: copy.reportNow,
            typeId: "rain",
            typeLabel: copy.reportTypes.rain,
          }}
        />,
      );
    });

    const request = container.querySelector(".mf-live-community-own-report__withdraw");
    await act(async () => request.click());
    expect(onWithdraw).not.toHaveBeenCalled();
    expect(container.textContent).toContain(copy.reportWithdrawBody);

    const confirm = container.querySelector(".mf-live-community-own-report__withdraw-confirm .is-destructive");
    await act(async () => confirm.click());
    expect(onWithdraw).toHaveBeenCalledOnce();
    expect(onWithdraw).toHaveBeenCalledWith("report-rain");
  });

  it("updates only the exact owned receipt and prevents update-withdraw races", async () => {
    const copy = getLiveViewCopy("it");
    let finishUpdate;
    const onUpdate = vi.fn(() => new Promise((resolve) => {
      finishUpdate = resolve;
    }));
    const onWithdraw = vi.fn().mockResolvedValue({ ok: true });
    const ownReport = {
      expiresAt: Date.now() + 120_000,
      groupId: "group-rain",
      reportId: "report-rain",
      revision: 1,
    };

    await act(async () => {
      root.render(
        <CommunityMapPhenomenon
          copy={copy}
          onUpdate={onUpdate}
          onWithdraw={onWithdraw}
          ownReport={ownReport}
          phenomenon={{
            confirmations: { no: 0, yes: 0 },
            countLabel: copy.reportCountOne,
            groupId: "group-rain",
            sourceKeys: ["opaque-source-a"],
            timeLabel: copy.reportNow,
            typeId: "rain",
            typeLabel: copy.reportTypes.rain,
          }}
        />,
      );
    });

    const update = container.querySelector(".mf-live-community-own-report__update");
    const withdraw = container.querySelector(".mf-live-community-own-report__withdraw");
    expect(update).not.toBeNull();

    await act(async () => withdraw.click());
    expect(update.disabled).toBe(true);
    await act(async () => container.querySelector(
      ".mf-live-community-own-report__withdraw-confirm button:not(.is-destructive)",
    ).click());

    await act(async () => update.click());
    expect(onUpdate).toHaveBeenCalledOnce();
    expect(onUpdate).toHaveBeenCalledWith(ownReport);
    expect(container.querySelector(".mf-live-community-own-report__withdraw").disabled).toBe(true);

    await act(async () => finishUpdate({ ok: true, revision: 2 }));
    expect(container.textContent).toContain(copy.reportUpdateSuccess);
    expect(onWithdraw).not.toHaveBeenCalled();
  });

  it("caps only the pilot own-report countdown at sixty minutes", async () => {
    const copy = getLiveViewCopy("it");
    const now = Date.parse("2026-09-20T20:08:00Z");
    const dateNow = vi.spyOn(Date, "now").mockReturnValue(now);
    const commonProps = {
      copy,
      ownReport: {
        expiresAt: now + (60 * 60_000) + 30_000,
        groupId: "group-rain",
        reportId: "report-rain",
      },
      phenomenon: {
        confirmations: { no: 0, yes: 0 },
        countLabel: copy.reportCountOne,
        groupId: "group-rain",
        sourceKeys: ["opaque-source-a"],
        timeLabel: copy.reportNow,
        typeId: "rain",
        typeLabel: copy.reportTypes.rain,
      },
    };

    await act(async () => {
      root.render(<CommunityMapPhenomenon {...commonProps} pilotStyle />);
    });

    expect(container.querySelector(".mf-live-community-own-report--pilot")?.textContent)
      .toContain("Scade tra 60 min");

    await act(async () => {
      root.render(<CommunityMapPhenomenon {...commonProps} />);
    });

    expect(container.querySelector(".mf-live-community-own-report")?.textContent)
      .toContain("Scade tra 61 min");
    expect(container.querySelector(".mf-live-community-own-report--pilot")).toBeNull();
    dateNow.mockRestore();
  });

  it("shows pilot update success in the button for exactly two seconds", async () => {
    vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout"] });
    const copy = getLiveViewCopy("it");
    const onUpdate = vi.fn().mockResolvedValue({ ok: true, revision: 2 });

    await act(async () => {
      root.render(
        <CommunityMapPhenomenon
          copy={copy}
          onUpdate={onUpdate}
          onWithdraw={vi.fn().mockResolvedValue({ ok: true })}
          ownReport={{
            expiresAt: Date.now() + 120_000,
            groupId: "group-rain",
            reportId: "report-rain",
            revision: 1,
          }}
          phenomenon={{
            confirmations: { no: 0, yes: 0 },
            countLabel: copy.reportCountOne,
            groupId: "group-rain",
            sourceKeys: ["opaque-source-a"],
            timeLabel: copy.reportNow,
            typeId: "rain",
            typeLabel: copy.reportTypes.rain,
          }}
          pilotStyle
        />,
      );
    });

    const update = container.querySelector(".mf-live-community-own-report__update");
    await act(async () => update.click());

    expect(onUpdate).toHaveBeenCalledOnce();
    expect(update.classList.contains("is-success")).toBe(true);
    expect(update.querySelector(".mf-live-community-own-report__update-label")?.textContent)
      .toBe(copy.reportUpdateDone);
    expect(update.querySelector(".lucide-check")).not.toBeNull();
    expect(update.querySelector(".lucide-refresh-cw")).toBeNull();
    expect(container.querySelector(".mf-live-community-own-report__update-status")).toBeNull();
    expect(container.querySelector(".mf-live-community-own-report__withdraw")).not.toBeNull();
    const announcement = container.querySelector(
      ".mf-live-community-own-report__update-announcement",
    );
    expect(announcement?.textContent).toBe(copy.reportUpdateSuccess);
    expect(announcement?.getAttribute("role")).toBe("status");

    await act(async () => vi.advanceTimersByTime(1_999));
    expect(update.classList.contains("is-success")).toBe(true);
    expect(update.querySelector(".mf-live-community-own-report__update-label")?.textContent)
      .toBe(copy.reportUpdateDone);

    await act(async () => vi.advanceTimersByTime(1));
    expect(update.classList.contains("is-success")).toBe(false);
    expect(update.querySelector(".mf-live-community-own-report__update-label")?.textContent)
      .toBe(copy.reportUpdate);
    expect(update.querySelector(".lucide-refresh-cw")).not.toBeNull();
    expect(container.querySelector(".mf-live-community-own-report__update-announcement")?.textContent)
      .toBe(copy.reportUpdateSuccess);
  });

  it("clears the pilot success reset timer when the report detail unmounts", async () => {
    vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout"] });
    const copy = getLiveViewCopy("it");

    await act(async () => {
      root.render(
        <CommunityMapPhenomenon
          copy={copy}
          onUpdate={vi.fn().mockResolvedValue({ ok: true, revision: 2 })}
          ownReport={{
            expiresAt: Date.now() + 120_000,
            groupId: "group-rain",
            reportId: "report-rain",
            revision: 1,
          }}
          phenomenon={{
            confirmations: { no: 0, yes: 0 },
            countLabel: copy.reportCountOne,
            groupId: "group-rain",
            sourceKeys: ["opaque-source-a"],
            timeLabel: copy.reportNow,
            typeId: "rain",
            typeLabel: copy.reportTypes.rain,
          }}
          pilotStyle
        />,
      );
    });

    await act(async () => container.querySelector(".mf-live-community-own-report__update").click());
    expect(vi.getTimerCount()).toBe(1);

    await act(async () => root.render(<div data-testid="replacement" />));
    expect(container.querySelector('[data-testid="replacement"]')).not.toBeNull();
    expect(vi.getTimerCount()).toBe(0);
  });

  it("keeps pilot update errors inside the retry button", async () => {
    const copy = getLiveViewCopy("it");
    const onUpdate = vi.fn()
      .mockResolvedValueOnce({ ok: false, reason: "request_failed" })
      .mockResolvedValueOnce({ ok: false, reason: "permission_denied" })
      .mockResolvedValueOnce({ ok: false, reason: "location_verification_failed" });

    await act(async () => {
      root.render(
        <CommunityMapPhenomenon
          copy={copy}
          onUpdate={onUpdate}
          onWithdraw={vi.fn().mockResolvedValue({ ok: true })}
          ownReport={{
            expiresAt: Date.now() + 120_000,
            groupId: "group-rain",
            reportId: "report-rain",
            revision: 1,
          }}
          phenomenon={{
            confirmations: { no: 0, yes: 0 },
            countLabel: copy.reportCountOne,
            groupId: "group-rain",
            sourceKeys: ["opaque-source-a"],
            timeLabel: copy.reportNow,
            typeId: "rain",
            typeLabel: copy.reportTypes.rain,
          }}
          pilotStyle
        />,
      );
    });

    const update = container.querySelector(".mf-live-community-own-report__update");
    await act(async () => update.click());

    expect(update.classList.contains("is-error")).toBe(true);
    expect(update.querySelector(".mf-live-community-own-report__update-label")?.textContent)
      .toBe(copy.reportUpdateRetry);
    const hint = update.querySelector(".mf-live-community-own-report__update-hint");
    expect(hint?.textContent).toBe(copy.reportUpdateRetryHint);
    expect(hint?.closest("button")).toBe(update);
    expect(container.querySelector(".mf-live-community-own-report__update-status")).toBeNull();
    expect(container.querySelector(".mf-live-community-own-report__withdraw")).not.toBeNull();
    const announcement = container.querySelector(
      ".mf-live-community-own-report__update-announcement",
    );
    expect(announcement?.textContent).toBe(copy.reportUpdateError);
    expect(announcement?.getAttribute("role")).toBe("status");

    await act(async () => update.click());
    expect(onUpdate).toHaveBeenCalledTimes(2);
    expect(update.querySelector(".mf-live-community-own-report__update-hint")?.textContent)
      .toBe(copy.reportUpdateLocationHint);
    const locationAnnouncement = container.querySelector(
      ".mf-live-community-own-report__update-announcement",
    );
    expect(locationAnnouncement?.textContent).toBe(copy.reportUpdateLocationError);

    await act(async () => update.click());
    expect(onUpdate).toHaveBeenCalledTimes(3);
    expect(update.querySelector(".mf-live-community-own-report__update-hint")?.textContent)
      .toBe(copy.reportUpdateLocationHint);
    expect(container.querySelector(
      ".mf-live-community-own-report__update-announcement",
    )?.textContent).toBe(copy.reportUpdateLocationError);
  });

  it("offers an explicit retry after an ambiguous update failure", async () => {
    const copy = getLiveViewCopy("it");
    const onUpdate = vi.fn()
      .mockResolvedValueOnce({ ok: false, reason: "request_failed" })
      .mockResolvedValueOnce({ ok: true, revision: 2 });

    await act(async () => {
      root.render(
        <CommunityMapPhenomenon
          copy={copy}
          onUpdate={onUpdate}
          ownReport={{
            expiresAt: Date.now() + 120_000,
            groupId: "group-rain",
            reportId: "report-rain",
            revision: 1,
          }}
          phenomenon={{
            confirmations: { no: 0, yes: 0 },
            countLabel: copy.reportCountOne,
            groupId: "group-rain",
            sourceKeys: ["opaque-source-a"],
            timeLabel: copy.reportNow,
            typeId: "rain",
            typeLabel: copy.reportTypes.rain,
          }}
        />,
      );
    });

    const update = container.querySelector(".mf-live-community-own-report__update");
    await act(async () => update.click());
    expect(update.textContent).toContain(copy.reportUpdateRetry);
    expect(container.textContent).toContain(copy.reportUpdateError);

    await act(async () => update.click());
    expect(onUpdate).toHaveBeenCalledTimes(2);
    expect(container.textContent).toContain(copy.reportUpdateSuccess);
  });

  it("clears an ambiguous timeout after the owned report revision advances", async () => {
    const copy = getLiveViewCopy("it");
    const onUpdate = vi.fn().mockResolvedValue({ ok: false, reason: "request_failed" });
    const phenomenon = {
      confirmations: { no: 0, yes: 0 },
      countLabel: copy.reportCountOne,
      groupId: "group-rain",
      sourceKeys: ["opaque-source-a"],
      timeLabel: copy.reportNow,
      typeId: "rain",
      typeLabel: copy.reportTypes.rain,
    };
    const renderPhenomenon = (revision) => (
      <CommunityMapPhenomenon
        copy={copy}
        onUpdate={onUpdate}
        ownReport={{
          expiresAt: Date.now() + 120_000,
          groupId: "group-rain",
          reportId: "report-rain",
          revision,
          updatedAt: 1_758_000_000_000,
        }}
        phenomenon={phenomenon}
      />
    );

    await act(async () => {
      root.render(renderPhenomenon(1));
    });

    const update = container.querySelector(".mf-live-community-own-report__update");
    await act(async () => update.click());
    expect(update.textContent).toContain(copy.reportUpdateRetry);
    expect(container.textContent).toContain(copy.reportUpdateError);

    await act(async () => {
      root.render(renderPhenomenon(2));
    });

    expect(container.textContent).not.toContain(copy.reportUpdateRetry);
    expect(container.textContent).not.toContain(copy.reportUpdateError);
    expect(container.textContent).toContain(copy.reportUpdateSuccess);
    expect(onUpdate).toHaveBeenCalledOnce();
  });

  it("keeps pending reconciliation separate and never retries without a tap", async () => {
    const copy = getLiveViewCopy("it");
    const pending = {
      expectedRevision: 2,
      operationId: "operation-pending",
      reportId: "report-pending",
    };
    const onRetry = vi.fn().mockResolvedValue({ ok: false, reason: "request_failed" });

    await act(async () => {
      root.render(
        <CommunityPendingUpdateRecovery
          copy={copy}
          onRetry={onRetry}
          pending={pending}
        />,
      );
    });

    expect(onRetry).not.toHaveBeenCalled();
    expect(container.textContent).toContain(copy.reportUpdatePendingTitle);
    const action = container.querySelector(".mf-live-pending-update button");
    await act(async () => action.click());
    expect(onRetry).toHaveBeenCalledWith({ ...pending, revision: 2 });
    expect(action.textContent).toContain(copy.reportUpdateRetry);
  });

  it("shows pending recovery only after the exact ownership receipt is gone", async () => {
    const now = Date.now();
    const personalStorage = storage();
    rememberCommunityReport(
      readCommunityPersonalState({ now, storage: personalStorage }),
      {
        expiresAt: now + 60_000,
        groupId: "group-rain",
        id: "report-rain",
        revision: 1,
      },
      { now, storage: personalStorage },
    );
    const pendingReportUpdates = [{
      expectedRevision: 1,
      operationId: "operation-pending",
      reportId: "report-rain",
    }];
    const commonProps = {
      model: buildOwnedReportModel(now),
      onReportLocate: vi.fn(),
      onReportSubmit: vi.fn(),
      onReportUpdate: vi.fn(),
      pendingReportUpdates,
      reportingEnabled: true,
    };

    await act(async () => {
      root.render(<LiveView {...commonProps} personalStorage={personalStorage} />);
    });
    expect(container.querySelector(".mf-live-pending-update")).toBeNull();

    await act(async () => {
      root.render(<LiveView {...commonProps} key="receipt-gone" personalStorage={storage()} />);
    });
    expect(container.querySelector(".mf-live-pending-update")).not.toBeNull();
    expect(container.textContent).toContain("Pioggia");
  });

  it("keeps the expiry dialog after the marker closes and restores focus on Close", async () => {
    const now = Date.now();
    const personalStorage = storage();
    rememberCommunityReport(
      readCommunityPersonalState({ now, storage: personalStorage }),
      {
        expiresAt: now + 60_000,
        groupId: "group-rain",
        id: "report-rain",
        revision: 1,
        typeId: "rain",
      },
      { now, storage: personalStorage },
    );
    const onReportUpdate = vi.fn(async () => {
      expireCommunityReport(
        readCommunityPersonalState({ now, storage: personalStorage }),
        "report-rain",
        { now, storage: personalStorage },
      );
      return {
        ok: false,
        reason: "observation_expired",
        reportId: "report-rain",
        serverState: {
          expires_at: now,
          report_id: "report-rain",
          revision: 1,
          server_time: now,
          status: "expired",
        },
      };
    });

    await act(async () => {
      root.render(
        <LiveView
          model={buildOwnedReportModel(now)}
          onReportLocate={vi.fn()}
          onReportSubmit={vi.fn()}
          onReportUpdate={onReportUpdate}
          personalStorage={personalStorage}
          reportingEnabled
        />,
      );
    });

    await act(async () => container.querySelector(".mf-live-community-map__marker").click());
    await act(async () => container.querySelector(".mf-live-community-own-report__update").click());
    await act(async () => new Promise((resolve) => globalThis.setTimeout(resolve, 0)));

    const dialog = document.body.querySelector(".mf-live-expired-update-dialog");
    expect(dialog).not.toBeNull();
    expect(document.body.querySelector(".mf-live-community-map__detail")).toBeNull();
    expect(container.querySelector(".mf-live-community-map__marker")).toBeNull();
    expect(container.textContent).toContain("Pioggia");
    expect(document.activeElement).toBe(dialog);

    await act(async () => [...dialog.querySelectorAll("button")]
      .find((button) => button.textContent === getLiveViewCopy("it").reportUpdateExpiredClose)
      .click());
    await act(async () => new Promise((resolve) => globalThis.setTimeout(resolve, 0)));
    expect(document.body.querySelector(".mf-live-expired-update-dialog")).toBeNull();
    expect(document.activeElement).toBe(container.querySelector('[role="region"]'));
  });

  it("opens the normal new-observation form after expiry without submitting", async () => {
    const now = Date.now();
    const personalStorage = storage();
    rememberCommunityReport(
      readCommunityPersonalState({ now, storage: personalStorage }),
      {
        expiresAt: now + 60_000,
        groupId: "group-rain",
        id: "report-rain",
        revision: 1,
        typeId: "rain",
      },
      { now, storage: personalStorage },
    );
    const onReportSubmit = vi.fn();
    const onReportLocate = vi.fn().mockResolvedValue({ ok: false, reason: "permission_denied" });
    const onReportUpdate = vi.fn(async () => {
      expireCommunityReport(
        readCommunityPersonalState({ now, storage: personalStorage }),
        "report-rain",
        { now, storage: personalStorage },
      );
      return { ok: false, reason: "observation_expired", reportId: "report-rain" };
    });

    await act(async () => {
      root.render(
        <LiveView
          model={buildOwnedReportModel(now)}
          onReportLocate={onReportLocate}
          onReportSubmit={onReportSubmit}
          onReportUpdate={onReportUpdate}
          personalStorage={personalStorage}
          reportingEnabled
        />,
      );
    });
    await act(async () => container.querySelector(".mf-live-community-map__marker").click());
    await act(async () => container.querySelector(".mf-live-community-own-report__update").click());

    const dialog = document.body.querySelector(".mf-live-expired-update-dialog");
    await act(async () => [...dialog.querySelectorAll("button")]
      .find((button) => button.textContent === getLiveViewCopy("it").reportUpdateExpiredNew)
      .click());
    await act(async () => new Promise((resolve) => globalThis.setTimeout(resolve, 0)));

    expect(document.body.querySelector(".mf-live-expired-update-dialog")).toBeNull();
    expect(document.body.querySelector(".mf-live-report-form[role=dialog]")).not.toBeNull();
    expect(onReportLocate).toHaveBeenCalledOnce();
    expect(onReportSubmit).not.toHaveBeenCalled();
  });

  it("removes a mismatched ownership CTA while keeping the public marker and daily quota", async () => {
    const now = Date.now();
    const personalStorage = storage();
    rememberCommunityReport(
      readCommunityPersonalState({ now, storage: personalStorage }),
      {
        expiresAt: now + 60_000,
        groupId: "group-rain",
        id: "report-rain",
        revision: 1,
      },
      { now, storage: personalStorage },
    );
    const onReportUpdate = vi.fn(async () => {
      releaseCommunityReportReceipt(
        readCommunityPersonalState({ now, storage: personalStorage }),
        "report-rain",
        { now, storage: personalStorage },
      );
      return {
        code: "community_observation_owner_mismatch",
        ok: false,
        reason: "observation_rejected",
        reportId: "report-rain",
      };
    });

    await act(async () => {
      root.render(
        <LiveView
          model={buildOwnedReportModel(now)}
          onReportLocate={vi.fn()}
          onReportSubmit={vi.fn()}
          onReportUpdate={onReportUpdate}
          personalStorage={personalStorage}
          reportingEnabled
        />,
      );
    });
    await act(async () => container.querySelector(".mf-live-community-map__marker").click());
    await act(async () => container.querySelector(".mf-live-community-own-report__update").click());
    await act(async () => new Promise((resolve) => globalThis.setTimeout(resolve, 0)));

    expect(container.querySelector(".mf-live-community-map__marker")).not.toBeNull();
    expect(document.body.querySelector(".mf-live-expired-update-dialog")).toBeNull();
    expect(getCommunityContributionCount(
      readCommunityPersonalState({ now: now + 1, storage: personalStorage }),
    )).toBe(1);

    await act(async () => container.querySelector(".mf-live-community-map__marker").click());
    expect(container.querySelector(".mf-live-community-own-report__update")).toBeNull();
  });
});
