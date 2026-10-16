# Evidenza storica TTL community

Questa directory e' un ledger append-only per campioni **LIVE** aggregati delle
dieci collection Firestore community. Un record non sostituisce il read-back
LIVE eseguito a ogni build Play: permette invece alla build protetta di
verificare il contratto degli writer anche quando, dopo la pulizia QA o la
normale scadenza TTL, una collection e' vuota.

I record storici precedenti all'introduzione del rango coprono otto collection
e restano immutabili come evidenza del vecchio contratto, ma non soddisfano il
gate corrente. Serve una nuova registrazione LIVE a dieci collection dopo
l'attivazione delle due nuove policy TTL.

## Registrazione esplicita

Non si assume che esistano documenti reali. I quattro campioni privati del
gate moderazione e i sei campioni mancanti, incluse le due collection della
reputazione, devono essere creati
temporaneamente da due tool marker-owned, entrambi dal commit backend tagged
indicato come `SourceCommit`.

1. Nel terminale A, da `backend`, eseguire prima il preview e poi lo smoke con
   hold massimo:

   ```powershell
   .\venv\Scripts\python.exe tools\smoke_community_moderation_live.py
   .\venv\Scripts\python.exe tools\smoke_community_moderation_live.py `
     --apply --hold-seconds 120
   ```

2. Dopo l'evento aggregato `evidence_ready`, nel terminale B eseguire prima il
   preview e poi il seed delle altre sei collection contro la stessa API
   tagged:

   ```powershell
   .\venv\Scripts\python.exe tools\seed_community_ttl_evidence_live.py `
     --api-base "https://<TAG>---meteofriul-api-<HASH>.a.run.app/api"
   .\venv\Scripts\python.exe tools\seed_community_ttl_evidence_live.py `
     --api-base "https://<TAG>---meteofriul-api-<HASH>.a.run.app/api" `
     --apply --hold-seconds 120
   ```

   Il report sintetico e' gia' scaduto e `moderation_hidden`. Il tool verifica
   che report e gruppo siano assenti sia dal servizio pubblico locale sia
   dalla API tagged prima della scrittura, durante il hold e dopo la pulizia.
   Collisioni o perdita del marker bloccano l'operazione; la pulizia
   transazionale non cancella mai documenti non marker-owned.

3. Solo quando entrambi i terminali hanno emesso `evidence_ready`, scegliere
   nel terminale C un nome UTC nuovo nel formato
   `yyyyMMddTHHmmssfffZ-community-ttl.evidence.json` e registrare prima che
   scada il hold:

```powershell
pwsh -NoProfile -File .\scripts\record-firestore-community-ttl-evidence.ps1 `
  -RecordLiveEvidence `
  -SourceCommit "<COMMIT_BACKEND_40_DELLA_REVISIONE_LIVE>" `
  -OutputPath .\release-history\firestore-community-ttl\20260824T120000000Z-community-ttl.evidence.json
```

4. Attendere l'esito finale verde e la pulizia di entrambi i tool. Non
   aggiungere il record a Git se uno dei due fallisce, se appare un report
   pubblico o se la pulizia non e' verificata. Un arresto brusco lascia solo
   documenti TTL-bounded; al riavvio non eliminare mai un documento che non
   conserva il marker di quella esecuzione.

Lo script legge Firestore e scrive una sola attestazione tecnica sanitizzata
nel log Cloud Logging dedicato `meteofriul-community-ttl-evidence`. L'evento
contiene solo schema, target, nonce casuale, commit e SHA-256 del core aggregato;
il recorder deve rileggerlo esattamente prima di creare il file. Richiede
l'identita' esatta
`meteofriul@gmail.com` / `meteo-friul` / `49007668366` / `(default)`, rifiuta
audit rossi e non espone alcun parametro fixture, e non sovrascrive mai un path.
Il file contiene solo
conteggi, estremi degli orizzonti, policy e identita' del target; non contiene
nomi documento, ID di report/fonte/installazione, coordinate o contenuti UGC.
`SourceCommit` deve essere il commit backend completo della revisione LIVE che
ha prodotto i campioni: il recorder legge direttamente da Git i blob di
writer, producer, audit, recorder e validator di quel commit e rifiuta una
working copy diversa.

Dopo la review eseguire i contract test, poi aggiungere e committare il nuovo
record. Non modificare, rinominare o cancellare record precedenti. La build
protetta rifiuta record non tracciati, sporchi o con una storia Git diversa da
una singola aggiunta. Rilegge inoltre LIVE da Cloud Logging il nonce e l'hash:
un JSON locale costruito da una fixture, anche se dichiara `live-read-only`,
fallisce senza l'entry remota corrispondente.

L'identita' operatore deve poter scrivere e rileggere il log dedicato
(`logging.logEntries.create` e `logging.logEntries.list`). Errori IAM,
propagazione assente o piu' entry per lo stesso nonce falliscono chiusi: il
recorder non crea il file e la build non prosegue.

## Legame con gli writer e scadenza

Ogni record conserva un SHA-256 deterministico sui byte esatti dei file che
definiscono e applicano la retention:

- `backend/app/repositories/community.py`;
- `backend/app/services/community.py`;
- `backend/app/services/community_moderation_digest.py`;
- `backend/tools/moderate_community_reports.py`;
- `backend/tools/smoke_community_moderation_live.py`;
- `backend/tools/seed_community_ttl_evidence_live.py`;
- `scripts/audit-firestore-community-ttl.ps1`;
- `scripts/firestore-community-ttl-audit.psm1`;
- `scripts/record-firestore-community-ttl-evidence.ps1`;
- `scripts/firestore-community-ttl-evidence.psm1`.

Il verifier della build Play e' volutamente escluso dal digest per evitare un
auto-hash ricorsivo; resta protetto dai suoi contract test e dalla regola Git
append-only del repository. Il recorder confronta i byte reali del worktree
con i blob del `SourceCommit`: non usa `git status`, quindi modifiche nascoste
con `assume-unchanged` o `skip-worktree` vengono comunque bloccate.

Qualsiasi modifica a uno di questi file invalida il record e richiede una nuova
registrazione LIVE append-only. La build ricalcola inoltre lo stesso digest dai
blob del commit backend attestato dalla revisione tagged, senza checkout, e
richiede che `sourceCommit` sia un suo antenato e che entrambi i commit abbiano
lo stesso digest writer del record. Un discendente con sole modifiche
frontend/documentali e' quindi ammesso; un discendente che cambia uno writer
non lo e'. La build usa il record piu' recente e lo rifiuta dopo 30 giorni; il
rinnovo puo' quindi avvenire prima della build e non richiede di eseguire lo
smoke nello stesso momento della compilazione.

Gli snapshot fixture sono ammessi soltanto dal wrapper di audit nei contract
test. Il recorder operativo non ha un parametro fixture e nessun record viene
accettato senza write/read-back Cloud Logging e successivo read-back LIVE della
build protetta. Finche non viene eseguita questa registrazione LIVE dopo il
commit, il gate resta intenzionalmente fail-closed.
