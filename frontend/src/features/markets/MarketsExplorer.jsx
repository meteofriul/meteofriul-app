import { useEffect, useRef, useState } from "react";
import { ArrowLeft, CalendarDays, ChevronRight, ExternalLink, Info, MapPin, Navigation, ShoppingBag, Store, X } from "lucide-react";
import { usePilotBackHandler } from "../../app/usePilotBackHandler";
import { useBrowserDialogBack } from "../../app/useBrowserDialogBack";
import { subscribeToMarketsDayClock } from "./marketsDayClock";
import { getMarketsCopy } from "./marketsCopy";
import { formatMarketDate, getMarket, MARKET_CATALOGUE, marketDateInEvents, marketDay, marketDirectionsUrl, marketKindLabel, publishedMarketDates, safeMarketUrl, selectMarkets } from "./marketsCatalog";

export function MarketsEntry({ language = "it", onOpen }) {
  const copy = getMarketsCopy(language);
  return <button type="button" className="mf-market-catalogue-link mf-market-catalogue-link--banner" onClick={() => onOpen?.()}>
    <span className="mf-market-banner__icon" aria-hidden="true"><Store size={27} strokeWidth={1.8} /></span>
    <span className="mf-market-banner__copy"><strong>{copy.title}</strong><span>{copy.explore}</span></span>
    <span className="mf-market-banner__arrow" aria-hidden="true"><ChevronRight size={22} strokeWidth={2.2} /></span>
  </button>;
}

const WEEKDAY_BADGES = ["DOM", "LUN", "MAR", "MER", "GIO", "VEN", "SAB"];
function marketCardBadge(market) {
  if (market.group === "regular") {
    const days = [...new Set((market.weekdays || []).filter(day => Number.isInteger(day) && day >= 0 && day <= 6))];
    if (!days.length) return null;
    if (days.length === 1) return { main: WEEKDAY_BADGES[days[0]], sub: "OGNI" };
    if (days.length === 2) return { main: days.map(day => WEEKDAY_BADGES[day]).join("/"), sub: "OGNI" };
    return { main: "PIÙ", sub: "GIORNI" };
  }
  const nextDate = market.dates?.[0]?.date;
  if (!nextDate) return null;
  const date = new Date(`${nextDate}T12:00:00Z`);
  return {
    main: new Intl.DateTimeFormat("it-IT", { day: "numeric", timeZone: "UTC" }).format(date),
    sub: new Intl.DateTimeFormat("it-IT", { month: "short", timeZone: "UTC" }).format(date).replace(".", "").toUpperCase(),
  };
}

function marketCardTitle(market) {
  const name = String(market.name || "");
  const suffix = ` di ${market.comune}`;
  return name.toLocaleLowerCase("it-IT").startsWith("mercato settimanale di ")
    && name.toLocaleLowerCase("it-IT").endsWith(suffix.toLocaleLowerCase("it-IT"))
    ? name.slice(0, -suffix.length) : name;
}

function MarketSummary({ market, language, onOpen }) {
  const copy = getMarketsCopy(language);
  const badge = marketCardBadge(market);
  const nextDate = market.dates?.[0]?.date;
  const distance = Math.round(market.distance);
  const when = market.group === "regular" ? market.cadence : nextDate ? formatMarketDate(nextDate, language) : copy.noDates;
  return <button type="button" className={`mf-market-card mf-market-card--${market.group}`} aria-label={`${market.name} · ${market.comune} · ${when} · ${copy.details}`} onClick={() => onOpen(market.id)}>
    <span className="mf-market-card__visual" aria-hidden="true">{badge
      ? <><strong>{badge.main}</strong><small>{badge.sub}</small></>
      : <Store size={27} strokeWidth={1.8} />}</span>
    <span className="mf-market-card__body">
      <strong>{marketCardTitle(market)}</strong>
      <span className="mf-market-card__location"><MapPin aria-hidden="true" size={13} /><span className="mf-market-card__city">{market.comune}</span>{distance > 0 ? <span className="mf-market-card__distance">· ≈ {distance} km</span> : null}</span>
      {market.group === "regular" || !nextDate ? <span className="mf-market-card__when"><CalendarDays aria-hidden="true" size={14} />
        <span>{market.group === "regular" ? market.cadence : copy.noDates}</span>
      </span> : null}
      {market.place ? <span className="mf-market-card__place">{market.place}</span> : null}
    </span>
    <span className="mf-market-card__arrow" aria-hidden="true"><ChevronRight size={16} /></span>
  </button>;
}

