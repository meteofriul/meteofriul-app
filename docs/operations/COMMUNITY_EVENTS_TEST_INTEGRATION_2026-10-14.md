# Community ed Eventi nella TEST — 14 ottobre 2026

Aggiornamento successivo: la candidata `92eb9337`, con tutte le modifiche UX
descritte in fondo a questo documento, è stata ricompilata e collaudata su
Android 15/16 e sul Galaxy A52 autorizzato. Vedere il
[resoconto Android della nuova APK](COMMUNITY_EVENTS_ANDROID_TEST_2026-10-14.md)
per identità, risultati e problemi ancora aperti. Le sezioni seguenti
conservano l'esito dell'integrazione e della precedente APK `d29a45cf`.

## Stato e identità

Integrazione locale sul ramo `codex/community-reports-simplification`, autorizzata
dal proprietario dopo l'approvazione del pannello compatto. Nessun push, cambio
di main, deploy, generazione AAB, operazione Play o installazione sul telefono.

- Main invariato: `5a68de5dc1607105f921d4d2b731170f1a8a0446`.
- Merge Eventi: `6dff122d983220b67fe91908bfa512050ea598d0`.
- Candidata di codice: `d29a45cf4437e2a642457d009725ba068fa142f9`.
- Eventi include `f7fe8e9696f5b61a54fda27617ec99834993f8b4`, ramo
  `codex/events-card-quarantine`, oltre ai cinque commit precedenti di quel ramo
  non ancora presenti nella TEST. Confronto dei sorgenti `backend/app/events`
  rispetto a `f7fe8e96`: nessuna differenza.
- Riferimento letto: chat **Audita la ricerca eventi**,
  `01a10865-49e4-7460-912a-76acfeb58743`. Nessun messaggio inviato a quella chat.

Questa è una candidata per il collaudo. Le prove Android della nuova APK e i
due problemi delle fonti Eventi sotto descritti impediscono di dichiarare
completata la verifica per una promozione.

## Segnalazioni reali, UX approvata

Il pannello legge il database SQLite della Community TEST, conservato dai
collaudi precedenti. Non legge o modifica la Community di produzione e non
aggiunge righe di esempio. Anche `community-list-preview.html` avvia adesso
la vera app, senza dati fittizi.

- Pannello inizialmente compatto, altezza 216 px; prima scheda 60 px.
- «Recenti · Ultime 48 ore» resta sottile; premendo «Recenti» si alza la lista.
- Maniglia, tab Mappa/Segnalazioni/Webcam e pulsante Segnala mantenuti.
- Elenco unico dal più recente al più vecchio, entro 48 ore e nel raggio
  esistente di 30 km dal Comune selezionato. Scorrimento con caricamento
  automatico delle pagine successive, senza nuovo pulsante Storico.
- Le osservazioni attive conservano gruppi, dettaglio e azioni esistenti.
  Quelle passate sono righe individuali in sola lettura, mai punti sulla mappa
  e mai votabili. Lo stato cambia anche al decorrere della scadenza.
- Paginazione stabile per data e ID; annullamento delle richieste al cambio
  di Comune; deduplicazione; ripetizione della pagina in caso di errore.
- Le modifiche di presentazione sono limitate alla TEST locale e alla variante
  Android localpilot. La schermata pubblica non attiva questo percorso.

Le regole approvate in precedenza restano: intervallo minimo 3 minuti,
4 invii/ora e 12/giorno, nessun tetto giornaliero ai punti, un punto per stesso
autore/fenomeno/Comune ogni 3 ore dall'ultimo premio, GPS richiesto per i voti.
Questo intervento non cambia soglie, attribuzione dei premi o moderazione.

## Collaudo browser della candidata

Pilot canonico su porta 5174, browser integrato, viewport 588 × 902.
Servizi Community e frontend riavviati con il codice candidato; database
conservato. Un primo riavvio ha rifiutato una porta non ancora liberata: nessun
processo sconosciuto è stato terminato. Dopo aver verificato la porta libera,
il nuovo avvio è riuscito; pagina raggiungibile con HTTP 200.

