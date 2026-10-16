import { ChevronRight, MapPin, ThumbsDown, ThumbsUp, X } from "lucide-react";
import { AppIconButton } from "../../ui/components/AppIconButton";
import { PILOT_LIVE_REPORT_ICONS } from "./liveReportIcons";
import { getCommunityHistoryCountLabel, getCommunityHistoryTimeLabel } from "./communityRecentReports";

function historyDate(report, language) {
  return new Intl.DateTimeFormat(language === "fur" ? "it-IT" : language, {
    day: "numeric", month: "short", hour: "2-digit", minute: "2-digit",
  }).format(report.createdAt);
}

function historyStatus(report, copy) {
  const state = copy.recentStates[report.status] || copy.recentStates.expired;
  return [state, report.mine && (report.point ? copy.historyPoint
    : report.validated ? copy.historyValidated : "")].filter(Boolean).join(" · ");
}

export function CommunityRecentHistoryRow({ report, copy, language, now, onOpen }) {
  const Icon = PILOT_LIVE_REPORT_ICONS[report.typeId] || MapPin;
  const status = historyStatus(report, copy);
  return <button type="button" data-history-id={report.id}
    onClick={onOpen}
    className={`mf-territory-map__browse-item mf-territory-map__browse-item--${report.typeId}`}>
    <span aria-hidden="true"><Icon size={18} strokeWidth={2.35} /></span>
    <span><strong>{copy.reportTypes[report.typeId] || report.typeId}{report.mine ? ` · ${copy.historyMine}` : ""}</strong>
      <small>{report.place} · <time dateTime={new Date(report.createdAt).toISOString()} title={historyDate(report, language)}>
        {getCommunityHistoryTimeLabel(report.createdAt, now, copy)}</time> · {getCommunityHistoryCountLabel(report, copy)}</small>
      <small title={status}>{status}</small></span>
    <ChevronRight aria-hidden="true" size={17} />
  </button>;
}

export function CommunityHistoryDetail({ report, copy, language, now, detailRef, onClose }) {
  const Icon = PILOT_LIVE_REPORT_ICONS[report.typeId] || MapPin;
  const title = copy.reportTypes[report.typeId] || report.typeId;
  const counts = report.confirmations;
  return <div className="mf-territory-map__detail-layer">
    <section role="dialog" aria-modal="true" aria-label={`${title} · ${report.place} · ${copy.historyTitle}`}
      ref={detailRef} tabIndex={-1}
      className="mf-live-community-map__detail mf-territory-map__report-detail mf-territory-map__report-detail--pilot mf-community-history-detail">
      <div className="mf-territory-map__report-primary-heading">
        <span aria-hidden="true" className={`mf-territory-map__report-type-icon mf-territory-map__report-type-icon--${report.typeId}`}>
          <Icon size={24} strokeWidth={2.35} />
        </span>
        <span className="mf-territory-map__report-heading-copy">
          <strong>{title}</strong><small>{report.place} · {getCommunityHistoryCountLabel(report, copy)}</small>
        </span>
        <AppIconButton ariaLabel={copy.liveMapDetailClose} className="mf-territory-map__report-heading-button mf-territory-map__report-close" icon={X} onClick={onClose} />
      </div>
      <p className="mf-community-history-detail__meta">
        <span>{copy.historyLastReport}: <time dateTime={new Date(report.createdAt).toISOString()} title={historyDate(report, language)}>
          {getCommunityHistoryTimeLabel(report.createdAt, now, copy)}</time></span>
        <strong>{historyStatus(report, copy)}</strong>
      </p>
      <dl className="mf-community-history-detail__counts">
        <div><dt><ThumbsUp aria-hidden="true" size={16} />{copy.historyConfirmations}</dt><dd>{counts?.yes ?? "—"}</dd></div>
        <div><dt><ThumbsDown aria-hidden="true" size={16} />{copy.confirmationEndedAction}</dt><dd>{counts?.no ?? "—"}</dd></div>
      </dl>
      <p className="mf-community-history-detail__notice">{copy.historyReadOnly}</p>
    </section>
  </div>;
}
