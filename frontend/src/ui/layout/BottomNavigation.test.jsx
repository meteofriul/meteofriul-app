import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import { CalendarDays, CloudSun, Home, Map } from "lucide-react";

import { getUiShellCopy } from "../../app/uiShellCopy";
import { BottomNavigation } from "./BottomNavigation";

const TABS = [
  { Icon: Home, id: "home" },
  { Icon: CloudSun, id: "weather" },
  { Icon: CalendarDays, id: "events" },
  { Icon: Map, id: "discover" },
];

describe("BottomNavigation accessibility copy", () => {
  it.each([
    ["it", "Navigazione principale"],
    ["fur", "Navigazion principâl"],
  ])("uses the localized %s navigation label", (language, navigationLabel) => {
    const markup = renderToStaticMarkup(
      <BottomNavigation
        activeTab="home"
        copy={getUiShellCopy(language)}
        onTabChange={() => {}}
        tabs={TABS}
      />,
    );

    expect(markup).toContain(`<nav aria-label="${navigationLabel}"`);
  });

  it.each([
    ["it", "Apri nel bollettino: Allerta arancione"],
    ["fur", "Vierç tal boletin: Alerte naranzon"],
  ])("adds a localized actionable alert badge in %s", (language, ariaLabel) => {
    const label = language === "fur" ? "Alerte naranzon" : "Allerta arancione";
    const markup = renderToStaticMarkup(
      <BottomNavigation
        activeTab="events"
        copy={getUiShellCopy(language)}
        officialAlert={{ label, tone: "orange" }}
        onOfficialAlertOpen={() => {}}
        onTabChange={() => {}}
        tabs={TABS}
      />,
    );

    expect(markup).toContain('class="mf-bottom-nav-alert-badge"');
    expect(markup).toContain('data-alert-tone="orange"');
    expect(markup).toContain(`aria-label="${ariaLabel}"`);
    expect(markup).not.toContain("lucide-triangle-alert");
  });

  it.each(["home", "weather", "events", "discover"])("keeps the alert badge visible on %s", (activeTab) => {
    const markup = renderToStaticMarkup(
      <BottomNavigation
        activeTab={activeTab}
        copy={getUiShellCopy("it")}
        officialAlert={{ label: "Allerta gialla", tone: "yellow" }}
        onOfficialAlertOpen={() => {}}
        onTabChange={() => {}}
        tabs={TABS}
      />,
    );

    expect(markup).toContain("mf-bottom-nav-alert-badge");
  });

  it("does not add an alert control to Eventi without an active alert", () => {
    const markup = renderToStaticMarkup(
      <BottomNavigation
        activeTab="events"
        copy={getUiShellCopy("it")}
        onOfficialAlertOpen={() => {}}
        onTabChange={() => {}}
        tabs={TABS}
      />,
    );

    expect(markup).not.toContain("mf-bottom-nav-alert-badge");
  });

  it.each([
    ["it", "Eventi: 42 eventi"],
    ["fur", "Evenis: 42 evenis"],
  ])("shows the localized events total inside the existing tab in %s", (language, ariaLabel) => {
    const markup = renderToStaticMarkup(
      <BottomNavigation
        activeTab="home"
        copy={getUiShellCopy(language)}
        eventsTotal={42}
        onTabChange={() => {}}
        tabs={TABS}
      />,
    );

    expect(markup).toContain(`aria-label="${ariaLabel}"`);
    expect(markup).toContain('class="mf-bottom-nav-count-badge mf-bottom-nav-event-badge">42</span>');
    expect(markup.match(/<button/g)).toHaveLength(TABS.length);
  });

  it.each([
    [99, "99"],
    [100, "99+"],
    [489, "99+"],
  ])("caps only the visual events badge for a total of %s", (eventsTotal, badgeText) => {
    const markup = renderToStaticMarkup(
      <BottomNavigation
        activeTab="home"
        copy={getUiShellCopy("it")}
        eventsTotal={eventsTotal}
        onTabChange={() => {}}
        tabs={TABS}
      />,
    );

    expect(markup).toContain(`aria-label="Eventi: ${eventsTotal} eventi"`);
    expect(markup).toContain(
      `class="mf-bottom-nav-count-badge mf-bottom-nav-event-badge">${badgeText}</span>`,
    );
  });

  it.each([
    [1, "today", "Eventi: 1 evento oggi"],
    [23, "today", "Eventi: 23 eventi oggi"],
    [1, "next", "Eventi: 1 evento nei prossimi 15 giorni"],
    [96, "next", "Eventi: 96 eventi nei prossimi 15 giorni"],
  ])("announces the exact contextual count for %s/%s", (eventsTotal, eventsPeriod, ariaLabel) => {
    const markup = renderToStaticMarkup(
      <BottomNavigation
        activeTab="home"
        copy={getUiShellCopy("it")}
        eventsPeriod={eventsPeriod}
        eventsTotal={eventsTotal}
        onTabChange={() => {}}
        tabs={TABS}
      />,
    );

    expect(markup).toContain(`aria-label="${ariaLabel}"`);
  });

  it.each([null, 0, -1, 2.5])("hides an unavailable or empty events total (%s)", (eventsTotal) => {
    const markup = renderToStaticMarkup(
      <BottomNavigation
        activeTab="home"
        copy={getUiShellCopy("it")}
        eventsTotal={eventsTotal}
        onTabChange={() => {}}
        tabs={TABS}
      />,
    );

    expect(markup).not.toContain("mf-bottom-nav-event-badge");
    expect(markup).not.toContain('aria-label="Eventi:');
  });

  it.each([
    ["it", 1, "Meteo: 1 segnalazione recente", "1"],
    ["it", 12, "Meteo: 12 segnalazioni recenti", "12"],
    ["fur", 2, "Timp: 2 segnalazions resintis", "2"],
    ["it", 120, "Meteo: 120 segnalazioni recenti", "99+"],
  ])("shows the localized community total for %s/%s", (language, total, ariaLabel, badgeText) => {
    const markup = renderToStaticMarkup(
      <BottomNavigation
        activeTab="home"
        communityReportsTotal={total}
        copy={getUiShellCopy(language)}
        onTabChange={() => {}}
        tabs={TABS}
      />,
    );

    expect(markup).toContain(`aria-label="${ariaLabel}"`);
    expect(markup).toContain(
      `class="mf-bottom-nav-community-badge mf-bottom-nav-count-badge">${badgeText}</span>`,
    );
  });

  it.each([null, 0, -1, 1.5])("hides an unavailable or empty community total (%s)", (total) => {
    const markup = renderToStaticMarkup(
      <BottomNavigation
        activeTab="home"
        communityReportsTotal={total}
        copy={getUiShellCopy("it")}
        onTabChange={() => {}}
        tabs={TABS}
      />,
    );

    expect(markup).not.toContain("mf-bottom-nav-community-badge");
    expect(markup).not.toContain('aria-label="Meteo:');
  });

  it.each([
    ["it", 1, "Meteo: 1 nuova segnalazione", "1"],
    ["it", 12, "Meteo: 12 nuove segnalazioni", "12"],
    ["fur", 1, "Timp: 1 gnove segnalazion", "1"],
    ["fur", 2, "Timp: 2 gnovis segnalazions", "2"],
    ["it", 120, "Meteo: 120 nuove segnalazioni", "99+"],
  ])("announces unread community reports for %s/%s without capping the accessible count", (language, total, ariaLabel, badgeText) => {
    const markup = renderToStaticMarkup(
      <BottomNavigation
        activeTab="home"
        communityReportsTotal={total}
        communityReportsUnread
        copy={getUiShellCopy(language)}
        onTabChange={() => {}}
        tabs={TABS}
      />,
    );

    expect(markup).toContain(`aria-label="${ariaLabel}"`);
    expect(markup).toContain(
      `class="mf-bottom-nav-community-badge mf-bottom-nav-count-badge">${badgeText}</span>`,
    );
    expect(markup).not.toContain("recenti");
  });

  it.each([null, 0, -1, 1.5])("hides an unavailable or empty unread community count (%s)", (total) => {
    const markup = renderToStaticMarkup(
      <BottomNavigation
        activeTab="weather"
        communityReportsTotal={total}
        communityReportsUnread
        copy={getUiShellCopy("it")}
        onTabChange={() => {}}
        tabs={TABS}
      />,
    );

    expect(markup).not.toContain("mf-bottom-nav-community-badge");
    expect(markup).not.toContain('aria-label="Meteo:');
  });

  it("preserves the recent-report label when unread mode is explicitly disabled", () => {
    const markup = renderToStaticMarkup(
      <BottomNavigation
        activeTab="home"
        communityReportsTotal={2}
        communityReportsUnread={false}
        copy={getUiShellCopy("it")}
        onTabChange={() => {}}
        tabs={TABS}
      />,
    );

    expect(markup).toContain('aria-label="Meteo: 2 segnalazioni recenti"');
    expect(markup).not.toContain("nuove segnalazioni");
  });

  it("keeps alert, community and events badges in distinct positions", () => {
    const markup = renderToStaticMarkup(
      <BottomNavigation
        activeTab="home"
        communityReportsTotal={3}
        copy={getUiShellCopy("it")}
        eventsPeriod="today"
        eventsTotal={23}
        officialAlert={{ label: "Allerta gialla", tone: "yellow" }}
        onOfficialAlertOpen={() => {}}
        onTabChange={() => {}}
        tabs={TABS}
      />,
    );

    expect(markup).toContain("mf-bottom-nav-alert-badge");
    expect(markup).toContain("mf-bottom-nav-community-badge");
    expect(markup).toContain("mf-bottom-nav-event-badge");
  });

  it("keeps Meteo navigation unchanged and gives the badge its own action", () => {
    const onOfficialAlertOpen = vi.fn();
    const onTabChange = vi.fn();
    const navigation = BottomNavigation({
      activeTab: "discover",
      copy: getUiShellCopy("it"),
      officialAlert: { label: "Allerta rossa", tone: "red" },
      onOfficialAlertOpen,
      onTabChange,
      tabs: TABS,
    });
    const weatherSlot = navigation.props.children.find((slot) => slot.key === "weather");
    const [weatherButton, alertButton] = weatherSlot.props.children;

    weatherButton.props.onClick();
    alertButton.props.onClick();

    expect(onTabChange).toHaveBeenCalledWith("weather");
    expect(onOfficialAlertOpen).toHaveBeenCalledOnce();
  });

  it("locks the alert action together with the rest of the navigation", () => {
    const markup = renderToStaticMarkup(
      <BottomNavigation
        activeTab="events"
        copy={getUiShellCopy("it")}
        navigationLocked
        officialAlert={{ label: "Allerta gialla", tone: "yellow" }}
        onOfficialAlertOpen={() => {}}
        onTabChange={() => {}}
        tabs={TABS}
      />,
    );

    expect(markup).toMatch(/mf-bottom-nav-alert-badge[^>]*disabled=""/);
  });
});
