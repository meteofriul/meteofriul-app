# 0.1.15 / 300037 — Galaxy e completezza Eventi, 24 ottobre 2026

**PASS dei percorsi osservati della AAB ufficiale; catalogo Eventi PARZIALE.**
La verifica non equivale a una qualifica completa Android né autorizza la
produzione. Rimane aperto il contrasto del testo secondario del radar scuro.

## Identità, sessioni ed evidenze

- App `com.meteofriul.app`, **0.1.15 / 300037**, aggiornata dal proprietario via
  Play Store alle 18:56:51; installer `com.android.vending`.
- Sorgente AAB `d15edb10067b972c10e4989ebebfe6410a194f2c`, main incorporato
  `0841020a`. AAB SHA256
  `81d3b1848ceb19c9095a46ca6b55bf8ce5bd00337c01fedf1d4d7582809d96cf`.
- Galaxy A52 SM-A525F, Android 14/API 34, target 36, 1080×2400, 420 dpi,
  navigazione a tre tasti. Pacchetto ufficiale minificato, non TEST/debug.
- Prima sessione circa 19:01–19:14 Europe/Rome, interrotta su richiesta del
  proprietario; ripresa circa 22:00–22:14. Nessuna prova durante lo scollegamento.
- Evidenze private durevoli nella radice canonica:
  `release-artifacts/android-play/evidence-300037/device-20261024/`.
  Screenshot, gerarchie, registrazioni e log non sono pubblicati in Git.
  [Ricevuta e hash](evidence/release-0.1.15-300037-device-20261024/verification.json).

Nessuna installazione dell'agente, AAB, emulatore, deploy, acquisizione o job
manuale, invio Community/notifiche, modifica destinatari, commit o push.
Sponsor confermati prima/dopo: `enabled=false`, zero campagne, revisione 117.

## Posizione e conservazione dello stato

Il proprietario conferma **«Sì, attiva prima e dopo»** l'aggiornamento Play:
testimonianza del proprietario, non misura dell'agente prima dell'update.
Al rientro l'app era in italiano/chiaro, ripristinati dal proprietario come
confermato in chat: non è una perdita di preferenze attribuita alla release.

Preferenza Posizione attiva, servizio Android attivo e permessi
fine/coarse/background concessi sono osservati separatamente. Allerte e Avvisi
rimangono attivi; autorizzazione notifiche conservata. Nessun interruttore
sensibile, permesso o servizio di sistema modificato.

Ripresa dopo 8 secondi in background nello stesso processo; avvio a freddo in
un nuovo processo con tempo Activity dichiarato 1.841 ms. Lingua friulana,
tema scuro e preferenze conservati in entrambe le prove. I **19 campi tecnici**
prima/dopo sono invariati, inclusi hash APK, versione, WebView e permessi.
Alla fine italiano/chiaro ripristinati, località Pordenone invariata, app su
Eventi. Nessuna cancellazione di dati o cache. Recupero da errori GPS,
geocodifica o timeout e precisione durante spostamenti non esercitati.

## Aria e pollini

Card e dettagli reali leggibili in italiano/chiaro e friulano/scuro, con unità,
fonte CAMS e ora del dato. Sei specie presenti nel dettaglio pollini.

| Ora locale del campione | PM2.5 | PM10 | O₃ | NO₂ | Graminacee |
| --- | --- | --- | --- | --- | --- |
| 19:00, italiano | 7,2 | 9,3 | 56,1 | 12,6 | 0,18 |
| 22:00, friulano | 10,1 | 11,6 | 37,6 | 16,2 | 0,15 |

Inquinanti in µg/m³, pollini in grani/m³. Artemisia 0,01; altre quattro specie
<0,01 nei campioni; elaborazione mostrata 02:00. Sono campioni di ore diverse,
non una discrepanza fra lingue. Questa prova legge l'app, non riattesta il job CAMS.

Due registrazioni di ingresso da Home a Meteo, 12 secondi ciascuna, esaminate
in **48 fotogrammi per lingua a 4 fps**: nessuna falsa «Dati non disponibili»
nei campioni. Dati già disponibili in cache; non provocati primo caricamento
a cache vuota, rete lenta, indisponibilità vera o errore di trasporto.
Il campionamento non esclude un transitorio inferiore a 250 ms. Le regressioni
automatiche precedenti non sostituiscono questi casi mancanti sul dispositivo.

## Sezioni e interazioni osservate

