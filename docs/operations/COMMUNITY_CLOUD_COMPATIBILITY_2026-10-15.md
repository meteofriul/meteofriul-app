# Segnalazioni: compatibilità e preparazione Cloud Run

> Resoconto storico del 15 ottobre 2026. Il contenuto è stato recuperato il
> 16 ottobre su `codex/community-compatibility-clean`, dalla nuova `main`,
> senza importare la cronologia precedente. Le revisioni cloud e le evidenze
> Android sotto riportate non sono state ricontrollate durante il recupero.
> Per i test ripetuti sulla nuova base vedere
> [il verbale del recupero](COMMUNITY_COMPATIBILITY_RECOVERY_2026-10-16.txt).

## Ambito

Richiesta: sistemare la compatibilità con l'app pubblicata e preparare il
rilascio backend. Ramo `codex/community-cloud-compatibility`, da main locale
`29357c3afcca083bada6c3ab4cb7c0e03f8b6817`. Main resta fermo. GitHub è consentito
in lettura, ma non è stato necessario consultarlo; nessun push o CI remota.
Nessuna AAB, installazione APK, pubblicazione Play, build cloud o distribuzione.

## Baseline verificata

- APK ufficiale letta dal Galaxy A52: `com.meteofriul.app`, 0.1.14 / 300031,
  installer `com.android.vending`, aggiornamento 12 ottobre 2026 alle 18:08:56.
  SHA-256 `2dc09e3b85ade5caaeb84354eccf37458f3b05539df53026af82adcb543dada2`.
- Bundle JS `main-DeYBVl6h.js`, SHA-256
  `982bd93a0b14ce47c22f70b83bd0b08ba20fe33d6fd9039308510f27aacd574e`.
  La conferma invia soltanto `accepted_terms`, `client_id`, `policy_version`,
  `vote`. Sono ancora presenti PATCH, correzione e ritiro/sostituzione con
  identificativo operazione e revisione. Nessun header di protocollo.
- API pubblica: `https://meteofriul-community-49007668366.europe-west1.run.app/api`;
  contratto `community-pilot-national-safety-v2`, intervallo 120 secondi,
  quote 4/ora e 12/giorno, correzione 300 secondi. Questi sono i valori della
  versione attualmente pubblicata, non quelli nuovi approvati.
- Cloud Run: progetto `meteo-friul`, regione `europe-west1`, servizio
  `meteofriul-community`, revisione `meteofriul-community-00002-tt2`, traffico
  100%. Immagine immutabile:
  `europe-west1-docker.pkg.dev/meteo-friul/meteofriul/community@sha256:6b1476afcf5d9f2633d54231d3ceca192b4027ad6afb9e37552fcc80f1cf2fb6`.
- Identità runtime `meteofriul-community@meteo-friul.iam.gserviceaccount.com`;
  1 CPU, 512 MiB, concurrency 4, timeout 60 s, massimo 20 istanze.
  Nessuna proposta di modifica a questi limiti o agli altri servizi Eventi/Meteo.

Il 15 ottobre alle **19:26:09 UTC** una lettura pubblica ha restituito 503
`community_storage_unavailable`; il ricontrollo alle **19:26:42 UTC** è riuscito.
Nei log della revisione attiva compare solo l'esito HTTP: non è stata accertata
la causa. La candidata locale aggiunge diagnostica con i soli nomi delle classi
di errore, senza token, GPS, identità, messaggi privati o stack trace. Il 503
rimane un'osservazione della baseline, non un errore attribuito alla candidata
né un problema dichiarato risolto.

## Compatibilità implementata

| Richiesta | Comportamento |
| --- | --- |
| Nessun header, app 0.1.14 | Contratto e operazioni precedenti sulle osservazioni legacy |
| `X-Meteo-Community-Rules: community-reports-v3` | Nuove regole, GPS e lista delle osservazioni viste obbligatori per entrambi i riscontri |
| Protocollo sconosciuto | 426 con messaggio leggibile, senza ripiego silenzioso |
| App vecchia su un gruppo v3 | 426: «Aggiorna Meteo Friûl per interagire con le nuove segnalazioni.» |
| Nuova app su un gruppo legacy | GPS e osservazioni viste verificati, poi uso del registro premi legacy; nessun secondo premio per lo stesso vecchio episodio |

