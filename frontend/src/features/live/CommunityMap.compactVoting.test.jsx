// @vitest-environment jsdom

import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { getLiveViewCopy } from "../../copy/liveViewCopy";
import { CommunityMapPhenomenon } from "./CommunityMap";

const REPORT_TYPES = ["rain", "storm", "snow", "hail", "fog", "wind", "ice", "quiet"];

describe("pilot compact community voting", () => {
  let container;
  let root;
  let onConfirm;

  beforeEach(() => {
    globalThis.IS_REACT_ACT_ENVIRONMENT = true;
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
    onConfirm = vi.fn();
  });

  afterEach(async () => {
    await act(async () => root.unmount());
    container.remove();
    delete globalThis.IS_REACT_ACT_ENVIRONMENT;
  });

  async function render({ language = "it", typeId = "rain", ...overrides } = {}) {
    const copy = getLiveViewCopy(language);
    await act(async () => {
      root.render(
        <CommunityMapPhenomenon
          compactVoting
          copy={copy}
          onConfirm={onConfirm}
          phenomenon={{
            confirmations: { no: 2, yes: 7 },
            countLabel: copy.reportCountOne,
            groupId: `group-${typeId}`,
            sourceKeys: ["opaque-source-a"],
            timeLabel: copy.reportNow,
            typeId,
            typeLabel: copy.reportTypes[typeId],
          }}
          {...overrides}
        />,
      );
    });
    return copy;
  }

  function voteButton(vote) {
    return container.querySelector(`.mf-live-community-map__confirm-button--${vote}`);
  }

  function voteLabel(vote) {
    return voteButton(vote)?.querySelector(".mf-live-community-map__confirm-label")?.textContent;
  }

  describe.each([
    ["it", "Confermo", "Non c’è più"],
    ["fur", "O confermi", "Nol è plui"],
  ])("universal labels in %s", (language, yesLabel, noLabel) => {
    it.each(REPORT_TYPES)("uses the same two labels for %s", async (typeId) => {
      await render({ language, typeId });
      expect(voteLabel("yes")).toBe(yesLabel);
      expect(voteLabel("no")).toBe(noLabel);
      expect(voteButton("yes").disabled).toBe(false);
      expect(voteButton("no").disabled).toBe(false);
      expect(onConfirm).not.toHaveBeenCalled();
    });
  });

  it("preserves explicit caller overrides as part of the existing component API", async () => {
    await render({
      confirmationActionLabel: "Piove ancora",
      confirmationEndedActionLabel: "Non piove più",
    });
    expect(voteLabel("yes")).toBe("Piove ancora");
    expect(voteLabel("no")).toBe("Non piove più");
  });

  it("preserves exact visible and accessible counts and the selected confirmation", async () => {
    await render({ confirmationCounts: { no: 3, yes: 12 }, confirmationVote: "yes" });
    expect(voteButton("yes").getAttribute("aria-label")).toBe("Confermo. Conferme: 12");
    expect(voteButton("no").getAttribute("aria-label")).toBe("Non c’è più. Non c’è più: 3");
    expect(voteButton("yes").getAttribute("aria-pressed")).toBe("true");
    expect(voteButton("no").getAttribute("aria-pressed")).toBe("false");
    expect(voteButton("yes").querySelector(".mf-live-community-map__confirm-count")?.textContent)
      .toBe("12");
    expect(voteButton("no").querySelector(".mf-live-community-map__confirm-count")?.textContent)
      .toBe("3");
    expect(voteButton("yes").querySelector(".mf-live-community-map__confirm-count")?.getAttribute("aria-hidden"))
      .toBe("true");
    expect(voteButton("yes").disabled).toBe(false);
    expect(voteButton("no").disabled).toBe(false);
  });

  it("keeps localized accessible count labels in Friulian", async () => {
    await render({ language: "fur" });
    expect(voteButton("yes").getAttribute("aria-label")).toBe("O confermi. Confermis: 7");
    expect(voteButton("no").getAttribute("aria-label")).toBe("Nol è plui. Nol è plui: 2");
  });

  it.each(["yes", "no"])("dispatches the unchanged %s action with its exact group and trigger", async (vote) => {
    await render({ typeId: "quiet" });
    const trigger = voteButton(vote);
    await act(async () => trigger.click());
    expect(onConfirm).toHaveBeenCalledExactlyOnceWith("group-quiet", vote, trigger);
  });

  it("disables both actions during loading and does not dispatch another vote", async () => {
    await render({ confirmationStatus: "loading" });
    expect(voteButton("yes").disabled).toBe(true);
    expect(voteButton("no").disabled).toBe(true);
    await act(async () => {
      voteButton("yes").click();
      voteButton("no").click();
    });
    expect(onConfirm).not.toHaveBeenCalled();
  });

  it("shows a GPS error even in the compact card that hides confirmation details", async () => {
    await render({ hideConfirmationDetails: true, confirmationStatus: "error", confirmationError: "Attiva il GPS e riprova." });
    expect(container.querySelector('[role="status"]').textContent).toBe("Attiva il GPS e riprova.");
    expect(container.querySelector(".mf-live-community-map__denial-explanation")).toBeNull();
  });

  it("preserves the denial lock and pressed state without changing the short labels", async () => {
    await render({ confirmationStatus: "success", confirmationVote: "no" });
    expect(voteLabel("yes")).toBe("Confermo");
    expect(voteLabel("no")).toBe("Non c’è più");
    expect(voteButton("yes").getAttribute("aria-pressed")).toBe("false");
    expect(voteButton("no").getAttribute("aria-pressed")).toBe("true");
    expect(voteButton("yes").disabled).toBe(true);
    expect(voteButton("no").disabled).toBe(true);
    await act(async () => {
      voteButton("yes").click();
      voteButton("no").click();
    });
    expect(onConfirm).not.toHaveBeenCalled();
  });

  it("never offers voting on an owned report even if a confirmation handler was passed", async () => {
    await render({
      ownReport: {
        expiresAt: Date.now() + 3_600_000,
        groupId: "group-rain",
        reportId: "own-report-rain",
      },
    });
    expect(voteButton("yes")).toBeNull();
    expect(voteButton("no")).toBeNull();
    expect(container.querySelector(".mf-live-community-own-report")).not.toBeNull();
    expect(onConfirm).not.toHaveBeenCalled();
  });

  it.each(REPORT_TYPES)("keeps default legacy contextual labels for %s", async (typeId) => {
    const copy = await render({ compactVoting: undefined, typeId });
    expect(voteLabel("yes")).toBe(copy.confirmationActions[typeId].yes);
    expect(voteLabel("no")).toBe(copy.confirmationActions[typeId].no);
  });

  it("keeps explicit caller labels in the legacy default", async () => {
    await render({
      compactVoting: undefined,
      confirmationActionLabel: "Conferma locale personalizzata",
      confirmationEndedActionLabel: "Smentita locale personalizzata",
    });
    expect(voteLabel("yes")).toBe("Conferma locale personalizzata");
    expect(voteLabel("no")).toBe("Smentita locale personalizzata");
  });
});
