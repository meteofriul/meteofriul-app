import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { WebStartupOnboarding } from "./WebStartupOnboarding";

describe("WebStartupOnboarding", () => {
  it("starts with one explicit GPS action and no notification prompt action", () => {
    const html = renderToStaticMarkup(
      <WebStartupOnboarding
        language="it"
        notificationRuntime={{ permission: "prompt", readOnly: false }}
        step="location"
      />,
    );

    expect(html).toContain("1 di 2 · Posizione");
    expect(html).toContain("Usa la mia posizione");
    expect(html).toContain(
      "Non conserviamo una cronologia delle coordinate GPS",
    );
    expect(html).not.toContain("mf-web-onboarding__actions--centered");
    expect(html).not.toContain("Autorizza notifiche");
  });

  it("explains official alerts and weather notices before the explicit web prompt", () => {
    const html = renderToStaticMarkup(
      <WebStartupOnboarding
        language="it"
        locationResult={{ ok: false, reason: "permission_denied" }}
        notificationRuntime={{ permission: "prompt", readOnly: false }}
        step="notifications"
      />,
    );

    expect(html).toContain("Allerte ufficiali");
    expect(html).toContain("Avvisi meteo");
    expect(html).toContain("anche quando la Web App non è aperta");
    expect(html).not.toContain("sospeso e in verifica");
    expect(html).toContain("Scegli il Comune");
    expect(html).toContain("Apri i permessi del sito dal lucchetto del browser");
    expect(html).toContain("Riprova posizione");
    expect(html).toContain("Autorizza notifiche");
  });

  it("shows an honest configured-build fallback in Furlan", () => {
    const html = renderToStaticMarkup(
      <WebStartupOnboarding
        language="fur"
        notificationRuntime={{
          permission: "unsupported",
          readOnly: true,
          reason: "web_enrollment_disabled",
          status: "not_configured",
        }}
        step="notifications"
      />,
    );

    expect(html).toContain("2 di 2 · Notifichis");
    expect(html).toContain("Notifichis te app Android");
    expect(html).toContain("no son ativis in cheste fase");
    expect(html).toContain("app Android Meteo Friûl");
    expect(html).toContain("mf-web-onboarding__actions--centered");
    expect(html).not.toContain("Lis Alertis uficiâls a saran ativis");
    expect(html).not.toContain("Autorize lis notifichis</button>");
  });

  it.each([
    ["timeout", "non ha risposto in tempo", true],
    ["stale_or_imprecise", "troppo vecchia o imprecisa", true],
    ["unsupported", "Chrome o Safari", false],
  ])("explains the %s GPS failure without weakening the location quality gate", (
    reason,
    expectedCopy,
    retryable,
  ) => {
    const html = renderToStaticMarkup(
      <WebStartupOnboarding
        language="it"
        locationResult={{ ok: false, reason }}
        notificationRuntime={{
          permission: "unsupported",
          readOnly: true,
          reason: "web_enrollment_disabled",
          status: "not_configured",
        }}
        step="notifications"
      />,
    );

    expect(html).toContain(expectedCopy);
    expect(html).toContain("Scegli il Comune");
    expect(html.includes("Riprova posizione")).toBe(retryable);
  });

  it("keeps the notification step in a checking state without calling it unsupported", () => {
    const html = renderToStaticMarkup(
      <WebStartupOnboarding
        language="it"
        notificationRuntime={{
          permission: "unknown",
          readOnly: true,
          status: "checking",
        }}
        step="notifications"
      />,
    );

    expect(html).toContain("Stiamo verificando");
    expect(html).toContain("Controllo in corso");
    expect(html).not.toContain("Questo browser non supporta");
    expect(html).not.toContain(">Chiudi</button>");
  });

  it("does not label a service worker initialization failure as an unsupported browser", () => {
    const html = renderToStaticMarkup(
      <WebStartupOnboarding
        language="it"
        notificationRuntime={{
          errorCategory: "service_worker",
          permission: "unsupported",
          readOnly: true,
          status: "error",
        }}
        step="notifications"
      />,
    );

    expect(html).toContain("Il componente notifiche del browser non si è attivato");
    expect(html).not.toContain("Questo browser non supporta");
  });

  it("uses a safe generic message for an unclassified initialization failure", () => {
    const html = renderToStaticMarkup(
      <WebStartupOnboarding
        language="fur"
        notificationRuntime={{
          errorCategory: "unknown",
          permission: "unsupported",
          readOnly: true,
          status: "error",
        }}
        step="notifications"
      />,
    );

    expect(html).toContain("No sin rivâts a inizializâ lis notifichis");
    expect(html).not.toContain("nol supuarte lis notifichis web");
  });
});
