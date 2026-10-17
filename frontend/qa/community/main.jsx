import { useState } from "react";
import { createRoot } from "react-dom/client";
import { Capacitor } from "@capacitor/core";
import { SettingsView } from "../../src/features/settings/SettingsView.jsx";
import { getFirebaseAppCheckToken } from "../../src/services/firebaseAppCheckAdapter.js";
import { fetchCommunityReputation, postCommunityReport, postCommunityReportConfirmation, LIVE_REPORT_CLIENT_ID_KEY } from "../../src/services/liveApi.js";
import "../../src/ui/index.css";
import "./qa.css";

const BASE = "http://127.0.0.1:8788";
const QA = "meteofriul-comm-qa-261016";
const CLIENT_KEY = "communityQa:synthetic-client:v1";
let clientId = localStorage.getItem(CLIENT_KEY);
if (!clientId) { clientId = `qa-android-${crypto.randomUUID()}`; localStorage.setItem(CLIENT_KEY, clientId); }
if (!clientId.startsWith("qa-android-")) throw new Error("qa_synthetic_identity_required");
const existing = localStorage.getItem(LIVE_REPORT_CLIENT_ID_KEY);
if (existing && existing !== clientId) throw new Error("qa_will_not_replace_existing_identity");
localStorage.setItem(LIVE_REPORT_CLIENT_ID_KEY, clientId);
const operationKey = "communityQa:operation:v1";
const operationId = localStorage.getItem(operationKey) || `qa-${crypto.randomUUID()}`;
localStorage.setItem(operationKey, operationId);
const noChange = () => {};
const timeout = () => AbortSignal.timeout(30000);
async function wire(path, { token, legacy = false, method = "POST", body } = {}) {
  if (!path.startsWith("/api/community/")) throw new Error("qa_path_rejected");
  const headers = { "Content-Type": "application/json", ...(token ? { "X-Firebase-AppCheck": token } : {}), ...(!legacy ? { "X-Meteo-Community-Rules": "community-reports-v3" } : {}) };
  const r = await fetch(BASE + path, { method, headers, body: body === undefined ? undefined : JSON.stringify(body), signal: timeout(), redirect: "error" });
  return { status: r.status, data: await r.json() };
}
export function CommunityQaApp() {
  const [busy, setBusy] = useState(false), [rows, setRows] = useState([]), [profile, setProfile] = useState(0), [showProfile, setShowProfile] = useState(false);
  async function run(full) {
    if (busy) return;
    setBusy(true); setRows([]); setShowProfile(false);
    const results = [];
    function check(name, pass, detail = "") {
      results.push({ name, pass: Boolean(pass), detail }); setRows([...results]);
      if (!pass) throw new Error(`qa_check_failed:${name}`);
    }
    try {
      check("Runtime Android nativo", Capacitor.isNativePlatform() && Capacitor.getPlatform() === "android");
      const health = await wire("/api/community/health", { method: "GET" });
      check("Backend isolato QA", health.status === 200 && health.data.project === QA);
      const token = await getFirebaseAppCheckToken({ forceRefresh: true });
      check("Token Firebase Android ottenuto", Boolean(token));
      const reputation = await fetchCommunityReputation({ clientId });
      check("Reputazione autenticata v3", Number.isInteger(reputation.points), `Punti: ${reputation.points}; inviate: ${reputation.total_reports}`);
      const legacy = await wire("/api/community/reputation", { token, legacy: true, body: { client_id: clientId } });
      check("Reputazione compatibile 0.1.14", legacy.status === 200 && legacy.data.points === reputation.points);
      if (full) {
        const missing = await wire("/api/community/reputation", { body: { client_id: clientId } });
        check("Senza token: accesso respinto", missing.status === 401);
        const invalid = await wire("/api/community/reputation", { token: "invalid-qa-token", body: { client_id: clientId } });
        check("Token invalido: accesso respinto", invalid.status === 401);
        for (const old of [true, false]) {
          const feed = await wire("/api/community/reports?istat_code=093033", { method: "GET", token, legacy: old });
          check(old ? "Lettura contratto 0.1.14" : "Lettura contratto v3", feed.status === 200 && feed.data.contract?.schema_version === (old ? "community-pilot-national-safety-v2" : "community-reports-v3"));
        }
        check("Scritture sintetiche QA abilitate", health.data.v3_writes_enabled === true);
        const command = { acceptedTerms: true, clientId, coords: { lat: 45.9567, lon: 12.6605, accuracyM: 25 }, ageMs: 10, istatCode: "093033", policyVersion: "community-guidelines-v2", selectedPlace: "Pordenone", typeId: "rain", operationId };
        const report = await postCommunityReport(command);
        check("Segnalazione sintetica Android", Boolean(report.report?.id));
        const replay = await postCommunityReport(command);
        check("Replay senza duplicati", replay.idempotent_replay === true && replay.report?.id === report.report.id);
        const witness = `${clientId}-witness`;
        const oldVote = await wire(`/api/community/reports/${encodeURIComponent(report.report.groupId)}/confirmation`, { token, legacy: true, body: { client_id: witness, vote: "yes", accepted_terms: true, policy_version: "community-guidelines-v2" } });
        check("Vecchio client su report v3: aggiornamento richiesto", oldVote.status === 426);
        const vote = { acceptedTerms: true, clientId: witness, groupId: report.report.groupId, policyVersion: "community-guidelines-v2", vote: "yes", coords: command.coords, ageMs: 10, reportIds: [report.report.id] };
        await postCommunityReportConfirmation(vote);
        const earned = await fetchCommunityReputation({ clientId });
        check("Punto assegnato dal backend", earned.points === 1 && earned.total_reports === 1 && earned.validated_reports === 1);
        await postCommunityReportConfirmation(vote);
        const repeated = await fetchCommunityReputation({ clientId });
        check("Nessun doppio premio", repeated.points === 1 && repeated.total_reports === 1);
        const other = await fetchCommunityReputation({ clientId: witness });
        check("Reputazioni separate", other.points === 0);
      }
      setProfile(x => x + 1); setShowProfile(true);
    } catch (e) {
      results.push({ name: "Esecuzione interrotta", pass: false, detail: String(e?.code || e?.message || "qa_error").slice(0,140) }); setRows([...results]);
    } finally {
      localStorage.setItem("communityQa:lastResults:v1", JSON.stringify(results));
      await fetch(BASE + "/__qa/results", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ results, utc: new Date().toISOString() }), signal: timeout() }).catch(() => {});
      setBusy(false);
    }
  }
  return <main className="qa-shell"><header><img src="/brand/pilot-test-orange-v1/mark.svg" alt=""/><div><h1>Community QA</h1><p>Ambiente isolato · dati sintetici</p></div></header>
    <p className="qa-note">Collaudo Android con Firebase QA. Questa app non invia dati alla produzione e non certifica Play Integrity.</p>
    <div className="qa-actions"><button disabled={busy} onClick={() => run(false)}>Verifica reputazione</button><button disabled={busy} onClick={() => run(true)}>Collaudo completo QA</button></div>
    {busy && <p role="status">Verifica in corso…</p>}
    <ol aria-live="polite">{rows.map((r,i)=><li key={i} className={r.pass ? "qa-pass" : "qa-fail"}><strong>{r.pass ? "OK" : "NON SUPERATO"} · {r.name}</strong>{r.detail && <small>{r.detail}</small>}</li>)}</ol>
    {showProfile && <section className="qa-profile"><h2>Profilo dell’app · risposta del backend QA</h2><SettingsView key={profile} appVersion="0.1.14-community-qa.2" activeLocation={{ name: "Pordenone", municipality: { name: "Pordenone", istatCode: "093033", province: "PN" } }} communityIdentity={{ alias: "Osservatore QA", avatarId: "mountain" }} language="it" themePreference="light" onSettingsBack={noChange} onNavigate={noChange}/></section>}
  </main>;
}
createRoot(document.getElementById("root")).render(<CommunityQaApp/>);
