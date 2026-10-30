# Mercati: attivazione del collegamento online

Il proprietario ha chiesto di riprendere il collegamento online il 30 ottobre.
Il coordinatore cura backend, configurazione del pannello, archivio e verifiche.
La pubblicazione editoriale delle 59 pratiche rimane separata.

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

- 38 test backend: archivio, API, provider Firestore, isolamento del servizio,
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
