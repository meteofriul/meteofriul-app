# Mercati: raggio e pannello in anteprima — 31 ottobre 2026

Il proprietario ha chiesto di proseguire il lavoro rimandando il salvataggio.
Modifiche nel working tree del ramo Mercati e del pannello: nessun nuovo commit,
push, merge a main o pubblicazione. Il coordinatore è l'unico editor dei file
condivisi coinvolti. [Hash e verifiche](evidence/MERCATI_ANTEPRIMA_RAGGIO_PANNELLO_20261031.json).

## Raggio condiviso integrato

Integrata la modifica del ramo `codex/events-markets-radius-settings-20261030`
(`f8c9ff5b`) sui sorgenti Mercati attuali. Risolte le sovrapposizioni in Eventi,
catalogo e test conservando il lettore dell'archivio gestito dal pannello.

- Un selettore in Impostazioni, da 5 a 50 km a passi di 5; default 20 km.
- Su richiesta successiva del proprietario, il raggio compare **soltanto nelle
  Impostazioni**: rimossi indicazione dei chilometri e collegamenti dedicati da
  Eventi e Mercati. Il valore scelto continua a filtrare Eventi, Mercati e
  l'anteprima della Home.
- Preferenza conservata alla riapertura, al cambio comune e allo svuotamento
  delle cache; cache Eventi e contatori distinti per raggio.
- La navigazione da un'edizione a Eventi usa il raggio corrente, senza
  ripristinare un vecchio valore dalla richiesta di navigazione.
- Corretto anche Home: l'anteprima Eventi usa la stessa preferenza. La località
  meteo rimane invariata; un cambio di raggio non riutilizza il vecchio stato
  degli eventi. Coperto da regressione del passaggio Home/Eventi/Home.
- Preservate sede per edizione, ritiro di un mercato e aggiornamenti del
  catalogo: il test integrato ora esercita insieme revisione remota e raggio.

Verifica dell'integrazione iniziale: **760 test in 67 file PASS**, comprendenti Home, routing,
Eventi, Mercati, Impostazioni, servizi e cache. Lint completo PASS. Build Web
di verifica in OS TEMP PASS (2130 moduli), service worker PASS (14 moduli)
e controllo standalone PASS. Nessuna dipendenza o versione modificata.
Avvisi di dimensione chunk e import misto Almanacco non bloccanti, già noti.

La correzione successiva «solo nelle Impostazioni» è stata verificata sui
sorgenti aggiornati: **760 test in 67 file PASS**, lint completo, nuova build
Web in OS TEMP, service worker e controllo standalone PASS. La navigazione
passa dall'accesso generale alle Impostazioni e la preferenza rimane attiva
al cambio comune, all'apertura di un'edizione e alla riapertura dell'app.
[Ricevuta della correzione con hash](evidence/MERCATI_RAGGIO_SOLO_IMPOSTAZIONI_20261031.json).
La ricevuta precedente resta la prova datata dell'integrazione iniziale;
non viene presentata come artefatto degli ultimi sorgenti.

## Pannello: bozze, ricerca e controlli più chiari

- Riepilogo separato di schede in archivio, pratiche e verifiche residue.
  I casi più completi non sono presentati come pronti alla pubblicazione.
- Ricerca per nome e comune anche nelle pratiche con revisione annidata;
  conteggi dei filtri dinamici e messaggio quando non ci sono risultati.
- Stato delle schede reso visibile, azione di apertura esplicita, riepilogo
  adattivo su schermi stretti. Fonti e dati documentati presentati con etichette
  leggibili al posto del JSON tecnico.
- Pubblicazione disattivata per default anche in sviluppo. Il comando non
  compare e il trasporto rifiuta l'operazione prima della rete. Il flag
  `VITE_MARKETS_PUBLICATION_ENABLED=true` resta una futura configurazione da
  non applicare senza approvazione esplicita.
- Salvataggio delle bozze disponibile. Gli errori di pubblicazione bloccata
  sono descritti come tali, senza presentarli come errori di rete.

**171 test in 29 file PASS**, lint completo e build di verifica PASS (1950
moduli). Applicati al pannello esterno dieci file con verifica degli hash
prima e dopo la copia, preservando eventuali modifiche concorrenti. Non
committati. Le compilazioni app e pannello non contengono il token locale.

## Servizi locali e archivio

Il pannello risponde su **http://127.0.0.1:5182/**. Il proxy amministrativo
raggiunge temporaneamente il servizio locale dedicato su **127.0.0.1:8003**,
indipendente dall'avvio meteo. La porta 8002 resta il default del proxy;
il helper imposta `MARKETS_LOCAL_API_TARGET` solo per questa anteprima.

Il servizio temporaneo usa lo SQLite esistente, richiede il token locale,
non espone il catalogo pubblico (404) e rifiuta la pubblicazione anche con
autenticazione valida (423). Accesso amministrativo anonimo rifiutato (401).
Le prove di rifiuto usano comandi vuoti, comunque invalidi: nessuna mutazione
dell'archivio è stata richiesta durante il controllo.

Verificati attraverso il proxy: revisione amministrativa **2**, revisione
pubblica **0**, 100 identità, 213 date e 59 pratiche. Il checksum del record
è identico alla copia prima dell'intervento: nessun contenuto modificato.
La credenziale continua a essere richiesta nel campo del pannello e rimane
nel file locale ignorato; non è stata memorizzata nel browser dall'agente.

Helper ignorati nel workspace: `.tmp/start-markets-drafts-20261031.ps1`,
`.tmp/start-markets-panel-20261031.ps1` e
`.tmp/markets-panel-20261030/local_api.py`. Sono strumenti temporanei per la
lavorazione locale, non servizi o pacchetti di distribuzione. Il riavvio del
pannello ha fermato solo il processo precedentemente avviato e verificato.

## Blocco dell'anteprima app e limiti visivi

Il launcher canonico pilota ha avviato i processi, poi li ha fermati durante
il controllo completo. Le prime risposte HTTP 200 non attestavano un avvio
completo. La diagnosi ha confrontato in sola lettura origine cloud e proxy:
entrambi restituiscono ICON `20261030T120000Z`, revisione 103, con
`usable_until=2026-10-31T12:00:00Z`, cioè **13:00 italiane del 31 ottobre**.
La verifica è avvenuta dopo questo termine.

Due tentativi, il secondo per osservare il proxy prima dell'arresto. Nessun
controllo allentato, orologio cambiato, fixture sostituita, job eseguito o
servizio cloud modificato. L'app sulla porta 5174 e l'API generale 8002 sono
rimaste ferme; il pannello usa il servizio separato 8003. Per riprendere la
prova pilota occorre verificare il recupero dei dati meteo o affrontare quel
problema con un incarico distinto, senza pubblicazioni implicite.

Il browser di controllo restituisce ancora `The browser access host is unavailable`
e l'interfaccia nativa segnala il pipe indisponibile. Nessuna verifica visiva
desktop o telefono dichiarata. I test DOM e le build non sostituiscono questa
revisione. Nessun APK/AAB generato o installato, nessun nuovo esito Safari/iPhone.

Restano da rivedere l'interfaccia effettiva e i contenuti destinati alla
pubblicazione: le 46 pratiche con limiti e anche i 13 casi più completi non
ricevono un'approvazione editoriale attraverso i test tecnici.
