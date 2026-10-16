# Gate Firestore TTL per gli outbox push

Questo gate e' obbligatorio prima di ogni AAB Play e dopo qualsiasi modifica
alla retention delle notifiche o ai writer. E' esclusivamente di lettura:
elenca le policy TTL Firestore e confronta lo stato cloud con il contratto
applicativo.

## Contratto

| Collection group | Campo TTL | Stato cloud | Orizzonte scritto dall'app |
| --- | --- | --- | --- |
| `push_official_alert_outbox` | `expires_at` | `ACTIVE` | 30 giorni |
| `push_local_notice_outbox` | `expires_at` | `ACTIVE` | 14 giorni |

L'orizzonte non e' contenuto nella policy TTL: il backend calcola il timestamp
`expires_at` quando scrive il documento. La policy deve usare offset zero, cosi'
Firestore considera direttamente quel timestamp.

TTL non significa "cancella dopo 30/14 giorni dalla policy". Firestore elimina
un documento soltanto quando il suo campo timestamp raggiunge la scadenza; la
cancellazione e' asincrona e normalmente avviene entro 24 ore. Un documento con
campo assente, `null` o di tipo non valido non scade. Per questo i record creati
prima dell'introduzione di `expires_at` richiedono una verifica una tantum e,
se presenti, un backfill oppure una pulizia esplicita. L'attivazione della policy
da sola non corregge quei record.

Il gate non si affida soltanto a una dichiarazione manuale: usa l'API Firestore
`runQuery` in sola lettura, proiettando esclusivamente `expires_at`, e blocca se
anche un solo documento corrente non contiene un timestamp valido. Non stampa
ID o contenuti dei documenti; nel risultato espone soltanto conteggi e digest
SHA-256 dell'insieme letto.

Il contratto non e' completo se le policy sono corrette ma i processi che
scrivono gli outbox stanno ancora eseguendo un'immagine precedente. Il gate
legge Cloud Run e Cloud Scheduler, seguendo i target realmente pianificati.
Per la AAB Play verifica contemporaneamente:

- `meteofriul-api`: una sola revisione standard `Ready` al 100% e la
  revisione `Ready` del tag API effettivamente usato dalla AAB;
- Scheduler `meteofriul-official-alert-sync` in `europe-west1`, abilitato
  ogni due ore Europe/Rome, diretto al job in `europe-west8`;
- Scheduler `meteofriul-local-notice` orario e i job
  `meteofriul-morning-forecast` (07:30) e
  `meteofriul-evening-forecast` (20:45), tutti in `europe-west1`;
- ciascun job `Ready`, Scheduler abilitato, orario e URI del target esatti;
- per ogni digest `@sha256` distinto, una prova Cloud Build `SUCCESS` e
  un archivio sorgente verificato che contiene lo stesso `push.py` corrente.

Un tag (`latest`, tag di commit o altro) non e' prova sufficiente: anche se in
quel momento risolve l'immagine corretta, puo' essere spostato senza modificare
la configurazione del job. Digest diversi sono ammessi solo se attestati;
uniformarli non e' una condizione per la AAB.

Riferimento ufficiale: https://firebase.google.com/docs/firestore/ttl

## Evidenza storica obbligatoria

Dopo la lettura/bonifica una tantum, creare senza sovrascrivere la storia
precedente:

`release-history/firestore-ttl/push-outbox-history.json`

Schema minimo:

```json
{
  "schemaVersion": "firestore-push-ttl-history-v1",
  "projectId": "meteo-friul",
  "databaseId": "(default)",
  "verifiedAtUtc": "2026-08-23T12:00:00Z",
  "ttlPolicies": [
    {
      "collectionGroup": "push_official_alert_outbox",
      "field": "expires_at",
      "state": "ACTIVE",
      "expirationOffsetSeconds": 0,
      "appHorizonDays": 30
    },
    {
      "collectionGroup": "push_local_notice_outbox",
      "field": "expires_at",
      "state": "ACTIVE",
      "expirationOffsetSeconds": 0,
      "appHorizonDays": 14
    }
  ],
  "collections": [
    {
      "collectionGroup": "push_official_alert_outbox",
      "field": "expires_at",
      "action": "backfilled",
      "readbackMethod": "firestore.runQuery.expires_at-projection",
      "observedDocumentCount": 12,
      "missingOrInvalidExpiresAt": 0,
      "provenance": {
        "mutationKind": "atomic-backfill",
        "operationAtUtc": "2026-08-23T11:58:00Z",
        "targetSetSha256": "<sha256 di 64 caratteri>",
        "postReadbackSha256": "<sha256 di 64 caratteri>"
      }
    },
    {
      "collectionGroup": "push_local_notice_outbox",
      "field": "expires_at",
      "action": "verified-empty",
      "readbackMethod": "firestore.runQuery.expires_at-projection",
      "observedDocumentCount": 4,
      "missingOrInvalidExpiresAt": 0,
      "provenance": {
        "mutationKind": "none-readback-only",
        "operationAtUtc": "2026-08-23T11:59:00Z",
        "targetSetSha256": "",
        "postReadbackSha256": "<sha256 di 64 caratteri>"
      }
    }
  ]
}
```

