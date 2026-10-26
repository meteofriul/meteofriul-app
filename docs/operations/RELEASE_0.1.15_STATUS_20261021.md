# Stato release 0.1.15 e lavoro salvato — aggiornamento sorgenti del 26 ottobre 2026

**Stato corrente — 26 ottobre:** release locale allineata a main `c2b2cfe1`; archivio preliminare dalla sorgente `83c12c58`, antenna radar e contrasto secondario scuro inclusi. Web e risorse Android compilate e archiviate dalla stessa base; 5.055 test, lint, contratti release e guardie API/TTL superati. Verbali Galaxy 300037 salvati. Sponsor spenti. Nessuna nuova AAB, riserva, installazione, push o distribuzione. **Verifica dal vivo CAMS aperta:** dati del 25 ottobre scaduti alle 07:00 italiane, prossima corsa ordinaria prevista alle 10:00. [Preparazione, archivio e limiti](RELEASE_WEB_ALIGNMENT_20261026.md).

**Eventi — aggiornamento del 26 ottobre:** PR 30 integrata, CI PR/main superate; solo job Eventi e policy `events-failures` aggiornati con rollback pronto. Il secondo tentativo Barcolana usa più tempo entro lo stesso budget; la chiusura della finestra degli errori non notifica più un falso recupero. [Deploy e verifica](EVENTS_BARCOLANA_RECOVERY_DEPLOY_20261026.md). Corsa ordinaria del 27 ottobre alle 05:00: `pending`; nessuna esecuzione manuale. Sponsor spenti, contratti Web/Android e pacchetti invariati.

**Ultima AAB prodotta:** **0.1.15 / 300037**, sorgente `d15edb10`, base main `0841020a`. Generata, firmata, validata e archiviata; **disponibile nel test interno dal 24 ottobre alle 18:52**. CI sul commit esatto PASS; sponsor disattivati. Web ricompilata dalla stessa sorgente, non pubblicata. Runtime della 300037 verificato sul Galaxy Android 14 nei percorsi osservati; restano limiti espliciti. TurismoFVG recuperata dalla successiva corsa manuale delle 22:24: 1.434 schede pubblicabili, 20 schede complessive in revisione; controllo allora pendente. Il distinto esito del 26 ottobre è descritto nello stato corrente; non sostituisce la prova della corsa del 25 ottobre. [Recupero e limiti](EVENTS_MANUAL_RECOVERY_20261024.md). [Verifica e dati Eventi](ANDROID_0.1.15_300037_DEVICE_CHECK_20261024.md). [Build, evidenze e limiti](ANDROID_0.1.15_300037_BUILD_20261024.md).

**AAB attualmente nel test interno:** **0.1.15 / 300037**, con gli stessi due account abilitati. Produzione invariata a 0.1.14 / 300031; sponsor disattivati. Nessuna installazione dell'agente. [Accettazione Play e limiti](ANDROID_0.1.15_300037_UPLOAD_20261024.md).

