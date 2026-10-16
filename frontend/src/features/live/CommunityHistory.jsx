import { useEffect, useState } from "react";
import { fetchCommunityHistory, getPersistentLiveReportClientId } from "../../services/liveApi";
import { PILOT_LIVE_REPORT_ICONS } from "./liveReportIcons";
import { MapPin } from "lucide-react";

// History is read-only. Public records contain no installation identities.
export function CommunityHistory({ location, copy, language = "it" }) {
  const [page, setPage] = useState({ reports: [], status: "loading", next: null });
  const [request, setRequest] = useState({ offset: 0, retry: 0 });
  const scope = JSON.stringify({ istatCode: location?.istatCode,
    lat: location?.lat, lon: location?.lon });
  useEffect(() => {
    let alive = true;
    const controller = new AbortController();
    fetchCommunityHistory({ location: JSON.parse(scope),
      clientId: getPersistentLiveReportClientId(), offset: request.offset,
    }, { signal: controller.signal }).then((result) => {
      if (!alive) return;
      setPage((previous) => ({ reports: request.offset
        ? [...previous.reports, ...result.reports].filter((item, i, all) => all.findIndex((entry) => entry.id === item.id) === i)
        : result.reports, status: "ready", next: result.next_offset }));
    }).catch(() => {
      if (alive) setPage((previous) => ({ ...previous, status: "error" }));
    });
    return () => { alive = false; controller.abort(); };
  }, [scope, request]);
  const states = language === "fur"
    ? { active: "Ative", expired: "Scjadude", replaced: "Sostituide", ceased: "No plui presint" }
    : { active: "Attiva", expired: "Scaduta", replaced: "Sostituita", ceased: "Non c’è più" };
  return <div className="mf-community-history" aria-label={copy.historyTitle}>
    <p>{copy.historyDescription}</p>
    {page.status === "loading" ? <p role="status">{copy.historyLoading}</p> : null}
    {page.reports.map((report) => {
      const Icon = PILOT_LIVE_REPORT_ICONS[report.typeId] || MapPin;
      const date = new Intl.DateTimeFormat(language === "fur" ? "it-IT" : language, {
        day: "numeric", month: "short", hour: "2-digit", minute: "2-digit",
      }).format(report.createdAt);
      return <article className={`mf-territory-map__browse-item mf-territory-map__browse-item--${report.typeId}`} key={report.id}>
        <span aria-hidden="true"><Icon size={18} /></span>
        <span><strong>{copy.reportTypes[report.typeId] || report.typeId}{report.mine ? ` · ${copy.historyMine}` : ""}</strong>
          <small>{report.place} · {date}</small><small>{states[report.status] || states.expired}
            {report.mine && report.point ? ` · ${copy.historyPoint}`
              : report.mine && report.validated ? ` · ${copy.historyValidated}` : ""}</small>
        </span>
      </article>;
    })}
    {page.status === "ready" && !page.reports.length ? <p>{copy.historyEmpty}</p> : null}
    {page.status === "error" ? <p role="status">{copy.historyError}</p> : null}
    {page.status === "error" || page.next !== null ? <button type="button"
      disabled={page.status === "loading"}
      onClick={() => { setPage((old) => ({ ...old, status: "loading" }));
        setRequest((old) => ({ offset: page.status === "error" ? old.offset : page.next, retry: old.retry + 1 })); }}>
      {page.status === "error" ? copy.historyRetry : copy.historyMore}
    </button> : null}
  </div>;
}