Azioni ammesse: `backfilled`, `cleaned`, `verified-empty`. Lo script non compie
nessuna di queste azioni: valida soltanto l'evidenza prodotta dopo un intervento
separato e approvato. `missingOrInvalidExpiresAt` deve essere zero per entrambe
le collection. La provenienza e' strutturata: tipo di mutazione, istante UTC,
digest dei record interessati e digest del read-back post-intervento. Non e'
accettata una semplice nota libera. Il file deve essere aggiunto una sola volta a Git, senza
modifiche successive: il gate verifica che sia tracciato, pulito e presente in
un solo commit. Se una verifica futura richiedera' nuova evidenza, andra'
aggiunto un nuovo file e aggiornato esplicitamente il percorso del gate, senza
riscrivere quello precedente.

## Attestazione del set live di writer

Il gate Play usa un contratto append-only per l'insieme dei writer realmente
raggiunti dall'app e dagli Scheduler. Per 0.1.13 e':

`release-history/firestore-ttl/runtime-writer-sets/play-0.1.13-20261009.json`

Il file vincola il digest dell'API standard, quello della revisione servita
dal tag Play della AAB e il digest di ciascuno dei quattro job schedulati.
Contiene una prova per ogni immagine distinta: commit sorgente, ID e regione
Cloud Build, SHA-256 dell'archivio sorgente e SHA-256 del `push.py` estratto.
I digest possono essere diversi: il requisito e' che ogni immagine attiva
contenga lo stesso writer TTL verificato, non che tutti i componenti usino
la stessa build.

Prima di creare il contratto, leggere in sola lettura Cloud Run e Scheduler,
verificare l'archivio sorgente di ogni build `SUCCESS` e il file `push.py`
estratto. Il gate rilegge live servizio, tag, job, Scheduler, policy TTL,
documenti Firestore e Cloud Build. Confronta gli hash e i commit sorgente,
richiede il file di contratto tracciato, pulito e presente in un solo commit
Git sul suo percorso letterale. Una revisione non Ready, un target Scheduler
cambiato, un digest senza prova o una divergenza del writer bloccano la AAB.

Le attestazioni precedenti in `runtime-writer-images/` restano immutabili
come evidenza storica per il vecchio audit v1; non attestano l'attuale set
live. Non modificarle o cancellarle per far passare il nuovo controllo.

## Gestione di un gate rosso

Non disabilitare il gate e non distribuire immagini solo per uniformare i
digest. Prima distinguere un target Scheduler spostato, una nuova build senza
prova, una reale divergenza di `push.py` o una variazione di policy/documenti
TTL. Se il codice writer e' identico, creare un nuovo contratto append-only
solo dopo aver verificato build e sorgenti; se il codice e' diverso, fermare
la AAB e trattare l'aggiornamento backend in un workstream separato, con
dry-run e controllo dei run naturali prima di riprovare. Una CI verde non
sostituisce l'audit live. Nessun job o servizio viene modificato dall'audit.

## Esecuzione

Dal root del repository:

```powershell
.\scripts\audit-firestore-push-ttl.ps1
```

Esiti:

- `0`: entrambe le policy sono `ACTIVE`, offset zero, retention applicativa
  30/14 giorni, read-back corrente senza campi mancanti, evidenza storica
  immutabile e prove complete per tutti i digest writer live;
- `2`: stato letto correttamente ma gate bloccato;
- `1`: audit non eseguibile o output cloud non interpretabile.

Il 23 agosto 2026 le due policy sono state verificate `ACTIVE`, con offset zero.
Il record ufficiale e i tre record locali storici sono stati regolarizzati con
un'unica scrittura atomica, impostando `expires_at` a partire dal rispettivo
`finished_at`; il read-back successivo non ha rilevato campi mancanti. Questa
evidenza storica e' in Git, ma non prova lo stato corrente: ogni AAB richiede
un nuovo audit live di policy, documenti e immagini dei cinque writer.

I test puri, compatibili con Windows PowerShell 5.1 e PowerShell 7, non usano
credenziali cloud:

```powershell
.\scripts\firestore-push-ttl-audit.contract.tests.ps1
.\scripts\firestore-push-ttl-live-writer-set.contract.tests.ps1
```
