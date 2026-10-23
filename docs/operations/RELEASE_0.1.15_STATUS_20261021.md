# Stato release 0.1.15 e lavoro salvato — aggiornamento del 23 ottobre 2026

**0.1.15 / 300033 è disponibile solo nel test interno personale di Google Play.
La promozione della release rimane sospesa.** Il proprietario l'ha installata
dal Play Store; la sessione sul Galaxy A52 Android 14 ha trovato un difetto
di confezionamento e un rilievo grafico. Il proprietario ha inoltre segnalato
la posizione nell'app spenta subito dopo l'aggiornamento, prima dei test.


**Nuova AAB 0.1.15 / 300035 generata e verificata**, sorgente `5e9bc7dc`,
non caricata né installata. CI `39917176816` e builder completo PASS;
configurazione nativa, Cordova, firma e mapping verificati nel file reale.
Web dalla medesima sorgente, non pubblicata. Sponsor disattivati.
[Verbale e artefatti](ANDROID_0.1.15_300035_BUILD_20261023.md).
Il tentativo 300034 è abbandonato con autorizzazione esplicita e conservato.

## Canali e rami

| Ambito | Stato attestato |
| --- | --- |
| Produzione Play | Lettura Console del 23 ottobre: 0.1.14 / 300031; nessuna promozione della 0.1.15 in produzione |
| Test interno Play | 0.1.15 / 300033, una sola lista selezionata con un utente; sponsor disattivati |
| Web pubblica | Pubblicazione del 21 ottobre da `1b0287c1`, versione 0.1.14; HTML e asset riconfermati il 22 ottobre. Candidata 0.1.15 da `5e9bc7dc` preparata, non distribuita; Safari/iPhone non verificato |
| `main` | `f9e178b2`, due commit locali oltre origin/main `d62683b9` nella lettura del 23 ottobre. Include aria/pollini verificati sul Galaxy, oltre alle altre correzioni approvate; native e posizione restano nel ramo release |
| `codex/release-0.1.15` | Main `f9e178b2` incorporato, posizione `2e5fc0b6` conservata, transitorio CAMS `53aba4ff` integrato. `5e9bc7dc` identifica la AAB 300035 e la candidata Web; PR 11 pubblicata in bozza, verifica runtime aperta |
| Artefatto installato | Sorgente `f82503e4daabc283a5caf77b49e7cf58439abf61`, AAB SHA256 `cb461c8e5e6fddd05407214a507e151e02e8041f403d9346c364bbe0174ba019` |

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
| NATIVE-CONFIG-01 | Nell'AAB 300033 mancano il JSON Capacitor e la risorsa Cordova `xml/config`. [Correzione locale del 22 ottobre](ANDROID_NATIVE_CONFIG_FIX_20261022.md): copia esplicita, keep mirato e controllo del bundle; regressioni locali superate. Confezionamento verificato nella 300035: JSON e risorsa presenti; resta il controllo sul telefono |
| LOCATION-UPDATE-01 | Causa dell'episodio Play ancora non provata. Il 22 ottobre è stato riprodotto e corretto localmente un percorso di avvio che disattiva la preferenza dopo errori temporanei: 114 test passano. Correzione integrata nel ramo release; da verificare sul dispositivo e non promossa su main. [Analisi e limiti](ANDROID_LOCATION_STARTUP_20261022.md) |
| BULLETIN-MAP-01 | [Spaziatura corretta e verificata su Brave/Galaxy](BULLETIN_MAP_LABEL_SPACING_20261022.md), già in main e incorporata nella candidata. Ricontrollata nel pilot integrato; non ancora presente nella AAB installata 300033 |
| CAMS-TRANSITION-01 | Causa riprodotta e corretta: cache incompleta durante una nuova richiesta. Fix `53aba4ff` nella candidata 300034, regressioni automatiche IT/FUR superate; nuova verifica nel pacchetto Android ancora aperta. [Verbale](CAMS_REENTRY_LOADING_20261023.md) |
| Copertura restante | Android 15/16, gesti, tablet/multi-window e percorsi con scritture o consegne reali non verificati; nessun PASS implicito |

Superate sul pacchetto ufficiale le prove di avvio/ripresa, Indietro, previsioni
FVG e nazionali, temi e campione IT/FUR, Eventi, ricerca, allerte, aria/pollini,
webcam e conferma Community **senza invio**. Nessun crash osservato nella sessione.
Lo stato delle preferenze è stato riportato alla prima osservazione dell'agente,
già successiva all'aggiornamento: non certifica la migrazione dal vecchio pacchetto.

Prima di una nuova AAB: correggere e verificare i rilievi pertinenti, con
regressioni mirate. Non ricostruire o sovrascrivere 300033; seguire il registro
e le autorizzazioni distinte del [runbook Play](PLAY_AAB_RUNBOOK.md).
Il tentativo Android 300034 è abbandonato; la 300035 è generata e verificata. Nessun upload, installazione, deploy o invio. [Preparazione precedente](RELEASE_0.1.15_300034_PREPARATION_20261023.md) e [verbale di build](ANDROID_0.1.15_300034_BUILD_20261023.md).

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
  nel [verbale della 300034](RELEASE_0.1.15_300034_PREPARATION_20261023.md); Safari/iPhone
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
risolve i rilievi del dispositivo. La PR release rimane in bozza anche dopo
questo salvataggio locale sul ramo release. Main non viene modificato da questa
preparazione e la CI del nuovo candidato non viene avviata senza push autorizzato.
La prova runtime nativa rimane un prerequisito della promozione del codice.
