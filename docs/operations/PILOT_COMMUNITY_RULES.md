# Segnalazioni della pilota: contratto delle operazioni

Ambito: esclusivamente la Community della pilota nazionale. Questo documento
descrive il contratto da verificare insieme al codice; non attesta una
pubblicazione o un'installazione Android. La versione beta non viene modificata.

## Regole per chi segnala

1. La località scelta determina la zona da consultare. Per inviare occorre un
   GPS recente e compatibile con il Comune dell'osservazione.
2. Le coordinate pubbliche sono un punto comunale approssimato. Il campione GPS
   preciso serve alla verifica e non entra nello storico persistente.
3. Una nuova osservazione dura 60 minuti. Il server determina tutti gli orari.
4. Tra osservazioni indipendenti devono passare almeno 2 minuti. Ogni
   installazione può creare al massimo 4 osservazioni negli ultimi 60 minuti
   e 12 nelle ultime 24 ore. Sono finestre mobili, non ore di calendario.
5. Può esistere una sola osservazione non scaduta per installazione, Comune e
   fenomeno. Fenomeni diversi possono coesistere. Il ritiro non restituisce
   quote già utilizzate.
6. **Aggiorna situazione** conferma che lo stesso fenomeno continua nello
   stesso Comune. Rinnova la visibilità per 60 minuti senza nuovi punti o
   consumo delle quote di creazione. Richiede GPS fresco compatibile con il
   Comune originale e non sposta il contributo.
7. **Correggi** permette, nei primi 5 minuti dalla creazione originale, di
   correggere tipo o Comune compatibile col GPS. Conserva contributo, data di
   creazione e scadenza; non assegna punti né consuma una quota di creazione.
   Le revisioni non cancellano smentite e moderazione e non riaprono la finestra
   di correzione.
8. **Ritira e sostituisci** ritira l'osservazione e apre il normale modulo per
   un nuovo invio esplicito. Concede una sola sostituzione senza l'attesa minima
   per quella sequenza. La sostitutiva consuma le quote 4/60 minuti e 12/24 ore
   e non genera un altro diritto alla sostituzione senza attesa.
9. **Ritira** rimuove il proprio contributo senza annullare quote, storia,
   smentite o protezioni anti-abuso. Le osservazioni degli altri restano.
10. Un'osservazione scaduta non può essere rinnovata, corretta o usata per
    ottenere una sostituzione senza attesa. Si può aprire un nuovo inserimento,
    che segue le regole ordinarie.
11. La presenza nei **Recenti** non rende aggiornabile un'osservazione scaduta
    e non la riattiva sulla mappa.
12. I 45 minuti non sono un blocco agli invii: riguardano esclusivamente
    l'attribuzione interna di reputazione/premi. Aggiornamento, correzione e
    sostituzione non sono scorciatoie per guadagnare punti.

## Invarianti del server

- Unicità, quote, titolarità, scadenza e revisione sono controllate nella
  transazione che accetta l'operazione. Le richieste simultanee non possono
  oltrepassare una quota o sostituire due volte la stessa osservazione.
- Alla scadenza (`ora server >= expires_at`) l'aggiornamento restituisce
  `community_observation_expired`. Non modifica contributo, revisione,
  scadenza, quote o reputazione. Restano le protezioni generali sulle richieste.
- I contributi respinti, cessati, nascosti o ritirati per smentite non possono
  essere riattivati tramite le azioni dell'autore. Le smentite non vengono
  cancellate cambiando revisione, ritirando o sostituendo.
- Ogni mutazione usa un identificativo dell'operazione legato all'autore e
  all'intento. Ripetere la stessa operazione restituisce l'esito già accettato;
  usare lo stesso identificativo per un intento diverso viene rifiutato.
- Una risposta persa non equivale a un rifiuto. L'app conserva l'operazione
  pendente e ne verifica l'esito prima di consentire un altro invio. La
  riapertura dell'app non invia automaticamente un nuovo contributo.
