# Stato release 0.1.15 e lavoro salvato — aggiornamento del 23 ottobre 2026

**Allineamento locale successivo:** main `2d8b0c32` incorporato nella release tramite `16890b8c`, con Tempo reale corretto e Web ricompilata dalla stessa sorgente. Test e build locali PASS; codice 300035 non cambiato né riutilizzato per una nuova AAB. [Verbale corrente](RELEASE_WEB_REALTIME_ALIGNMENT_20261023.md).

**0.1.15 / 300035 è disponibile solo nel test interno personale di Google Play.
Il proprietario l'ha aggiornata via Play Store. Tempo reale risulta vuoto:
difetto riprodotto sul Galaxy dopo la segnalazione del proprietario,
promozione sospesa.** Nessuna nuova AAB o installazione dell'agente; la preparazione locale successiva è riportata sopra.

Posizione conservata dopo ripresa e avvio a freddo; il proprietario la conferma
attiva prima e subito dopo l'aggiornamento. Aria/pollini IT/FUR e navigazione
superano i controlli osservati; configurazione nativa presente nell'APK e
precedente errore assente all'avvio. Restano da esercitare sul telefono gli
errori temporanei GPS; Android 15/16 e grandi schermi non provati.
[Verbale sul Galaxy](ANDROID_0.1.15_300035_DEVICE_CHECK_20261023.md).

AAB 300035 e sua candidata Web storica dalla sorgente `5e9bc7dc`; CI `39917176816` e builder PASS.
Web non pubblicata, sponsor disattivati. La PR 11 resta in bozza e la release
non è stata promossa su main. Il tentativo 300034 resta abbandonato e conservato.
[Build](ANDROID_0.1.15_300035_BUILD_20261023.md) ·
[Accettazione Play](ANDROID_0.1.15_300035_UPLOAD_20261023.md).

## Canali e rami

| Ambito | Stato attestato |
| --- | --- |
| Produzione Play | Lettura Console del 23 ottobre: 0.1.14 / 300031; nessuna promozione della 0.1.15 in produzione |
| Test interno Play | 0.1.15 / 300035 disponibile dal 23 ottobre alle 09:59, una sola lista selezionata con un utente; sponsor disattivati |
| Web pubblica | Pubblicazione del 21 ottobre da `1b0287c1`, versione 0.1.14; HTML e asset riconfermati il 22 ottobre. Candidata 0.1.15 aggiornata da `16890b8c` preparata, non distribuita; Safari/iPhone non verificato |
| `main` | `2d8b0c32`, allineato a GitHub tramite PR 17; CI 39935808248 verde. Include aria/pollini e fix Tempo reale verificati nell’anteprima Galaxy; posizione e altre modifiche della release restano nel ramo dedicato |
| `codex/release-0.1.15` | Main `2d8b0c32` incorporato con sorgente `16890b8c`; Posizione, transitorio CAMS e configurazione nativa conservati. Web e asset Web Android allineati e verificati localmente. Nessuna nuova AAB o promozione della release su main |
| Ultimo artefatto osservato sul telefono (300035) | Sorgente `5e9bc7dcdc6183a2fc43ada2dea3dfb22f2a3dc1`, AAB SHA256 `1bcf6a32348eee0f098f475c179523a309d962a86c3faf8736a0bd29a1622762`; installer Play Store |

I documenti successivi non cambiano il commit sorgente dell'AAB già firmata.
La versione nella configurazione di `main` può quindi differire da quella del
test interno: non va modificata solo per far coincidere i numeri.