export function MarketDetail({ market, language = "it", now = new Date(), radius = 20, onViewEvent, titleRef, catalogue = MARKET_CATALOGUE }) {
  const copy = getMarketsCopy(language);
  const dates = publishedMarketDates(market, now, catalogue);
  const source = safeMarketUrl(market.url);
  const stale = marketDay(now) > catalogue.validThrough || (market.validThrough && marketDay(now) > market.validThrough);
  const directions = marketDirectionsUrl(market);
  const hours = String(market.hours || "").trim();
  const hoursAlreadyInCadence = hours && String(market.cadence || "").toLocaleLowerCase("it").includes(hours.toLocaleLowerCase("it"));
  const firstHour = hours.match(/\b\d{1,2}:\d{2}\b/)?.[0];
  const hoursAlreadyInNote = market.group === "occasional" && dates.length && firstHour && String(market.scheduleNote || "").includes(firstHour);
  const holidayAdviceInNote = /\bfestiv/i.test(market.scheduleNote || "");
  return <article className="mf-market-detail">
    <p className="mf-market-detail__kicker">{market.comune} · {market.prov} · {marketKindLabel(market)}</p>
    <h3 ref={titleRef} tabIndex={-1}>{market.name}</h3>
    <section><h4><MapPin aria-hidden="true" size={18} />{copy.where}</h4><p>{market.place || copy.noPlace}</p></section>
    {directions ? <a className="mf-market-detail__directions" href={directions} target="_blank" rel="noopener noreferrer"><Navigation size={18} aria-hidden="true" />{copy.directions}</a> : null}
    <section><h4><CalendarDays aria-hidden="true" size={18} />{copy.when}</h4>
      {market.group === "occasional" && dates.length ? <ul className="mf-market-dates">{dates.map(edition => <li key={edition.id || edition.date}>
        <span className="mf-market-dates__date"><time dateTime={edition.date}>{formatMarketDate(edition.date, language)}</time>{edition.hours ? <span>{edition.hours}</span> : null}</span>
        {edition.venue?.place ? <span>{edition.venue.place}</span> : null}
        {edition.venue && marketDirectionsUrl(market, edition) ? <a className="mf-market-link" href={marketDirectionsUrl(market, edition)} target="_blank" rel="noopener noreferrer">{copy.directions}</a> : null}
        {onViewEvent && marketDateInEvents(edition.date, now) ? <button type="button" onClick={() => onViewEvent({ marketId: market.id, date: edition.date, radius, ...(edition.id ? { editionId: edition.id } : {}) })}>
          {copy.viewEvent}<ChevronRight aria-hidden="true" size={16} />
        </button> : null}
      </li>)}</ul> : <><p>{market.cadence}</p>{market.group === "occasional" ? <p className="mf-markets-note">{copy.noDates}</p> : null}</>}
      {hours && !hoursAlreadyInCadence && !hoursAlreadyInNote ? <p>{hours}</p> : null}
      {market.scheduleNote ? <p>{market.scheduleNote}</p> : null}
      {stale || (market.group === "occasional" && dates.length) || (market.group === "regular" && !holidayAdviceInNote)
        ? <p className="mf-markets-note">{stale ? copy.stale : market.group === "regular" ? copy.usualNote : copy.dateNote}</p> : null}
    </section>
    {market.group === "regular" && dates.length ? <section>
      <h4>{copy.dates}</h4>
      <ul className="mf-market-dates">{dates.map(edition => <li key={edition.id || edition.date}>
        <span className="mf-market-dates__date"><time dateTime={edition.date}>{formatMarketDate(edition.date, language)}</time>{edition.hours ? <span>{edition.hours}</span> : null}</span>
        {edition.venue?.place ? <span>{edition.venue.place}</span> : null}
        {edition.venue && marketDirectionsUrl(market, edition) ? <a className="mf-market-link" href={marketDirectionsUrl(market, edition)} target="_blank" rel="noopener noreferrer">{copy.directions}</a> : null}
        {onViewEvent && marketDateInEvents(edition.date, now) ? <button type="button" onClick={() => onViewEvent({ marketId: market.id, date: edition.date, radius, ...(edition.id ? { editionId: edition.id } : {}) })}>
          {copy.viewEvent}<ChevronRight aria-hidden="true" size={16} />
        </button> : null}
      </li>)}</ul>
      {dates.some(edition => !marketDateInEvents(edition.date, now)) ? <p className="mf-markets-note">{copy.later}</p> : null}
    </section> : null}
    <footer className="mf-market-detail__source">
      {source ? <a href={source} target="_blank" rel="noopener noreferrer"><ExternalLink size={16} aria-hidden="true" />{copy.source}: {market.authority}</a> : null}
      <span>{copy.checked}: {formatMarketDate(market.checked, language)}</span>
    </footer>
  </article>;
}

