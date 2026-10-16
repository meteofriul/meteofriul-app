# Piano di consegna delle allerte nazionali

Data: 2026-09-20  
Stato: decisione di prodotto approvata; progettazione e rollout ancora da eseguire  
Perimetro: allerte ufficiali in-app e push, bollettino OSMER, avvisi previsionali ICON

## Decisione

Meteo Friûl estenderà meteo e segnalazioni partecipative a tutta Italia, mantenendo
riconoscibile la propria origine friulana. Le allerte devono seguire la località meteo
attiva e non la sezione editoriale friulana.

Il prodotto distinguerà sempre quattro contenuti diversi:

1. **allerte ufficiali della località**, ricavate da fonti istituzionali e associate
   alla corretta zona di allerta;
2. **bollettino OSMER per il Friuli Venezia Giulia**, consultabile anche da fuori
   regione come contenuto informativo dichiaratamente regionale;
3. **avvisi previsionali Meteo Friûl**, eventualmente calcolati dai dati ICON e mai
   presentati come allerte ufficiali;
4. **segnalazioni della community**, che non costituiscono una fonte di allerta e non
   generano push nel perimetro di questo piano.

Il precalcolo nazionale ICON e la pipeline delle allerte restano indipendenti. Una
corsa ICON incompleta non deve bloccare un'allerta ufficiale; un problema nella fonte
ufficiale non deve essere mascherato da una previsione ICON.

Meteo Friûl non sostituisce IT-alert, i canali della Protezione Civile, le autorità
regionali o i comportamenti di autoprotezione indicati dalle istituzioni.

## Stato di partenza

### Pilota locale

La variante `localPilot` usata per lo sviluppo sul telefono non registra target FCM:

- il plugin push nativo è deliberatamente disattivato;
- non sono ricevute notifiche ufficiali o avvisi previsionali;
- le preferenze condivise visibili nell'interfaccia non equivalgono a un permesso del
  sistema operativo né a una registrazione server;
- i contenuti in-app possono essere verificati senza attivare consegne esterne.

Questa separazione deve rimanere invariata durante lo sviluppo nazionale. Nessun test
locale deve inviare notifiche reali per effetto collaterale.

### In-app corrente

Le allerte operative correnti sono regionali FVG. Il client le abilita insieme alla
capability OSMER e le conserva in una cache regionale FVG. Fuori FVG, la pagina
Bollettino viene sostituita dallo stato “allerte nazionali in preparazione”.

Il backend riconcilia fonti della Protezione Civile FVG e il riscontro ARPA/OSMER,
conserva lo stato confermato e non interpreta un errore di rete come “nessuna
allerta”. Questa prudenza deve essere mantenuta.

### Push Play corrente

La build Play abilitata può registrare un dispositivo Android soltanto dopo il
consenso alle notifiche e la verifica App Check. La consegna corrente:

- ammette soltanto un Comune canonico FVG;
- invia un'allerta regionale verificata, non verde e ancora valida;
- sceglie oggi un solo evento per l'intera regione, con precedenza alla severità
  maggiore e poi al più recente;
- non filtra ancora per le zone FVG-A, FVG-B, FVG-C e FVG-D;
- deduplica per firma, usa un outbox persistente e limita il TTL alla validità
  residua, con massimo sei ore;
- apre la sezione Bollettino al tocco.

Il job owner FVG è documentato con esecuzione bioraria. Prima di qualificare la
consegna come tempestiva deve essere misurata e approvata una frequenza più adatta;
la proposta iniziale è un controllo ogni 10–15 minuti, indipendente dalle corse ICON.

Dal 27 settembre 2026 la stessa consegna è disponibile anche nella Web App/PWA
ufficiale, con consenso esplicito del browser, App Check Web e FID Firebase. Il
canale Web conserva la stessa deduplica e apre la sezione Bollettino al tocco.

## Fonti ufficiali e autorità

### Copertura nazionale DPC

La prima copertura nazionale userà il Bollettino di criticità nazionale/allerta del
Dipartimento della Protezione Civile. La fonte ufficiale mette a disposizione dati
PDF, SHP, XML e un archivio pubblico. Le zone di allerta sono ambiti territoriali,
non semplici confini comunali. Il bollettino DPC è una sintesi nazionale delle
valutazioni dei Centri funzionali regionali: costituisce il piano comune di
copertura, non una fonte gerarchicamente superiore alle allerte regionali.