| Scenario | Riscontro |
| --- | --- |
| Apertura Segnalazioni | PASS: pannello chiuso a 216 px, prima riga completa, pulsante Segnala visibile |
| Dati reali | PASS: 7 osservazioni nel database TEST della zona Pordenone, 5 scadute e 2 sostituite; corrispondenza tra API e lista |
| Apertura e scorrimento | PASS: «Recenti» espande la lista, fondo raggiunto, messaggio di fine storico visibile, nessun comando tagliato |
| Righe passate | PASS: sola lettura, nessuna azione Confermo/Non c'è più |
| Eventi candidato | PASS: richieste reali su 8784, pagine 0/100/200/300 sul medesimo snapshot, 317 record di catalogo entro 20 km |
| Eventi nell'interfaccia | PASS: 46 eventi di oggi, apertura del dettaglio TurismoFVG «Le Rose per il cambiamento climatico», filtro Convegni con 5 risultati |
| Origine Android | PASS HTTP: richiesta con Origin `http://localhost` accettata con header CORS corrispondente; non sostituisce una prova WebView |

Non inserite nuove segnalazioni o conferme durante questo collaudo. La
paginazione Community oltre 50 righe è verificata dai test automatici: i 7
record reali non sono sufficienti per esercitarla manualmente. Le prove
pregresse GPS/invio/punti sono conservate nei rispettivi resoconti e non
vengono presentate come rieseguite sulla nuova APK.

Evidenze versionate in
[evidence/community-events-test-2026-10-14](evidence/community-events-test-2026-10-14/SHA256SUMS.txt):
vista compatta, espansa e fondo lista, dettaglio Eventi, identità del backend,
riscontri HTTP e riepilogo controlli. Browser lasciato sulla lista compatta.

## Backend Eventi candidato e raccolta reale

La sola APK non verifica la correzione Eventi. È stato quindi avviato il backend
locale su `127.0.0.1:8784`, usando routing, filtri, dettaglio e paginazione del
codice candidato. Solo il caricamento del catalogo è sostituito con la lettura
di un file locale immutabile; il server non accede a Cloud Storage.

La raccolta ha letto i siti pubblici reali usando il codice integrato e una
copia locale del catalogo precedente. Scritture esclusivamente locali tramite
lo storage in memoria dell'audit; nessuna esecuzione dei job Cloud Run.

Catalogo finale dopo un solo tentativo mirato sulle fonti fallite:

- Snapshot UTC `2026-10-14T15:45:13.846290+00:00`.
- SHA-256 `5abc841b4108a8c6ec8193aa68bb5198b02585fa49d62274e28897d263417069`.
- File `.tmp/community-real-history-2026-10-14/events-catalog-retry.json`.
- Endpoint `/health`: commit `d29a45cf4437e2a642457d009725ba068fa142f9`,
  stesso hash, `published: false`.

**Esito complessivo parziale: 13 fonti pubblicabili, 2 respinte.**

| Fonte/caso | Esito |
| --- | --- |
| TurismoFVG | 1.264 eventi, 14 voci in revisione/quarantena; inventario completo, entro budget, nessun dettaglio pendente o ambiguo |
| Letture dettaglio TurismoFVG | 404 letture strutturate, 0 letture fallite, 0 quarantene dovute a errore di lettura nel ciclo reale |
| Azalea | FAIL: dopo il timeout iniziale, il tentativo mirato rileva `unrecognized Azalea archive cards` |
| Galleria Spazzapan | FAIL: `Spazzapan current_exhibitions inventory changed` anche nel tentativo mirato |

Le due fonti respinte rimangono escluse dai risultati pubblicabili: nessun
allentamento dei controlli per renderle verdi. La raccolta reale conferma il
percorso di lettura sano e la quarantena strutturale TurismoFVG; non ha
incontrato un guasto di trasporto isolato, coperto invece dai test automatici.
I monitor Attems/Giro/annuale già nel catalogo non sono stati rieseguiti in cloud.

## Verifiche automatiche

| Controllo | Esito |
| --- | --- |
| Suite frontend completa | 4.820 PASS, 13 FAIL iniziali, 13 saltati; 546 file |
| Ricontrollo frontend | 92 PASS su 8 file, compresi tutti i 6 file inizialmente falliti |
| Integrazione pannello | 43 PASS: compatto, espansione, dettagli attivi, storico in sola lettura, caricamento progressivo |
| Servizi e paginazione | 51 PASS su 4 file, compresi cursore e annullamento richieste |
| Suite backend completa | 1.844 PASS, 5 FAIL iniziali, 746 subtest PASS |
| Ricontrollo backend | 10 PASS nei 2 file inizialmente falliti |
| Guardie build locale | 27 PASS |
| Lint | PASS |
| Contratti R8 | PASS configurazione, mapping, simboli, metadati Capacitor e stack trace; keep rule troppo ampie assenti |
| Pulizia workspace e diff | PASS prima del nuovo baseline; diff senza errori di whitespace |

