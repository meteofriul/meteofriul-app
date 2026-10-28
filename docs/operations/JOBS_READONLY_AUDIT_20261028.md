# Prima verifica dei job — 28 ottobre 2026

Base sorgente: `9f81253e6b1832816e4032930b7b5eb64ebff6ad` (main), ramo di
lavoro `codex/job-control-inventory`. [Inventario e responsabilità](JOBS_INVENTORY.md).
Il coordinatore è l'unico autore di documentazione e configurazione dell'agente;
`build_verifica` ha esaminato le configurazioni e i controlli locali.

Questa verifica legge lo stato dei servizi; non modifica job, scheduler,
policy, destinatari, dipendenze o sorgenti applicativi. Nessun retry, deploy,
avvio manuale, invio di prova o controllo periodico. Nessuna variazione della
qualificazione della AAB 300038, degli artefatti Web o delle prove su dispositivo.

## Disponibilità effettiva di controllo_job

Il [profilo](../../.codex/agents/controllo_job.toml) usa i campi `name`,
`description` e `developer_instructions`, secondo la
[documentazione degli agenti](https://learn.chatgpt.com/docs/agent-configuration/subagents).
Non aggiunge privilegi IAM o sandbox, né automazioni periodiche.

| Prova | Esito effettivo |
| --- | --- |
| TOML e istruzioni | **VERIFICATO** con `tomllib`; confini in sola lettura, responsabilità e limiti espliciti |
| Tipo nella chat già aperta | **NON DISPONIBILE**: `unknown agent_type 'controllo_job'`. Non si presume un ricaricamento automatico del catalogo |
| CLI npm 0.130.0 | Avvio bloccato: prima incompatibilità `service_tier=default`, poi modello corrente non supportato. Nessun aggiornamento o cambio modello |
| CLI già inclusa nell'editor, 0.164.0-alpha.11.1 | **VERIFICATO** in una nuova sessione `read-only`: avviato realmente `agent_type=controllo_job`, figlio `/root/controllo_job_audit_20261028`, concluso con risposta. Nessun fallback in questa prova |

La prima prova con la CLI dell'editor in modalità effimera aveva fallito prima
della risposta del figlio (`no rollout found`). La sessione normale ha risolto
quel blocco. È stato usato soltanto un override di processo `service_tier=fast`;
installazioni e configurazioni globali sono rimaste invariate.

La raccolta cloud è stata svolta da `/root/controllo_job_audit`, tipo `default`
che legge e applica il nuovo profilo: è dichiarata come tale. Il nuovo agente
nativo ha poi verificato autonomamente le cinque evidenze su job, scheduler,
esecuzioni e policy; non ha eseguito una seconda raccolta cloud. Un secondo
incarico allo **stesso figlio nativo**, concluso da `running` a `completed`,
ha verificato i riepiloghi di log e prodotti ora disponibili: pubblicazione
parziale Eventi, recupero CAMS, ICON/monitor, allerte, contatori FCM e falso
scostamento di codifica. Le due risposte sono conservate e hanno hash nella
ricevuta. I risultati sotto includono questa lettura supplementare.
La disponibilità nativa è provata nella nuova sessione CLI, non retroattivamente
nel catalogo di questa chat.

## Perimetro, orari e prove conservate

Account atteso verificato prima delle letture, progetto `meteo-friul`.
Raccolta **28 ottobre 16:10–16:22:49 UTC**, cioè **17:10–17:22:49 Europe/Rome**.
Letti job Cloud Run nelle regioni restituite, scheduler in `europe-west1` e
`europe-west8`, policy Monitoring, log aggregati, sette endpoint GET e tre
oggetti Storage. Nessuna modifica della configurazione globale di gcloud.

[Ricevuta sanificata JSON](JOBS_READONLY_AUDIT_20261028.json): nomi, regioni,
cron/fusi, identificativi delle esecuzioni, risultati campionati, endpoint,
oggetti, timestamp, query e hash delle evidenze locali. I log grezzi non sono
inclusi. Nomi di fonti, codici pubblici comunali e contatori aggregati non sono
identità di utenti o destinatari.

Risultato: **14 istanze job Ready, 11 scheduler ENABLED, 224 esecuzioni nel
campione (220 riuscite, 4 fallite)**. Il nome locale `executions-48h.json`
non dimostra una finestra completa:

- `europe-west1`: limite 200, dal 26 ottobre 19:50:13Z al 28 ottobre 16:10:06Z;
- `europe-west8`: 24 corse nel filtro 48 ore, dal 26 ottobre 17:00:01Z al
  28 ottobre 15:00:06Z;
- log: massimo 60 record per ultima esecuzione; ulteriori due corse CAMS
  fallite lette con limite 60 combinato (38 record restituiti).

Gli undici cron e fusi corrispondono ai riferimenti dell'inventario. Tutti gli
scheduler letti sono in west1; quello FVG invoca west8. Il monitor freschezza
passa dal proprio dispatcher HTTP. Non è stata provata per ogni corsa la catena
esatta Scheduler → RunJob: la vicinanza degli orari non viene usata come prova.

## Esito per ciascun job

Nomi nella tabella senza il prefisso comune `meteofriul-`; regione
`europe-west1`, salvo indicazione. I conteggi sono del campione sopra.
`VERIFICATO` riguarda esclusivamente i riscontri descritti.

| Job | Esecuzioni e prova | Risultato sui dati e giudizio | Limiti / chi interviene |
| --- | --- | --- | --- |
| `morning-forecast` | 2/2 riuscite; ultima `xvj72`, 28/10 06:30:44Z | **VERIFICATO** riepilogo: 51 tentativi, 51 accettazioni FCM, 0 errori | Notifica vista sul telefono **NON VERIFICABILE**; `meteo` |
| `evening-forecast` | 1/1 riuscita; `62j8k`, 27/10 19:45:01Z | **VERIFICATO** riepilogo: 51 tentativi, 51 accettazioni FCM, 0 errori | Corsa del 28 sera non ancora dovuta; consegna su telefono non verificata; `meteo` |
| `local-notice` | 45/45 riuscite; ultima `8fspn`, 28/10 16:00:04Z | **VERIFICATO** `no_candidate`, `sent=0`, `failed=0`; zero invii non è un guasto | Non esercitato un invio con candidato reale; `meteo` |
| `official-alert-sync` (west8) | 24/24 riuscite; ultima `rc5lx`, 28/10 15:00:06Z | **VERIFICATO** `no_active_alert`; GET count=0, acquisizione 15:00:15Z | Non provato il percorso con nuova allerta attiva; `meteo` |
| `national-official-alert-sync` | 22/22 riuscite; ultima `pz7nv`, 28/10 15:35:04Z | **VERIFICATO** `status=ok`, `reason=stored`; GET sul campione Roma `complete=true`, `green` | Un comune non certifica tutte le zone nazionali; `meteo` |
| `national-official-alert-send` | 23/23 riuscite; ultima `s2zxv`, 28/10 15:50:06Z | **VERIFICATO** `no_candidate`, `sent=0`, `failed=0` | Nessuna policy dedicata a questo job individuata fra le 23 lette; il monitor del sync non prova copertura del send. `meteo` |
| `icon` | 3/3 riuscite; ultima `knmvk`, 28/10 06:00:00Z | **VERIFICATO** pubblicazione e puntatore HTTP della corsa `20261028T000000Z`; monitor senza criticità alle 16:10Z | Non rilette tutte le località/ore del bundle; `meteo` |
| `national-icon` | 3/3 riuscite; ultima `v48nw`, 28/10 06:00:03Z | **VERIFICATO** puntatore HTTP e monitor della stessa corsa 28/10 00Z | Il puntatore conserva `experimental_local_pilot_only`; non attesta una qualificazione nazionale di prodotto. `meteo` |
| `cams` | 8 riuscite, 2 fallite; ultima `cfh6s`, 28/10 15:00:22Z riuscita | **ANOMALIA** alle 09Z del 27/28; **VERIFICATO** recupero negli slot successivi, ultimo `complete=true`, aria/pollini/UV verificati, GET ciclo 28/10 00Z | Causa esterna di acquisizione e tutte le località non verificate; `meteo` |
| `events-refresh` | 2/2 fallite: `ntm55` il 27, `kps9r` il 28 alle 04Z | **ANOMALIA** su tre fonti; catalogo parzialmente aggiornato il 28 alle 04:06:53Z, 3 `stale`, 7 `partial`, 5 `fresh` | Non controllate singole schede/UI né approfondita la causa del 27; `eventi` |
| `icon2i-freshness` | 89/89 riuscite; ultima `kp8f2`, 28/10 16:10:06Z | **VERIFICATO** stati FVG/nazionale: `check_completed=1`, `check_state=0`, `critical_active=0`, `complete=true`, 56 campioni futuri; ultimi 6 controlli senza indeterminati | Sono risultati del monitor, non un nuovo replay indipendente di ogni sonda; email/incidenti non verificati. `meteo` |
| `official-alert-sync` (west1 storico) | Nessuna corsa nel campione; ultima `g7w74`, 08/10 | **VERIFICATO** presenza dell'istanza e assenza di target fra gli scheduler letti | Funzionamento attuale **NON VERIFICABILE**; non confonderlo con west8, non riattivato. `meteo` |
| `event-source-publication-control` | Nessuna corsa nel campione; ultima `lthg9`, 29/08 | **VERIFICATO** job storico, nessun target Scheduler trovato | Gate manuale attuale **NON VERIFICABILE**, non provocato. `eventi` |
| `local-notice-tolerance-qa` | Nessuna corsa nel campione; ultima `vcgqj`, 19/10 | **VERIFICATO** job di prova, nessun target Scheduler trovato | Nessun nuovo test QA eseguito; `meteo` |

Job shadow Eventi, digest Community e un job dedicato al monitor delle sintesi
per data locale non compaiono nell'elenco letto. Non è una prova circa altri
account o funzioni eventualmente integrate in immagini non ispezionate.

## Anomalie concrete e monitoraggio

**Eventi.** La corsa del 28 termina con
`event source verification failed: Barcolana, CSS Udine, Magazzino delle Idee`.
Il catalogo Storage continua a essere pubblicato; non si conclude che tutta la
sezione sia ferma. Metadati delle tre fonti conservate:

| Fonte | Ultimo aggiornamento UTC | Ultimo errore registrato |
| --- | --- | --- |
| CSS Udine | 26/10 04:00:47Z, oltre 48 ore alla lettura | `source_verification_failed` |
| Barcolana | 25/10 07:59:50Z, oltre 48 ore | `adapter_exception`, `ValueError` |
| Magazzino delle Idee | 27/10 04:00:45Z, circa 36 ore | `adapter_exception`, `ReadTimeout` |

Il catalogo conserva anche `review_required` per Palazzo Attems/GiroFVG,
controllati il 25 ottobre. Le altre sette fonti `partial` restano tali, senza
essere dichiarate pienamente valide. Pordenonelegge e Cinema Muto sono `fresh`
con zero eventi: non classificati come errore per il solo conteggio nullo.
Il GET `/health` Eventi risponde 200 ma non certifica le singole schede servite.

**CAMS.** Entrambe le corse delle 09Z riportano
`acquisition_nonrecoverable_failure`, `manual_review`, `retryable=false` per
aria e pollini; pubblicazione fermata in quella corsa. UV
`uv_outside_scheduled_window` è invece coerente con gli slot previsti.
Le corse successive riescono; l'ultima delle 15Z verifica tutte le componenti.
La famiglia CAMS HTTP è pubblicata alle 10:01:15Z, ciclo del 28/10 00Z.
Non è stata determinata la causa esterna dei due errori né dimostrata la
continuità minuto per minuto durante quelle acquisizioni. Il grant di continuità
a 36 ore menzionato nel verbale del deploy non è stato collaudato da questa
lettura: la presenza della famiglia corrente non basta a chiudere quel punto.

**Policy.** Lette 23 policy: 21 abilitate (18 del catalogo più le tre del
monitor freschezza) e due vecchie prove disabilitate. Nessuna modifica.
Lo script esistente in `-Mode Audit` restituisce 17 `unchanged` e
`icon-fvg-last-success=drifted`, `ready=false`, exit 2. Il confronto mirato
isola una differenza di codifica: il testo live coincide con il JSON letto
UTF-8, mentre Windows PowerShell lo legge come `PoichÃ©` invece di `Poiché`.
Quindi il segnale non prova una soglia cloud cambiata; il comando Audit resta
comunque non superato. La correzione della lettura UTF-8 è separata, senza
eseguire `Apply` o modificare policy per annullare il falso scostamento.
Incidenti, consegna delle email e valutazione effettiva delle metriche non
sono stati interrogati; la copertura del dispatcher nazionale resta da chiarire.

## Come riprodurre le letture

Usare il progetto esplicito `meteo-friul` e l'account già autorizzato.
Gli schemi delle query, i limiti e le URL sono nella ricevuta JSON, senza credenziali:

1. `gcloud run jobs list --project=meteo-friul`, con selezione di nomi,
   regioni, condizioni e ultima esecuzione; `gcloud scheduler jobs list`
   nelle due regioni, selezionando cron/fuso/stato/target.
2. `gcloud run jobs executions list --project=meteo-friul --region=<regione>
   --limit=200`, selezionando metadati e stato; dichiarare il limite.
3. `gcloud logging read` filtrato su `cloud_run_job`, nome, regione e
   `run.googleapis.com/execution_name`, limite 60 e intervallo dichiarato.
   Estrarre solo contatori e categorie di errore, non log con dati privati.
4. GET degli endpoint e degli oggetti già elencati nella ricevuta; confrontare
   timestamp/identità del prodotto, non soltanto HTTP 200.
5. Con toolchain prescritta, leggere le policy tramite lo script esistente
   `scripts/sync-cloud-run-job-monitoring.ps1 -Mode Audit` e distinguere
   l'attuale problema di codifica da modifiche reali. Mai usare `Apply`
   durante una verifica.

## Controlli locali e lint

L'indice README collega i documenti già presenti per architettura, regole
dell'app, vincoli, versioni e UI; distingue i responsabili e i verbali storici.
Il nuovo inventario rimanda alle configurazioni reali, senza duplicare le
soglie delle policy in un secondo file operativo.

Verifica finale documentale **PASS**: 55 collegamenti locali/anchor risolti,
TOML e JSON validi, 14 hash delle evidenze corrispondenti, conteggi delle
esecuzioni e degli scheduler ricontrollati. `git diff --check` e controllo
canonical workspace **PASS**, con 4000 file nell'indice e nessun output
generato, segreto locale o riferimento attivo obsoleto tracciato. Nessuna
build, installazione di dipendenze o suite applicativa eseguita per questi
soli cambiamenti documentali e di profilo.

Prima della sistemazione locale descritta sotto, `build_verifica` ha riprodotto
`npm run lint` da `frontend/` con Node
**22.17.1**, npm **10.9.2**, ESLint **10.5.0**. Il comando effettivo è
`eslint .`; entrambi i tentativi, incluso quello fuori sandbox, terminano con
**exit code 2**:

```text
EPERM: operation not permitted, scandir '…\frontend\.pytest_cache'
```

Il percorso termina nella cache Python locale del frontend, all'interno della
radice canonica. In quei due tentativi il lint completo era **BLOCCATO**:
la scansione non arrivava a una verifica completa delle regole ESLint. La CI verde del
consolidamento precedente è un'evidenza distinta, non l'esito di questo comando.

Proposta formulata prima della sistemazione: diagnosticare
l'accesso Windows a questa sola cache (permessi/processi), oppure riprodurre
il controllo in un checkout pulito con la toolchain prescritta. Solo dopo la
diagnosi, autorizzare un'eventuale rimozione della cache generata interessata.
Conservare `npm run lint`, regole, esclusioni e gate CI; nessun aggiramento del
controllo in questo incarico. Non sono stati cambiati ACL o rimossi file.

### Blocco lint risolto nello stesso checkout il 28 ottobre

Diagnosi in sola lettura: Windows negava apertura, elenco e lettura ACL di
`frontend/.pytest_cache` anche fuori sandbox (`ERROR_ACCESS_DENIED`,
NTSTATUS `0xC0000022`); `frontend` e `frontend/src` erano invece leggibili.
L'utente ha poi eseguito la lettura in PowerShell amministrativa: ereditarietà
ACL disabilitata (`AreAccessRulesProtected=True`), ACL canonica, tre regole
esplicite Allow/FullControl e contenuto `v`, `.gitignore`, `CACHEDIR.TAG`,
`README.md`. Non è stato identificato chi abbia creato tali permessi.

Il proprietario ha spostato la sola cache, in modo reversibile, da
`frontend/.pytest_cache` a `tmp/pytest-cache-frontend-quarantena-20261028`.
Entrambi i percorsi erano stati verificati nella radice canonica; destinazione
inizialmente assente, fuori dal frontend ed esclusa da Git. Il coordinatore
ha confermato sorgente assente e quarantena presente prima della prova.
Nessuna modifica di ACL, esclusioni ESLint, regole, dipendenze o protezioni.

**Lint completo PASS, exit code 0**, eseguito dal coordinatore da `frontend/`
sulla sorgente `e6bc26767f8a5aff77f4c0e3c49df3c69bfade7d`, con Node
`22.17.1` e npm `10.9.2` selezionati solo per il processo e i suoi figli:
`npm run lint` → `eslint .`, senza opzioni aggiuntive. Non è una prova limitata
ai file versionati: è lo stesso comando completo che prima si bloccava.

Ricevuta locale: `tmp/lint-cache-recovery-20261028/verification.json`, SHA256
`f175c4128b65d94a083e6fd6872a1e921a88f5f32bd7e42a0c34b2ae40530383`;
contiene versioni, risultato, stato dei percorsi e hash di manifest, lockfile
e configurazione ESLint rimasti invariati. I precedenti esiti negativi e la
ricevuta dell'audit cloud restano evidenze storiche distinte.

Le altre cache nella radice e nel backend risultavano anch'esse inaccessibili
all'utente non elevato; non sono state spostate o qualificate da questa prova.
Nessuna nuova build, suite, modifica ai job o verifica su dispositivi.

## Limiti comuni

- Stato `Ready`, successo Cloud Run e HTTP 200 sono prove diverse da freschezza,
  completezza e correttezza dei dati. Ogni giudizio riguarda il campione letto.
- Le accettazioni FCM non dimostrano visualizzazione sui telefoni. Policy
  abilitate non dimostrano ricezione delle email né chiusura degli incidenti.
- Nessuna verifica delle cartelle di landing/pannello, di altri progetti cloud,
  di Safari/iPhone o di nuovi artefatti Android/Web.
- Evidenze locali sanificate conservate in `tmp/controllo-job-audit-20261028/`,
  ignorato da Git. Nessun token, destinatario o identificatore privato nei
  riepiloghi destinati al repository.