- Il diritto alla sostituzione è legato alla sequenza originale, all'autore e
  alla validità residua. Non è una deroga ai massimali e non si rigenera sul
  contributo sostitutivo. Il solo ritiro non crea questo diritto.
- I messaggi distinguono doppione, attesa minima, limite degli ultimi 60 minuti,
  limite delle ultime 24 ore, GPS incompatibile e stato non più modificabile.

## Persistenza e confine del collaudo

La persistenza locale della pilota deve salvare nella stessa transazione
osservazioni, revisioni, storico, quote, voti e smentite, moderazione, blocchi,
reputazione, operazioni accettate e diritti di sostituzione. Un errore di
scrittura deve rifiutare l'operazione senza successo apparente e senza
applicazione parziale. Un archivio corrotto non deve diventare un archivio vuoto.

L'archivio locale non rende il telefono indipendente dal PC. Il passaggio a
servizi HTTPS e storage cloud isolati richiederà un collaudo di equivalenza
transazionale; nessun deploy è implicito in questa modifica. Anche il collaudo
browser non attesta che l'APK sul telefono sia già aggiornato.

Lo storico privato delle revisioni e le risposte complete delle operazioni
hanno una conservazione di 48 ore, distinta dalla visibilità pubblica di un'ora.
Per un'operazione già accettata resta poi una ricevuta tecnica minima, senza
contenuto o alias: impedisce che un vecchio tentativo venga eseguito di nuovo
al ritorno della rete. Non prolunga la presenza del contributo nei Recenti o
sulla mappa. Le quote mantengono la propria finestra mobile e le protezioni
restano valide per i contributi a cui si applicano.

## Casi di accettazione

- Pioggia e vento dello stesso autore nello stesso Comune, con intervallo valido.
- Doppione Comune+fenomeno, quarta/quinta creazione, dodicesima/tredicesima,
  confini esatti delle finestre mobili e due richieste concorrenti.
- Correzione prima/dopo cinque minuti, collisione con un contributo esistente,
  GPS incompatibile, scadenza invariata e conservazione dello storico.
- Sostituzione usata una volta, abbandono e riapertura del modulo, replay della
  richiesta e tentativo di catena; quote piene non aggirabili.
- Timeout dopo l'accettazione di creazione, correzione, ritiro e sostituzione;
  riconciliazione e retry dello stesso ID senza doppioni.
- Rinnovo prima/alla/dopo scadenza, smentita prima/dopo rinnovo e tre smentite.
- Riavvio del servizio, conservazione di quote/smentite/ricevute e rifiuto delle
  mutazioni parziali in caso di errore del database.

I parametri 2 minuti, 4/60 minuti e 12/24 ore sono valori iniziali della pilota.
La loro efficacia d'uso deve essere osservata durante il collaudo.

## Verifica locale del 21 settembre 2026

- Backend: 181 test e 32 sottocasi superati fra Community pilota, persistenza,
  geografia e regressioni del servizio condiviso.
- Frontend: suite completa con 4.347 test superati e 13 esclusi; ulteriori
  verifiche mirate del recupero, del simulatore e dell'isolamento pilota.
- Launcher: contratto PowerShell superato; servizio locale verificato con
  `storage: sqlite`, regole v2 e intervallo minimo di 120 secondi.
- Browser: nello scenario di prova isolato, verificati invio, correzione senza
  duplicazione, sostituzione con secondo invio esplicito, assenza di una catena
  di sostituzioni e feedback di aggiornamento. Ripristinato poi il percorso
  normale `/?tab=live`.

I timeout e i riavvii sono coperti da test automatici, inclusa la chiusura
brutale del processo durante una transazione. Non è stato eseguito un nuovo
collaudo su Samsung: nessun APK è stato costruito o installato, né sono stati
eseguiti deploy o push. Le prove Android storiche non attestano queste regole.
