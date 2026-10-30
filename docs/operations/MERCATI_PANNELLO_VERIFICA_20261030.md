# Mercati: verifica del collegamento al pannello — 30 ottobre 2026

Verifica locale del workstream `codex/mercati-integration-20261028`, a partire
dal commit `c2d64db3`. Questa evidenza riguarda il codice modificato nel checkout,
non un servizio pubblicato né una release Android. I file di confine sono
identificati dagli hash nel [verbale JSON](evidence/MERCATI_PANNELLO_VERIFICA_20261030.json).

## Esito del flusso comune

È stata eseguita una prova attraverso tre implementazioni reali: gli helper
JavaScript del pannello preparano le pratiche; l'API FastAPI salva e pubblica in
un archivio SQLite temporaneo; il lettore JavaScript dell'app consuma i JSON
pubblicati da quell'API. Il test usa `TestClient`, senza avviare servizi o
scrivere su database remoti.

- Le 59 pratiche comprendono 13 casi più completi e 46 con verifiche residue.
  La preparazione completa di prova produce 100 identità uniche: 60 iniziali,
  19 aggiornamenti degli stessi ID e 40 nuove bozze. L'archivio iniziale fornito
  all'applicazione resta invece di 60 mercati con 59 pratiche separate.
- Salvataggio e pubblicazione delle sole bozze conservano le 53 schede e le
  161 date pubbliche iniziali. Le date totali nell'archivio sono 176; le 15
  delle identità escluse non diventano pubbliche.
- Spostare una singola edizione mantiene il suo ID, registra la data precedente
  e applica la sede specifica. Il client mostra una sola occorrenza, con la stessa
  data e sede nella scheda Mercati, in Eventi e nel collegamento a Maps.
- Sospensione, archiviazione e successivo ripristino producono nuove revisioni.
  Un riavvio del repository SQLite restituisce lo stesso snapshot pubblicato.
- La cache del client conserva la revisione più recente attraverso il riavvio
  e rifiuta una risposta precedente. Note editoriali e pratiche non sono presenti
  nei JSON pubblici.
- Un nuovo mercato creato tramite l'helper del pannello, completato e approvato
  nel test, passa dalle 53 alle 54 schede pubbliche e compare nel comune e nel
  giorno della settimana indicati. Questa aggiunta avviene soltanto nel database
  temporaneo della prova.

La prova trasversale comprende cinque flussi API e quattro test Vitest sul contenuto
realmente pubblicato. Non è una prova visuale nel browser.

### Ripetizione della prova trasversale

I quattro harness sono conservati in
[`evidence/mercati-panel-20261030/`](evidence/mercati-panel-20261030/).
Usano il pannello affiancato `PANNELLO INSERZIONI`; al generatore JavaScript si
può passare come primo argomento il percorso di un altro checkout del pannello.
Occorrono le dipendenze già preparate dai rispettivi lockfile. Non installano
pacchetti, non usano credenziali reali e non richiamano endpoint di rete.

Da PowerShell nella radice canonica, mantenendo la stessa sessione:

```powershell
$env:MF_MARKETS_QA_DIR = Join-Path $env:TEMP ('mf-markets-cross-' + [guid]::NewGuid().ToString('N'))
$qaNode = Join-Path $env:LOCALAPPDATA 'MeteoFriul/toolchains/node-v22.17.1-win-x64/node.exe'
$qaPython = Join-Path $env:LOCALAPPDATA 'Programs/Python/Python313/python.exe'
& $qaNode docs/operations/evidence/mercati-panel-20261030/panel-payload.mjs
Push-Location backend
& $qaPython -X utf8 ../docs/operations/evidence/mercati-panel-20261030/verify.py
Pop-Location
Push-Location frontend
& $qaNode node_modules/vitest/vitest.mjs run --configLoader native --config ../docs/operations/evidence/mercati-panel-20261030/vitest.config.mjs
Pop-Location
```

Fermarsi al primo esito diverso da zero. Gli output JSON rimangono nella
directory temporanea indicata da `MF_MARKETS_QA_DIR`; il database SQLite di
prova viene chiuso e rimosso dal relativo `TemporaryDirectory`.

