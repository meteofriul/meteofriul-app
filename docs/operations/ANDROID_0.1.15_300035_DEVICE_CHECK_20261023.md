# 0.1.15 / 300035 — verifica sul Galaxy dopo aggiornamento Play

**Esito aggiornato: FAIL — Tempo reale vuoto nella 300035; promozione sospesa.**
I controlli mirati precedenti su Posizione, CAMS e navigazione non erano una
verifica completa. Tempo reale era stato omesso: il proprietario ha segnalato
il problema dopo il primo riepilogo e l’agente lo ha riprodotto sul Galaxy.
Il proprietario ha aggiornato dal Play Store; l'agente ha verificato il pacchetto
già installato. Nessuna nuova AAB, installazione, emulatore, push, merge, deploy,
job o invio manuale. Sponsor disattivati prima e dopo la sessione.

## Identità e ambiente

- 23 ottobre 2026, osservazioni sul telefono circa 10:30–10:48 Europe/Rome.
- App ufficiale `com.meteofriul.app`, **0.1.15 / 300035**, installer
  `com.android.vending`; ultimo aggiornamento sul telefono alle 10:15:25.
- Sorgente compilata `5e9bc7dcdc6183a2fc43ada2dea3dfb22f2a3dc1`.
- AAB SHA256 `1bcf6a32348eee0f098f475c179523a309d962a86c3faf8736a0bd29a1622762`.
- Galaxy A52 SM-A525F, Android 14/API 34, target 36, 1080×2400, 420 dpi,
  navigazione a tre tasti; WebView 155.0.8059.43 invariata.
- Pacchetto ufficiale minificato distribuito da Play, non APK debug o TEST.

[Ricevuta strutturata e hash delle evidenze](evidence/release-0.1.15-300035-device-20261023/verification.json).
Screenshot, gerarchie, registrazioni e log privati restano nella radice canonica
in `release-artifacts/android-play/evidence-300035/device-20261023/`, ignorata
da Git. Nessun identificativo del telefono, alias, token o dato di account
è copiato nella ricevuta condivisibile.

## Posizione

Il proprietario conferma: **«Era attiva ed è rimasta attiva»**, riferendosi a
prima e subito dopo l'aggiornamento Play. È una testimonianza del proprietario,
non una misura dell'agente eseguita prima dell'aggiornamento.

La prima lettura dell'agente e quelle successive mostrano la localizzazione
automatica attiva, con «Attiva anche ad app chiusa». Il servizio Posizione
Android è attivo; i permessi fine, coarse, background e notifiche sono concessi.
I tre livelli sono stati controllati separatamente.

Superati ritorno dal background (8 secondi, stesso processo) e avvio a freddo
(nuovo processo, senza cancellare dati/cache): la preferenza resta attiva.
Non sono stati toccati interruttore Posizione, località predefinita o permessi.
I 18 campi della baseline tecnica prima/dopo sono invariati, inclusi hash degli
APK installati, data di aggiornamento, permessi e impostazioni di sistema.

**Limite:** non è stato indotto un errore GPS temporaneo, un timeout o un errore
di geocodifica sul telefono; non è stata misurata la precisione o la variazione
della posizione durante uno spostamento. Le regressioni automatiche dei casi
negativi restano documentate nell'[analisi del difetto](ANDROID_LOCATION_STARTUP_20261022.md).
La causa dell'episodio precedente della 300033 non diventa provata con questa
sessione. LOCATION-UPDATE-01 supera il percorso ordinario su dispositivo;
il recupero da errore temporaneo sul dispositivo resta aperto.

## Aria e pollini

Card e dettagli caricano dati reali sia in italiano sia in friulano. Nel campione:
PM2.5 **13 µg/m³**, PM10 **16,1 µg/m³**, ozono **28,6 µg/m³**, NO₂ **17,9 µg/m³**;
graminacee **0,06 grani/m³**, sei specie e due attive. I dettagli delle due
lingue riportano gli stessi valori e unità.

Riferimento del dato: **23/10/2026, 10:00**. Elaborazione mostrata:
**22/10, 02:00**. «Ultimo dato CAMS» / «Ultin dât CAMS» identifica il dato
disponibile: non è una misura di centralina né una nuova attestazione della
corsa ordinaria dei job CAMS.

Rientro da Impostazioni registrato per 12 secondi in ciascuna lingua, con
scorrimento immediato alle card e ispezione a 4 fotogrammi al secondo:
nessuna falsa indisponibilità nei campioni osservati; i valori sono subito
disponibili. Le registrazioni originali sono conservate. Verificata anche
la leggibilità delle card in tema scuro/friulano e l'apertura/chiusura dei
dettagli mediante Indietro Android.

**Limite:** la cache disponibile ha reso immediato il recupero. Il testo
intermedio «Caricamento…» / «In cjariament…» non è stato esercitato sul telefono
in questa sessione; nessun ritardo di rete, errore remoto o svuotamento della
cache è stato imposto. Le regressioni controllate IT/FUR del
[transitorio CAMS](CAMS_REENTRY_LOADING_20261023.md) restano la prova dei rami
di caricamento e indisponibilità effettiva. L'osservazione campionata non
esclude un transitorio più breve dei campioni o in condizioni diverse.