Le prime esecuzioni complete sono state eseguite in parallelo e hanno prodotto
timeout nei test sensibili ai tempi. Questi casi sono passati nei ricontrolli
con carico ridotto. Quattro asserzioni frontend ancora riferite alle vecchie
etichette/contatori Impostazioni sono state aggiornate alla UX già approvata
(Inviate, Confermate e Punti) e ricontrollate. Non si presenta l'esecuzione
completa iniziale come interamente verde né si sommano i ricontrolli ai test
unici della suite. Gli skip restano tali.

Log completi locali in `.tmp/community-real-history-2026-10-14/`:
`frontend-all.log`, `frontend-recheck.log`, `integration-tests.log`,
`services-final.log`, `backend-all.log`, `backend-recheck.log`,
`guards-final.log`, `lint-final.log`, `r8-contract.log`,
`events-collection.log`, `events-retry.log`, `android-build.log`.

## APK e controlli Android

- APK conservata: `.tmp/community-real-history-2026-10-14/meteofriul-community-events-test.apk`.
- SHA-256 `282d696e0629e1e011d8f1dc3d5d6e03b0bb634e9f51775bcbec8e08cc0cf3d2`.
- Package `com.meteofriul.app.localpilot`; variante localPilot, non minificata.
- Build nativa e guardie PASS, 170 task Gradle. Asset caricato da `index.html`:
  `assets/main-BJJhM0cl.js`, verificati indirizzi Community 8783 ed Eventi 8784,
  cursore storico e percorso UX della lista recente.
- Compilata con `build-android-local-weather-pilot.ps1 -CommunityPilot -EventsLocal`
  fuori dalla sandbox; nessun aggiornamento SDK, Gradle o dipendenze.
- Avvisi ancora presenti: dimensione chunk, repository `flatDir`, feature
  Gradle deprecate. Non sono attestazioni di risoluzione degli avvisi Play.

| Area obbligatoria | Valutazione su questa candidata |
| --- | --- |
| Edge-to-edge/inset/contrasto | Contratti automatici presenti nella suite e compilazione PASS; nuova matrice runtime Android 15/16 e precedente NON VERIFICATA |
| API barre deprecate | Nessun setter deprecato reintrodotto nei sorgenti applicativi; dipendenze e futuro esito Play non dichiarati risolti |
| Orientamento/schermi grandi | Policy esistente conservata: smartphone verticali, schermi >=600 dp e multi-window adattivi, nessun blocco globale nel manifest; nuova matrice runtime NON VERIFICATA |
| R8/risorse | Contratti PASS; runtime minificato NON VERIFICATO, perché questa APK non è minificata |

Resta aperto il riscontro sui tre tasti con sistema chiaro dell'immagine
Android 15 documentato nel [collaudo precedente](ANDROID_TEST_UI_FIXES_2026-10-13.md).
Le prove sul [Galaxy A52](COMMUNITY_REPORTS_PHONE_TEST_2026-10-13.md) riguardano
un'altra APK e non vengono trasferite a questa candidata.

La TEST richiede i servizi sul PC. Community: 8783; Eventi candidato: 8784;
meteo locale: 8781; meteo nazionale: 8782 quando disponibile. Per un futuro
collaudo Android autorizzato predisporre i relativi `adb reverse` prima
dell'installazione. La fixture meteo rimane il 4 settembre 2026 alle 12:00Z:
non rappresenta il meteo corrente e non è oggetto di questo collaudo.
In questa sessione Home e Previsioni mostrano «Meteo non disponibile» /
«Previsioni non disponibili»: è una limitazione del profilo meteo con fixture,
non un esito PASS sulle previsioni correnti.

## Ripresa locale

Avviare Eventi con `scripts/serve-local-events-candidate.py --catalog
.tmp/community-real-history-2026-10-14/events-catalog-retry.json`, con
`PYTHONPATH` impostato alla cartella `backend` del workspace e le variabili
di configurazione Eventi già usate dal progetto. Verificare `/health` e hash.

