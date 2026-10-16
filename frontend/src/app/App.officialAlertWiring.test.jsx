import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

const testState = vi.hoisted(() => ({
  alert: {
    action: { anchor: "official-alerts", tab: "bulletin", type: "tab-anchor" },
    label: "Allerta arancione",
    meta: "Protezione Civile FVG",
    paragraphs: ["Temporali forti su tutta la regione."],
    text: "Temporali forti su tutta la regione.",
    tone: "orange",
    validityLabel: "Valida fino alle 23:59",
  },
  payload: { active: true, alerts: [{ id: "regional-orange" }] },
}));

vi.mock("../services/officialAlertsRuntime", () => ({
  loadOfficialAlertsRuntime: vi.fn(),
  readInitialOfficialAlertsRuntime: () => ({ payload: testState.payload }),
}));

vi.mock("../features/bulletin/bulletinViewModel", () => ({
  buildOfficialAlertPresentation: (payload) => (
    payload === testState.payload ? testState.alert : null
  ),
}));

vi.mock("../ui/layout/AppShell", () => ({
  AppShell: ({ children, officialAlert }) => (
    <div data-app-shell-alert={officialAlert?.label || "none"}>{children}</div>
  ),
}));

vi.mock("./labFlags", () => ({
  readUiV3LabFlag: () => false,
}));

vi.mock("./AppRoutes", () => ({
  AppRoutes: ({ officialAlert }) => (
    <div data-app-routes-alert={officialAlert?.label || "none"} />
  ),
}));

import App from "./App";

describe("App official alert wiring", () => {
  it("derives one independent alert presentation and shares it with shell and routes", () => {
    const markup = renderToStaticMarkup(<App />);

    expect(markup).toContain('data-app-shell-alert="Allerta arancione"');
    expect(markup).toContain('data-app-routes-alert="Allerta arancione"');
  });
});