| Percorso | Risultato |
| --- | --- |
| Home | Meteo, Sintesi, anteprima Eventi e contenuti caricati anche dopo avvio a freddo; IT e FUR |
| Previsioni | Card uniformi, selezione giorno/ora coerente, dati reali e dettaglio CAMS leggibili; IT chiaro e FUR scuro. Il doppio 02:00 del 25 ottobre coincide con il cambio d'ora, non è contato come duplicato erroneo |
| Bollettino | Località e menù rimangono fissi nello scorrimento IT; mappa e quote senza la sovrapposizione precedente, testi FUR leggibili. Data editoriale osservata 23/10 13:35: non attestata qui una nuova pubblicazione OSMER del 24 |
| Tempo reale | Mappa visibile fino al piccolo distacco dalla barra inferiore, dock utilizzabile in entrambe le lingue; lista segnalazioni vuota coerente con mappa, 35 webcam, dettaglio Piancavallo aperto e Indietro funzionante |
| Radar | Attivazione, legenda FUR, play/pausa funzionanti; orario passa da 21:55 live a 20:40 e 21:00 durante riproduzione. Nessun eco di pioggia nel campione: accuratezza degli echi non verificata |
| Community | Form GPS IT/FUR leggibile senza sovrapposizioni, conferma No/Sì e richiamo 112. No torna alla scelta; chiusura senza inviare. Ricevuta di invio, voti e lista popolata non provati |
| Eventi | Oggi 2 / Prossimi 7 a Pordenone; contatore leggibile in IT e FUR scuro. Barra fissa durante scorrimento IT; dettaglio PEOPLE, PLACES & THINGS completo dei dati disponibili e Indietro torna alla lista |
| Scopri | Calendario, contenuti culturali e sezione del comune visibili in IT e FUR |
| Impostazioni e ricerca | Lingua/tema conservati e poi ripristinati. Indietro torna a Eventi. Ricerca Roma con tastiera aperta e un solo comando Cancella ricerca; cancellazione e chiusura senza selezione, località invariata |

**Rilievo aperto RADAR-DARK-CONTRAST:** «Nissune precipitazion rilevade» è molto
attenuato in scuro, già annotato nella 300036. Nessuna correzione in questa
sessione; il funzionamento della mappa non chiude il difetto di leggibilità.
Webcam notturna molto scura: apertura dimostrata, freschezza e accuratezza
dell'immagine non attestate. Previsioni nazionali, link esterni, consegna
notifiche e percorsi con scritture non ripetuti sulla 300037.

## Completezza degli Eventi pubblicati

Lettura del 24 ottobre alle 22:12 Europe/Rome, solo Storage/API e ultime
esecuzioni già esistenti, senza raccolta dalle fonti. Catalogo della corsa
**24/10 04:00 UTC**, generazione `1792814817227349`, SHA256
`b25e5ea5ec8a8b092ec47eb7bb2c5c2a4c3dedda5bd77ba95ef71f6107700923`.
Ultima esecuzione `meteofriul-events-refresh-68drg`, conclusa alle 04:07:01 UTC
con exit 1: è la corsa precedente al deploy del fix TurismoFVG.

- **15 fonti: 9 fresh, 5 partial, 1 stale (TurismoFVG).**
- 357 righe nelle fonti pubblicabili prima di filtri e raggruppamenti.
- TurismoFVG conserva 1.375 righe del 23 ottobre soltanto per diagnosi: fonte
  esclusa dalle risposte correnti, non 1.375 eventi necessariamente attuali
  o vicini all'utente. L'errore registrato è `adapter_exception`.
- Sei schede delle fonti parziali sono in revisione: Azalea 1 (cambio programma),
  CSS Udine 1 (orario ambiguo), Pordenone Pensa 2 (date da separare), SagreFVG 1
  (comune/provincia), Villa Manin 1 (disaccordo calendario/anno).
- Fonti fresh con zero schede non sono considerate automaticamente fallite.

Campioni API a centri comunali pubblici, raggio 20 km, limite 500, snapshot
vincolato allo stesso catalogo. Paginazione completa (`next_offset=null`),
conteggio ricevuto uguale a `total`, nessuna riga identica duplicata nei campioni.
Tutte le risposte dichiarano `catalog_status=degraded`, nessuna contiene TurismoFVG.

| Campione API | Righe | Orario assente | Immagine assente | Descrizione/estratto assente |
| --- | --- | --- | --- | --- |
| Pordenone | 100 | 12 | 7 | 2 |
| Udine | 120 | 46 | 5 | 1 |
| Gradisca d'Isonzo | 48 | 26 | 5 | 1 |

