# APK TEST Community ed Eventi — collaudo del 14 ottobre 2026

## Esito

APK aggiornata sugli emulatori Android 15/16 e, dopo autorizzazione esplicita,
sul Galaxy A52. Invio con GPS, conferma da un'altra installazione, punti,
storico, spiegazione del profilo ed Eventi verificati nei casi sotto descritti.
**La candidata non è pronta per la promozione:** contrasto dei tre tasti su
Android 15 FAIL, matrice Android ancora parziale, runtime minificato non
verificato e due fonti Eventi respinte dal collaudo della raccolta.

Nessun cambiamento a main, push GitHub, deploy, job Cloud Run, operazione Play
o AAB. Le nuove osservazioni e i voti sono esclusivamente nella Community TEST
locale. La versione ufficiale e la variante tester sul telefono sono invariate.

Questo documento aggiorna la parte Android del
[resoconto di integrazione](COMMUNITY_EVENTS_TEST_INTEGRATION_2026-10-14.md),
che descrive anche la raccolta Eventi reale e i collaudi browser precedenti.

## Candidata e contenuti

- Ramo: `codex/community-reports-simplification`.
- Commit compilato: `92eb93378f1ed7f3580cc19d5ada6fc5461d640f`.
- Main invariato: `5a68de5dc1607105f921d4d2b731170f1a8a0446`.
- Package: `com.meteofriul.app.localpilot`.
- Versione: `0.1.14-local-pilot`, versionCode `300031`, min SDK 24, target 36.
- Variante debug localPilot, **non minificata**, firma Android Debug verificata.
- APK locale: `.tmp/community-events-apk-2026-10-14/meteofriul-community-events-92eb9337-test.apk`.
- SHA-256: `a2150c82f6774b8bc70bad939c028a0f5c72cab2f4cf9bbae1b0f69b08a5432c`.
- Bundle Web caricato: `/assets/main-COQT5dim.js`.

Comprende pannello compatto e storico reale 48 ore (`d29a45cf`), correzione
della lista Sentinelle (`bf63fddc`), soli stati nell'elenco (`156d552f`),
conteggi raggruppati e dettaglio storico in sola lettura (`4d992c4b`),
«Sentinelle, alias e punti» nelle Opzioni (`92eb9337`). La spiegazione è
inizialmente chiusa e non introduce pulsanti aggiuntivi.

Eventi include `f7fe8e9696f5b61a54fda27617ec99834993f8b4`, ramo
`codex/events-card-quarantine`, già integrato tramite `6dff122d`.
Verificati antenato e assenza di differenze in `backend/app/events` tra
`f7fe8e96` e la candidata. Riletta la chat **Audita la ricerca eventi**;
nessun messaggio inviato a quella chat.

Build tramite `scripts/build-android-local-weather-pilot.ps1 -CommunityPilot
-EventsLocal`, fuori sandbox, 170 task Gradle riusciti. Nessun aggiornamento
di SDK o toolchain. Restano gli avvisi già noti su chunk Web, `flatDir` e
funzionalità Gradle deprecate; non sono stati scambiati per errori runtime.

## Ambienti e dati

| Ambiente | Identità e configurazione |
| --- | --- |
| Android 16 | AVD `MeteoFriul_Community_API36`, API 36, `google/sdk_gphone64_x86_64/emu64xa:16/BE2A.250530.026.D1/13818094:user/release-keys`, WebView 133.0.6943.137 |
| Android 15 | AVD `MeteoFriul_R8_Opt_API35`, API 35, `google/sdk_gphone64_x86_64/emu64xa:15/AE3A.240806.043/12960925:userdebug/dev-keys`, WebView 124.0.6367.219 |
| Telefono | Galaxy A52 SM-A525F, Android 14/API 34, WebView attiva 155.0.8059.43, tre tasti, sistema scuro, tema app Sistema |
| Dimensioni | Tutti 1080 × 2400 px, densità 420 (circa 411 dp di larghezza). API 36 provato anche a densità 240, larghezza minima 720 dp, nei due orizzontali 2400 × 1080 |

Community usa SQLite su `127.0.0.1:8783`; Eventi usa il backend candidato su
`127.0.0.1:8784`. Entrambi dichiarano `published: false`. Configurati gli
`adb reverse` per i dispositivi autorizzati. L'APK verifica queste destinazioni
nei propri asset; non usa i dati dimostrativi della pagina QA.

