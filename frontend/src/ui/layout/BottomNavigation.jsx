const ALERT_TONES = new Set(["yellow", "orange", "red"]);

export function BottomNavigation({
  activeTab,
  communityReportsTotal = null,
  communityReportsUnread = false,
  copy,
  eventsPeriod = null,
  eventsTotal = null,
  navigationLocked = false,
  officialAlert = null,
  onOfficialAlertOpen,
  onTabChange,
  tabs,
}) {
  const showOfficialAlertBadge = Boolean(officialAlert);
  const officialAlertTone = ALERT_TONES.has(officialAlert?.tone)
    ? officialAlert.tone
    : "neutral";
  const officialAlertLabel = String(
    officialAlert?.label || copy.officialAlertTitle || "",
  ).trim();
  const officialAlertAriaLabel = [
    copy.officialAlertNavigationLabel,
    officialAlertLabel,
  ].filter(Boolean).join(": ");

  return (
    <nav aria-label={copy.navigationLabel || "Navigazione principale"} className="mf-bottom-nav">
      {tabs.map(({ id, Icon }) => {
        const selected = activeTab === id;
        const showAlertBadge = id === "weather" && showOfficialAlertBadge;
        const showEventsBadge = id === "events"
          && Number.isInteger(eventsTotal)
          && eventsTotal > 0;
        const showCommunityBadge = id === "weather"
          && Number.isInteger(communityReportsTotal)
          && communityReportsTotal > 0;
        const eventsBadgeText = eventsTotal > 99 ? "99+" : eventsTotal;
        const communityBadgeText = communityReportsTotal > 99 ? "99+" : communityReportsTotal;
        const eventsCountLabel = eventsPeriod === "today"
          ? eventsTotal === 1 ? copy.eventCountTodayOneLabel : copy.eventCountTodayLabel
          : eventsPeriod === "next"
            ? eventsTotal === 1 ? copy.eventCountNextOneLabel : copy.eventCountNextLabel
            : copy.eventCountLabel || "eventi";
        const communityCountLabel = communityReportsUnread
          ? communityReportsTotal === 1
            ? copy.communityReportUnreadCountOneLabel
            : copy.communityReportUnreadCountLabel
          : communityReportsTotal === 1
            ? copy.communityReportCountOneLabel
            : copy.communityReportCountLabel;
        const tabAriaLabel = showEventsBadge
          ? `${copy.tabs[id]}: ${eventsTotal} ${eventsCountLabel}`
          : showCommunityBadge
            ? `${copy.tabs[id]}: ${communityReportsTotal} ${communityCountLabel}`
            : undefined;

        return (
          <div className="mf-bottom-nav-slot" key={id}>
            <button
              aria-label={tabAriaLabel}
              aria-current={selected ? "page" : undefined}
              className={`mf-bottom-nav-item ${selected ? "is-active" : ""}`}
              disabled={navigationLocked && !selected}
              onClick={() => onTabChange(id)}
              type="button"
            >
              <span aria-hidden="true" className="mf-bottom-nav-item__icon">
                <Icon size={20} strokeWidth={2.25} />
                {showEventsBadge ? (
                  <span className="mf-bottom-nav-count-badge mf-bottom-nav-event-badge">
                    {eventsBadgeText}
                  </span>
                ) : null}
                {showCommunityBadge ? (
                  <span className="mf-bottom-nav-community-badge mf-bottom-nav-count-badge">
                    {communityBadgeText}
                  </span>
                ) : null}
              </span>
              <span>{copy.tabs[id]}</span>
            </button>
            {showAlertBadge ? (
              <button
                aria-label={officialAlertAriaLabel}
                className="mf-bottom-nav-alert-badge"
                data-alert-tone={officialAlertTone}
                disabled={navigationLocked}
                onClick={onOfficialAlertOpen}
                type="button"
              >
              </button>
            ) : null}
          </div>
        );
      })}
    </nav>
  );
}