export function MarketsExplorer({ request, location, language = "it", radius = 20, onClose, onViewEvent, catalogue = MARKET_CATALOGUE }) {
  const [period, setPeriod] = useState("all");
  const [selectedId, setSelectedId] = useState(request?.marketId || null);
  const [seenRequest, setSeenRequest] = useState(request);
  const [today, setToday] = useState(() => new Date());
  const dialogRef = useRef(null), titleRef = useRef(null), listRef = useRef(null), lastCardRef = useRef(null);
  if (seenRequest !== request) {
    setSeenRequest(request);
    if (request) setSelectedId(request.marketId || null);
  }
  const copy = getMarketsCopy(language);
  const model = request ? selectMarkets({ location, radius, period, now: today, catalogue }) : { supported: false, items: [] };
  const selected = model.supported ? getMarket(selectedId, catalogue) : null;
  const back = () => {
    if (selected) {
      setSelectedId(null);
      window.requestAnimationFrame(() => (lastCardRef.current || listRef.current?.querySelector("button"))?.focus({ preventScroll: true }));
    } else onClose();
  };
  usePilotBackHandler(back, Boolean(request));
  useBrowserDialogBack(onClose, Boolean(request));
  useEffect(() => request ? subscribeToMarketsDayClock(setToday) : undefined, [request]);
  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return undefined;
    if (request) {
      const opener = document.activeElement;
      if (!dialog.open) dialog.showModal();
      const previousOverflow = document.body.style.overflow;
      document.body.style.overflow = "hidden";
      return () => {
        if (dialog.open) dialog.close();
        document.body.style.overflow = previousOverflow;
        if (opener?.isConnected) opener.focus({ preventScroll: true });
      };
    }
    if (dialog.open) dialog.close();
  }, [request]);
  useEffect(() => { if (selected) titleRef.current?.focus(); }, [selected]);
  useEffect(() => () => { if (dialogRef.current?.open) dialogRef.current.close(); }, []);

  const openMarket = id => {
    lastCardRef.current = document.activeElement;
    setSelectedId(id);
  };
  if (!request) return null;
  return <dialog ref={dialogRef} className={`mf-markets-dialog${selected ? " is-detail" : ""}`} aria-labelledby="mf-markets-title"
    onCancel={event => { event.preventDefault(); back(); }}
    onClick={event => { if (event.target === dialogRef.current) onClose(); }}>
    <header className="mf-markets-header">
      <div>{selected ? <button className="mf-markets-header__back" type="button" aria-label={copy.back} onClick={back}><ArrowLeft aria-hidden="true" size={20} /></button>
        : <ShoppingBag aria-hidden="true" size={22} />}<h2 id="mf-markets-title">{selected ? copy.details : copy.title}</h2></div>
      <button type="button" aria-label={copy.close} onClick={onClose}><X aria-hidden="true" size={22} /></button>
    </header>
    {selected ? <div className="mf-markets-detail-scroll" key={selected.id}>
      <MarketDetail market={selected} language={language} now={today} radius={radius} onViewEvent={onViewEvent} titleRef={titleRef} catalogue={catalogue} />
    </div> : null}
    <div ref={listRef} className="mf-markets-content" hidden={Boolean(selected)}>
      {!model.supported ? <p className="mf-markets-empty" role="status">{copy.outside}</p> : <>
        <div className="mf-markets-context"><div aria-label={`${copy.area}: ${model.origin.name}`}><MapPin aria-hidden="true" size={18} /><strong>{model.origin.name}</strong></div></div>
        <div className="mf-markets-tabs" role="group" aria-label={language === "fur" ? "Period" : "Periodo"}>
          {["all", "today", "weekend"].map(value => <button type="button" key={value} aria-pressed={period === value} onClick={() => setPeriod(value)}>{copy[value]}</button>)}
        </div>
        {marketDay(today) > catalogue.validThrough ? <p className="mf-markets-note">{copy.stale}</p> : null}
        {!model.items.length ? <p className="mf-markets-empty" role="status">{catalogue.unavailable ? copy.unavailable : model.areaCount ? copy.noMatches : copy.noCoverage}</p> : null}
        {["regular", "occasional"].map(group => {
          const items = model.items.filter(market => market.group === group);
          return items.length ? <section className="mf-markets-group" key={group} aria-labelledby={"mf-markets-" + group}>
            <h3 id={"mf-markets-" + group}>{copy[group]}<span>{items.length}</span></h3>
            {group === "regular" ? <p className="mf-markets-group__hint"><Info aria-hidden="true" size={14} />{copy.holidayHint}</p> : null}
            <div className="mf-markets-grid">{items.map(market => <MarketSummary key={market.id} market={market} language={language} onOpen={openMarket} />)}</div>
          </section> : null;
        })}
      </>}
      <p className="mf-markets-coverage"><span>{copy.distance}</span><span>{copy.coverage}</span></p>
      {language === "fur" ? <p className="mf-markets-note" lang="fur">{copy.contentLanguage}</p> : null}
    </div>
  </dialog>;
}
