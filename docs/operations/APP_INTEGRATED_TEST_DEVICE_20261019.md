# Candidato integrato: verifica della TEST sul Galaxy — 19 ottobre 2026

## Esito e perimetro

**PASS per l'allineamento locale dell'app a main.** Aggiornata soltanto la TEST
sul Galaxy A52, preservando dati, preferenze e app ufficiale. Il proprietario ha
autorizzato installazione e promozione a main subordinata alle verifiche.
Le prove pertinenti sono passate; il ramo può avanzare main mediante fast-forward.
Nessun push, deploy, AAB, invio Community reale o attivazione delle notifiche.

Questo verbale verifica il candidato applicativo recuperato nel
[piano di allineamento](APP_APPROVED_TEST_ALIGNMENT_20261019.md). Non certifica
una nuova release Play e non cambia il controllo dei job previsto per il 20 ottobre.

## Sorgente e artefatto

| Identità | Valore |
| --- | --- |
| Main di partenza | `6bd4216964ad81f7dcd20d478cde7b0db5ba442c` |
| Candidato applicativo | `bbef86141066c2e34abf8ac7ebf838909ef36c20` |
| HEAD usato per il build, con documentazione | `b0135d51c2a5b2560afa4fe9d7896134fd972511` |
| Configurazione TEST riutilizzata | `e7c27181296bfed82f4c44f2d527d773963248b5` |
| Package aggiornato | `com.meteofriul.app.localpilot` |
| Versione precedente → nuova | `0.1.14-full-test.5` / `300036` → `0.1.14-full-test.6` / `300037` |
| SHA-256 APK installato | `87b0873959057d32d1c4322fdd986cf0576b361758fa8473268a3baa23ee887b` |
| SHA-256 certificato, invariato | `4801ec985589d0c1195da9c8194136b4bdd49227dbd28712b26f45e795bbefca` |
| Dispositivo | Samsung Galaxy A52, SM-A525F, Android 14 / API 34 |
| Schermo e navigazione | 1080 × 2400, 420 dpi, verticale, tre tasti |
| WebView | `com.google.android.webview 155.0.8059.43`, invariata |

Build minificato, non debuggable, con resource shrinking e ottimizzazione R8.
Il builder Full TEST esistente è stato eseguito fuori sandbox, con Gradle offline
e due worker. Nessuna installazione di dipendenze. Il primo tentativo si è fermato
al controllo dei file Capacitor: la junction delle dipendenze aveva cambiato sei
percorsi nel file generato, senza cambiare plugin o versioni. Verificata questa
sola differenza, la ripetizione dello stesso builder è passata, senza disattivare
il controllo. Firma, package, versione, branding e guardia del bundle sono passati.

La confezione TEST è isolata in un checkout temporaneo separato. Dei 47 file
frontend cambiati dal candidato rispetto a main, 46 coincidono con il build
normalizzando CRLF/LF. `App.jsx` aggiunge solo l'abilitazione nazionale propria
della TEST; mantiene il codice candidato di Indietro e notifiche. Le ulteriori
differenze TEST sono elencate nella
[provenienza](evidence/app-integrated-phone-2026-10-19/source-provenance.json).

Per provare la ricevuta senza invii, il punto d'ingresso Full TEST abilita
l'anteprima Community interattiva già esistente, interamente in memoria. Il form
mostra esplicitamente «Anteprima locale» e «Posizione simulata». Una protezione
aggiuntiva della sola TEST rifiuta le richieste `fetch` diverse da GET/HEAD/OPTIONS.
Meteo ed Eventi usano i servizi reali; la scheda sponsor rimane sintetica e marcata QA.
Queste impostazioni, il namespace isolato, il marchio arancione, il package TEST
e i file di build non vengono portati su main.

## Verifiche sul telefono

Le prove sono avvenute fra le 22:44 e le 23:00 italiane. Ogni schermata rilevante
è accompagnata dalla gerarchia UI Android. L'app ufficiale non è stata aperta né
modificata durante queste prove.

