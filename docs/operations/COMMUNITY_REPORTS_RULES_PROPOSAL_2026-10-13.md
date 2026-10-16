# Segnalazioni Community: regole attuali e cambiamenti decisi

Data: 13 ottobre 2026.

Ramo di lavoro: `codex/community-reports-simplification`.

Questo riepilogo sostituisce la versione precedente della proposta. Tutte
le scelte di prodotto sotto elencate sono concordate, incluse le quattro
precisazioni finali del 13 ottobre. Le regole sono implementate nel ramo
segnalazioni e verificate con test automatici e servizio SQLite locale.
Main e il servizio pubblico restano invariati. La precedente simulazione
rimane una pagina separata di riferimento; l’app mantiene la UX esistente.

Per **utente** si intende la stessa installazione dell'app, non una persona
identificata attraverso un account. Il rango è **puramente estetico**: non dà
peso al voto, visibilità o premi. Le protezioni sui punti servono a evitare
spam e farming, non a proteggere vantaggi funzionali.

## Decisioni

### Invio e presenza sulla mappa

| Regola | Oggi | Decisione |
| --- | --- | --- |
| Posizione | GPS recente, compatibile con il Comune. Posizione precisa non pubblica. | Invariata. |
| Segnalazioni contemporanee | Più fenomeni coesistono; vietato duplicare lo stesso fenomeno nello stesso Comune. | **Una sola segnalazione attiva per installazione.** |
| Intervallo minimo tra invii | 2 minuti. | **3 minuti.** |
| Massimali degli invii | 4 negli ultimi 60 minuti; 12 nelle ultime 24 ore. | **Invariati: 4 negli ultimi 60 minuti e 12 nelle ultime 24 ore, per installazione.** Sono finestre mobili. |
| Durata | 60 minuti, prorogabili con aggiornamento. | **60 minuti dall'invio, senza rinnovo.** |
| Invio successivo | Si aggiunge agli altri. | La precedente è **archiviata automaticamente** quando la nuova è accettata. |
| Invio fallito | Non crea una nuova osservazione. | La precedente resta attiva fino alla scadenza. |
| Aggiornamento, correzione, sostituzione separata, ritiro manuale | Presenti. | **Eliminati.** Si invia una nuova osservazione. |
| Pulsante principale | Diverse azioni di gestione. | Un solo pulsante **"Segnala"**. |
| Prima dell'invio | Nessun riepilogo. | **Schermata di riepilogo** ("Stai segnalando **pioggia** a **[Comune]**. Invia?"). |
| "Annulla invio" | Non presente. | **Non introdotto.** Da riconsiderare dopo il lancio solo con dati reali. |

Pubblicazione della nuova osservazione e archiviazione della precedente
avvengono **in un'unica transazione sul server**: un invio fallito non deve
far sparire quella precedente.

L'attesa minima di 3 minuti e i massimali 4/60 minuti e 12/24 ore si
applicano insieme. Una sola osservazione attiva limita la presenza sulla
mappa, ma non sostituisce i limiti alla frequenza degli invii. Archiviare
automaticamente la precedente non restituisce una quota di invio.

Con una sola segnalazione attiva, inviare "vento" dopo "pioggia" sostituisce
il proprio contributo sulla pioggia anche se entrambi i fenomeni continuano.
Gli eventuali contributi degli altri utenti sulla pioggia restano attivi.

### Conferme e punti