Riferimenti primari:

- [Bollettino di criticità e download dati](https://mappe.protezionecivile.gov.it/it/mappe-rischi/bollettino-di-criticita/index.html)
- [Zone di allerta meteo-idro](https://www.protezionecivile.gov.it/it/approfondimento/rischio-meteo-idro--le-zone-di-allerta/)
- [Archivio open data DPC](https://github.com/pcm-dpc/DPC-Bollettini-Criticita-Idrogeologica-Idraulica)

L'adapter deve conservare fonte, revisione, data di emissione, intervallo di validità,
giorno di previsione, tipo di rischio, livello, zona e URL del documento. SHP/XML e
metadati devono essere trattati come un unico snapshot versionato: non si pubblica un
insieme parziale come se fosse completo.

### Dettaglio FVG

In Friuli Venezia Giulia la fonte nazionale viene affiancata dal dettaglio regionale
già verificato. DPC e Protezione Civile FVG/ARPA OSMER restano layer distinti, con
autorità, validità e aggiornamenti propri. Lo stesso principio vale per ogni Regione:
un adapter regionale verificato può fornire il dettaglio ufficiale più specifico,
senza essere degradato a semplice arricchimento né sovrascrivere il record DPC.

Quando i due record descrivono lo stesso evento:

- l'interfaccia evita doppioni ma mostra chiaramente entrambe le provenienze;
- la consegna push produce una sola notifica per evento e zona;
- il dettaglio regionale può arricchire testo e zone, ma non riscrive la storia del
  record DPC;
- un disaccordo non viene risolto fondendo arbitrariamente livelli diversi: viene
  conservato come stato diagnostico e la consegna rimane fail-closed finché la regola
  di precedenza non è verificata.

### Bollettino OSMER fuori FVG

Il bollettino meteorologico OSMER potrà essere consultato anche quando la località
attiva è Urbino, Roma o Palermo, ma in una sezione separata e con un titolo stabile,
per esempio:

> Bollettino Friuli Venezia Giulia — OSMER

Questa sezione:

- non cambia città quando cambia la località meteo nazionale;
- non usa il nome della località attiva nel titolo o nei testi;
- non alimenta badge, stato di allerta o push della località nazionale;
- non viene presentata come previsione locale fuori FVG;
- può convivere con webcam e contenuti friulani dichiaratamente editoriali.

Un eventuale futuro abbonamento “Segui le allerte FVG” richiederà un secondo opt-in
esplicito e separato. Non è il comportamento predefinito di questo piano.

## Risoluzione geografica

Ogni località nazionale deve avere identità canonica sufficiente prima di abilitare
le allerte:

- codice ISTAT del Comune;
- codice regione e provincia, quando applicabili;
- coordinate pubbliche/canoniche;
- una o più `alertZoneIds` verificate e versionate;
- versione del catalogo geografico usato per la risoluzione.

Il solo nome della città non è mai sufficiente. Per Comuni che intersecano più zone,
il mapping comunale conserva tutte le zone pertinenti; una posizione GPS precisa può
identificare il punto e la zona specifica soltanto quando la geometria e l'accuratezza
lo consentono.

In caso di identità mancante, geometria ambigua o catalogo scaduto:

- l'app mostra “Zona di allerta non determinata”;
- non attribuisce un'allerta di un'altra zona;
- non invia push location-aware;
- non ripiega sul FVG, sul nome della città o sulla zona più vicina.

## Esperienza in-app di destinazione

La pagina Bollettino diventerà composita:

1. **Allerte per la località attiva** — DPC nazionale e, in FVG, dettaglio regionale;
2. **Previsione locale** — dati ICON nazionali quando disponibili;
3. **Radar nazionale DPC**;
4. **Bollettino Friuli Venezia Giulia — OSMER** — contenuto editoriale distinto.

Home mostra soltanto l'allerta pertinente alla località attiva. Il bollettino OSMER
fuori FVG resta raggiungibile, ma non occupa lo slot dell'allerta locale.

Il client richiede lo stato per `alertZoneIds`, non una risposta globale priva di
contesto. La cache viene indicizzata almeno per fonte, revisione e zona. Cambiare
località invalida la presentazione corrente senza cancellare le cache legittime di
altre zone.

Un record attivo può essere trattenuto in-app durante un errore temporaneo soltanto
entro la sua validità ufficiale, con fonte e ultimo aggiornamento visibili. Una
risposta vuota, stale o non autorevole non può cancellare un'allerta precedente.

## Consegna push nazionale

### Consenso e preferenze

Il default logico di una preferenza non concede il permesso del sistema operativo.
La registrazione avviene solo dopo un'azione dell'utente e il consenso OS.

Le preferenze minime restano separate:

- **Allerte ufficiali della località**;
- **Avvisi meteo Meteo Friûl**.

Disabilitandole entrambe, il client rimuove il target dal backend. La modifica della
località o delle preferenze provoca una nuova registrazione idempotente.

### Località manuale

Una località scelta manualmente è una sottoscrizione persistente e intenzionale. Le
allerte seguono quella località anche se il telefono si trova fisicamente altrove,
finché l'utente non la cambia. L'interfaccia deve dichiarare quale Comune e quali
zone sono seguiti.

### Posizione automatica

La posizione automatica aggiorna il target soltanto con:

- consenso esplicito alla localizzazione;
- consenso separato alla localizzazione in background, se usata ad app chiusa;
- prova recente e sufficientemente precisa;
- risoluzione server-side verso identità e zona canoniche.

Le coordinate grezze servono a risolvere il target ma non vengono conservate nel
profilo push. Se il permesso background manca, il sistema non finge un inseguimento
in tempo reale: resta sulla località dichiarata nell'interfaccia finché l'app non può
aggiornarla legittimamente.

### Selezione e invio

Per ogni nuova revisione ufficiale, il dispatcher:

1. verifica firma/identità della fonte, freschezza e validità;
2. calcola le zone interessate;
3. seleziona esclusivamente dispositivi opt-in con zona compatibile;
4. ricontrolla transazionalmente target, preferenza, versione ed enrollment;
5. deduplica per dispositivo, fonte, revisione, evento e zona;
6. limita il TTL alla validità residua;
7. invia un deep link alla scheda della località e dell'allerta corretta.

Uno stato verde o una cessazione aggiorna l'in-app soltanto dopo una lettura fresca e
autorevole. Non genera automaticamente una notifica di “fine allerta” nella prima
versione. Retry, lease e outbox rimangono bounded; una fonte non verificata non può
produrre una notifica.

## Avvisi previsionali ICON

Gli avvisi calcolati dal modello nazionale sono un prodotto diverso dalle allerte
ufficiali. Possono riguardare pioggia intensa, temporali, vento, neve, ghiaccio o
caldo, ma devono:

- usare il canale Android a priorità inferiore dedicato agli avvisi meteo;
- avere un opt-in indipendente;
- dichiarare sempre “previsione Meteo Friûl” e la corsa ICON usata;
- conservare soglie, finestra temporale e probabilità verificabili;
- essere deduplicati per corsa, cella geografica e fenomeno;
- non usare nei testi le parole “allerta ufficiale” o attribuzioni DPC/OSMER;
- spegnersi fail-closed se il blocco nazionale è incompleto, non verificato o stale.

Il percorso attuale degli avvisi locali usa Open-Meteo ed è limitato al sistema FVG
condiviso. Non va esteso implicitamente: deve essere sostituito o migrato in modo
esplicito alla pipeline ICON nazionale prima dell'attivazione.

## Fail-closed e osservabilità

Sono bloccanti per una nuova consegna push:

- snapshot parziale o non atomico;
- fonte, revisione o validità mancanti;
- mapping zona assente o ambiguo;
- dato stale oltre la soglia approvata;
- discordanza non risolta tra fonti;
- preferenza disabilitata o permesso revocato;
- località cambiata durante il calcolo;
- versione app, App Check o enrollment non ammessi;
- outbox o persistenza non disponibili.

Ogni job produce metriche separate per acquisizione, parsing, pubblicazione, zone
risolte, dispositivi eleggibili, deduplicati, inviati e falliti. Gli audit non devono
contenere token FCM, installation ID, coordinate precise o dati personali.

La frequenza del job allerte è indipendente da quella ICON. Prima dell'attivazione
nazionale vanno misurate latenza di pubblicazione della fonte, latenza end-to-end,
revisioni tardive, errata corrige e comportamento durante un'interruzione.

## Fasi di implementazione

### Fase A — Contratti e fixture

- definire il record ufficiale nazionale e la chiave di revisione;
- acquisire fixture DPC per verde, giallo, arancione, rosso, aggiornamento, errata
  corrige, valutazione non trasmessa e payload incompleto;
- definire il catalogo versionato Comune/coordinate → `alertZoneIds`;
- separare nelle capability `officialAlerts` da `osmer`.

Uscita: nessuna UI o push; parser e policy pure con test deterministici.

### Fase B — Acquisizione DPC in ombra

- implementare adapter SHP/XML e snapshot atomico;
- conservare revisioni e diagnostica senza pubblicare nell'app;
- confrontare per almeno due settimane output, orari, aggiornamenti ed errata
  corrige con la fonte ufficiale;
- misurare la frequenza di polling senza dipendere da richieste utente.

Uscita: report di copertura completo e zero mutazioni client.

### Fase C — Resolver nazionale

- costruire mapping di tutti i Comuni italiani verso una o più zone;
- verificare campioni di confine e Comuni multi-zona;
- integrare reverse geocoding e posizione background senza conservare coordinate raw;
- introdurre endpoint location-aware in modalità shadow.

Uscita: ogni località pubblicabile ha identità e zona verificabili.

### Fase D — In-app

- attivare prima le allerte DPC per la località nazionale;
- mantenere il dettaglio FVG quando pertinente;
- mostrare OSMER fuori FVG nella sezione editoriale separata;
- validare transizioni località FVG ↔ nazionale, cache e risposte tardive.

Uscita: nessun push nazionale; dati visibili e attribuiti correttamente.

### Fase E — Push dry-run Play

- estendere la registrazione al Comune e alle zone nazionali canoniche;
- eseguire il dispatcher senza FCM, confrontando destinatari attesi e reali;
- verificare manuale, GPS foreground/background, revoca permessi e cambio zona;
- correggere il deep link degli avvisi locali prima del rollout.

Uscita: zero destinatari fuori zona e nessuna duplicazione DPC/FVG.

### Fase F — Coorte controllata e attivazione

- abilitare una piccola coorte Play con rollback;
- verificare dispositivo reale, app chiusa, doze, riavvio, token ruotato e tap;
- osservare almeno un ciclo con stato attivo e uno con cessazione autorevole;
- ampliare soltanto dopo audit dei log privi di dati sensibili.

Uscita: consegna nazionale attiva con evidenza append-only e monitoraggio.

### Fase G — Avvisi ICON

- attivare soltanto dopo la stabilità delle allerte ufficiali;
- calibrare soglie su dati storici e falsi positivi;
- avviare in shadow, poi dry-run e infine coorte separata.

## Matrice minima dei test

| Area | Casi obbligatori |
| --- | --- |
| Sorgente DPC | snapshot completo/parziale, revisione, aggiornamento, errata corrige, timeout, XML/SHP discordanti |
| Zone | Comune singolo, multi-zona, confine, coordinate ambigue, catalogo scaduto, omonimi |
| In-app | FVG, Urbino, Roma, Palermo, cambio rapido di località, cache precedente, risposta tardiva |
| OSMER | locale FVG, consultazione fuori FVG, etichetta regionale, assenza di badge/push nazionale |
| Push | opt-in/out, permesso negato/revocato, manuale, GPS recente/stale, background, token ruotato |
| Dispatch | filtro per zona, deduplica DPC/FVG, validità, TTL, retry, outbox indisponibile |
| ICON | blocco incompleto, corsa stale, cella errata, soglia, deduplica, copy non ufficiale |
| Privacy | nessuna coordinata raw nel profilo, log senza token/ID, cancellazione target |

I test principali da estendere comprendono:

- backend: policy territoriale, location service/API, adapter DPC, resolver zone,
  weather API, push service/API, sync ufficiale e local notice;
- frontend: product scope, routing Bollettino, wiring allerte, impostazioni,
  registrazione push, cache/runtime allerte, deep link e background location.

## Avanzamento implementativo

- 25 settembre 2026: introdotto il parser puro del CAP DPC e il contratto
  `meteofriul.official_alert_zones.v1`. Il CAP conserva zona, rischio, livello e
  validità, ma non può confermare come verdi le zone omesse senza lo SHP della stessa
  revisione. Gli identificativi DPC `Friu-A` ... `Friu-D` sono gli unici alias
  cross-source già approvati verso `FVG-A` ... `FVG-D`. Nessun percorso UI, cache o
  push FVG è stato modificato in questa fase.
- 25 settembre 2026: aggiunto il parser completo dei DBF `today`/`tomorrow` inclusi
  nello ZIP SHP DPC e la riconciliazione fail-closed con il CAP della stessa
  revisione. Solo lo snapshot riconciliato può confermare uno stato verde; identità,
  rischio, livello o copertura discordanti bloccano la pubblicazione. La geometria
  non è ancora usata per associare Comuni o GPS e nessun runtime FVG è stato
  collegato a questo contratto.
- 25 settembre 2026: aggiunto il builder offline e create-only del catalogo
  Comune → zone. L'overlay usa i confini comunali ISTAT non generalizzati e conserva
  tutte le intersezioni positive, separando l'eventuale zona del punto pubblico. Il
  prefisso regionale DPC è un secondo vincolo obbligatorio per impedire che minime
  differenze di confine attribuiscano, per esempio, una zona veneta a un Comune FVG.
  L'audit reale copre 7.894 Comuni e mantiene i 215 Comuni FVG esclusivamente nelle
  zone `FVG-A` ... `FVG-D`. Il catalogo generato è versionato, firmato con digest e
  letto da un resolver ISTAT fail-closed; non è ancora collegato alle API, alla UI o
  al dispatcher push FVG.
- 26 settembre 2026: aggiunta la proiezione pura di uno snapshot nazionale
  riconciliato per codice ISTAT. I Comuni multizona conservano ogni zona e il livello
  visuale è quello più cautelativo, senza perdere i rischi distinti. In FVG la
  proiezione DPC dichiara obbligatorio il dettaglio regionale e vieta l'uso standalone:
  non può quindi sostituire accidentalmente il contratto FVG corrente. Nessun endpoint
  o invio push è stato attivato in questa fase.
- 26 settembre 2026: aggiunto l'acquisitore atomico della pagina DPC e degli asset
  ufficiali XML/SHP. Accetta soltanto URL HTTPS esatti nel repository DPC, pretende la
  stessa revisione nei due ZIP, applica limiti dimensionali e riconcilia CAP e DBF
  prima di restituire lo snapshot. Verifica reale: revisione `20260926_1442`, 187
  zone e 1.122 stati coerenti. Non è ancora schedulato né collegato al repository FVG.
- 26 settembre 2026: aggiunti stato e persistenza nazionali nella collection separata
  `national_official_alert_snapshots`. La scrittura richiede una lettura Firestore
  autorevole, rifiuta rollback e conflitti nella stessa revisione; le letture utente
  non interrogano mai la fonte DPC. La collection regionale
  `official_alert_snapshots` e il relativo servizio FVG restano invariati.
- 26 settembre 2026: aggiunto il job applicativo nazionale. Accetta come successo una
  nuova revisione salvata in Firestore o un no-op sulla stessa revisione già
  persistita; rollback, conflitti, sorgente incompleta e memoria-only in Cloud sono
  fallimenti. Il job dichiara e mantiene il push disabilitato per costruzione e non è
  ancora stato creato o schedulato in Cloud Run.
- 26 settembre 2026: aggiunto l'endpoint read-only separato
  `/api/weather/official-alerts/national?municipality_istat=...`. Legge soltanto lo
  snapshot persistito e non effettua fetch on-demand. L'endpoint regionale storico
  `/api/weather/official-alerts` non è cambiato; in FVG la risposta nazionale conserva
  il blocco `standalone_display_allowed: false` finché manca la riconciliazione con il
  dettaglio regionale.
- 26 settembre 2026: collegata la sezione Bollettino nazionale fuori FVG mediante il
  solo codice ISTAT esatto. Vista, API client e cache sono separati dal runtime
  regionale; un payload FVG con `standalone_display_allowed: false`, una località
  diversa o un contratto scaduto vengono rifiutati. I Comuni multizona mostrano tutte
  le zone e spiegano l'uso del livello più cautelativo. Il ramo FVG continua a montare
  esclusivamente il bollettino OSMER e le impostazioni push non sono state estese.
- 8 ottobre 2026: iniziato un sottoinsieme della fase E, limitato alla località
  scelta manualmente e alle installazioni Android Play dalla versioneCode 300029 in
  avanti. Un valutatore separato incrocia lo snapshot DPC persistito e riconciliato,
  il Comune ISTAT canonico fuori FVG, il catalogo zone e le preferenze del dispositivo.
  Il job di audit ammette soltanto `PUSH_MODE=dry_run`, legge Firestore e restituisce
  conteggi aggregati senza token, ID o coordinate: non scrive outbox e non chiama FCM.
  `candidate_records` conta i record zona/rischio/giorno attivi proiettati, non il
  numero di notifiche da inviare. Nessun job Cloud o Scheduler e nessuna API live sono
  stati collegati a questo valutatore. Restano fuori da questa prima tranche il GPS,
  la policy di raggruppamento e deduplica di un evento multi-zona, il deep link, la
  prova su dispositivo e l'autorizzazione separata alla consegna reale.
- 8 ottobre 2026: preparato **solo nel ramo `codex/national-locality-alerts`** un
  mittente nazionale separato, ancora non distribuito né schedulato. Usa lo stesso
  validatore dello snapshot persistito, un outbox dedicato
  `push_national_alert_outbox`, un canale Android distinto e una notifica per Comune
  e giorno di previsione. La firma di deduplica dipende da Comune, giorno e record
  zona/rischio/livello, non dalla revisione di acquisizione: una nuova revisione
  senza cambiamenti per il Comune non rinvia l'avviso. Un esito FCM sconosciuto
  dopo la claim non è ritentato automaticamente, per non duplicare un'allerta.
  La nuova policy ammette solo Android Play con Comune selezionato manualmente,
  consenso alle allerte, App Check/enrollment verificati e versionCode **300030 o
  successivo**. FVG, Web/PWA, versioni precedenti e GPS sono esclusi. Il tap apre il
  Bollettino soltanto se il Comune attivo coincide ancora con quello notificato.

### Gate per il mittente nazionale preparato

Il nuovo entrypoint è `python -m app.jobs.send_national_official_alerts`. Senza
configurazione `NATIONAL_OFFICIAL_ALERTS_PUSH_MODE` è `off`: non legge dispositivi,
non scrive e non invia. `dry_run` legge lo snapshot persistito e restituisce solo
conteggi; `send` richiede anche `NATIONAL_OFFICIAL_ALERTS_SEND_GATE=confirmed`,
`NATIONAL_OFFICIAL_ALERTS_SEND_MAX_DEVICES` (1–5000) e
`NATIONAL_OFFICIAL_ALERTS_MIN_VERSION_CODE` (almeno 300030 e non inferiore alla
policy Play corrente). In `send`, superare il limite di dispositivi candidati
blocca l'intera corsa **prima** di scrivere l'outbox. Gli altri parametri Play
(generation, App Check e paginazione) sono quelli già validati da
`PushPilotConfig`. Il job non va agganciato al sync DPC esistente o ai job FVG.

Prima di distribuire o schedulare: CI verde, audit del diff e della configurazione
Cloud Run/Scheduler, dry-run su snapshot reale, prova del client Play 300030+ su
telefono con consenso esplicito, controllo di revoca/cambio Comune e approvazione
specifica del proprietario per ogni passaggio live. Questa preparazione **non**
autorizza deploy, invii, build AAB, caricamento Play o merge.

## Vincoli di rilascio

- backend e catalogo zone vanno distribuiti e verificati prima dei client;
- il client precedente deve continuare a ricevere soltanto il contratto FVG che sa
  interpretare;
- nessuna attivazione nazionale parte da una richiesta dell'utente o da una corsa
  ICON;
- nessun deploy, push FCM o modifica della beta è autorizzato da questo documento;
- ogni passaggio `shadow → dry-run → send` richiede evidenza e approvazione separate.
