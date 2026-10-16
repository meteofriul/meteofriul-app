import { useEffect, useRef, useState } from "react";
import {
  ArrowLeft, ArrowRight, Check, CheckCircle2, Clock3, CloudFog, CloudHail,
  CloudLightning, CloudRain, CloudSun, History, LocateFixed, MapPin, Moon,
  Plus, RotateCcw, Send, ShieldCheck, Snowflake, Sun, Trophy, Wind, X,
} from "lucide-react";
import { createPreviewState, creationWait, currentRecords, historyRecords, HOUR, PREVIEW_TYPES, previewReducer, rankFor } from "./communityPreviewState";
import "../../../ui/tokens/colors.css";
import "../../../ui/tokens/typography.css";
import "./communityPreview.css";

const ICONS = { rain: CloudRain, storm: CloudLightning, snow: Snowflake, hail: CloudHail, fog: CloudFog, wind: Wind, ice: Snowflake, quiet: Sun };
const STATES = { active: "Attiva", expired: "Scaduta", replaced: "Sostituita", ceased: "Non più presente" };
const time = (value) => new Intl.DateTimeFormat("it-IT", { hour: "2-digit", minute: "2-digit", timeZone: "Europe/Rome" }).format(value);
const historyTime = (value) => new Intl.DateTimeFormat("it-IT", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", timeZone: "Europe/Rome" }).format(value);
const typeFor = (id) => PREVIEW_TYPES.find((item) => item.id === id);

function PhenomenonIcon({ type, size = 23 }) {
  const Icon = ICONS[type] || CloudSun;
  return <span className={`cp-icon cp-icon--${type}`}><Icon size={size} aria-hidden="true" /></span>;
}

function ReportCard({ report, now, history, onVote }) {
  const title = typeFor(report.type)?.label;
  const remaining = Math.max(0, Math.ceil((report.expiresAt - now) / 60_000));
  return <article className={`cp-card ${report.mine ? "cp-card--mine" : ""}`}>
    <div className="cp-report-head">
      <PhenomenonIcon type={report.type} />
      <div className="cp-report-title"><strong>{title}</strong><span>{report.place} · {history ? historyTime(report.createdAt) : time(report.createdAt)}</span></div>
      {report.mine ? <span className="cp-pill cp-pill--mine">Tu</span> : null}
      {history ? <span className={`cp-pill cp-pill--${report.status}`}>{STATES[report.status]}</span> : null}
    </div>
    <div className="cp-report-meta">
      {report.status === "active" ? <span><Clock3 size={13} aria-hidden="true" />Ancora {remaining} min</span> : null}
      {report.mine && report.point ? <span className="cp-point"><CheckCircle2 size={14} aria-hidden="true" />1 punto ottenuto</span>
        : report.mine && report.validated ? <span>Confermata · senza nuovo punto</span>
          : report.yes > 0 ? <span>{report.yes} {report.yes === 1 ? "conferma" : "conferme"}</span>
            : report.status !== "active" ? <span>Non confermata</span>
              : <span>In attesa di conferma</span>}
    </div>
    {!history && !report.mine && report.status === "active" ? <div className="cp-votes">
      <button type="button" aria-pressed={report.voted === "yes"} disabled={report.voted === "no"} onClick={() => onVote(report.id, "yes")}><Check size={16} aria-hidden="true" />{report.voted === "yes" ? "Hai confermato" : "Confermo"}</button>
      <button type="button" disabled={report.voted === "no"} onClick={() => onVote(report.id, "no")}><X size={16} aria-hidden="true" />Non c’è più</button>
    </div> : null}
  </article>;
}

function MapSketch({ records }) {
  return <div className="cp-map" aria-label="Schema illustrativo di Pordenone con segnalazioni di esempio">
    <svg viewBox="0 0 460 195" aria-hidden="true" preserveAspectRatio="xMidYMid slice">
      <rect width="460" height="195" fill="var(--cp-map-base)" />
      <path d="M0 0h150l-22 70-80 22L0 66ZM350 0h110v72l-65 30-70-55ZM0 150l104-20 55 65H0ZM360 145l100-40v90H310Z" fill="var(--cp-map-green)" />
      <g stroke="var(--cp-map-road)" strokeWidth="9" fill="none"><path d="M-20 175L490 24M35-20l130 245M0 58l460 83M288-25l-38 247M405-10L340 215" /></g>
      <g stroke="var(--cp-map-line)" strokeWidth="1.4" fill="none"><path d="M-20 175L490 24M35-20l130 245M0 58l460 83M288-25l-38 247M405-10L340 215" /></g>
      <path d="M201-10C173 45 292 60 231 120S262 160 218 210" fill="none" stroke="var(--cp-map-water)" strokeWidth="7" />
      <text x="201" y="120" fill="var(--cp-muted)" fontSize="13" fontWeight="700">Pordenone</text>
      <text x="320" y="40" fill="var(--cp-muted)" fontSize="10">Cordenons</text>
      <text x="48" y="144" fill="var(--cp-muted)" fontSize="10">Porcia</text>
    </svg>
    {records.slice(0, 4).map((report, index) => <span key={report.id} className={`cp-map-pin ${report.mine ? "is-mine" : ""}`} style={{ left: `${[40, 63, 28, 76][index]}%`, top: `${[34, 58, 66, 25][index]}%` }} title={`${typeFor(report.type)?.label}${report.mine ? " · Tu" : ""}`}><PhenomenonIcon type={report.type} size={18} /></span>)}
    <span className="cp-map-caption">Mappa illustrativa · dati di esempio</span>
  </div>;
}

function ReportDialog({ state, gps, fail, onGpsRetry, onFailureConsumed, onStateChange, onClose }) {
  const dialog = useRef(null);
  const timer = useRef(null);
  const [step, setStep] = useState("choose");
  const [selected, setSelected] = useState("");
  const [accepted, setAccepted] = useState(false);
  const [busy, setBusy] = useState(false);
  const own = currentRecords(state).find((report) => report.mine && report.status === "active");
  const type = typeFor(selected);
  useEffect(() => {
    dialog.current?.showModal();
    return () => clearTimeout(timer.current);
  }, []);
  function submit() {
    if (busy || !accepted) return;
    setBusy(true);
    timer.current = setTimeout(() => {
      const next = previewReducer(state, { type: "submit", phenomenon: selected, gps, fail });
      onStateChange(next);
      if (fail) onFailureConsumed();
      if (!next.error) setStep("receipt");
      setBusy(false);
    }, 450);
  }
  return <dialog ref={dialog} className="cp-dialog" aria-labelledby="cp-dialog-title" onCancel={(event) => { if (busy) event.preventDefault(); else onClose(); }}>
    <div className="cp-dialog-top">
      <span className="cp-eyebrow">{step === "receipt" ? "Fatto" : step === "review" ? "2 di 2 · Riepilogo" : "1 di 2 · Osservazione"}</span>
      <button className="cp-icon-button" type="button" disabled={busy} aria-label="Chiudi segnalazione" onClick={onClose}><X size={20} /></button>
    </div>
    <h2 id="cp-dialog-title">{step === "choose" ? "Cosa vedi adesso?" : step === "review" ? "Controlla e invia" : "Segnalazione inviata"}</h2>
    {step === "choose" ? <>
      <p className="cp-dialog-intro">Segnala il meteo che osservi nella tua zona.</p>
      <div className="cp-types">{PREVIEW_TYPES.map((item) => <button type="button" key={item.id} aria-pressed={selected === item.id} onClick={() => setSelected(item.id)}><PhenomenonIcon type={item.id} /><span>{item.label}</span>{selected === item.id ? <Check size={15} aria-hidden="true" /> : null}</button>)}</div>
      <div className={`cp-location ${!gps ? "cp-location--error" : ""}`}><LocateFixed size={21} aria-hidden="true" /><div><strong>{gps ? "Pordenone" : "Posizione non disponibile"}</strong><span>{gps ? "Comune verificato dalla posizione" : "La posizione serve a verificare dove osservi il fenomeno."}</span></div>{!gps ? <button type="button" onClick={onGpsRetry}>Riprova</button> : null}</div>
      <p className="cp-privacy"><ShieldCheck size={15} aria-hidden="true" />Sulla mappa appare solo la zona del Comune.</p>
      <button className="cp-primary" type="button" disabled={!selected || !gps} onClick={() => setStep("review")}>Continua<ArrowRight size={18} aria-hidden="true" /></button>
    </> : step === "review" ? <>
      <div className="cp-review"><PhenomenonIcon type={selected} size={34} /><span>Stai segnalando</span><strong>{type.label}</strong><span>a <b>Pordenone</b></span></div>
      <div className="cp-review-details"><p><Clock3 size={17} aria-hidden="true" />Visibile per 60 minuti, fino alle {time(state.now + HOUR)}.</p>{own ? <p><History size={17} aria-hidden="true" />Sostituirà la tua segnalazione di {typeFor(own.type).label.toLocaleLowerCase("it")}, che resterà nello storico.</p> : null}</div>
      <label className="cp-consent"><input type="checkbox" checked={accepted} onChange={(event) => setAccepted(event.target.checked)} disabled={busy} /><span>Confermo di descrivere ciò che osservo adesso.</span></label>
      {state.error ? <p className="cp-error" role="alert">{state.error}</p> : null}
      <button className="cp-primary" type="button" disabled={busy || !accepted} onClick={submit}>{busy ? "Invio in corso…" : "Invia segnalazione"}<Send size={18} aria-hidden="true" /></button>
      <button className="cp-back" type="button" disabled={busy} onClick={() => { onStateChange({ ...state, error: "" }); setStep("choose"); }}><ArrowLeft size={15} aria-hidden="true" />Torna alla scelta</button>
    </> : <>
      <div className="cp-success"><CheckCircle2 size={48} aria-hidden="true" /><h3>{type.label} a Pordenone</h3><p>La tua osservazione è ora sulla mappa.</p><span>Scade alle {time(state.now + HOUR)}</span></div>
      <p className="cp-receipt-note">{state.notice}</p>
      <button className="cp-primary" type="button" onClick={onClose}>Torna alle segnalazioni<ArrowRight size={18} aria-hidden="true" /></button>
    </>}
  </dialog>;
}

export default function CommunityPreview() {
  const [state, setState] = useState(() => createPreviewState());
  const [tab, setTab] = useState("now");
  const [open, setOpen] = useState(false);
  const [dark, setDark] = useState(false);
  const [wide, setWide] = useState(false);
  const [gps, setGps] = useState(true);
  const [fail, setFail] = useState(false);
  const records = currentRecords(state);
  const active = records.filter((report) => report.status === "active" && report.voted !== "no");
  const own = active.find((report) => report.mine);
  const history = historyRecords(state);
  const wait = creationWait(state);
  const countdown = wait.seconds >= 3600
    ? `${Math.floor(wait.seconds / 3600)} h ${Math.ceil((wait.seconds % 3600) / 60)} min`
    : `${Math.floor(wait.seconds / 60)}:${String(wait.seconds % 60).padStart(2, "0")}`;
  const apply = (action) => setState((current) => previewReducer(current, action));
  useEffect(() => {
    document.documentElement.dataset.theme = dark ? "dark" : "light";
  }, [dark]);

  return <div className={`cp-workspace ${wide ? "cp-workspace--wide" : ""}`}>
    <header className="cp-preview-heading"><span className="cp-preview-label">ANTEPRIMA LOCALE</span><h1>Le nuove segnalazioni</h1><p>Prova il percorso con dati di esempio. Nessuna segnalazione viene pubblicata.</p></header>
    <main className="cp-layout">
      <section className="cp-app" aria-label="Anteprima dell’app">
        <header className="cp-app-header"><CloudSun size={26} aria-hidden="true" /><strong>Meteo Friûl</strong><span>COMMUNITY</span></header>
        <div className="cp-content">
          <div className="cp-title-row"><div><span className="cp-eyebrow"><MapPin size={13} aria-hidden="true" /> Pordenone e dintorni</span><h2>Segnalazioni</h2></div><span className="cp-live-dot" title="Dati di esempio">Adesso</span></div>
          <div className="cp-tabs" aria-label="Visualizzazione"><button type="button" aria-pressed={tab === "now"} onClick={() => setTab("now")}>Sulla mappa<span>{active.length}</span></button><button type="button" aria-pressed={tab === "history"} onClick={() => setTab("history")}><History size={16} aria-hidden="true" />Storico · 48 ore</button></div>
          {!open && (state.notice || state.error) ? <p className={state.error ? "cp-error" : "cp-notice"} role="status">{state.error || state.notice}</p> : null}
          {tab === "now" ? <>
            <MapSketch records={active} />
            {own ? <><h3 className="cp-section-title">La tua osservazione</h3><ReportCard report={own} now={state.now} /></> : <p className="cp-empty-own">Nessuna tua segnalazione attiva. Cosa vedi nella tua zona?</p>}
            <h3 className="cp-section-title">Dalla Community</h3>
            <div className="cp-report-list">{active.filter((report) => !report.mine).map((report) => <ReportCard key={report.id} report={report} now={state.now} onVote={(id, vote) => apply({ type: "vote", id, vote, gps })} />)}</div>
            {!active.some((report) => !report.mine) ? <p className="cp-empty-own">Non ci sono altre osservazioni attive nella zona.</p> : null}
          </> : <>
            <p className="cp-history-intro">Le osservazioni della zona nelle ultime 48 ore. Quelle archiviate restano consultabili e non si possono votare.</p>
            <div className="cp-report-list">{history.map((report) => <ReportCard key={report.id} report={report} now={state.now} history />)}</div>
            {!history.length ? <p className="cp-empty-own">Nessuna osservazione nelle ultime 48 ore.</p> : null}
          </>}
          <section className="cp-profile" aria-label="Il tuo contributo"><div className="cp-profile-rank"><Trophy size={17} aria-hidden="true" /><strong>{rankFor(state.points)}</strong></div><div className="cp-stats"><span><b>{state.total}</b>Inviate</span><span><b>{state.validated}</b>Confermate</span><span><b>{state.points}</b>Punti</span></div><details><summary>Inviate, confermate e punti</summary><p><b>Inviate:</b> tutte le tue osservazioni accettate, anche quelle scadute. <b>Confermate:</b> quelle convalidate da un’altra installazione, anche senza un nuovo punto.</p><p><b>Punti:</b> al massimo uno per segnalazione convalidata. Per lo stesso fenomeno nello stesso Comune devono passare 3 ore dall’ultimo punto ricevuto. Nessun tetto giornaliero ai punti. “Tranquillo” e il solo voto non danno punti. Il rango è solo estetico.</p></details></section>
        </div>
        <footer className="cp-app-footer"><button className="cp-primary" type="button" disabled={wait.seconds > 0} onClick={() => { apply({ type: "clear" }); setOpen(true); }}><Plus size={21} aria-hidden="true" />{wait.seconds ? `Segnala tra ${countdown}` : "Segnala"}</button><p>{wait.seconds ? wait.reason === "hour" ? "Hai raggiunto 4 invii negli ultimi 60 minuti." : wait.reason === "day" ? "Hai raggiunto 12 invii nelle ultime 24 ore." : "Almeno 3 minuti tra due invii." : own ? "La nuova osservazione sostituisce la tua precedente." : "La tua osservazione resterà attiva per 60 minuti."}</p></footer>
      </section>
      <aside className="cp-controls" aria-label="Controlli dell’anteprima">
        <span className="cp-eyebrow">Solo per questa prova</span><h2>Esplora il percorso</h2><p>Interfaccia interattiva con stato in memoria. La mappa e il GPS sono simulati; ricaricando riparti dall’esempio iniziale.</p>
        <div className="cp-control-group"><strong>Visualizzazione</strong><div className="cp-control-buttons"><button type="button" aria-pressed={dark} onClick={() => setDark(!dark)}>{dark ? <Sun size={16} /> : <Moon size={16} />}{dark ? "Tema chiaro" : "Tema scuro"}</button><button type="button" aria-pressed={wide} onClick={() => setWide(!wide)}>{wide ? "Vista telefono" : "Vista ampia"}</button></div></div>
        <div className="cp-control-group"><strong>Tempo simulato · {time(state.now)}</strong><div className="cp-control-buttons">{[3, 60, 180].map((minutes) => <button type="button" key={minutes} onClick={() => apply({ type: "advance", minutes })}>+{minutes === 180 ? "3 ore" : `${minutes} min`}</button>)}</div><small>Usa +3 min per superare l’attesa tra invii.</small></div>
        <div className="cp-control-group"><strong>Prova gli imprevisti</strong><label><input type="checkbox" checked={!gps} onChange={(event) => setGps(!event.target.checked)} />GPS non disponibile</label><label><input type="checkbox" checked={fail} onChange={(event) => setFail(event.target.checked)} />Il prossimo invio fallisce</label><small>Se l’invio fallisce, la tua osservazione precedente deve restare.</small></div>
        <div className="cp-control-group"><strong>Conferma da un’altra installazione</strong><button type="button" disabled={!own} onClick={() => apply({ type: "witness", id: own?.id })}><CheckCircle2 size={16} />Conferma la tua osservazione</button><small>Simula un altro osservatore. Non è un’autoconferma disponibile nell’app.</small></div>
        <button className="cp-reset" type="button" onClick={() => { setState(createPreviewState()); setTab("now"); setGps(true); setFail(false); }}><RotateCcw size={16} />Ricomincia la prova</button>
      </aside>
    </main>
    {open ? <ReportDialog state={state} gps={gps} fail={fail} onFailureConsumed={() => setFail(false)} onStateChange={setState} onGpsRetry={() => setGps(true)} onClose={() => setOpen(false)} /> : null}
  </div>;
}