Titolo, fonte, URL, date valide, comune e sede/luogo sono presenti in tutti
questi campioni. Tre schede MESS di Udine e tre di Gradisca rappresentano un
programma con sessioni e distanza dalla sessione più vicina: non hanno un
singolo punto lat/lon e non sono classificate come coordinate perse.
Il campo separato `address` è assente: la sede può includere già l'indirizzo
in `venue`/`place`. Non si dichiarano orari o immagini esistenti dove mancano.
I campioni territoriali possono sovrapporsi: i denominatori non vanno sommati
come eventi unici regionali. Non verificata la correttezza fattuale di ogni
scheda sul sito originario né la completezza rispetto a tutti gli eventi FVG.

Il totale API 100 non corrisponde a 100 schede «Oggi»: include date future,
anche oltre l'orizzonte UI di 15 giorni, e occorrenze/ripetizioni fra fonti.
A Pordenone 90 righe sono oltre il periodo 24/10–08/11; dieci intervalli lo
intersecano, con due righe per Sagra del Pan Zal. La UI osservata mostra
2 oggi e 7 prossimi. Questo riscontro non è un replay completo del frontend.
La UI mantiene la diagnostica delle fonti nei dati senza mostrare messaggi
tecnici quando esistono eventi disponibili, secondo il comportamento corrente.

**Conclusione: consultazione funzionante, copertura non completa.** Il fix
TurismoFVG è già distribuito ma questa lettura non può certificarne il recupero.
Resta il controllo programmato della specifica corsa ordinaria del
**25 ottobre alle 04:00 UTC / 05:00 Europe/Rome** dopo il cambio d'ora.
Durante questa verifica sul telefono non è stata avviata alcuna corsa manuale
e non è stato anticipato il follow-up. Successivamente, su autorizzazione
esplicita del proprietario, la corsa manuale delle 22:24 ha recuperato TurismoFVG:
[risultati successivi e limiti](EVENTS_MANUAL_RECOVERY_20261024.md). I numeri sopra restano la fotografia
precedente; non attestano la visualizzazione del catalogo nuovo sul Galaxy.
Il verbale `docs/operations/JOBS_TARGETED_DEPLOY_20261024.md` resta nel
worktree separato `events-turismofvg-404`; non è importato nel ramo release
da questa verifica.

## Nativo, log e quattro aree Android

508 asset dell'APK base installato coincidono con l'AAB archiviata: zero
mancanti o diversi. Presenti JSON Capacitor, registro plugin e `xml/config`;
WebView debugging spento, nessun server di sviluppo. Hash APK prima/dopo
immutati. Configurazione nativa e avvio del pacchetto minificato verificati.

Log della sessione ripresa: 845 righe prima del riavvio e 562 dopo, senza
crash, ANR, errori JavaScript non gestiti o `net::ERR_` nei campioni.
Occorrenze numeriche 401/403 non sono errori HTTP: timestamp/ID dei job e
`res=0x403` del layout. Messaggi di dipendenze Android/WebView e feature flag
restano distinti e non dichiarati risolti; contenuto sensibile dei log privato.

| Area obbligatoria | Evidenza e limite |
| --- | --- |
| Edge-to-edge / inset | Schermate portrait e ricerca con tastiera osservate su Android 14 a tre tasti; Android 15/16, gesti, cutout e altre dimensioni NON VERIFICATI |
| API di sistema deprecate | Toolchain invariata; rimangono avvisi delle dipendenze e valutazione del nuovo rapporto Play, non chiusi da questo collaudo |
| Orientamento / grandi schermi | Portrait osservato; rotazione fisica, tablet e multi-window NON VERIFICATI |
| R8 / risorse | Release minificata effettiva, avvio a freddo e percorsi elencati verificati; non tutti i bridge/plugin. Limiti di shrinking e simboli transitivi del verbale build conservati |

Web candidata dalla stessa sorgente `d15edb10`, ancora non pubblicata. La prova
Android non verifica servizi/cache da origine Web autorizzata né Safari/iPhone
e PWA. Evidenze e aggiornamenti documentali salvati localmente nel ramo release;
nessuna modifica al codice o agli artefatti firmati. Commit/push e promozione
restano azioni distinte.

[Build](ANDROID_0.1.15_300037_BUILD_20261024.md) ·
[Upload](ANDROID_0.1.15_300037_UPLOAD_20261024.md) ·
[Stato release](RELEASE_0.1.15_STATUS_20261021.md) ·
[Parità Web](WEB_ANDROID_RELEASE_PARITY.md).