## Difetti trovati e corretti durante il riesame

1. Il salvataggio dell'intero seed con le 59 pratiche cancellava il campo `id`
   prima di usarlo per recuperare l'evidenza immutabile: `KeyError` al primo
   salvataggio. Corretto e coperto dal round trip del seed completo e dalla
   preparazione di tutte le pratiche.
2. Un feed precedente poteva conservare giorno e orario di un mercato
   settimanale dopo una modifica dal pannello. Il calendario gestito ora governa
   giorni, orari e luogo; intervalli generici non generano nuove edizioni.
3. Dopo una modifica del comune, il vecchio feed poteva sfuggire al riconoscimento
   dell'identità. Gli alias esatti dei comuni precedenti vengono conservati e
   utilizzati per riconciliare l'evento, senza introdurre confronti approssimativi
   tra mercati di comuni diversi.

## Altre verifiche del workstream

- Backend: **68 test PASS**, di cui 30 Mercati e 38 regressioni
  Sponsor/Webcam/Firebase; `compileall` e controllo del diff superati. Esiti
  trasmessi dall'editor backend dopo le correzioni sopra.
- Pannello in staging: **163 test PASS**, lint e build Web superati secondo
  l'esecuzione finale del coordinatore, dopo l'allineamento del motivo minimo
  di tre caratteri e l'aggiunta del tipo di mercato modificabile. I 12 file
  consegnati al pannello esterno coincidono con quelli verificati per hash.
  La build non prova l'aspetto del form nel browser. Il ramo del pannello è
  `codex/markets-management-20261030`; le modifiche restano nel working tree
  insieme a quelle preesistenti, che non sono state incluse in un commit automatico.
- Raggio di ricerca: ramo distinto `codex/events-markets-radius-settings-20261030`,
  commit `f8c9ff5b`, **159 test PASS**, lint e build Web/service worker superati.
  Questi risultati non attestano un'integrazione dei due rami nel checkout corrente.
- Client Mercati: esecuzione finale aggregata di **196 test in 21 file PASS**,
  successiva alle correzioni del riesame. Lint completo dell'app superato.
  Build Web: 2.129 moduli, service worker: 14 moduli, controllo dello script
  autonomo superato; output in una directory temporanea del sistema.
- Servizi locali verificati dal coordinatore: app sulla porta `5174` e pannello
  sulla porta `5182` rispondono HTTP 200. L'app riceve schema 2, revisione 0,
  53 mercati e 161 date pubbliche; il proxy amministrativo del pannello riceve
  60 mercati, 176 date, 59 pratiche (13/46), storage SQLite e nessun errore di
  pubblicazione. È una verifica HTTP del collegamento, non una prova visuale.

Ambiente: Windows/PowerShell, Node `22.17.1`, Python `3.13`; Vite/Vitest caricati
con `--configLoader native`. Il percorso `backend/venv/Scripts/python.exe` non è
presente in questo checkout: la prova usa l'interprete Python 3.13 installato
localmente, come gli altri controlli backend di questo workstream.

## Limiti e controlli ancora aperti

- Il browser automatizzato ha restituito al coordinatore
  `The browser access host is unavailable`. Banner e form non hanno quindi
  una verifica visuale attestata da questa evidenza.
- Il provider Firestore è coperto da test con un client simulato, incluse
  revisioni a blocchi e recupero dopo risposta persa. Nessuna prova contro il
  database di produzione, assegnazione del claim `marketsAdmin`, bootstrap
  cloud o pubblicazione di servizi è stata eseguita.
- Il pannello richiede un endpoint di produzione esplicito; in sviluppo usa il
  proxy locale. L'autorizzazione Mercati resta distinta da Sponsor e Webcam.
- Nessun APK/AAB generato, installazione su telefono, prova Android, Safari su
  iPhone o Add to Home Screen. Web pubblico, Play e dati remoti restano invariati.
- Le verifiche residue delle 46 pratiche e quelle puntuali dei 13 casi più
  completi restano evidenza editoriale aperta: il collaudo tecnico non le risolve.