Eventi serve lo stesso catalogo locale immutabile raccolto oggi: snapshot
`2026-10-14T15:45:13.846290+00:00`, SHA-256
`5abc841b4108a8c6ec8193aa68bb5198b02585fa49d62274e28897d263417069`.
L'health espone il commit di avvio `d29a45cf`; i sorgenti Eventi sono identici
a quelli della candidata. Nessuna nuova raccolta o pubblicazione in questo
collaudo Android. Restano **13 fonti pubblicabili e 2 respinte**: Azalea
(`unrecognized Azalea archive cards`) e Spazzapan (inventario cambiato).

La fixture meteo resta il 4 settembre alle 12:00Z: «Meteo non disponibile»
non certifica il funzionamento del meteo corrente. Il collegamento notifiche
del profilo locale non risulta riuscito; le notifiche push non sono un PASS.
Per usare questa TEST il PC, i servizi locali e il collegamento ADB devono
restare disponibili. Non è un'APK autonoma per la distribuzione.

## Collaudo funzionale sulla nuova APK

Tutte le interazioni sono native tramite ADB sul solo pacchetto TEST. GPS
degli emulatori impostato tramite console Android; GPS del telefono reale,
senza coordinate simulate o sostituzione delle API JavaScript.

| Scenario | Esito e riscontro |
| --- | --- |
| Aggiornamento telefono | PASS: `adb install -r`, hash dell'APK riletta dal telefono identico alla candidata. Alias Cjampane dal Cîl, precedente storico e 1 inviata/1 confermata/1 punto conservati |
| Isolamento pacchetti | PASS: versione e `lastUpdateTime` di `com.meteofriul.app` e `com.meteofriul.app.tester` identiche prima/dopo; solo localpilot aggiornata alle 19:40:29 |
| Invio da Android 16 | PASS: Pioggia a Pordenone con GPS; ricevuta e scadenza 60 minuti. Inviate 1 → 2, punti ancora 1 |
| Conferma da Android 15 | PASS: GPS e «Confermo», conteggio 0 → 1. Autore API 36: confermate 1 → 2 e punti 1 → 2; profilo del confermante invariato a 2 inviate/1 confermata/1 punto |
| Non c'è più dal telefono | PASS: GPS reale, conteggio 0 → 1 nel dettaglio Pioggia. Nessun punto aggiuntivo; conferme ancora 1. Il marcatore è nascosto al votante secondo la regola esistente; il gruppo resta attivo per gli altri sotto la soglia di 3 riscontri |
| Invio dal telefono | PASS: Temporale a Pordenone, GPS ricontrollato all'invio, ricevuta e scadenza 60 minuti. Profilo 2 inviate/1 confermata/1 punto; il nuovo fenomeno parte con 0 conferme e 0 riscontri |
| Conferma della segnalazione del telefono | PASS: Android 15 conferma Temporale con GPS. Backend e profilo del telefono, riaperto dopo la conferma: 2 inviate/2 confermate/2 punti |
| UX Recenti | PASS sui casi osservati: pannello inizialmente compatto, «Recenti» espande la lista; pulsante Segnala accessibile. Numero di segnalazioni e tempo trascorso, stato sotto; nessuna riga rossa di riscontri nell'elenco |
| Storico | PASS: record preesistenti di 21–25 ore visibili. Sul telefono, Pioggia scaduta mostra 1 segnalazione, 21 ore fa, 1 punto, Conferme 1/Non c'è più 0, nessun comando di voto. API 36 verifica anche dettaglio Grandine con entrambi i conteggi a 1 |
| Profilo | PASS: spiegazione chiusa all'apertura, apertura e testo approvato leggibile sul telefono, contatori sotto l'alias. Tema e Comune conservati |
| Eventi | PASS: 46 eventi di oggi e dettaglio «Le Rose per il cambiamento climatico», fonte TurismoFVG, su API 36 e telefono. Il telefono passa dal vecchio catalogo a quello candidato locale |
| Ripresa e tastiera | PASS sul telefono: ritorno dal background con profilo e tema conservati; selettore Comune sopra la tastiera, chiusura accessibile, nessuna località cambiata |

Il profilo già aperto non è stato considerato aggiornato in tempo reale:
il nuovo punteggio è verificato dopo riapertura delle Opzioni. Nessun dato
del database, orologio o punteggio è stato modificato direttamente per far
passare il collaudo. Le sole letture SQLite di verifica omettono identificativi
delle installazioni e coordinate.

I casi di spam, tre ore, scadenza a 60 minuti, limite 48 ore e paginazione
oltre 50 record sono coperti dai test automatici. Non sono stati tutti
rieseguiti manualmente aspettando la durata reale. Il raggruppamento con
conteggio storico maggiore di 1 è coperto dai test, non dai pochi record
preesistenti osservati sul telefono.