Prima del lanciatore canonico impostare
`VITE_LOCAL_EVENTS_PROXY_TARGET=http://127.0.0.1:8784`, poi eseguire
`scripts/start-local-weather-pilot.ps1 -CommunityPilot
-WeatherTestNow 2026-09-04T12:00:00Z`. Se il frontend è già attivo con un'altra
destinazione Eventi, richiederne il riavvio tramite il medesimo script.
Non fermare processi sconosciuti per liberare le porte.

## Riscontri invio/conferma e lista sentinelle — verifica successiva

Su richiesta del proprietario, mostrati i componenti attuali tramite la
modalità locale `communityReportQa=interactive`, con invio e voto in memoria.
Nessuna nuova osservazione o conferma salvata nel database TEST.

- Invio: ricevuta «Segnalazione inviata!», fenomeno, Comune, scadenza,
  identità e «Vedi sulla mappa».
- Conferma: la scheda resta aperta, il pulsante Confermo è selezionato e il
  conteggio aumenta (nell'esempio 4 → 5). Nessun popup separato.
- Il proprietario ha rilevato icone sovrapposte a «Sentinelle Meteo» aprendo
  l'elenco. La lista conservava `grid-column: 2` nella griglia compatta a una
  colonna, creando una colonna implicita e riducendo l'etichetta a 2 px.
- Corretto il solo posizionamento della lista nel layout pilot:
  `grid-column: 1 / -1`. Etichetta, icone/alias e lista occupano ora tre righe
  distinte. Nel browser a 588 × 902, etichetta larga 298 px e nessuna
  sovrapposizione; verificate apertura e richiusura, senza modificare la
  dimensione delle icone o la UX del pannello Recenti.
- Test esistenti `liveCss.test.js` e `TerritoryImmersiveMap.integration.test.jsx`:
  **101 PASS**. `git diff --check`: PASS.

Schermate dimostrative conservate nello stesso archivio delle evidenze:
`ricevuta-invio-demo.png` e `conferma-sentinelle-demo.png`. La ricevuta è stata
raggiunta anche tramite tastiera e mostra il relativo indicatore di focus.
Questa correzione CSS successiva è visibile nel browser TEST; l'APK identificata
sopra precede la correzione e non è stata ricompilata in questa verifica.

## Recenti: stato nella lista, riscontri nel dettaglio

Su richiesta del proprietario, la lista Recenti della TEST mostra soltanto
lo stato (Attiva, Scaduta, Sostituita, ecc.) sotto i dati della segnalazione.
I conteggi «Non c’è più» restano nel dettaglio, accanto al relativo pulsante:
nessuna modifica a voti, soglie o regole dei punti.

Rimossa la riga rossa che sporgeva dalle schede e la maggiorazione di altezza
del pannello compatto che serviva a ospitarla. Conservati espansione da
Recenti, maniglia di ridimensionamento e altezza compatta di 216 px.

Verifica browser a 588 × 902 nella modalità locale dimostrativa
`communityReportQa=interactive`: tutte le schede attive sono alte 60 px e
il testo rimane nei loro bordi; aprendo Vento forte sono visibili i 2 riscontri
«Non c’è più» del caso dimostrativo. Nessun nuovo invio o voto eseguito.
Schermate: `recenti-solo-stato-demo.png` e `riscontri-dettaglio-demo.png`
nell'archivio delle evidenze. Il test d'integrazione della lista verifica
anche che i riscontri assenti dall'elenco rimangano disponibili nel dettaglio.
`liveCss.test.js` e `TerritoryImmersiveMap.integration.test.jsx`: **101 PASS**.

Modifica solo nel ramo segnalazioni e nell'anteprima browser TEST; main e
produzione invariati. L'APK identificata sopra non contiene questa modifica
e non è stata ricompilata o installata in questa verifica.

## Storico: conteggio, tempo trascorso e dettaglio dei riscontri

La TEST ora mostra nelle voci archiviate il numero di segnalazioni e il tempo
trascorso dall'ultimo invio del riepilogo: minuti nella prima ora, poi ore
intere fino al limite delle 48 ore. Il tempo si aggiorna con l'orologio già
presente nella lista; la data esatta resta nel campo `time` e nel suo titolo.
Il pannello resta compatto, espandibile da Recenti e ridimensionabile.

Aprendo una voce storica compare una scheda con fenomeno, Comune, numero di
segnalazioni, tempo trascorso, stato, **Conferme** e **Non c'è più**. È in sola
lettura: l'unico pulsante è Chiudi. La chiusura ripristina la lista e il focus.
Il dettaglio delle segnalazioni ancora attive mantiene le azioni precedenti.

Il servizio locale espone i contatori già conservati nelle osservazioni.
La richiesta `grouped: true`, usata dalla lista TEST, raggruppa gli archivi
prima della paginazione: stesso episodio, gruppo e stato. Le osservazioni
ancora attive restano individuali nell'API, per essere riconciliate con la
mappa senza duplicati. Stati differenti restano distinti nello storico.
Il conteggio comprende solo le osservazioni ancora nella finestra di 48 ore.
Le conferme sono il totale del gruppo nell'ultimo snapshot pertinente, non
la somma delle copie salvate sulle singole osservazioni. Un nuovo episodio
nello stesso gruppo orario non eredita il riepilogo dell'episodio precedente.
I record preesistenti senza identificatore di episodio restano singoli:
non si ricostruiscono raggruppamenti incerti. Le risposte non espongono
identità delle installazioni o dei votanti; punti personali solo al titolare.

Verifiche:

- Frontend: 62 PASS su cinque file (lista, storico, integrazione, copy e hook).
- API/hook: 29 PASS su due file, incluso il parametro di raggruppamento;
  il file hook è ricontrollato, non conteggiato come copertura aggiuntiva unica.
- Backend: 45 PASS tra regole e SQLite, inclusi voti non duplicati, cambio da
  conferma a «Non c'è più», riuso del gruppo orario, gruppo con 55 osservazioni
  prima della paginazione, persistenza dopo riavvio e scadenza.
- Lint PASS; diff verificato localmente.
- Browser: dettaglio e lista a 588 × 902; controllo del dettaglio a larghezza
  360 px, senza overflow dei contatori, poi ripristino del viewport originale.
- Riavviata solo Community tramite il lanciatore canonico con
  `-CommunityPilot -RestartCommunity -WeatherTestNow 2026-09-04T12:00:00Z`.
  Meteo, frontend ed Eventi locali riutilizzati. Nessun servizio cloud mutato.

L'anteprima interattiva conserva i suoi esempi attivi in memoria; le sette
voci storiche verificate provengono dal database TEST esistente. La Grandine
archiviata mostrata nel dettaglio ha 1 conferma e 1 «Non c'è più» realmente
salvati nei collaudi precedenti. Nessun nuovo invio o voto effettuato per
questa verifica. Evidenze: `storico-conteggi-lista.png`,
`storico-conteggi-dettaglio.png` e `storico-conteggi-api.json` nello stesso
archivio. Log locali in `.tmp/community-history-counts-2026-10-14/`.

Modifica sul ramo segnalazioni, main invariato. Non ricompilata né installata
una nuova APK: i controlli Android della candidata restano quelli documentati
sopra, senza trasferire a questa modifica esiti runtime non eseguiti.

## Profilo nelle Opzioni: Sentinelle, alias e punti

La spiegazione esistente nel profilo è rinominata «Sentinelle, alias e punti».
Resta chiusa inizialmente e usa lo stesso controllo di espansione. Il testo
approvato spiega chi sono le Sentinelle Meteo, cosa rappresenta l'alias e come
leggere gli alias dalle icone nelle schede. Seguono le regole già presenti
di Inviate, Confermate e Punti, senza modificarne il contenuto. Aggiornata
anche la copia in friulano; nessun nuovo pulsante o cambiamento ai conteggi.

Verificati nel browser TEST lo stato iniziale chiuso, l'apertura e la
richiusura, e la leggibilità a 588 × 902. Evidenza:
`profilo-sentinelle-alias-punti.png` nello stesso archivio. Test esistenti
`SettingsPilotInteractions.test.jsx` e `SettingsView.test.jsx`: **59 PASS**;
ESLint sul componente e controllo del diff: PASS.

Modifica locale nel ramo segnalazioni. Main e produzione invariati; questa
verifica riguarda l'anteprima browser, senza ricompilazione o installazione APK.
