import { useEffect, useRef, useState } from "react";
import { ArrowLeft, CalendarDays, ChevronRight, ExternalLink, MapPin, Navigation, ShoppingBag, X } from "lucide-react";
import { usePilotBackHandler } from "../../app/usePilotBackHandler";
import { useBrowserDialogBack } from "../../app/useBrowserDialogBack";
import { EVENT_RADII } from "../events/eventsRadius";
import { subscribeToMarketsDayClock } from "./marketsDayClock";
import { getMarketsCopy } from "./marketsCopy";
import { formatMarketDate, getMarket, MARKET_CATALOGUE, marketDateInEvents, marketDay, marketDirectionsUrl, publishedMarketDates, safeMarketUrl, selectMarkets } from "./marketsCatalog";

export function MarketsEntry({ language = "it", onOpen }) {
  const copy = getMarketsCopy(language);
  return <button type="button" className="mf-markets-entry" onClick={() => onOpen?.()}>
    <span className="mf-markets-entry__icon"><ShoppingBag size={25} aria-hidden="true" /></span>
    <span><strong>{copy.title}</strong><span>{copy.intro}</span><b>{copy.explore}</b></span>
    <ChevronRight size={22} aria-hidden="true" />
  </button>;
}

function MarketSummary({ market, language, onOpen }) {
  const copy = getMarketsCopy(language);
  return <button type="button" className="mf-market-card" onClick={() => onOpen(market.id)}>
    <span className="mf-market-card__top"><span>{market.comune} · {market.prov}</span><span>≈ {Math.round(market.distance)} km</span></span>
    <strong>{market.name}</strong>
    <span className="mf-market-card__kind">{market.kind}</span>
    <span className="mf-market-card__when"><CalendarDays aria-hidden="true" size={17} />
      <span>{market.group === "regular" ? copy.usual + ": " + market.cadence
        : market.dates[0] ? copy.published + ": " + formatMarketDate(market.dates[0].date, language) : copy.noDates}</span>
    </span>
    {market.place ? <span className="mf-market-card__place"><MapPin aria-hidden="true" size={16} />{market.place}</span> : null}
    <span className="mf-market-card__action">{copy.details}<ChevronRight aria-hidden="true" size={17} /></span>
  </button>;
}

export function MarketDetail({ market, language = "it", now = new Date(), radius = 20, onViewEvent, titleRef, catalogue = MARKET_CATALOGUE }) {
  const copy = getMarketsCopy(language);
  const dates = publishedMarketDates(market, now, catalogue);
  const source = safeMarketUrl(market.url);
  const stale = marketDay(now) > catalogue.validThrough || (market.validThrough && marketDay(now) > market.validThrough);
  const directions = marketDirectionsUrl(market);
  return <article className="mf-market-detail">
    <p className="mf-market-detail__kicker">{market.comune} · {market.prov} · {market.kind}</p>
    <h3 ref={titleRef} tabIndex={-1}>{market.name}</h3>
    <section><h4><MapPin aria-hidden="true" size={18} />{copy.where}</h4><p>{market.place || copy.noPlace}</p>
      {directions ? <a className="mf-market-link" href={directions} target="_blank" rel="noopener noreferrer"><Navigation size={17} aria-hidden="true" />{copy.directions}</a> : null}
    </section>
    <section><h4><CalendarDays aria-hidden="true" size={18} />{copy.when}</h4><p>{market.cadence}</p>
      {market.hours ? <p>{market.hours}</p> : null}
      {market.scheduleNote ? <p>{market.scheduleNote}</p> : null}
      <p className="mf-markets-note">{stale ? copy.stale : market.group === "regular" ? copy.usualNote : copy.dateNote}</p>
    </section>
    {market.group === "occasional" || dates.length ? <section>
      <h4>{copy.dates}</h4>
      {dates.length ? <ul className="mf-market-dates">{dates.map(edition => <li key={edition.id || edition.date}>
        <time dateTime={edition.date}>{formatMarketDate(edition.date, language)}</time>
        {edition.venue?.place ? <span>{edition.venue.place}</span> : null}
        {edition.venue && marketDirectionsUrl(market, edition) ? <a className="mf-market-link" href={marketDirectionsUrl(market, edition)} target="_blank" rel="noopener noreferrer">{copy.directions}</a> : null}
        {onViewEvent && marketDateInEvents(edition.date, now) ? <button type="button" onClick={() => onViewEvent({ marketId: market.id, date: edition.date, radius, ...(edition.id ? { editionId: edition.id } : {}) })}>
          {copy.viewEvent}<ChevronRight aria-hidden="true" size={16} />
        </button> : null}
      </li>)}</ul> : <p>{copy.noDates}</p>}
      {dates.some(edition => !marketDateInEvents(edition.date, now)) ? <p className="mf-markets-note">{copy.later}</p> : null}
    </section> : null}
    <footer className="mf-market-detail__source">
      {source ? <a href={source} target="_blank" rel="noopener noreferrer"><ExternalLink size={16} aria-hidden="true" />{copy.source}: {market.authority}</a> : null}
      <span>{copy.checked}: {formatMarketDate(market.checked, language)}</span>
    </footer>
  </article>;
}

