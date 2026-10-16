// @vitest-environment jsdom
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { PilotLanguageOnboarding } from "./PilotLanguageOnboarding";

describe("PilotLanguageOnboarding", () => {
  let container;
  let root;

  beforeEach(() => {
    globalThis.IS_REACT_ACT_ENVIRONMENT = true;
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
  });

  afterEach(async () => {
    await act(async () => root.unmount());
    container.remove();
    delete globalThis.IS_REACT_ACT_ENVIRONMENT;
  });

  it("offers the two explicit language choices without a dismiss action", async () => {
    const onLanguageSelect = vi.fn();

    await act(async () => {
      root.render(
        <PilotLanguageOnboarding
          language="it"
          onLanguageSelect={onLanguageSelect}
        />,
      );
    });

    expect(container.textContent).toContain("Scegli la lingua");
    expect(container.textContent).toContain("Benvenuto · Benvignût");
    expect(container.textContent).toContain("Italiano");
    expect(container.textContent).toContain("Furlan");
    expect(container.querySelector(".mf-web-onboarding--language")).not.toBeNull();
    expect(container.querySelector(".mf-pilot-language-onboarding__heading .mf-web-onboarding__icon"))
      .not.toBeNull();
    expect(container.querySelector(".mf-pilot-language-onboarding__heading h2")?.textContent)
      .toBe("Scegli la lingua");
    expect(container.querySelector(".mf-web-onboarding__card.mf-pilot-language-onboarding"))
      .not.toBeNull();
    expect(container.querySelector('[aria-label="Chiudi"]')).toBeNull();
    expect(container.querySelector('button[aria-pressed="true"]')?.textContent).toBe("Italiano");

    await act(async () => {
      [...container.querySelectorAll("button")]
        .find((button) => button.textContent === "Furlan")
        .click();
    });

    expect(onLanguageSelect).toHaveBeenCalledWith("fur");
  });
});