L'header seleziona il contratto e **non è una credenziale**. App Check, app ID
ammessi, limiti, moderazione e transazioni continuano ad applicarsi a entrambi.
Il frontend aggiunge soltanto l'header alle richieste Community cloud. La UX,
gli endpoint loopback della TEST e le richieste Webcam non cambiano.

Tutti leggono lo stesso archivio: nessuna copia dei dati TEST in produzione,
nessun nuovo alias, nessun azzeramento di punti o contatori esistenti. Gli invii
legacy successivi al rilascio incrementano il contatore Inviate una volta sola;
non si inventano invii storici mancanti. I riscontri legacy vengono conservati
anche nel loro snapshot storico. La retention rimane 48 ore.

I nuovi gruppi hanno un identificativo `group-v3-…:ISTAT:finestra` distinto da
quelli legacy. Una conferma vecchia, priva di GPS e del contenuto osservato,
non può validare un nuovo contenuto. Durante la convivenza possono comparire
due gruppi dello stesso fenomeno/Comune se provengono dalle due generazioni:
non vengono fusi attribuendo loro conferme incompatibili. Le osservazioni
legacy conservano le regole con cui sono state inviate; le nuove adottano
quelle approvate (3 minuti, un'osservazione attiva, premio ogni 3 ore per
autore/fenomeno/Comune, nessun tetto giornaliero ai punti).

Dopo un primo invio v3 riuscito, la stessa installazione non può tornare alle
vecchie operazioni per aggirare le regole. Il vincolo è registrato nella ricevuta
atomica permanente e sopravvive a scadenza, redazione dei contenuti e riavvio.
Una richiesta fallita non attiva il vincolo. Le ricevute già accettate restano
consultabili e ripetibili senza creare un secondo invio. Nessun campo top-level
dello schema dello storage è aggiunto o rimosso.

## Verifica locale

- Suite backend regole, reputazione, API, SQLite, snapshot cloud e compatibilità:
  **123 test e 36 subtest PASS**.
- Client: **45 test in 3 file PASS**, incluso header cloud, GPS, identità dei
  gruppi e assenza dell'header su loopback/Webcam. ESLint mirato PASS.
- Scenari misti: vecchio invio/conferma senza GPS, aggiornamento, correzione,
  ritiro e sostituzione; conferma nuova rigorosa; nessun voto vecchio su v3;
  nessun doppio punto; mantenimento del premio precedente nella finestra di
  3 ore; quote condivise e rollback atomico di un upgrade fallito.
- Due connessioni SQLite simultanee: un solo invio accettato. Snapshot cloud
  simulati: riavvio e risposta persa dopo il commit riconciliano l'operazione
  senza raddoppiare invii, premi o archivio.
- Packaging allowlist e hash geografico PASS; sintassi PowerShell PASS.
- Dal contesto finale, con il runtime locale ma senza importare il backend del
  workspace: **31 test unittest PASS**. Archivio verificato file per file:
  esattamente 35 file ammessi, hash tutti corrispondenti. Questo non sostituisce
  la futura compilazione dell'immagine Docker.

Le prove cloud qui sono offline, sul repository reale con servizi Firestore/GCS
simulati. App Check viene simulato nei test. Non certificano una nuova revisione
Cloud Run, token di distribuzione reali o una nuova app Android. Il precedente
collaudo Android resta in [COMMUNITY_FINAL_ANDROID_2026-10-15.md](COMMUNITY_FINAL_ANDROID_2026-10-15.md).

## Pacchetto e sequenza di rilascio

Pacchetto preparato sul commit
`eea5a64dd72bc62d192343564003ce3851cde25f`, nella directory locale ignorata
`build/community-cloud/eea5a64d-20261015T193501Z/`:

- `release-manifest.json`: identità, baseline, hash e ambienti;
- `source.tar.gz`: SHA-256
  `8b60793863089ecd0f316ff2126119fbdaeffb870b32a212a37f08a75ba47533`;