| Regola | Oggi | Decisione |
| --- | --- | --- |
| Semplice invio | Zero punti. | Invariata. |
| Segnalazione convalidata | Può assegnare un punto all'autore. | **Al massimo un punto per segnalazione convalidata**, rispettando la regola delle 3 ore sotto descritta. |
| Altro utente segnala lo stesso fenomeno nello stesso gruppo | Può convalidare entrambi i contributi. | Conservata. |
| Chi preme "Conferma" | Nessun punto per il voto. | Invariata. |
| Autoconferma | Vietata. | Invariata. |
| Ulteriori conferme sullo stesso contributo | Non moltiplicano i punti. | Invariata. |
| Doppia conferma per assegnare un punto | Non richiesta. | **Non introdotta.** |
| Limite giornaliero ai punti | 3 punti. | **Eliminato: nessun tetto giornaliero ai punti.** Restano i massimali degli invii e la regola delle 3 ore. |
| Limite per coppia confermante/autore | Non previsto. | **Non introdotto.** Lo stesso confermante può convalidare più osservazioni dello stesso autore. |
| Attesa tra premi | 45 minuti. | **Eliminata.** |
| Un punto per episodio | Esistono protezioni parziali. | **Un solo punto per (fenomeno, Comune, autore) ogni 3 ore, decorrenti dall'ultimo punto effettivamente assegnato per la stessa combinazione.** Impedisce di ripremiare lo stesso fenomeno tramite ripubblicazioni o alternanza pioggia/vento. |
| Segnalazione "tranquillo" | Nessun punto. | Invariata; conta comunque come invio. |
| Scadenza | Non si confermano segnalazioni scadute. | Invariata; anche quelle sostituite non sono più votabili. |
| Punto già ottenuto | Resta dopo scadenza o cessazione. | Invariata. |
| Voti dopo cambio di fenomeno | Alcune procedure riuniscono voti precedenti. | **Nessun trasferimento dei voti dal vecchio fenomeno al nuovo.** |
| Moderazione | Può revocare punti di contributi invalidi. | Conservata. |

Ogni conferma deve essere collegata al contenuto effettivamente osservato.
Il raggruppamento sulla mappa non deve trasferire voti da una segnalazione
precedente a una nuova con fenomeno diverso. Una conferma in ritardo su una
segnalazione sostituita non deve premiare quella nuova, e richieste ripetute
non devono assegnare due volte lo stesso punto.

Le 3 ore decorrono dall'ultimo punto assegnato per lo stesso fenomeno,
Comune e autore: non dall'invio della segnalazione, da un punto ottenuto
per un altro fenomeno o dall'inizio di una fascia oraria. Un nuovo punto
per quella combinazione è possibile quando sono trascorse almeno 3 ore.
Una convalida senza punto non sposta il termine. La regola non prolunga
la durata di 60 minuti delle segnalazioni e non rende votabili quelle
scadute o sostituite.

#### Esempio

| Momento | Cosa succede |
| --- | --- |
| 12:00 | Invio di pioggia: zero punti. |
| 12:01 | Un'altra installazione conferma: un punto all'autore. |
| 12:03 | Lo stesso autore segnala vento: la pioggia passa nello storico, il punto resta. |
| 12:04 | Qualcuno conferma il vento: un altro punto all'autore (fenomeno diverso, non bloccato dalla regola delle 3 ore). |
| 12:07 | Lo stesso autore segnala di nuovo pioggia nello stesso Comune: la nuova osservazione scade alle 13:07, se non sostituita prima. |
| 12:08 | Un'altra installazione conferma la nuova pioggia: la segnalazione è convalidata, ma **non** assegna un nuovo punto. Il precedente punto per la pioggia risale alle 12:01. |
| 15:01 | Sono trascorse 3 ore dall'ultimo punto per la pioggia in quel Comune. Un nuovo invio di pioggia, se accettato e convalidato mentre è attivo, può ricevere un punto. La segnalazione delle 12:07 è già scaduta e non viene ripremiata. |

### Azioni sulle segnalazioni altrui

| Regola | Oggi | Decisione |
| --- | --- | --- |
| Conferma positiva | Testi diversi secondo la schermata. | **"Confermo".** |
| Fenomeno terminato | Testi che mescolano "Smentisci" e cessazione. | **"Non c'è più".** |
| Posizione per votare | Controlli da uniformare. | **GPS recente e compatibile con il Comune per entrambe le azioni**, "Confermo" e "Non c'è più". |
| Ritiro dalla mappa | 3 voti negativi ritirano il gruppo per tutti. | Soglia invariata (3), ma **contano solo i voti di installazioni con GPS recente e compatibile col Comune.** |
| Effetto sui punti già ottenuti | La cessazione non li revoca. | Invariata. |