## Quattro aree Android obbligatorie

| Area | Esito sulla candidata |
| --- | --- |
| Edge-to-edge | **FAIL** nel caso API 35 sistema chiaro: tre tasti scuri su fondo scuro. PASS nei casi osservati API 36 app scura/sistema chiaro con tre tasti, app chiara e scura/sistema scuro con gesti, API 35 sistema scuro con tre tasti. Gesti API 35 leggibili in avvio, ma tema sistema iniziale non annotato. Galaxy A52 nelle condizioni sopra: barre, pannelli, tastiera e dettaglio Eventi accessibili |
| API barre deprecate | PASS per assenza dei setter dei colori delle barre e opt-out edge-to-edge nei sorgenti applicativi `frontend/android/app/src/main`; test plugin e build PASS. Dipendenze e nuovo esito Play **NON VERIFICATI**, nessun upload eseguito |
| Orientamento e ridimensionamento | PASS dei casi osservati: API 36 telefono resta verticale alla rotazione 1; API 35 alla rotazione 3. API 36 a 720 dp si dispone nei due orizzontali; lista espansa e dettaglio Eventi accessibili. Manifest/policy esistenti conservati. Non è una prova di tablet fisico o pieghevole |
| R8/risorse | Contratti di configurazione, mapping, simboli, metadati Capacitor e stack trace PASS; keep rule troppo ampie assenti. **Runtime minificato NON VERIFICATO:** la TEST è debug. Nessuna attestazione di risoluzione dell'avviso Play sull'ottimizzazione |

**Matrice residua NON VERIFICATA:** tutte le combinazioni tema/navigazione su
ogni API, cutout laterali nei due versi, 320/360 dp, multi-window e resize
durante l'uso con conservazione dello stato, tutti i percorsi Home/Meteo/Eventi/
Scopri/Opzioni nelle diverse geometrie, rotazioni fisiche del telefono e
ricaricamento WebView in tutte le condizioni. I casi osservati non vengono
estesi a quelli mancanti.

L'avvio degli emulatori ha richiesto assestamento e, su API 36, passaggio al
renderer host dopo il fallimento iniziale del renderer software. Sull'API 35
il buffer crash contiene un errore del launcher all'avvio, non della TEST.
Nessun riferimento a crash del pacchetto TEST negli ultimi 100 record dei
buffer consultati; questo controllo limitato non è un audit completo crash/ANR.
I log di altre app del telefono non sono inclusi nelle evidenze versionate.

## Controlli automatici

| Controllo eseguito sulla candidata | Esito |
| --- | --- |
| Frontend, 9 file di integrazione/UX/Android/Eventi | 199 PASS |
| Frontend, storico/hook/API, altri 3 file | 30 PASS; totale unico di questa sessione 229 |
| Backend, regole/SQLite/Eventi/API | 70 PASS |
| Backend, audit fonti/quarantena | 37 PASS |
| Backend, isolamento errori/regionali/catalogo/cloud | 113 PASS; totale unico di questa sessione 220 |
| Guardie release e localpilot | 9 + 7 PASS |
| Contratti R8 | PASS; verifica statica, non runtime minificato |
| Pulizia workspace canonico | PASS prima della nuova candidata |
| Build, firma, identità asset e hash telefono | PASS |

La suite completa precedente e i relativi ricontrolli sono descritti nel
resoconto di integrazione: non sono stati presentati come una nuova esecuzione
completa. CI remota non eseguita, GitHub non aggiornato come richiesto.

## Evidenze e seguito

Schermate native, manifest, identità dei backend, contatori sanitizzati e log
dei test sono versionati in
[evidence/community-events-android-2026-10-14](evidence/community-events-android-2026-10-14/SHA256SUMS.txt).
Il file `checks.json` contiene anche confronto dei pacchetti e hash dell'APK
installata. APK e log operativi completi restano nell'area locale `.tmp`;
nessun APK, credenziale o database è aggiunto a Git.

Prima della promozione: correggere e ricollaudare il contrasto API 35 nel
filone Android dedicato, completare la matrice applicabile e il runtime R8,
chiudere il confronto della raccolta Eventi per Azalea/Spazzapan, quindi
riesaminare la candidata risultante. Le regole del progetto tengono separati
questi filoni e distinguono promozione del codice, build AAB, upload e pubblicazione.
Non è stata concessa né registrata una deroga ai risultati aperti.

Fine sessione: emulatori arrestati ordinatamente senza cancellare dati;
servizi locali lasciati attivi; Galaxy A52 lasciato sulla lista Recenti compatta
della TEST, con tema Sistema e località Pordenone conservati.