**Precedente pacchetto osservato sul Galaxy:** AAB **0.1.15 / 300036** generata e verificata da `9d5ff2f4`, con main `2d8b0c32` e Tempo reale corretto. Web storica associata dalla stessa sorgente; sponsor spenti. Disponibile nel test interno dalle 13:37 del 23 ottobre e aggiornata dal proprietario via Play. Verifica sul Galaxy Android 14: PASS dei percorsi osservati, compreso Tempo reale dopo avvio a freddo; qualifica completa ancora limitata dalla matrice non esercitata. Nessuna installazione dell’agente. [Verbale storico](ANDROID_0.1.15_300036_DEVICE_CHECK_20261023.md).
**Antenna radar — pubblicata in main il 25 ottobre:** commit `738c6538` verificato su Brave/Galaxy in chiaro e scuro, con radar attivo e disattivo, integrato tramite [PR 28](https://github.com/meteofriul/meteofriul-app/pull/28), merge `d159ec59`. CI della PR e di main superate in tutti e tre i job. [Verbale ed evidenze](RADAR_ANTENNA_ICON_20261025.md). Il 26 ottobre la release e la candidata Web incorporano queste sorgenti; AAB e pubblicazioni restano quelle precedenti. Sponsor disattivati; nuovo controllo Eventi del 27 ottobre alle 05:00 mantenuto.

**Avvio HTTP FVG — sorgenti del 25 ottobre:** [PR 26](https://github.com/meteofriul/meteofriul-app/pull/26) integrata in main (`613fe78a`), commit della correzione `a431bd14`. 91 test locali e CI di PR/main superati. [Verbale, evidenze e limiti](WEATHER_HTTP_STARTUP_20261025.md). Il successivo deploy HTTP del 25 ottobre e la corsa avvisi delle 18:00 sono attestati nelle evidenze operative locali: source_failed=0 e tolleranze esercitate in 11/11 punti. Contratti Web/Android invariati; nessuna nuova AAB necessaria per il solo servizio HTTP.

**Sintesi per data locale — sorgenti del 25 ottobre:** [PR 24](https://github.com/meteofriul/meteofriul-app/pull/24) integrata in main (`8a47c752`); 84 test locali e CI di PR/main superati. [Verbale e limiti](SUMMARY_LOCAL_DATE_MONITOR_20261025.md). Nuovo allarme non attivato: collegamento operativo ancora da completare. Orari, Web/Android e sponsor invariati. Il controllo Eventi del 26 ottobre è concluso; quello del 27 ottobre resta attivo.

**Aggiornamento backend del 25 ottobre:** PR 22 integrata, CI superata e solo job Eventi aggiornato. [Verbale e rollback](EVENTS_PNPENSA_BARCOLANA_DEPLOY_20261025.md). Corsa ordinaria del 26 ottobre alle 05:00 italiane fallita con Barcolana stale per ReadTimeout. Correzione del timeout e distinzione degli allarmi distribuite il 26 ottobre; recupero da verificare nella corsa del 27 ottobre. Web/Android mantengono il contratto; il recupero Barcolana non è attestato.


**La precedente 0.1.15 / 300035 è stata sostituita nel test interno dalla 300036.
Nella prova storica della 300035 Tempo reale risultava vuoto:
difetto riprodotto sul Galaxy dopo la segnalazione del proprietario,
promozione allora sospesa. Il difetto è risolto nella 300036 verificata sopra.** La prova della AAB 300036 è quella indicata sopra; nessuna installazione dell'agente.

Già nella prova della 300035: Posizione conservata dopo ripresa e avvio a freddo; il proprietario la conferma
attiva prima e subito dopo l'aggiornamento. Aria/pollini IT/FUR e navigazione
superano i controlli osservati; configurazione nativa presente nell'APK e
precedente errore assente all'avvio. Restano da esercitare sul telefono gli
errori temporanei GPS; Android 15/16 e grandi schermi non provati.
[Verbale sul Galaxy](ANDROID_0.1.15_300035_DEVICE_CHECK_20261023.md).

AAB 300035 e sua candidata Web storica dalla sorgente `5e9bc7dc`; CI `39917176816` e builder PASS.
Web non pubblicata, sponsor disattivati. La sospensione della promozione per
Tempo reale appartiene alla 300035; la successiva prova della 300036 è descritta
sopra. Il tentativo 300034 resta abbandonato e conservato.
[Build](ANDROID_0.1.15_300035_BUILD_20261023.md) ·
[Accettazione Play](ANDROID_0.1.15_300035_UPLOAD_20261023.md).

## Preparazione CAMS/Eventi precedente alla 300037 (storico)

Release locale allineata in fast-forward all'ultimo main `0841020a`; nuova
candidata Web 0.1.15 e soli asset Web Android compilati dalla stessa sorgente.
Archivio `release-artifacts/web-candidates/20261024-0.1.15-0841020a/`.
Guardie locali (16 test), binding API prima/dopo, CARTO, service worker e hash
PASS. CI completa e prove Galaxy riutilizzate dopo verifica dell'identità
dei sorgenti. Sponsor disattivati, zero campagne. I 6.916 file protetti e il
ledger sono invariati. Nessuna AAB, installazione, deploy o invio.
Il ramo release è pubblicato su GitHub con la documentazione aggiornata;
main e pacchetti restano invariati. Codice identico alla CI verde `40107051151`.
[Verbale e limiti](RELEASE_WEB_CAMS_EVENTS_ALIGNMENT_20261024.md).

## Primo allineamento sorgenti del 24 ottobre (storico)

Il ramo `codex/release-0.1.15` contiene `cd471769` (quattro correzioni successive
alla 300036) e main `23153e54`, uniti senza conflitti in `ffa61949`. I sorgenti
frontend sono identici a quelli delle prove del 23 ottobre; i 116 test mirati
sono nuovamente superati dopo l’allineamento. Il 24 ottobre anche la prova
Brave/Galaxy IT/FUR delle quattro correzioni è PASS, nei limiti del
[verbale dedicato](WEB_POST_300036_GALAXY_20261024.md). Promozione e CI sono
tracciate nella [PR 19](https://github.com/meteofriul/meteofriul-app/pull/19).

Questa è la base sorgente comune per il prossimo pacchetto Web e Android;
non una nuova AAB o Web distribuibile. Sponsor disattivati. Nessuna nuova
versione riservata, installazione, pubblicazione o invio manuale.
[Allineamento, controlli e passaggi ancora aperti](RELEASE_WEB_SOURCE_ALIGNMENT_20261024.md).

## Promozione e GitHub dopo la PR 19

Le correzioni `53bedfe4` e il registro `dd7ea109` sono stati pubblicati tramite
la [PR 20](https://github.com/meteofriul/meteofriul-app/pull/20), merge `7813d5c4`.
Corretti il transitorio prima della prima risposta aria/pollini e il contatore
Eventi poco contrastato in scuro. Prova Brave/Galaxy IT/FUR, 76 test, lint e
compilazione PASS; hash dei sorgenti confermati prima della promozione.
[CI della PR](https://github.com/meteofriul/meteofriul-app/actions/runs/40106722957) e [CI di main](https://github.com/meteofriul/meteofriul-app/actions/runs/40107051151) entrambe verdi nei tre job.
Il ramo `codex/release-0.1.15` è successivamente allineato in locale a
`0841020a`, con candidata Web aggiornata come indicato sopra e ramo release pubblicato su GitHub. Nessuna nuova AAB, installazione, pubblicazione Web/Play,
modifica dei job o invio. Sponsor disattivati.
[Verbale e limiti](CAMS_INITIAL_LOADING_EVENTS_CONTRAST_20261024.md).

## Canali e rami

| Ambito | Stato attestato |
| --- | --- |
| Produzione Play | Lettura Console del 24 ottobre: 0.1.14 / 300031; nessuna promozione della 0.1.15 in produzione |
| Test interno Play | 0.1.15 / 300037 disponibile dal 24 ottobre alle 18:52; stessa unica lista con due account, configurazione prima/dopo identica; sponsor disattivati |
| Web pubblica | Pubblicazione del 21 ottobre da `1b0287c1`, versione 0.1.14; HTML e asset riconfermati il 23 ottobre. Candidata locale corrente 0.1.15 da `83c12c58`, con main `a4135392`, non distribuita; archivio storico della 300037 conservato; Safari/iPhone non verificato |
| Base main incorporata nelle AAB | Nuova 300037: `0841020a`, con PR 19/20; sorgente `d15edb10`, CI 40111204820 verde. La 300036 già in Play resta immutabile dalla vecchia base `2d8b0c32` |
| `codex/release-0.1.15` | Main `a4135392` incorporato localmente tramite `eb829a07`; candidata `83c12c58`. Nuovi commit non pushati, CI della nuova sorgente pendente. Web e risorse Android archiviate insieme; nessuna nuova AAB. La 300037 interna e i vecchi artefatti restano invariati |
| Ultimo artefatto osservato sul telefono (300037) | Sorgente `d15edb10067b972c10e4989ebebfe6410a194f2c`, AAB SHA256 `81d3b1848ceb19c9095a46ca6b55bf8ce5bd00337c01fedf1d4d7582809d96cf`; installer Play Store; [verifica sul Galaxy](ANDROID_0.1.15_300037_DEVICE_CHECK_20261024.md) |

I commit successivi, anche quando modificano il frontend, non cambiano il
commit sorgente dell’AAB già firmata. L’allineamento conserva la configurazione
0.1.15; la successiva build autorizzata ha riservato e prodotto la 300037.
Il solo canale interno ora usa la 300037; produzione e Web sono invariati.
Non riutilizzare il codice 300037: artefatto e registri precedenti restano immutabili.

**Preparazione locale del 22 ottobre:** la guardia del ramo release consente
un'altra AAB ufficiale con nome 0.1.15 e codice crescente, anche dopo 300033
accettata da Play. Riserve aperte e codici già consumati restano bloccati.
Suite locali e audit ledger superati; nessuna nuova versione riservata o
generata. [Dettagli e limiti](ANDROID_NATIVE_CONFIG_FIX_20261022.md#numerazione-e-prossimi-passi).

## Verifica storica della 300037 sul Galaxy — 24 ottobre sera

Posizione conservata anche secondo il proprietario prima/dopo update. Avvio,
ripresa e riavvio, Home, Previsioni, Bollettino, Tempo reale, Eventi, Scopri,
Impostazioni e conferma Community senza invio verificati nei percorsi descritti.
CAMS IT/FUR leggibile senza falsa indisponibilità nei 48 campioni per lingua;
cache vuota/errore di rete non provocati. Contatore Eventi scuro leggibile in
entrambe le lingue. Diciannove campi tecnici invariati; italiano/chiaro ripristinati.

Catalogo Eventi del 24 ottobre ancora degradato: 9 fonti fresh, 5 partial,
TurismoFVG stale. Sei schede in revisione; controlli API completi su tre centri
comunali, con limiti di orari/immagini espliciti. Recupero TurismoFVG da verificare
alla corsa del 25 ottobre alle 05:00 italiane. Rimane attenuato il testo
secondario del radar scuro. Nessuna nuova installazione, esecuzione manuale,
invio, deploy o pubblicazione. [Ricevuta, risultati e limiti](ANDROID_0.1.15_300037_DEVICE_CHECK_20261024.md).

## Rilievi aperti e prossima azione

| Rilievo | Evidenza e stato |
| --- | --- |
| REALTIME-LAYOUT-01 | FAIL nella 300035 installata. Fix `40af8779` approvato e in main, integrato nella AAB 300036 da `9d5ff2f4`; regressioni e build PASS, sorgenti identici alla prova Brave/Galaxy. CHIUSO nella 300036 installata da Play sul Galaxy: mappa e dock visibili in IT chiaro/FUR scuro, webcam e lista utilizzabili, conferma dopo avvio a freddo. Matrice Android restante esplicita nel nuovo verbale |
| NATIVE-CONFIG-01 | Nell'AAB 300033 mancano il JSON Capacitor e la risorsa Cordova `xml/config`. [Correzione locale del 22 ottobre](ANDROID_NATIVE_CONFIG_FIX_20261022.md): copia esplicita, keep mirato e controllo del bundle; regressioni locali superate. CHIUSO nella 300035: JSON e risorsa presenti anche nell’APK installato; avvio a freddo sul Galaxy senza il precedente errore |
| LOCATION-UPDATE-01 | Causa dell'episodio Play ancora non provata. Il 22 ottobre è stato riprodotto e corretto localmente un percorso di avvio che disattiva la preferenza dopo errori temporanei: 114 test passano. Correzione inclusa nella sorgente 300036 oggetto della PR 11. Percorsi ordinari sul Galaxy PASS; proprietario conferma preferenza attiva prima/dopo Play. Recupero da errore temporaneo sul dispositivo ancora non esercitato. [Analisi e limiti](ANDROID_LOCATION_STARTUP_20261022.md) |
| BULLETIN-MAP-01 | [Spaziatura corretta e verificata su Brave/Galaxy](BULLETIN_MAP_LABEL_SPACING_20261022.md), già in main e incorporata nella candidata. Ricontrollata nei campioni delle AAB 300035 e 300036 installate sul Galaxy il 23 ottobre |
| CAMS-TRANSITION-01 | Causa riprodotta e corretta: cache incompleta durante una nuova richiesta. Fix `53aba4ff` incluso nella AAB 300035, regressioni automatiche IT/FUR superate; rientro IT/FUR sul Galaxy senza falsa indisponibilità osservata. Con cache disponibile i valori arrivano subito: testo di caricamento intermedio non esercitato sul telefono. [Verbale](CAMS_REENTRY_LOADING_20261023.md) |
| WEB-300036-01/04 | Quattro correzioni `cd471769`: layout GPS Community, Eventi «Mostre altris», errore fonte OSMER in FUR e recupero CAMS. Test locali, browser PC e Brave/Galaxy IT/FUR superati nei casi documentati. [Prova reale e limiti](WEB_POST_300036_GALAXY_20261024.md); incluse nella 300037, ora osservata sul Galaxy nei percorsi descritti nel verbale del 24 ottobre; percorsi di errore non indotti restano distinti. [Verbale](WEB_0.1.15_300036_CORRECTIONS_20261023.md) |
| Copertura restante | Android 15/16, gesti, tablet/multi-window e percorsi con scritture o consegne reali non verificati; nessun PASS implicito |

Superate sul precedente pacchetto ufficiale 300033 le prove di avvio/ripresa, Indietro, previsioni
FVG e nazionali, temi e campione IT/FUR, Eventi, ricerca, allerte, aria/pollini,
webcam e conferma Community **senza invio**. Nessun crash osservato nella sessione.
Lo stato delle preferenze è stato riportato alla prima osservazione dell'agente,
già successiva all'aggiornamento: non certifica la migrazione dal vecchio pacchetto.

La verifica corrente non ricostruisce né sovrascrive gli artefatti precedenti.
Promozione del codice e pubblicazione restano azioni separate secondo il
[runbook Play](PLAY_AAB_RUNBOOK.md), con i limiti runtime sopra dichiarati.
La 300037 è ora installata dal proprietario; nessuna installazione dell’agente, deploy o invio manuale. [Preparazione precedente](RELEASE_0.1.15_300034_PREPARATION_20261023.md) e [verbale di build](ANDROID_0.1.15_300034_BUILD_20261023.md).

## Servizi e Web

- **ICON:** nuova corsa `20261021T000000Z` verificata; checkpoint schema 2,
  215 documenti/sidecar compatibili con i due lettori storici e sei località
  nazionali. **Aggiornamento 22 ottobre:** consumatore distribuito e corsa
  ordinaria delle 21:00 del 21 ottobre verificata: tolleranze usate in 7/7
  comuni, 42/42 valutazioni possibili, nessun candidato tempestivo da inviare.
  Tolleranza SWE e consegna FCM degli avvisi locali non esercitate in quella corsa.
  [Esiti del consumatore e riepilogo serale](JOBS_RECOVERY_DEPLOY_20261021.md).
  [Verbale ICON](ICON2I_PAYLOAD_LIMIT_DEPLOY_20261020.md).
- **Allerte FVG:** correzione distribuita e corsa ordinaria verificata; primo
  invio parziale e successiva deduplicazione documentati. La notifica ricevuta
  dal proprietario non dimostra consegna a tutti i dispositivi.
  [Verbale allerte](FVG_ALERTS_DEPLOY_20261020.md).
- **Community:** aggiornamento compatibile v2/v3 già distribuito e attivato;
  il controllo sul Galaxy non ha eseguito nuove scritture.
  [Verbale Community](COMMUNITY_0.1.15_DEPLOY_20261021.md).
- **Sponsor:** schede, sviluppo del pannello e allineamento dati restano
  sospesi fino a nuovo ordine. Ultima lettura 24 ottobre alle 22:16 dopo il collaudo: `enabled=false`,
  zero campagne, revisione 117.
- **Web:** pubblicazione del 21 ottobre confermata; il nuovo pacchetto locale
  0.1.15 deve ancora essere pubblicato separatamente. Manifest e sorgenti comuni
  nel [verbale corrente](ANDROID_0.1.15_300037_BUILD_20261024.md); Safari/iPhone
  resta non verificato nel [piano Web](WEB_ANDROID_RELEASE_PARITY.md).
- **Eventi, aggiornamento 22 ottobre:** correzioni distribuite, corsa ordinaria
  delle 06:00 verificata; Cinema Muto, Barcolana e Spazzapan recuperati. Restano
  12 schede in revisione e i monitor Attems/GiroFVG. La classificazione degli
  errori FCM resta un'attività distinta.
  [Verbale Eventi e limiti](JOBS_RECOVERY_DEPLOY_20261021.md).

## Registri, prove e GitHub

- [PR 11 — promozione del codice verificato e verbali della release](https://github.com/meteofriul/meteofriul-app/pull/11).
- [Verbale build e accettazione Play](https://github.com/meteofriul/meteofriul-app/blob/codex/release-0.1.15/docs/operations/ANDROID_0.1.15_BUILD_20261021.md).
- [Verbale sul Galaxy e rettifica sulla posizione](https://github.com/meteofriul/meteofriul-app/blob/codex/release-0.1.15/docs/operations/ANDROID_0.1.15_DEVICE_CHECK_20261021.md).
- [Ricevuta strutturata del dispositivo](https://github.com/meteofriul/meteofriul-app/blob/codex/release-0.1.15/release-history/android-preparation/0.1.15-20261021/device-verification.json).
- [Registro immutabile del ramo release](https://github.com/meteofriul/meteofriul-app/blob/codex/release-0.1.15/release-history/android-play/README.md).
- [Regole obbligatorie di preparazione](ANDROID_BUILD_PREVENTION_RULES.md).

Le riserve 300032 (abbandonata senza bundle) e 300033 (bundle accettato da Play)
restano consumate e immutabili nel ramo release. Non duplicare o riscrivere quei
record per la sincronizzazione documentale di main: consultarli prima di una
nuova riserva. I log privati, gli screenshot e gli artefatti firmati restano
nell'archivio locale ignorato `release-artifacts/android-play/`; non vengono
pubblicati su GitHub. Sono conservati gli hash delle evidenze nei verbali.

La CI verde controlla il codice nei commit indicati dalle esecuzioni, non
risolve i rilievi del dispositivo. CI del sorgente `39944265214`, dei record di
build `39945799912` e dell'accettazione Play `39948472277` verdi per la 300036.
Il salvataggio dell'accettazione Play segue il registro append-only previsto dal runbook.

Il 23 ottobre il proprietario ha autorizzato commit/push dei verbali e
allineamento a main dopo la prova della 300036. La PR 11 è stata unita in `eb109518`;
il suo record GitHub conserva l’esito e la CI. Il successivo allineamento del
24 ottobre è documentato separatamente: prova delle quattro correzioni
sul dispositivo completata e PR 19 promossa. Le due rifiniture ulteriori
sono anch'esse verificate e pubblicate in main tramite PR 20, con CI verde. Nessuno SHA di merge sostituisce l’identità
sorgente della AAB già firmata.
Nessuna pubblicazione Web o produzione Play è inclusa. Restano espliciti i casi
non esercitati, i vecchi worktree indipendenti e i loro file non ancora salvati;
non vengono importati né eliminati per questo allineamento.
