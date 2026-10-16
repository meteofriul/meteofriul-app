// @vitest-environment jsdom
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { SettingsView } from "./SettingsView";

const back = vi.hoisted(() => ({ register: vi.fn(), unregister: vi.fn() }));
vi.mock("../../services/pilotBackNavigation", () => ({ registerPilotBackHandler: back.register }));
vi.mock("../../services/localWeatherPilot", () => ({
  isDefinitiveAppExperience: () => true,
  isLocalWeatherPilot: () => true,
  getLocalWeatherPilotNow: () => Date.now(),
  getLocalWeatherPilotTestNow: () => null,
}));

let container;
let root;
let originalShow;
let originalClose;
beforeEach(() => {
  vi.clearAllMocks();
  back.register.mockReturnValue(back.unregister);
  globalThis.IS_REACT_ACT_ENVIRONMENT = true;
  originalShow = Object.getOwnPropertyDescriptor(HTMLDialogElement.prototype, "showModal");
  originalClose = Object.getOwnPropertyDescriptor(HTMLDialogElement.prototype, "close");
  Object.defineProperty(HTMLDialogElement.prototype, "showModal", {
    configurable: true, value() { this.open = true; },
  });
  Object.defineProperty(HTMLDialogElement.prototype, "close", {
    configurable: true, value() { this.open = false; this.dispatchEvent(new Event("close")); },
  });
  container = document.createElement("div");
  document.body.append(container);
  root = createRoot(container);
});
afterEach(async () => {
  await act(async () => root.unmount());
  container.remove();
  vi.restoreAllMocks();
  if (originalShow) Object.defineProperty(HTMLDialogElement.prototype, "showModal", originalShow);
  else delete HTMLDialogElement.prototype.showModal;
  if (originalClose) Object.defineProperty(HTMLDialogElement.prototype, "close", originalClose);
  else delete HTMLDialogElement.prototype.close;
  delete globalThis.IS_REACT_ACT_ENVIRONMENT;
});

it("lets Android Back close the profile information without leaving Settings", async () => {
  await act(async () => root.render(<SettingsView activeLocation={{ city: "Pordenone" }} />));
  const open = container.querySelector('[aria-label="Sentinelle, alias e punti"]');
  const dialog = container.querySelector("dialog");
  expect(dialog.open).toBe(false);
  expect(back.register).not.toHaveBeenCalled();
  await act(async () => open.click());
  expect(dialog.open).toBe(true);
  await act(async () => back.register.mock.calls[0][0]());
  expect(dialog.open).toBe(false);
  expect(container.querySelector(".mf-settings-identity")).not.toBeNull();
  expect(back.unregister).toHaveBeenCalledOnce();
  await act(async () => open.click());
  expect(dialog.open).toBe(true);
  await act(async () => container.querySelector('[aria-label="Chiudi informazioni"]').click());
  expect(dialog.open).toBe(false);
  expect(back.unregister).toHaveBeenCalledTimes(2);
});