"Non c'è più" descrive la fine del fenomeno, non dichiara falsa la
segnalazione originaria. La segnalazione di un abuso resta un'azione distinta.

### Storico e ranghi

| Aspetto | Oggi | Decisione |
| --- | --- | --- |
| Storico | "Recenti" e registrazioni tecniche interne di 48 ore. | **Storico generale della zona delle ultime 48 ore** (non personale), con indicazione "tu" sulle voci proprie. Finestra calcolata dall'invio. |
| Contenuto | n/d | Fenomeno, Comune, orario, esito (attiva, scaduta, sostituita, non c’è più). |
| Privacy | n/d | Il payload contiene solo `mine: true/false`, **mai** identificativi di altre installazioni. |
| Punto ottenuto | n/d | Mostrato solo sulle voci con `mine: true`. |
| Voci archiviate | n/d | Non votabili. |
| Inviate (contatore) | Difetto individuato nell'analisi. | Contare ogni nuovo invio accettato, una sola volta. |
| Convalidate (contatore) | Il filtro dei premi può alterarlo. | Contarle indipendentemente dall'assegnazione dei punti. |
| Osservadôr dal Cîl | 0–4 punti. | 0–4 punti. |
| Vuaite dal Timp | 5–19 punti. | **5–14 punti.** |
| Sentinele dal Teritori | Da 20 punti. | **Da 15 punti.** |

## Precisazioni finali confermate

- Nessun tetto giornaliero ai punti.
- Nessun limite di un premio ogni 24 ore per la stessa coppia confermante/autore.
- Storico generale della zona consultabile per 48 ore dall'invio.
- GPS recente e compatibile con il Comune per entrambi i voti.

Non viene introdotta un'anzianità minima dell'installazione per votare.
L'ipotesi delle 24 ore resta un possibile intervento futuro, solo se emergono
abusi reali e dopo una nuova decisione.

## Anteprima locale dell'interfaccia

Avvio dal workspace canonico attraverso
`scripts/start-local-weather-pilot.ps1`; pagina
`http://127.0.0.1:5174/community-preview.html`.

La pagina è un ingresso di sviluppo separato dall'app. Non chiama le API
Community e non salva dati: invio, posizione, conferme e tempo sono simulati.
Permette di provare il riepilogo, la sostituzione, gli errori d'invio, lo
storico, i contatori, il tema scuro e la vista ampia. Non dimostra che le
transazioni, i controlli GPS o la concorrenza del server reale siano corretti.
Queste verifiche preliminari sono seguite dall’implementazione descritta sotto.

Verifiche locali del 13 ottobre 2026:

- 17 test della simulazione superati: sostituzione senza ereditare voti,
  conservazione in caso di errore, quote mobili e confini temporali, punti
  separati dalle convalide, scadenze, GPS per entrambi i voti e ranghi.
- Il raggruppamento conserva la fascia oraria esistente: due osservazioni
  attive dello stesso fenomeno e Comune, ma in fasce orarie diverse, non
  si convalidano automaticamente. Questo è distinto dalle 3 ore dei premi.
- Controllo nel browser: invio fallito e ripetuto con successo, storico della
  precedente, incremento del rango al quinto punto, conferma senza punto
  nelle 3 ore, scadenza a 60 minuti e blocco di entrambi i voti senza GPS.
- Aspetto verificato in tema chiaro/scuro, vista ampia e viewport mobile
  390 × 844; selettore senza scorrimento orizzontale. Evidenze locali in
  `.tmp/community-reports-preview/` (non versionate).
- ESLint dei file aggiunti e controllo del workspace canonico superati.
  Build Web ordinaria riuscita in una cartella temporanea; pagina e codice
  dell'anteprima esclusi dall'output. Restano gli avvisi preesistenti sui
  chunk e sull'import di AlmanacView.

