# Mercati: attivazione del collegamento online

**Stato corrente: attivazione online sospesa per indicazione del proprietario.**
Il coordinatore aveva interpretato la richiesta di riprendere i Mercati,
insieme alle precedenti richieste di collegamento online, come via libera
all'attivazione. Il proprietario ha chiarito «non ancora se compare online»
e ha rifiutato il comando di distribuzione prima della sua esecuzione.
Il lavoro prosegue in anteprima locale; nessuna operazione di attivazione
online deve ripartire senza una nuova indicazione esplicita.

La preparazione tecnica già eseguita non equivale alla pubblicazione.
Il coordinatore conserva la responsabilità di backend, configurazione del
pannello, archivio e verifiche. La pubblicazione editoriale delle 59 pratiche
rimane separata anche da un'eventuale futura attivazione del servizio.

Il proprietario ha successivamente ammesso la possibilità di collegare il solo
pannello mantenendo i Mercati disattivati nell'app, poi ha precisato il vincolo
definitivo: **nessuna pubblicazione automatica; prima interfaccia pronta, dati
destinati alla pubblicazione completi e revisione del risultato da parte sua**.
Questo vale anche per pannello e servizio. La precedente apertura al solo
pannello non è un'autorizzazione a distribuirlo senza questa revisione.
Non sono seguite altre operazioni cloud.

## Blocco locale per il futuro collegamento del solo pannello

Il servizio ora usa `MARKETS_PUBLIC_CATALOGUE_ENABLED=false` per impostazione
predefinita. Il catalogo pubblico non viene esposto (404); una pubblicazione
amministrativa è rifiutata (423), anche con un account autorizzato, prima di
leggere o modificare l'archivio. Lettura e salvataggio delle bozze restano
disponibili per gli amministratori. CORS accetta soltanto il pannello in questa
modalità; origini dell'app escluse. Le API generali dell'anteprima locale restano
invariate.

Verifica corrente: **40 test backend superati**, compresi il comportamento
predefinito a catalogo spento, il blocco della pubblicazione, l'autenticazione e
la lettura amministrativa. Il blocco operativo locale è stato verificato:
interrompe lo script prima di autenticazione, rete o mutazioni.
Questa protezione è soltanto nei sorgenti locali: l'immagine conservata sotto
precede il blocco e **non è una candidata valida per il nuovo perimetro**.
Nessuna nuova build cloud o distribuzione è stata avviata.

La disponibilità per una pubblicazione non è attestata: revisione visiva
completa ancora aperta; 46 pratiche mantengono verifiche residue e tutte le 59
richiedono approvazione editoriale prima di entrare nel catalogo per gli utenti.

## Punto di arresto verificato

- Build cloud riuscita: `04afca0c-4927-409d-814c-91dec56a8d50`, sorgente
  `1c2155413e4b9b2811a97e7d1be3165d94f7cc18`.
  Immagine conservata, non distribuita:
  `europe-west1-docker.pkg.dev/meteo-friul/meteofriul/markets@sha256:215ed7955d4d0a846159d846baca7949fd1beeb5907a1361d2b4db0f43387a36`.
- Identità runtime dedicata e ruolo con cinque permessi predisposti:
  `datastore.databases.get`, `datastore.entities.create`,
  `datastore.entities.get`, `datastore.entities.update`,
  `firebaseauth.users.get`. Nessun permesso di eliminazione.
- Firestore inizializzato il 30 ottobre alle 22:04:39 UTC: revisione
  amministrativa 0 e revisione pubblica interna 0, 60 identità e 59 pratiche
  del seed. La proiezione interna contiene 53 schede e 161 date, ma non è
  stata esposta da un servizio Mercati. Le regole client negano l'accesso.
- **Non eseguiti:** distribuzione Cloud Run, attribuzione `marketsAdmin`
  all'operatore, trasferimento del lotto locale preparato, aggiornamento del
  pannello Hosting, collegamento dell'app pubblica, nuove release Web/Android.