## Configurazione nativa e navigazione

L'APK base effettivamente installato contiene `assets/capacitor.config.json`,
il registro plugin e `res/xml/config.xml`; gli hash dei due JSON coincidono
con quelli del pacchetto approvato. Confrontati inoltre tutti i 508 file degli
asset del bundle con quelli installati: nessuno mancante o diverso.
Debug WebView disattivato, nessun server
di sviluppo. Dopo avvio a freddo non ricompare l'errore
`Unable to load capacitor.config.json`, né un errore relativo al file Cordova.
**NATIVE-CONFIG-01 è chiuso per confezionamento e avvio sul Galaxy.**

Nessun crash, ANR, errore JavaScript non gestito o `net::ERR_` nei due log
raccolti (1.084 righe non vuote prima dell'avvio a freddo, 515 dopo). Le occorrenze
numeriche isolate «401/403» non sono risposte HTTP. Rimangono avvisi di
Android/WebView su ricerca `classes.dex` negli split, capacità media/Bluetooth,
opt-in `OnBackInvokedCallback` e feature flag: non sono dichiarati risolti.

Controlli di navigazione eseguiti sulla 300035:

- Indietro da Impostazioni torna alla sezione precedente.
- Sintesi Home apre Bollettino lasciando visibili località e menù.
- Località e menù restano fissi durante lo scorrimento di Bollettino ed Eventi;
  le previsioni continuano a scorrere normalmente.
- Mappa del giorno: etichette di quota e località leggibili senza la precedente
  sovrapposizione nel campione. BULLETIN-MAP-01 riconfermato sul runtime nativo.
- Eventi carica il catalogo; il dettaglio copre normalmente la sezione e
  Indietro torna alla lista, mantenendo la posizione di scorrimento.

## REALTIME-LAYOUT-01 — difetto riprodotto dopo la segnalazione del proprietario

Il 23 ottobre, circa 11:02 Europe/Rome, l'agente apre Meteo → Tempo reale
nella stessa 300035. Restano visibili intestazione, località, tre tab e menù
inferiore; l'area centrale è vuota. Due acquisizioni distanziate confermano
il difetto. La gerarchia contiene i controlli della mappa, 35 webcam e il dock,
ma quest'ultimo risulta sopra l'area utile: la presenza nella gerarchia non è
un PASS di visibilità. Nessun comando Segnala o invio è stato attivato.

L'ispezione dei sorgenti identifica una discrepanza concreta introdotta dal
raggruppamento della navigazione in `aa505cd6`: `AppRoutes.jsx` ora rende due
figli della griglia (navigazione raggruppata e contenuto), mentre `live.css`
mantiene tre righe `auto auto minmax(0, 1fr)` e anche la variante per finestre
basse ne mantiene tre. Lo spazio elastico resta nella terza riga vuota.
È la causa sospetta coerente con il collasso osservato; la correzione non è
stata ancora applicata né verificata. Non si attribuisce il difetto ai job.

Evidenze aggiunte: `realtime-entry.png/xml`, `realtime-still-blank.png/xml`
e log privato separato, senza sovrascrivere le prove precedenti. La ricevuta
complessiva è aggiornata a FAIL e conserva i risultati parziali validi.
Il resoconto iniziale non poteva essere presentato come verifica di tutta
l'app. Prima della promozione serve correggere il layout e riprovare Tempo
reale, mappa e controlli nel pacchetto ufficiale; la sola assenza di crash
non dimostra il funzionamento. Telefono lasciato sulla schermata del difetto.

## Quattro aree Android e limiti di rilascio

| Area | Risultato di questa sessione |
| --- | --- |
| Edge-to-edge / inset | Nessuna sovrapposizione con barre di sistema nelle schermate portrait osservate su Android 14 a tre tasti. Android 15/16, gesti e matrice cutout/tastiera non verificati |
| API system bar deprecate | Toolchain invariata; gli avvisi delle dipendenze non sono chiusi da questa prova |
| Orientamento / adattività | Portrait osservato; rotazione, tablet e multi-window non esercitati |
| R8 / risorse | Avvio a freddo e percorsi selezionati superati sul pacchetto ufficiale minificato; configurazioni native presenti. Non è una prova di tutti i plugin e di tutte le funzioni |

Sponsor: `enabled=false`, zero campagne, revisione 117, letture prima/dopo.
Pannello e allineamento dati sponsor non attivati. Ripristinati italiano e
tema chiaro; app lasciata sulla Home. Posizione, Allerte e Avvisi conservati.
Non eseguite segnalazioni Community o notifiche di prova.

Il difetto Tempo reale lascia incompleta la qualifica della candidata e
blocca la promozione. Questo verbale non esegue promozione su main o
pubblicazione in produzione. La Web candidata
rimane quella della stessa sorgente, non pubblicata; Safari/iPhone non verificato.
Restano distinti i limiti sopra e le verifiche storiche sulla 300033.
[Stato release](RELEASE_0.1.15_STATUS_20261021.md) · [Build](ANDROID_0.1.15_300035_BUILD_20261023.md).