Per questa prova le fixture meteo locali, estranee ai dati della Community
simulata, sono state avviate con
`-WeatherTestNow '2026-09-04T12:00:00Z'` perché lo snapshot disponibile
risulta scaduto alla data odierna. Non è una verifica del meteo corrente.
Non sono stati eseguiti test Android, pubblicazioni o migrazioni dei dati.

## Implementazione nel ramo segnalazioni

Verifica del 13 ottobre 2026; baseline `main` invariata:
`5a68de5dc1607105f921d4d2b731170f1a8a0446`.

- Servizio `CommunityReportsService`, contratto `community-reports-v3`,
  sugli archivi transazionali esistenti (memoria, SQLite, snapshot Cloud).
  Nessun deployment o migrazione sul servizio pubblico.
- Una sola osservazione attiva per installazione; archiviazione e nuova
  creazione nella stessa transazione. Ricevuta idempotente, limiti mobili
  invariati, minimo 180 secondi e scadenza di 60 minuti senza rinnovo.
- Registro per singola osservazione: invii, convalide e punti separati;
  le 3 ore sono registrate dal momento del punto effettivo per autore,
  fenomeno e Comune. Nessun tetto giornaliero ai punti o limite per coppia.
- Entrambi i voti richiedono GPS valido e gli ID delle osservazioni viste.
  Se nel frattempo il contenuto del gruppo cambia, il server rifiuta il
  voto e richiede di aggiornare la mappa. Anche il voto salvato localmente
  è associato agli ID, per non nascondere o confermare nuovi contenuti.
- Storico della zona con paginazione, finestra di 48 ore dall’invio,
  proiezione pubblica senza identificativi delle installazioni e dettaglio
  del punto limitato alle proprie voci.
- La UX mantiene mappa, navigazione, otto icone e pannello esistenti.
  Aggiunti riepilogo prima dell’invio, storico nel pannello Segnalazioni e
  spiegazione dei tre contatori nel profilo; rimossi gli accessi alle azioni
  di correzione/rinnovo/ritiro. Le API corrispondenti rifiutano tali azioni.
- I client precedenti privi degli ID/GPS necessari non possono votare con
  il nuovo contratto. Prima di un rilascio pubblico occorre coordinare
  aggiornamento client/server; questa prova locale non autorizza il rilascio.
- I contatori preesistenti sono conservati. Non è stata inventata una
  ricostruzione retroattiva degli invii oltre i dati disponibili: l’eventuale
  riconciliazione dello storico pubblico richiede un controllo dedicato.

### Evidenze e limiti

- **156 test backend superati**, inclusi 19 casi nuovi per transazioni,
  concorrenza, idempotenza, cambio fenomeno, limiti, GPS, premi, ranghi,
  privacy, moderazione e persistenza dopo riapertura di SQLite.
- **991 test frontend superati** (64 file), inclusi riepilogo, cambio del
  Comune durante il riepilogo, GPS per entrambi i voti, storico paginato,
  voti locali legati al contenuto e recupero delle vecchie operazioni.
- ESLint sui file modificati e controllo pulizia del workspace superati.
- Prova via HTTP soltanto su `127.0.0.1:8783`, archivio SQLite: invio e
  conferma danno `1 inviata / 1 confermata / 1 punto`; sostituzione con
  diverso fenomeno e replay danno `2 inviate / 1 confermata / 1 punto`.
  GPS insufficiente rifiutato mantenendo la precedente attiva; nessuna
  convalida trasferita alla nuova. Dati fittizi identificati come test locali.
- UI reale aperta su `http://127.0.0.1:5174/`, con launcher canonico e
  `-CommunityPilot`. Verificati scheda, nuovi pulsanti, errore GPS visibile,
  storico con voce sostituita, tre contatori e spiegazione del profilo,
  tema chiaro/scuro e viewport 390 × 844. Evidenze non versionate in
  `.tmp/community-rules-evidence/`; log test in `.tmp/community-rules-*-tests.log`.
