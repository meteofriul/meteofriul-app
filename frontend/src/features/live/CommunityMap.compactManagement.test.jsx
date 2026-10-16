// @vitest-environment jsdom

import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { getLiveViewCopy } from "../../copy/liveViewCopy";
import { CommunityMapPhenomenon } from "./CommunityMap";

const NOW = Date.parse("2026-09-21T12:00:00Z");

describe("pilot compact own-observation management", () => {
  let container;
  let root;
  let copy;
  let ownReport;
  let actions;
  let fetchMock;

  beforeEach(() => {
    globalThis.IS_REACT_ACT_ENVIRONMENT = true;
    vi.useFakeTimers({ toFake: ["Date", "setTimeout", "clearTimeout"] });
    vi.setSystemTime(NOW);
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
    copy = getLiveViewCopy("it");
    ownReport = Object.freeze({
      correctionUntil: NOW + 300_000,
      createdAt: NOW,
      expiresAt: NOW + 3_600_000,
      groupId: "group-rain",
      istatCode: "093033",
      place: "Pordenone",
      replacementAvailable: true,
      reportId: "report-rain",
      revision: 1,
      typeId: "rain",
    });
    actions = {
      onCorrect: vi.fn(),
      onReplace: vi.fn().mockResolvedValue({ ok: true }),
      onUpdate: vi.fn().mockResolvedValue({ ok: true, revision: 2 }),
      onWithdraw: vi.fn().mockResolvedValue({ ok: true }),
    };
    fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(async () => {
    await act(async () => root.unmount());
    container.remove();
    vi.useRealTimers();
    vi.unstubAllGlobals();
    delete globalThis.IS_REACT_ACT_ENVIRONMENT;
  });

  async function render(overrides = {}) {
    await act(async () => {
      root.render(
        <CommunityMapPhenomenon
          {...actions}
          compactManagement
          copy={copy}
          ownReport={ownReport}
          phenomenon={{
            confirmations: { no: 0, yes: 0 },
            countLabel: copy.reportCountOne,
            groupId: "group-rain",
            place: "Pordenone",
            sourceKeys: ["opaque-source-a"],
            timeLabel: copy.reportNow,
            typeId: "rain",
            typeLabel: copy.reportTypes.rain,
          }}
          pilotStyle
          {...overrides}
        />,
      );
    });
  }

  function button(label) {
    return [...container.querySelectorAll("button")]
      .find((candidate) => candidate.textContent.trim() === label) || null;
  }

  async function click(label) {
    const target = button(label);
    expect(target, `Expected button: ${label}`).not.toBeNull();
    await act(async () => target.click());
    return target;
  }

  function expectNoOperations() {
    Object.values(actions).forEach((callback) => expect(callback).not.toHaveBeenCalled());
    expect(fetchMock).not.toHaveBeenCalled();
  }

  async function openChange() {
    await click("Aggiorna o modifica");
    await click("Voglio cambiare la segnalazione");
  }

  it("opens the icon editor directly without mutation or an intermediate choice", async () => {
    const onEdit = vi.fn();
    await render({ onEdit });

    await click("Aggiorna o modifica");

    expect(onEdit).toHaveBeenCalledExactlyOnceWith(ownReport);
    expect(button("Il fenomeno continua")).toBeNull();
    expect(button("Voglio cambiare la segnalazione")).toBeNull();
    expect(button("Ritira segnalazione")).not.toBeNull();
    expectNoOperations();
    expect(ownReport.revision).toBe(1);
    expect(ownReport.expiresAt).toBe(NOW + 3_600_000);
  });

  it("offers direct management when the editor is the only management callback", async () => {
    const onEdit = vi.fn();
    await render({ onCorrect: undefined, onEdit, onReplace: undefined, onUpdate: undefined });

    await click("Aggiorna o modifica");

    expect(onEdit).toHaveBeenCalledExactlyOnceWith(ownReport);
    expectNoOperations();
  });

  it.each([null, { expiresAt: NOW + 3_600_000 }])("does not expose direct editing without an owned receipt (%j)", async (report) => {
    const onEdit = vi.fn();
    await render({ onEdit, ownReport: report });

    expect(button("Aggiorna o modifica")).toBeNull();
    expect(onEdit).not.toHaveBeenCalled();
    expectNoOperations();
  });

  it("hides direct editing during withdrawal confirmation, pending and error states", async () => {
    const onEdit = vi.fn();
    let finishWithdrawal;
    actions.onWithdraw.mockImplementation(() => new Promise((resolve) => { finishWithdrawal = resolve; }));
    await render({ onEdit });
    await click("Ritira segnalazione");

    expect(button("Aggiorna o modifica")).toBeNull();
    expect(document.activeElement).toBe(button("Mantieni"));
    expect(button("Mantieni")?.querySelector(".lucide-thumbs-up")?.getAttribute("aria-hidden")).toBe("true");
    expect(onEdit).not.toHaveBeenCalled();
    expectNoOperations();

    await click(copy.reportWithdrawConfirm);
    expect(button("Aggiorna o modifica")).toBeNull();
    expect(button("Mantieni")?.disabled).toBe(true);
    await click("Mantieni");
    expect(button("Aggiorna o modifica")).toBeNull();
    expect(onEdit).not.toHaveBeenCalled();
    expect(actions.onWithdraw).toHaveBeenCalledExactlyOnceWith(ownReport.reportId);
    await act(async () => finishWithdrawal({ ok: false }));
    expect(button("Aggiorna o modifica")).toBeNull();
    expect(document.activeElement).toBe(button("Mantieni"));

    await click("Mantieni");
    expect(document.activeElement).toBe(button("Ritira segnalazione"));
    await click("Aggiorna o modifica");
    expect(onEdit).toHaveBeenCalledExactlyOnceWith(ownReport);
  });

  it("does not opt legacy controls into direct editing merely because the callback exists", async () => {
    const onEdit = vi.fn();
    await render({ compactManagement: false, onEdit });

    expect(button("Aggiorna o modifica")).toBeNull();
    await click(copy.reportUpdate);
    expect(actions.onUpdate).toHaveBeenCalledExactlyOnceWith(ownReport);
    expect(onEdit).not.toHaveBeenCalled();
  });

  it("groups the unique own-report title and clock expiry in the compact summary", async () => {
    await render();

    const ownSection = container.querySelector(".mf-live-community-own-report");
    const summary = ownSection.querySelector(".mf-live-community-own-report__summary");
    const title = summary?.querySelector("strong");
    const expiry = summary?.querySelector(".mf-live-community-own-report__expiry");
    expect(summary?.parentElement).toBe(ownSection);
    expect(title?.textContent).toBe(copy.ownReportLabel);
    expect(title?.getAttribute("tabindex")).toBe("-1");
    expect(expiry?.textContent).toBe("Scade tra 60 min");
    expect(expiry?.querySelector(".lucide-clock-3")?.getAttribute("aria-hidden")).toBe("true");
    expect(ownSection.querySelectorAll("strong")).toHaveLength(1);
    expect(ownSection.querySelectorAll(".mf-live-community-own-report__expiry")).toHaveLength(1);
    expect(summary.querySelector("button")).toBeNull();

    await click("Aggiorna o modifica");
    expect(ownSection.querySelectorAll(".mf-live-community-own-report__summary")).toHaveLength(1);
    expect(ownSection.querySelectorAll("strong")).toHaveLength(1);
    expect(ownSection.querySelectorAll(".mf-live-community-own-report__expiry")).toHaveLength(1);
    expectNoOperations();
  });

  it("preserves the legacy title and expiry as direct siblings without the compact wrapper or clock", async () => {
    await render({ compactManagement: undefined });

    const ownSection = container.querySelector(".mf-live-community-own-report");
    const [title, expiry] = ownSection.children;
    expect(ownSection.querySelector(".mf-live-community-own-report__summary")).toBeNull();
    expect(title.tagName).toBe("STRONG");
    expect(title.textContent).toBe(copy.ownReportLabel);
    expect(title.hasAttribute("tabindex")).toBe(false);
    expect(expiry.tagName).toBe("SMALL");
    expect(expiry.textContent).toBe("Scade tra 60 min");
    expect(expiry.querySelector("svg")).toBeNull();
    expect(ownSection.querySelectorAll("strong")).toHaveLength(1);
    expectNoOperations();
  });

  it("starts with exactly two actions and navigates without mutating or requesting data", async () => {
    await render();

    expect([...container.querySelectorAll("button")].map((entry) => entry.textContent.trim()))
      .toEqual(["Aggiorna o modifica", "Ritira segnalazione"]);
    expect(container.textContent).toContain("Scade tra 60 min");
    expect(button(copy.reportUpdate)).toBeNull();

    await click("Aggiorna o modifica");
    expect(button("Il fenomeno continua")).not.toBeNull();
    expect(button("Voglio cambiare la segnalazione")).not.toBeNull();
    expect(button("Ritira segnalazione")).toBeNull();
    expect(document.activeElement).toBe(container.querySelector("h3"));
    expectNoOperations();

    await click("Voglio cambiare la segnalazione");
    expect(button("Ho sbagliato")).not.toBeNull();
    expect(button("La situazione è cambiata")).not.toBeNull();
    expect(button("Ritira e continua")).toBeNull();
    expectNoOperations();

    await click(copy.reportManageBack);
    expect(button("Il fenomeno continua")).not.toBeNull();
    await click(copy.reportManageBack);
    expect(document.activeElement).toBe(button("Aggiorna o modifica"));
    expectNoOperations();
  });

  it("routes a mistaken report only to correction, leaving its timestamps unchanged", async () => {
    await render();
    await openChange();
    await click("Ho sbagliato");

    expect(actions.onCorrect).toHaveBeenCalledExactlyOnceWith(ownReport);
    expect(actions.onUpdate).not.toHaveBeenCalled();
    expect(actions.onWithdraw).not.toHaveBeenCalled();
    expect(actions.onReplace).not.toHaveBeenCalled();
    expect(fetchMock).not.toHaveBeenCalled();
    expect(ownReport.createdAt).toBe(NOW);
    expect(ownReport.expiresAt).toBe(NOW + 3_600_000);
    expect(ownReport.revision).toBe(1);
  });

  it("requires an explicit final confirmation before a changed situation replaces anything", async () => {
    await render();
    await openChange();
    await click("La situazione è cambiata");
    expect(container.textContent).toContain(copy.reportReplacementBody);
    expect(button("Ritira e continua")).not.toBeNull();
    expectNoOperations();

    await click(copy.reportManageBack);
    expectNoOperations();
    expect(button("Il fenomeno continua")).not.toBeNull();
    await click("Voglio cambiare la segnalazione");
    await click("La situazione è cambiata");
    await click("Ritira e continua");

    expect(actions.onReplace).toHaveBeenCalledExactlyOnceWith(ownReport);
    expect(actions.onCorrect).not.toHaveBeenCalled();
    expect(actions.onUpdate).not.toHaveBeenCalled();
    expect(actions.onWithdraw).not.toHaveBeenCalled();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("skips the intention chooser once correction has expired, but not replacement confirmation", async () => {
    await render({ ownReport: { ...ownReport, correctionUntil: NOW } });
    await openChange();

    expect(button("Ho sbagliato")).toBeNull();
    expect(button("La situazione è cambiata")).toBeNull();
    expect(button("Ritira e continua")).not.toBeNull();
    expectNoOperations();
    await click("Ritira e continua");
    expect(actions.onReplace).toHaveBeenCalledExactlyOnceWith({ ...ownReport, correctionUntil: NOW });
  });

  it("removes correction at the original five-minute deadline without renewing or rewriting the receipt", async () => {
    await render();
    await openChange();
    await act(async () => vi.advanceTimersByTime(299_999));
    expect(button("Ho sbagliato")).not.toBeNull();
    await act(async () => vi.advanceTimersByTime(1));

    expect(button("Ho sbagliato")).toBeNull();
    expect(button("La situazione è cambiata")).not.toBeNull();
    expect(ownReport.correctionUntil).toBe(NOW + 300_000);
    expect(ownReport.expiresAt).toBe(NOW + 3_600_000);
    expectNoOperations();
  });

  it("rechecks the correction deadline on a stale button before invoking the callback", async () => {
    await render();
    await openChange();
    const staleCorrection = button("Ho sbagliato");
    vi.setSystemTime(NOW + 300_000);
    await act(async () => staleCorrection.click());

    expect(button("Ho sbagliato")).toBeNull();
    expectNoOperations();
  });

  it("does not offer change when correction and replacement are unavailable", async () => {
    await render({ ownReport: { ...ownReport, correctionUntil: NOW, replacementAvailable: false } });
    await click("Aggiorna o modifica");
    expect(button("Il fenomeno continua")).not.toBeNull();
    expect(button("Voglio cambiare la segnalazione")).toBeNull();
    expect(container.textContent).toContain(copy.reportChangeUnavailable);
    expectNoOperations();
  });

  it("updates only after the continuation choice and shows summary success for two seconds", async () => {
    await render();
    await click("Aggiorna o modifica");
    expectNoOperations();
    await click("Il fenomeno continua");

    expect(actions.onUpdate).toHaveBeenCalledExactlyOnceWith(ownReport);
    expect(actions.onCorrect).not.toHaveBeenCalled();
    expect(actions.onReplace).not.toHaveBeenCalled();
    expect(button(copy.reportUpdateDone)?.disabled).toBe(true);
    expect(button("Ritira segnalazione")).not.toBeNull();
    const ownHeading = container.querySelector(".mf-live-community-own-report__summary strong");
    expect(ownHeading?.textContent).toBe(copy.ownReportLabel);
    expect(document.activeElement).toBe(ownHeading);
    expect(container.querySelector(".mf-live-community-own-report__update-announcement")?.textContent)
      .toBe(copy.reportUpdateSuccess);

    await act(async () => vi.advanceTimersByTime(1_999));
    expect(button(copy.reportUpdateDone)).not.toBeNull();
    await act(async () => vi.advanceTimersByTime(1));
    expect(button("Aggiorna o modifica")).not.toBeNull();
    expect(document.activeElement).toBe(ownHeading);
    expect(actions.onUpdate).toHaveBeenCalledOnce();
  });

  it("locks child choices and navigation while an update is unresolved", async () => {
    let resolveUpdate;
    actions.onUpdate.mockImplementation(() => new Promise((resolve) => { resolveUpdate = resolve; }));
    await render();
    await click("Aggiorna o modifica");
    await click("Il fenomeno continua");

    expect(button(copy.reportUpdating)?.disabled).toBe(true);
    expect(button(copy.reportManageBack)?.disabled).toBe(true);
    expect(button("Voglio cambiare la segnalazione")?.disabled).toBe(true);
    await click("Voglio cambiare la segnalazione");
    await click(copy.reportManageBack);
    expect(actions.onCorrect).not.toHaveBeenCalled();
    expect(actions.onReplace).not.toHaveBeenCalled();
    expect(actions.onWithdraw).not.toHaveBeenCalled();
    expect(actions.onUpdate).toHaveBeenCalledOnce();

    await act(async () => resolveUpdate({ ok: true, revision: 2 }));
    expect(button(copy.reportUpdateDone)).not.toBeNull();
  });

  it("keeps update errors retryable inside the child action without withdrawing or replacing", async () => {
    actions.onUpdate.mockResolvedValueOnce({ ok: false, reason: "request_failed" });
    await render();
    await click("Aggiorna o modifica");
    await click("Il fenomeno continua");

    const retry = container.querySelector(".mf-live-community-own-report__update.is-error");
    expect(retry?.textContent).toContain(copy.reportUpdateRetry);
    expect(retry?.textContent).toContain(copy.reportUpdateRetryHint);
    expect(container.querySelector(".mf-live-community-own-report__update-status")).toBeNull();
    expect(button(copy.reportUpdateDone)).toBeNull();
    expect(actions.onCorrect).not.toHaveBeenCalled();
    expect(actions.onReplace).not.toHaveBeenCalled();
    expect(actions.onWithdraw).not.toHaveBeenCalled();
    await act(async () => retry.click());
    expect(actions.onUpdate).toHaveBeenCalledTimes(2);
    expect(button(copy.reportUpdateDone)).not.toBeNull();
  });

  it("does not reinterpret server-confirmed expiry as success, correction, or replacement", async () => {
    actions.onUpdate.mockResolvedValueOnce({ ok: false, reason: "observation_expired" });
    await render();
    await click("Aggiorna o modifica");
    await click("Il fenomeno continua");

    expect(actions.onUpdate).toHaveBeenCalledExactlyOnceWith(ownReport);
    expect(button(copy.reportUpdateDone)).toBeNull();
    expect(container.querySelector(".mf-live-community-own-report__update.is-error")).toBeNull();
    expect(actions.onCorrect).not.toHaveBeenCalled();
    expect(actions.onReplace).not.toHaveBeenCalled();
    expect(actions.onWithdraw).not.toHaveBeenCalled();
    expect(ownReport.expiresAt).toBe(NOW + 3_600_000);
  });

  it("keeps withdrawal behind its existing explicit confirmation and prevents competing management", async () => {
    await render();
    await click("Ritira segnalazione");
    expect(button("Aggiorna o modifica")).toBeNull();
    expect([...container.querySelectorAll("button")].map((entry) => entry.textContent.trim()))
      .toEqual(["Mantieni", copy.reportWithdrawConfirm]);
    expect(container.textContent).toContain(copy.reportWithdrawBody);
    expectNoOperations();
    await click("Mantieni");
    expect(button("Aggiorna o modifica")?.disabled).toBe(false);
    expectNoOperations();
    await click("Ritira segnalazione");
    await click(copy.reportWithdrawConfirm);

    expect(actions.onWithdraw).toHaveBeenCalledExactlyOnceWith("report-rain");
    expect(actions.onCorrect).not.toHaveBeenCalled();
    expect(actions.onReplace).not.toHaveBeenCalled();
    expect(actions.onUpdate).not.toHaveBeenCalled();
  });

  it("keeps the full cancellation label and update control outside compact pilot presentation", async () => {
    await render({ compactManagement: false });
    await click(copy.reportWithdraw);

    expect(button(copy.reportWithdrawCancel)).not.toBeNull();
    expect(button(copy.reportWithdrawCancel).querySelector(".lucide-thumbs-up")).toBeNull();
    expect(button("Mantieni")).toBeNull();
    expect(button(copy.reportUpdate)?.disabled).toBe(true);
    await click(copy.reportWithdrawCancel);
    expectNoOperations();
  });

  it("uses the short Friulian keep label without voting or withdrawing", async () => {
    copy = getLiveViewCopy("fur");
    await render();
    await click(copy.reportWithdrawCompact);
    expect(button("Ten")).not.toBeNull();
    await click("Ten");
    expect(button(copy.reportManage)?.disabled).toBe(false);
    expectNoOperations();
  });

  it("preserves the direct update control when compact management is not opted into", async () => {
    await render({ compactManagement: undefined });
    expect(button("Aggiorna o modifica")).toBeNull();
    expect(button(copy.reportUpdate)).not.toBeNull();
    expect(button(copy.reportWithdraw)).not.toBeNull();
    await click(copy.reportUpdate);
    expect(actions.onUpdate).toHaveBeenCalledExactlyOnceWith(ownReport);
  });
});