- Il lotto locale rimane alla revisione amministrativa 1 con 100 identità,
  213 date e 59 pratiche preparate (13/46); non è stato copiato sul cloud.
  Nessuna nuova scheda approvata o pubblicata.
- Nessuna promozione a main. Le risorse cloud già predisposte sono conservate;
  non è stato eseguito un rollback o una cancellazione implicita.

Il comando `operate.py deploy` è stato respinto prima di avviare il processo;
non è un tentativo di distribuzione fallito dopo aver modificato il servizio.
Gli script operativi locali hanno un blocco esplicito della ripresa.
Per un'eventuale ripresa autorizzata occorre prima rileggere lo stato remoto:
il bootstrap è già avvenuto e non deve essere ripetuto.

## Stato prima dell'intervento

Verifica remota in sola lettura sul progetto `meteo-friul` (`49007668366`):
nessun servizio Mercati, nessun puntatore `markets_archive/current` e nessun
claim `marketsAdmin` sull'account amministrativo atteso. I permessi Sponsor
e Webcam esistono gia. Le regole Firestore negano ogni accesso client diretto.
Il pannello Hosting `meteofriul-inserzioni` ha una release dell'11 ottobre;
il Centro di gestione e l'editor Mercati sono presenti nel lavoro locale.

## Perimetro

- Servizio Cloud Run dedicato `meteofriul-markets`, regione `europe-west1`.
  Espone solo catalogo e amministrazione Mercati, con autenticazione Firebase.
- Identita runtime dedicata; lettura, creazione e aggiornamento Firestore e
  verifica dell'account Firebase, senza autorizzazione a eliminare i dati.
- Archivio unico `markets_archive`, con inizializzazione create-only dal seed
  verificato e successivo trasferimento delle 59 bozze locali tramite API.
- Stesso operatore del pannello, con aggiunta di `marketsAdmin` conservando
  integralmente i claim precedenti. Nessun token locale distribuito.
- Pannello collegato all'endpoint HTTPS esplicito; Sponsor e Webcam conservano
  endpoint, dati, permessi e comportamento esistenti.
- Le 53 schede e le 161 date pubbliche iniziali rimangono invariate. Le 59
  pratiche (13 piu complete, 46 con limiti) restano bozze non approvate.

Il client dell'app supporta `VITE_MARKETS_API_BASE`, separato dalle altre API.
L'attivazione del servizio e del pannello non distribuisce automaticamente
questa integrazione nella Web pubblica o in Android. Versioni, APK/AAB, Play
e promozione a main rimangono fuori da questo passaggio.

## Preparazione verificata

- 40 test backend: archivio, API, provider Firestore, isolamento del servizio,
  CORS, autorizzazione e infrastruttura Firebase.
- 8 test del lettore Mercati, inclusa la base separata e il rifiuto di URL
  senza HTTPS, con credenziali, query o percorsi errati.
- ESLint dei file frontend modificati, compileall e controllo diff superati.
- Il packaging legge un commit pulito e include soltanto i file esplicitamente
  elencati. La build cloud ripete i test del contratto nel container.

Questa sezione registra la preparazione prima delle operazioni remote.
L'esito di distribuzione e migrazione deve essere registrato separatamente,
con digest immutabile, revisione del servizio, revisioni dati e rollback.
Le evidenze locali di lavoro sono in `.tmp/markets-online-20261030/`.

### Prima build nel container

La build `86439df4-a991-4fe3-a66d-76b2633271de` si e fermata nei test:
mancava `app_check.py`, importato dalla regressione Firebase, e l'hash di una
fonte conservava i fine riga Windows. Aggiunto il modulo all'elenco del contesto
e normalizzato il calcolo degli hash a LF, come previsto da `.gitattributes`.
Una regressione confronta lo stesso seed generato da fonti LF e CRLF.
La rigenerazione cambia soltanto la provenienza del seed, senza cambiare le
60 identita, le 176 date o le 59 pratiche. Nessun servizio o dato remoto
e stato attivato dalla build fallita.