- Il browser integrato non fornisce GPS: al termine di queste prove Web la verifica completa dell’invio
  tramite UI Android restava da effettuare nella TEST. I test con GPS sopra
  usano coordinate di fixture, non costituiscono una prova sul dispositivo.
- Le fixture meteo usano ancora `-WeatherTestNow '2026-09-04T12:00:00Z'`;
  Community usa l’ora corrente. Il meteo nazionale locale non disponibile
  in questa sessione è estraneo alla verifica delle regole Community.
- Nessun telefono modificato, nessun push GitHub, AAB, upload Play,
  aggiornamento main o pubblicazione in produzione.

### APK TEST iniziale, prima del collaudo Android

La preparazione descritta qui è stata seguita dal
[collaudo Android 15/16 con GPS](COMMUNITY_REPORTS_ANDROID_TEST_2026-10-13.md):
prove principali Community superate, candidata finale installata solo sugli
emulatori, rilievi ancora aperti su barre e orientamento. Il documento di collaudo
riporta hash aggiornato, schermate ed esiti; telefono e main restano esclusi.

- Commit del codice candidato: `1923c2e79e86bc2477b727f1ff0bcda1679b17f5`.
- Commit delle regole: `f43fe99955f5d511b5462457108d03ea847f4464`.
- APK locale conservato in
  `.tmp/community-rules-evidence/meteofriul-community-rules-test.apk`.
- SHA-256: `3fc435b7558c8b97ad83842d3398024b8b6d28bad33ca7c9267f939b3eb37077`.
- Package: `com.meteofriul.app.localpilot`; variante debug `localPilot`,
  separata dal pacchetto pubblico. Compilazione e guard del bundle superati;
  al termine della sola preparazione **non ancora installato né verificato in esecuzione su Android**.
- Community: `http://127.0.0.1:8783/api`, collegamento ADB reverse necessario
  quando si procederà alla prova su emulatore. Nessun backend pubblico
  aggiornato. Il servizio locale è stato riavviato dal launcher canonico e
  conserva storico e contatori (2 inviate / 1 confermata / 1 punto).
- La prima compilazione ha rilevato fallback ai servizi pubblici nel bundle
  locale. Sono esclusi a compilazione nel solo profilo Android con servizi
  loopback, incluso UV; configurazione errata Community rifiutata prima
  della richiesta. I profili pubblici e cloud mantengono i loro indirizzi.
  Il guard non è stato allentato; i suoi **6 test** sono superati. I test
  aggiuntivi dei servizi sono inclusi nei 991 sopra indicati.
- Log build: `.tmp/community-rules-android-build.log`. Manifest del
  candidato: `.tmp/community-rules-evidence/candidate.json`.

Valutazione delle quattro aree Android per questa preparazione:

| Area | Evidenza / limite del candidato |
| --- | --- |
| Edge-to-edge e inset | Codice nativo invariato. Verifica runtime su Android 15/16 e versione precedente da eseguire su questo APK. |
| API deprecate delle barre | Nessuna modifica nativa. La build segnala una API deprecata nella dipendenza PushNotificationsPlugin: non classificata come risolta né come API delle barre senza analisi. |
| Orientamento, ridimensionamento, schermi grandi | UI Web controllata a larghezza telefono e nella finestra browser. Rotazione e schermi grandi Android non verificati su questo candidato. |
| R8 e risorse | `localPilot` è debug non minificata; compilazione riuscita, nessuna prova aggiuntiva del comportamento release/R8. |

Nessuna delle evidenze di compilazione sostituisce il collaudo runtime o
l’eventuale futura approvazione per main, Play e produzione.

## Riferimenti

L'analisi del codice e le riproduzioni dei difetti dei contatori sono in
[Segnalazioni e punti della Community](COMMUNITY_REPORTS_REVIEW_2026-10-13.md).
Le proposte di quel documento precedono questo riepilogo: per le scelte di
prodotto discusse successivamente, il riferimento aggiornato è questo file.