| Scenario | Esito ed evidenza |
| --- | --- |
| Aggiornamento senza perdita dati | PASS. `adb install -r`; prima installazione e inode dei dati invariati. Nessun uninstall o cancellazione dati. Pordenone, italiano e scuro presenti all'avvio e ripristinati al termine. |
| App ufficiale preservata | PASS. `com.meteofriul.app` resta `0.1.14` / `300031`; hash di base e tre split, date, dati e permessi identici prima/dopo. |
| Previsioni italiano, chiaro/scuro | PASS. Giorni uniformi, pioggia leggibile, contorno e sfumatura uguali per giorno e ora: [chiaro](evidence/app-integrated-phone-2026-10-19/forecast-it-light-selected.png), [scuro](evidence/app-integrated-phone-2026-10-19/forecast-it-dark-selected.png). |
| Previsioni friulano, chiaro/scuro | PASS. Vuê/Doman/Miercus e mese completo senza troncamenti: [chiaro](evidence/app-integrated-phone-2026-10-19/forecast-fur-light.png), [scuro](evidence/app-integrated-phone-2026-10-19/forecast-fur-dark.png). |
| Pill del bollettino | PASS. Larghezza uniforme e nomi completi. Sul telefono la fascia scorre; la pill parzialmente visibile al bordo diventa intera scorrendo: [IT](evidence/app-integrated-phone-2026-10-19/bulletin-it-light.png), [FUR a fine fascia](evidence/app-integrated-phone-2026-10-19/bulletin-fur-last-day.png). |
| Conferma Community | PASS in simulazione. No ritorna alla scelta conservando Pioggia; Sì apre la ricevuta; titolo, pulsanti e richiamo 112 leggibili, nessuna X nella conferma: [IT](evidence/app-integrated-phone-2026-10-19/community-confirm-it-light.png), [FUR](evidence/app-integrated-phone-2026-10-19/community-confirm-fur-dark.png). |
| Ricevuta Community | PASS in simulazione. Testi centrati, nessuna sovrapposizione, Inviata da / Inviade di: [IT](evidence/app-integrated-phone-2026-10-19/community-success-it-light.png), [FUR](evidence/app-integrated-phone-2026-10-19/community-success-fur-dark.png). |
| Indietro Android | PASS. Chiude dettaglio orario, dettaglio aria e ricevuta; ritorna da Impostazioni. Da Home un solo Back porta al launcher Samsung; la riapertura riesce e conserva le preferenze. |
| Aggiornamento FVG | PASS. Pordenone mostra ICON-2I 14:00. Udine passa dalla cache delle [02:00](evidence/app-integrated-phone-2026-10-19/forecast-udine-light.png) alla corsa delle [14:00](evidence/app-integrated-phone-2026-10-19/forecast-udine-refreshed.png), senza svuotare lo storage. Resta esplicito l'avviso di continuità sui singoli valori dell'ultimo aggiornamento valido. |
| CAMS FVG | PASS. [Dettaglio aria Udine](evidence/app-integrated-phone-2026-10-19/cams-udine-air.png) con PM2.5, PM10, O₃ e NO₂, fonte e orari. |
| Nazionale | PASS per le [previsioni Roma](evidence/app-integrated-phone-2026-10-19/forecast-roma-settled.png), ICON-2I 14:00. UV, aria e pollini risultano non disponibili e sono dichiarati tali; non sono marcati come verificati disponibili. |
| Eventi | PASS. [Catalogo reale](evidence/app-integrated-phone-2026-10-19/events-real-loaded.png): presentazione a Caneva e Sagra del Pan Zal. Lo sponsor QA è distinto dagli eventi reali. A Roma è mostrato che gli Eventi coprono solo FVG. |
| Ripresa e log | PASS. [Home dopo riapertura](evidence/app-integrated-phone-2026-10-19/home-relaunch-settled.png). Nessuna firma di crash/ANR/errore JS non gestito nelle 601 righe del PID raccolte prima dell'uscita. Una segnalazione interna Android `AconfigStorageReadException` non ha interrotto il percorso. |

La regressione con quota storage esaurita resta coperta dai test locali mirati;
non è stata provocata artificialmente sul telefono. La ricevuta simulata non è
una prova di invio backend. Le notifiche della TEST restano negate da Android e
la localizzazione in background resta negata, come prima dell'aggiornamento.

## Verifiche automatiche e limiti Android

- 808 test applicativi mirati già passati sullo stesso codice, con ESLint e
  controllo di pulizia: [risultati](evidence/app-approved-alignment-2026-10-19/local-checks.json).
- Altri 7 test su barre e safe area passati; 9 test del release guard passati.
  Contratti R8 su configurazione, archivio mapping, inventario simboli, metadati
  dei permessi Capacitor e stack trace passati. Nessuna regola keep estesa introdotta.
- Edge-to-edge/inset: PASS nelle schermate osservate, temi chiaro/scuro, tastiera
  del selettore e navigazione a tre tasti su API 34. Android 15/16 e gesti:
  **NON VERIFICATI** in questa attività; nessun emulatore o test cloud avviato.
- API deprecate: nessuna modifica al codice nativo applicativo o alla toolchain
  nel candidato promosso. I controlli delle barre passano; i rilievi delle
  dipendenze non vengono dichiarati risolti da questa prova.
- Orientamento/schermi grandi: manifest dell'APK con Activity ridimensionabile,
  senza blocco portrait globale. Verificato il telefono in verticale; tablet,
  multi-window, ridimensionamento e la restante matrice: **NON VERIFICATI**.
- R8: eseguito realmente l'APK minificato della TEST. Conservati mapping e
  inventario librerie; questo non equivale a verificare il futuro pacchetto Play
  con firma, App Check, push e servizi in background di produzione.

Per il futuro rilascio resta obbligatorio il
[runbook Android](PLAY_AAB_RUNBOOK.md#controlli-android-obbligatori-per-ogni-release).
Nessuna CI remota avviata: il push è vietato dal perimetro attuale. La promozione
locale non dichiara già superata la futura CI di main.

## Conservazione e passaggio a main

Risultati, hash e screenshot/gerarchie selezionati sono versionati in
[phone-checks.json](evidence/app-integrated-phone-2026-10-19/phone-checks.json).
APK esatto, archivio R8, inventario librerie ed evidenze complete sono conservati
localmente, fuori da `.tmp`, in
`release-artifacts/android-play/full-test-integration-20261019/` nel workspace
canonico. Il nome della directory storica non indica una AAB: contiene la sola
TEST APK e gli allegati, tutti esclusi da Git. Non include chiavi di firma.

La promozione locale include i quattro commit applicativi del piano e la relativa
documentazione, mediante fast-forward dal main di partenza. Il checkout originario
della TEST e il checkout canonico su un altro ramo restano invariati. Nessun file
della confezione TEST viene integrato. Il prossimo push e ogni rilascio richiedono
un passaggio distinto; in questa attività non sono stati eseguiti.