**Preparazione locale del 22 ottobre:** la guardia del ramo release consente
un'altra AAB ufficiale con nome 0.1.15 e codice crescente, anche dopo 300033
accettata da Play. Riserve aperte e codici già consumati restano bloccati.
Suite locali e audit ledger superati; nessuna nuova versione riservata o
generata. [Dettagli e limiti](ANDROID_NATIVE_CONFIG_FIX_20261022.md#numerazione-e-prossimi-passi).

## Rilievi aperti e prossima azione

| Rilievo | Evidenza e stato |
| --- | --- |
| REALTIME-LAYOUT-01 | FAIL nella 300035 installata. Fix `40af8779` approvato e in main, integrato nella candidata `16890b8c`; regressioni e build PASS, sorgenti identici alla prova Brave/Galaxy. Rimane aperta la verifica su una nuova AAB minificata; non chiuso dal solo allineamento |
| NATIVE-CONFIG-01 | Nell'AAB 300033 mancano il JSON Capacitor e la risorsa Cordova `xml/config`. [Correzione locale del 22 ottobre](ANDROID_NATIVE_CONFIG_FIX_20261022.md): copia esplicita, keep mirato e controllo del bundle; regressioni locali superate. CHIUSO nella 300035: JSON e risorsa presenti anche nell’APK installato; avvio a freddo sul Galaxy senza il precedente errore |
| LOCATION-UPDATE-01 | Causa dell'episodio Play ancora non provata. Il 22 ottobre è stato riprodotto e corretto localmente un percorso di avvio che disattiva la preferenza dopo errori temporanei: 114 test passano. Correzione integrata nel ramo release, non promossa su main. Percorsi ordinari sul Galaxy PASS; proprietario conferma preferenza attiva prima/dopo Play. Recupero da errore temporaneo sul dispositivo ancora non esercitato. [Analisi e limiti](ANDROID_LOCATION_STARTUP_20261022.md) |
| BULLETIN-MAP-01 | [Spaziatura corretta e verificata su Brave/Galaxy](BULLETIN_MAP_LABEL_SPACING_20261022.md), già in main e incorporata nella candidata. Ricontrollata nel campione della AAB 300035 installata sul Galaxy il 23 ottobre |
| CAMS-TRANSITION-01 | Causa riprodotta e corretta: cache incompleta durante una nuova richiesta. Fix `53aba4ff` incluso nella AAB 300035, regressioni automatiche IT/FUR superate; rientro IT/FUR sul Galaxy senza falsa indisponibilità osservata. Con cache disponibile i valori arrivano subito: testo di caricamento intermedio non esercitato sul telefono. [Verbale](CAMS_REENTRY_LOADING_20261023.md) |
| Copertura restante | Android 15/16, gesti, tablet/multi-window e percorsi con scritture o consegne reali non verificati; nessun PASS implicito |

Superate sul precedente pacchetto ufficiale 300033 le prove di avvio/ripresa, Indietro, previsioni
FVG e nazionali, temi e campione IT/FUR, Eventi, ricerca, allerte, aria/pollini,
webcam e conferma Community **senza invio**. Nessun crash osservato nella sessione.
Lo stato delle preferenze è stato riportato alla prima osservazione dell'agente,
già successiva all'aggiornamento: non certifica la migrazione dal vecchio pacchetto.

La verifica corrente non ricostruisce né sovrascrive gli artefatti precedenti.
Promozione del codice e pubblicazione restano azioni separate secondo il
[runbook Play](PLAY_AAB_RUNBOOK.md), con i limiti runtime sopra dichiarati.
La 300035 è installata dal proprietario; nessuna installazione dell’agente, deploy o invio manuale. [Preparazione precedente](RELEASE_0.1.15_300034_PREPARATION_20261023.md) e [verbale di build](ANDROID_0.1.15_300034_BUILD_20261023.md).

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
  sospesi fino a nuovo ordine. Ultima lettura 23 ottobre: `enabled=false`,
  zero campagne, revisione 117.
- **Web:** pubblicazione del 21 ottobre confermata; il nuovo pacchetto locale
  0.1.15 deve ancora essere pubblicato separatamente. Manifest e sorgenti comuni
  nel [verbale corrente](RELEASE_WEB_REALTIME_ALIGNMENT_20261023.md); Safari/iPhone
  resta non verificato nel [piano Web](WEB_ANDROID_RELEASE_PARITY.md).
- **Eventi, aggiornamento 22 ottobre:** correzioni distribuite, corsa ordinaria
  delle 06:00 verificata; Cinema Muto, Barcolana e Spazzapan recuperati. Restano
  12 schede in revisione e i monitor Attems/GiroFVG. La classificazione degli
  errori FCM resta un'attività distinta.
  [Verbale Eventi e limiti](JOBS_RECOVERY_DEPLOY_20261021.md).

## Registri, prove e GitHub

- [PR 11 — codice e preparazione release, in bozza](https://github.com/meteofriul/meteofriul-app/pull/11).
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
risolve i rilievi del dispositivo. La PR release rimane in bozza dopo
il caricamento nel test interno. Main non viene modificato; CI del sorgente
`39917176816` e dei record di build `39918859098` entrambe verdi. Il salvataggio
dell'accettazione Play segue il registro append-only previsto dal runbook.
La prova runtime nativa rimane un prerequisito della promozione del codice.