- `runtime.env.yaml`: archivio pubblico, scritture v3 disattivate;
- `validation.env.yaml`: puntatore e prefisso snapshot separati per il collaudo.

Evidenze versionate in
[evidence/community-cloud-compatibility-2026-10-15](evidence/community-cloud-compatibility-2026-10-15).
Il commit successivo di sole evidenze non cambia il codice della candidata.

`scripts/prepare-community-cloud-release.ps1` prepara esclusivamente file
locali da un commit pulito del ramo: contesto allowlist in TEMP, archivio
`source.tar.gz`, configurazione runtime e manifest con hash sotto
`build/community-cloud/`. La geografia è l'unico input ignorato ammesso, con
hash già fissato. Non entrano APK, chiavi, database utenti o credenziali.
Il Dockerfile esegue anche i test misti e incorpora il commit sorgente come
label. Cloud Build richiede `_SOURCE_COMMIT` di 40 caratteri.

Il pacchetto contiene anche `validation.env.yaml`: servizio dedicato
`meteofriul-community-validation`, puntatore Firestore
`community_state_v2/compat-validation-<commit8>` e prefisso snapshot
`community/v2/validation/<commit8>/snapshots/`, scritture v3 abilitate. Il bucket
resta quello esistente, ma nessun puntatore o snapshot utente viene copiato.
Lo stato di prova deve essere inizializzato vuoto con un'operazione create-only
prima del collaudo; la configurazione di validazione non va mai usata per
distribuire il servizio pubblico. Queste risorse non sono state create qui.

1. Prima dell'esecuzione, rileggere revisione, traffico, digest, account e
   configurazione attivi. Devono corrispondere alla baseline del manifest.
2. Avviare Cloud Build sul solo contesto preparato, con tag `compat-<commit8>`
   e `_SOURCE_COMMIT=<commit40>`. Registrare l'esito e il digest prodotto;
   **l'immagine non è stata ancora costruita** in questo lavoro.
3. Distribuire quel digest senza traffico (`--no-traffic`) con tag dedicato.
   Aggiungere l'host esatto dell'URL del tag a `COMMUNITY_ALLOWED_HOSTS`,
   conservando quello canonico. Verificare l'URL effettivamente restituito,
   App Check, storage e contratto. Il tag dà un URL di prova distinto dal
   traffico ordinario ([procedura Google](https://cloud.google.com/run/docs/rollouts-rollbacks-traffic-migration)).
4. Il primo rilascio mantiene `COMMUNITY_V3_WRITES_ENABLED=0`: l'app pubblicata
   continua sul vecchio contratto; letture v3, reputazione e storico sono
   disponibili, nuovi invii/voti v3 restituiscono 503 `community_v3_rollout_pending`.
   I flag di moderazione e le ricevute restano accessibili. Non distribuire il
   nuovo client con le scritture ancora disattivate.
5. Collaudare le scritture v3 su **storage di staging separato**, con identità
   di prova e App Check, senza inserire fenomeni inventati nella mappa pubblica.
   Non usare il tag della revisione collegata allo storage di produzione per
   queste scritture: `--no-traffic` non isola il database.
6. Dopo esito favorevole e autorizzazione al rilascio, promuovere la revisione
   compatibile. Attivazione delle scritture v3 e distribuzione della nuova app
   sono passaggi coordinati successivi; nessuno di essi è eseguito qui.

### Ripristino

Prima di qualsiasi scrittura v3 è possibile tornare alla revisione baseline
fissata nel manifest, senza ripristinare un vecchio snapshot dei dati. Dopo
scritture v3, **non** riportare traffico alla vecchia immagine priva dei nuovi
controlli: disattivare le scritture v3 mantenendo una revisione compatibile,
conservare ricevute/dati e distribuire una correzione. Un rewind dello snapshot
perderebbe operazioni accettate e non fa parte di questa procedura.

Durante il collaudo cloud verificare l'assenza di errori storage ripetuti,
incluso il 503 isolato osservato sulla baseline. GitHub, CI GitHub, AAB e Play
non sono prerequisiti per costruire e collaudare questo backend.