export function MarketsExplorer({ request, location, language = "it", onClose, onViewEvent, catalogue = MARKET_CATALOGUE, catalogueStatus }) {
  const [radius, setRadius] = useState(20);
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
      window.requestAnimationFrame(() => (lastCardRef.current || listRef.current?.querySelector("select"))?.focus({ preventScroll: true }));
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
  return <dialog ref={dialogRef} className="mf-markets-dialog" aria-labelledby="mf-markets-title"
    onCancel={event => { event.preventDefault(); back(); }}
    onClick={event => { if (event.target === dialogRef.current) onClose(); }}>
    <header className="mf-markets-header">
      <div><ShoppingBag aria-hidden="true" size={22} /><h2 id="mf-markets-title">{copy.title}</h2></div>
      <button type="button" aria-label={copy.close} onClick={onClose}><X aria-hidden="true" size={22} /></button>
    </header>
    {selected ? <div className="mf-markets-detail-scroll" key={selected.id}>
      <button className="mf-markets-back" type="button" onClick={back}><ArrowLeft aria-hidden="true" size={18} />{copy.back}</button>
      <MarketDetail market={selected} language={language} now={today} radius={radius} onViewEvent={onViewEvent} titleRef={titleRef} catalogue={catalogue} />
    </div> : null}
    <div ref={listRef} className="mf-markets-content" hidden={Boolean(selected)}>
      {!model.supported ? <p className="mf-markets-empty" role="status">{copy.outside}</p> : <>
        <div className="mf-markets-context"><div><small>{copy.area}</small><strong>{model.origin.name}</strong></div>
          <label>{copy.radius}<select aria-label={copy.radius} value={radius} onChange={event => setRadius(Number(event.target.value))}>
            {EVENT_RADII.map(value => <option value={value} key={value}>{value} km</option>)}
          </select></label>
        </div>
        <div className="mf-markets-tabs" role="group" aria-label={language === "fur" ? "Period" : "Periodo"}>
          {["all", "today", "weekend"].map(value => <button type="button" key={value} aria-pressed={period === value} onClick={() => setPeriod(value)}>{copy[value]}</button>)}
        </div>
        <p className="mf-markets-note">{copy.distance}</p>
        {marketDay(today) > catalogue.validThrough ? <p className="mf-markets-note">{copy.stale}</p> : null}
        {!model.items.length ? <p className="mf-markets-empty" role="status">{catalogue.unavailable ? copy.unavailable : model.areaCount ? copy.noMatches : copy.noCoverage}</p> : null}
        {catalogueStatus === "cached" ? <p className="mf-markets-note">{copy.cached}</p> : null}
        {["regular", "occasional"].map(group => {
          const items = model.items.filter(market => market.group === group);
          return items.length ? <section className="mf-markets-group" key={group} aria-labelledby={"mf-markets-" + group}>
            <h3 id={"mf-markets-" + group}>{copy[group]}<span>{items.length}</span></h3>
            <div className="mf-markets-grid">{items.map(market => <MarketSummary key={market.id} market={market} language={language} onOpen={openMarket} />)}</div>
          </section> : null;
        })}
      </>}
      <p className="mf-markets-coverage">{copy.coverage}</p>
      {language === "fur" ? <p className="mf-markets-note" lang="fur">{copy.contentLanguage}</p> : null}
    </div>
  </dialog>;
}
