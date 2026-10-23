# Tentativo 0.1.15 / 300034 e preparazione 300035 — 23 ottobre 2026

**Seguito:** la [300035 è generata e verificata](ANDROID_0.1.15_300035_BUILD_20261023.md). Le sezioni sotto conservano lo stato e la diagnosi del tentativo 300034.

## Esito e autorizzazioni

Il tentativo 300034 ha compilato il bundle, ma il builder si è arrestato prima
del manifesto di rilascio per un filtro bundletool errato. Non è stato caricato,
installato o promosso. Il proprietario ha autorizzato esplicitamente l'abbandono
del 300034 e la generazione della **0.1.15 / 300035**, senza upload Play.
La riserva 300034 è conservata e l'abbandono è registrato append-only.
Il codice 300035 è configurato, non ancora riservato in questa fase.
Sponsor, pannello e sincronizzazione dei dati sponsor rimangono disattivati.

## GitHub e sorgenti

- Ramo `codex/release-0.1.15`, PR [#11](https://github.com/meteofriul/meteofriul-app/pull/11) in bozza.
- Sorgente del tentativo 300034: `5d6331aaf00dfc489b56a0fe71716c1cff7ee9a7`.
- CI [39914464091](https://github.com/meteofriul/meteofriul-app/actions/runs/39914464091): frontend, backend e contratti Windows PASS.
- Main non promosso. Il precedente candidato Web da `c30cfe33` conserva la stessa UI e versione visibile 0.1.15; il nuovo numero cambia solo la build Android.

## Tre arresti distinti

1. Prima della riserva: il set TTL non includeva il job avvisi distribuito il
   21 ottobre. Nuova attestazione immutabile, sorgenti e Cloud Build verificati,
   audit in sola lettura PASS. Nessun nuovo deploy. [Provenienza](evidence/release-0.1.15-300034-build-20261023/writer-attestation.json).
2. Prima della riserva: il comando usava la sorgente backend riscritta
   `599aea2f` anziché l'originale `e180b87a` già documentata per la 300033.
   Ricontrollati identità di 179 file/percorso/modo Git e ancestry della prova
   TTL. L'attestazione corretta era già presente; nessuna guardia modificata.
3. Dopo riserva e compilazione: `dump resources` richiede `--resource=xml/config`.
   Il filtro `--resource=com.meteofriul.app:xml/config` restituisce output vuoto
   anche con la risorsa presente. Il controllo ha quindi rifiutato il bundle.

## Correzione del controllo e prove

Il builder usa ora il formato type/name documentato nell'help di bundletool
1.18.3. Il validatore verifica separatamente l'unico package
`com.meteofriul.app`, il nome `xml/config`, il valore predefinito e l'esistenza
non vuota della risorsa nel ZIP. Non accetta dump vuoti, di altri package,
duplicati o privi del file. La fixture riproduce l'output del bundle reale.

- 43 asserzioni native PASS, inclusi i controlli negativi aggiunti.
- Contratti builder PASS; il sotto-test Gradle è esplicitamente saltato.
- Il Gradle effettivo del tentativo 300034 è riuscito: 294 task, 2m15s.
- Diagnostica sul bundle preservato: JSON Capacitor, registro plugin, risorsa
  Cordova e mapping R8 PASS; firma di ogni payload con certificato upload atteso.
- Il filtro corretto sul vecchio 300033 non trova `xml/config`: il keep mirato
  del nuovo pacchetto rimane necessario. Il vecchio artefatto resta invariato.

Il file diagnostico 300034 è conservato localmente sotto
`release-artifacts/android-play/pending-validation/300034/`, senza manifesto
di accettazione e senza poter riutilizzare il codice per una nuova build.
SHA256: `f903af5c19d315266f757293af80bb553d7f4f72fe031a4663e21728170c9b8c`.
[Esiti e hash](evidence/release-0.1.15-300034-build-20261023/bundle-diagnostic.json).

## Limiti

Nessuna prova browser, telefono o emulatore in questa attività. La presenza
nel bundle non chiude la verifica runtime di NATIVE-CONFIG-01, Posizione o
CAMS. Restano i quattro ambiti del runbook: inset Android 15/16, API deprecate,
tablet/multi-window e comportamento minificato. Nel log permane l'avviso della
dipendenza Capacitor PushNotificationsPlugin sulle API deprecate, oltre alle
funzionalità Gradle da migrare per Gradle 9; nessun aggiornamento toolchain qui.
Quattro librerie native transitive senza simboli di debug forniti: limite
registrato, non dichiarato risolto. R8 e shrinking restano attivi.

Prima della nuova build: commit, push e CI della guardia corretta. Poi builder
protetto, nuovo manifesto e verifiche sul file 300035. Upload Play personale,
installazione e promozione main richiedono i rispettivi passaggi autorizzati.
