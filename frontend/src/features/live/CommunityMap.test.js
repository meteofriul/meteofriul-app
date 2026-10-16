import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import { getLiveViewCopy } from "../../copy/liveViewCopy";
import {
  CommunityGuidelinesConsentDialog,
  CommunityMapPhenomenon,
  CommunityModerationDialog,
} from "./CommunityMap";
import {
  hideCommunityModerationSources,
  submitCommunityModerationFlag,
} from "./communityModerationActions";
import {
  isolateCommunityModalBackground,
  trapCommunityModerationFocus,
} from "./communityModerationFocus";

describe("community map moderation actions", () => {
  it("keeps keyboard focus inside the moderation dialog", () => {
    const first = { focus: vi.fn() };
    const last = { focus: vi.fn() };
    const dialog = {
      contains: vi.fn(
        (element) => element === dialog || element === first || element === last,
      ),
      querySelectorAll: vi.fn(() => [first, last]),
    };
    const forwardEvent = { key: "Tab", preventDefault: vi.fn(), shiftKey: false };
    const backwardEvent = { key: "Tab", preventDefault: vi.fn(), shiftKey: true };

    expect(trapCommunityModerationFocus(forwardEvent, dialog, last)).toBe(true);
    expect(forwardEvent.preventDefault).toHaveBeenCalledTimes(1);
    expect(first.focus).toHaveBeenCalledTimes(1);
    expect(trapCommunityModerationFocus(backwardEvent, dialog, first)).toBe(true);
    expect(backwardEvent.preventDefault).toHaveBeenCalledTimes(1);
    expect(last.focus).toHaveBeenCalledTimes(1);

    const initialBackwardEvent = {
      key: "Tab",
      preventDefault: vi.fn(),
      shiftKey: true,
    };
    expect(trapCommunityModerationFocus(initialBackwardEvent, dialog, dialog)).toBe(true);
    expect(last.focus).toHaveBeenCalledTimes(2);

    const initialForwardEvent = {
      key: "Tab",
      preventDefault: vi.fn(),
      shiftKey: false,
    };
    expect(trapCommunityModerationFocus(initialForwardEvent, dialog, dialog)).toBe(true);
    expect(first.focus).toHaveBeenCalledTimes(2);
    expect(dialog.querySelectorAll.mock.calls[0][0]).toContain("summary");
  });

  it("makes the app background inert while the modal is open", () => {
    const attributes = new Map();
    const appRoot = {
      getAttribute: vi.fn((name) => attributes.get(name) ?? null),
      inert: false,
      removeAttribute: vi.fn((name) => attributes.delete(name)),
      setAttribute: vi.fn((name, value) => attributes.set(name, value)),
    };
    const release = isolateCommunityModalBackground({
      getElementById: vi.fn(() => appRoot),
    });

    expect(appRoot.inert).toBe(true);
    expect(attributes.get("aria-hidden")).toBe("true");
    release();
    expect(appRoot.inert).toBe(false);
    expect(attributes.has("aria-hidden")).toBe(false);
  });

  it("also isolates a portaled map while a nested consent dialog is open", () => {
    const createTarget = ({ ariaHidden = null, inert = false } = {}) => {
      const attributes = new Map();
      if (ariaHidden != null) attributes.set("aria-hidden", ariaHidden);
      return {
        attributes,
        getAttribute: vi.fn((name) => attributes.get(name) ?? null),
        inert,
        removeAttribute: vi.fn((name) => attributes.delete(name)),
        setAttribute: vi.fn((name, value) => attributes.set(name, value)),
      };
    };
    const appRoot = createTarget({ ariaHidden: "true", inert: true });
    const mapLayer = createTarget();
    const release = isolateCommunityModalBackground({
      getElementById: vi.fn(() => appRoot),
      querySelectorAll: vi.fn(() => [mapLayer]),
    });

    expect(appRoot.inert).toBe(true);
    expect(appRoot.attributes.get("aria-hidden")).toBe("true");
    expect(mapLayer.inert).toBe(true);
    expect(mapLayer.attributes.get("aria-hidden")).toBe("true");

    release();
    expect(appRoot.inert).toBe(true);
    expect(appRoot.attributes.get("aria-hidden")).toBe("true");
    expect(mapLayer.inert).toBe(false);
    expect(mapLayer.attributes.has("aria-hidden")).toBe(false);
  });

  it("keeps the map report action distinct from the no-longer-present vote", () => {
    const copy = getLiveViewCopy("it");
    const markup = renderToStaticMarkup(
      createElement(CommunityMapPhenomenon, {
        copy,
        onConfirm: () => {},
        onOpenModeration: () => {},
        phenomenon: {
          confirmations: { no: 0, yes: 1 },
          countLabel: copy.reportCountOne,
          groupId: "group-rain",
          sourceKeys: ["opaque-source-a"],
          timeLabel: copy.reportNow,
          typeId: "rain",
          typeLabel: copy.reportTypes.rain,
        },
      }),
    );

    expect(markup).toContain(`aria-label="${copy.reportManageContent}"`);
    expect(markup).toContain("Piove ancora");
    expect(markup).toContain("Non piove più");
    expect(markup).toContain('aria-label="Piove ancora. Conferme: 1"');
    expect(markup).toContain('aria-label="Non piove più. Smentite: 0"');
    expect(markup).toContain("lucide-thumbs-up");
    expect(markup).toContain("lucide-thumbs-down");
    expect(markup).toContain("mf-live-community-map__confirm-count");
    expect(markup).toContain(copy.confirmationRecentOne);
    expect(markup).toContain("Fonte anonima ·");
    expect(markup).not.toContain("opaque-source-a");
  });

  it("keeps confirmation actions while hiding compact report details", () => {
    const copy = getLiveViewCopy("it");
    const markup = renderToStaticMarkup(
      createElement(CommunityMapPhenomenon, {
        copy,
        hideConfirmationDetails: true,
        onConfirm: () => {},
        phenomenon: {
          confirmations: { no: 1, yes: 1 },
          countLabel: copy.reportCountOne,
          groupId: "group-rain",
          sourceKeys: ["opaque-source-a"],
          timeLabel: copy.reportNow,
          typeId: "rain",
          typeLabel: copy.reportTypes.rain,
        },
      }),
    );

    expect(markup).toContain("mf-live-community-map__confirm-actions");
    expect(markup).toContain("Piove ancora");
    expect(markup).toContain("Non piove più");
    expect(markup).toContain('aria-label="Piove ancora. Conferme: 1"');
    expect(markup).toContain('aria-label="Non piove più. Smentite: 1"');
    expect(markup).not.toContain("mf-live-community-map__denial-explanation");
    expect(markup).not.toContain("mf-live-community-map__confirmation-summary");
    expect(markup).not.toContain("mf-live-community-map__denial-status");
    expect(markup).not.toContain(copy.denialExplanation);
    expect(markup).not.toContain(copy.confirmationRecentOne);
    expect(markup).not.toContain(copy.denialCountOne);
  });

  it("labels an own report without offering self-confirmation or moderation", () => {
    const copy = getLiveViewCopy("it");
    const markup = renderToStaticMarkup(
      createElement(CommunityMapPhenomenon, {
        copy,
        onConfirm: () => {},
        onOpenModeration: () => {},
        ownReport: {
          expiresAt: Date.now() + 120_000,
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
      }),
    );

    expect(markup).toContain(copy.ownReportLabel);
    expect(markup).not.toContain("Piove ancora");
    expect(markup).not.toContain(copy.reportManageContent);
  });

  it("offers persistent withdrawal only for an owned report with its exact id", () => {
    const copy = getLiveViewCopy("it");
    const phenomenon = {
      confirmations: { no: 0, yes: 0 },
      countLabel: copy.reportCountOne,
      groupId: "group-rain",
      sourceKeys: ["opaque-source-a"],
      timeLabel: copy.reportNow,
      typeId: "rain",
      typeLabel: copy.reportTypes.rain,
    };
    const owned = renderToStaticMarkup(
      createElement(CommunityMapPhenomenon, {
        copy,
        onWithdraw: () => {},
        ownReport: {
          expiresAt: Date.now() + 120_000,
          groupId: "group-rain",
          reportId: "report-rain",
        },
        phenomenon,
      }),
    );
    const inferredOnly = renderToStaticMarkup(
      createElement(CommunityMapPhenomenon, {
        copy,
        onWithdraw: () => {},
        ownReport: { groupId: "group-rain" },
        phenomenon,
      }),
    );

    expect(owned).toContain(copy.reportWithdraw);
    expect(owned).toContain("lucide-trash-2");
    expect(inferredOnly).not.toContain(copy.reportWithdraw);
  });

  it("renders one-time guidelines consent before the first confirmation", () => {
    const copy = getLiveViewCopy("it");
    const markup = renderToStaticMarkup(
      createElement(CommunityGuidelinesConsentDialog, {
        copy,
        onAccept: () => {},
        onClose: () => {},
      }),
    );

    expect(markup).toContain('role="dialog"');
    expect(markup).toContain(copy.confirmationTermsPrompt);
    expect(markup).toContain(copy.confirmationTermsAccept);
    expect(markup).toContain(copy.confirmationConsentSubmit);
    expect(markup).toContain('type="checkbox"');
  });

  it("offers a focused local block for every source in a mixed group", () => {
    const copy = getLiveViewCopy("it");
    const markup = renderToStaticMarkup(
      createElement(CommunityModerationDialog, {
        copy,
        onClose: () => {},
        onHideSources: () => {},
        phenomenon: { sourceKeys: ["source-a", "source-b"] },
      }),
    );

    expect(markup).toContain(copy.reportHideSourcesBody);
    expect(markup).toContain(copy.reportHideSources);
    expect(markup).toContain('autofocus=""');
    expect(markup).not.toContain("source-a");
    expect(markup).not.toContain("source-b");
  });

  it("closes the moderation dialog after a successful flag", async () => {
    const onClose = vi.fn();
    const onFlag = vi.fn().mockResolvedValue({ ok: true });
    const phenomenon = { groupId: "group-rain" };

    await expect(submitCommunityModerationFlag({
      onClose,
      onFlag,
      phenomenon,
      reason: "inaccurate",
    })).resolves.toEqual({ ok: true });

    expect(onFlag).toHaveBeenCalledWith(phenomenon, "inaccurate");
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("keeps the moderation dialog open when the flag request fails", async () => {
    const onClose = vi.fn();

    await expect(submitCommunityModerationFlag({
      onClose,
      onFlag: vi.fn().mockResolvedValue({ ok: false }),
      phenomenon: { groupId: "group-rain" },
      reason: "misuse",
    })).resolves.toEqual({ ok: false });

    expect(onClose).not.toHaveBeenCalled();
  });

  it("hides the single opaque source and closes the dialog", () => {
    const onClose = vi.fn();
    const onHideSources = vi.fn();
    const phenomenon = { sourceKeys: ["source-a"] };

    hideCommunityModerationSources({ onClose, onHideSources, phenomenon });

    expect(onHideSources).toHaveBeenCalledWith(phenomenon);
    expect(onClose).toHaveBeenCalledTimes(1);
  });
});
