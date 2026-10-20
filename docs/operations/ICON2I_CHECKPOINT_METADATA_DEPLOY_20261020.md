# ICON-2I: deploy della correzione del checkpoint, 20 ottobre 2026

**Verifica serale fallita: nuova corsa non pubblicata, tolleranze ancora non verificate.**
L'esecuzione ordinaria delle 18:00 UTC / 20:00 italiane ha raggiunto un limite
di dimensione nella validazione. Il deploy delle 09:06 UTC resta quello
documentato sotto; nessun nuovo deploy o acquisizione manuale è stato eseguito.
Il solo esito serale non autorizzava la promozione; la successiva correzione
locale, i 183 test e l'autorizzazione al passaggio su main sono documentati
nel [verbale del limite](ICON2I_PAYLOAD_LIMIT_FIX_20261020.md).

## Artefatto e verifica prima del deploy

- Sorgente: commit `9ef1410e71e95a8b31fa54ba5b5543d0b68aa12a`, ramo
  `codex/icon2i-checkpoint-metadata`, base main `bf304281aa9851369687c2dd646b8bd473c0b23d`.
  La correzione resta sul ramo dedicato; nessun push Git o promozione a main.
- Immagine distribuita:
  `europe-west1-docker.pkg.dev/meteo-friul/meteofriul/weather-worker@sha256:e72f606ffe1feec5f1c108f945ec5dbce43cfebef3d69913fc72c11b04cbcae2`.
- Build `7d210639-1ba9-4e85-8ec5-f5e278a3cae2`: SUCCESS.
  Base fissata al digest del precedente produttore `b8719b7f...`; nessun
  aggiornamento di dipendenze. Tutti i 180 file esportati verificati con hash.
  Differiscono dalla precedente distribuzione solo due sorgenti runtime
  (`run_pilot.py`, `operational_diagnostics.py`) e i rispettivi test.
- Nell'immagine Linux: **123 test passati in un'unica esecuzione**, zero errori,
  fallimenti o casi saltati; rete bloccata. ecCodes API runtime 2.50.0.
  Il decoder Python e reale, ma l'interfaccia dei messaggi ecCodes e simulata
  nei test: non si dichiara decodificata una nuova corsa del fornitore.

## Modifica applicata e rollback

Aggiornata esclusivamente l'immagine di `meteofriul-icon` nel progetto
`meteo-friul`, regione `europe-west1`, account `meteofriul@gmail.com`.
Risorse, identita, retry e altri parametri del produttore invariati.
Confrontati prima/dopo: **altri 12 job, 11 scheduler e servizio HTTP invariati**.
Il QA conserva `dry_run`; nessun job di invio e stato aggiornato o attivato.
Questo non significa che siano stati disabilitati i job operativi preesistenti.

Rollback compatibile verificato e disponibile, non eseguito:
`europe-west1-docker.pkg.dev/meteo-friul/meteofriul/weather-worker@sha256:3be1d207321e8ea0cee07466c9ac29fcec230ba4e10b3267647fa8f0cb2315a6`.
Mantiene il lettore checkpoint 1/2. Non tornare a un lettore rigido e non
cancellare checkpoint, esiti terminali o dati immutabili per forzare il recupero.

## Lettura delle app dopo il deploy

- FVG: latest e manifest ancora identici, corsa `20261019T120000Z`.
  Riletti Pordenone, Udine e Gradisca d'Isonzo; byte invariati.
  Riutilizzate le verifiche dei due client storici `2f02c8ba` e `8497e773`
  su tutti i 215 documenti dello stesso manifest immutabile.
- Nazionale: riletti Milano, Canazei, Roma, Napoli, Palermo e Cagliari,
  corsa `20261020T000000Z`; blocchi con gli stessi hash gia accettati
  dai due client storici. E un campione, non una verifica di tutta Italia.
- CORS Android confermato. ADB non rileva telefoni collegati: nessuna nuova
  verifica visiva sul Galaxy e nessuna installazione.

La compatibilita sui dati attuali e confermata; **non prova ancora la lettura
dei documenti generati dal produttore corretto**. Nessuna AAB, emulatore,
modifica di preferenze, invio di prova o esecuzione QA avviati in questo passaggio.

## Controllo serale gia autorizzato

Il follow-up di questa chat `verifica-tolleranze-icon-sulla-nuova-corsa`
e riattivato per la finestra del 20 ottobre, 20:20 e 21:20 Europe/Rome,
con massimo due controlli e arresto al completamento o a un problema che
richiede decisione. Nessun nuovo scheduler GCP. La proposta di calendario
senza scadenza e stata respinta dalla revisione automatica; l'aggiornamento
limitato a due occorrenze, con vincolo esplicito alla sola data odierna,
e stato accettato. L'attesa normale o lo stato invariato non generano messaggi.

Usare la radice canonica `F:/proggetto Meteo Friul App/meteo FRIUL`:

1. Leggere l'esecuzione ordinaria serale, verificare il digest sopra, successo,
   pubblicazione di una corsa maggiore di `20261019T120000Z`, checkpoint
   schema 2, log `source_quality` e metadati delle tolleranze. Non forzare una
   nuova acquisizione e non riaprire lo slot terminale mattutino.
2. `python .tmp/verify_icon_hotfix_http.py --name new-run-http --require-new`:
   215 documenti con entrambi i vecchi client e 215 sidecar validi, legati a
   corsa, comune, ora e hash. Le evidenze complete possono essere riusate;
   una cartella senza risultato non e un controllo riuscito.
3. Solo dopo: `python .tmp/execute_icon_hotfix_qa.py`, una sola volta.
   Se esiste `execution-submission.json`, leggere quell'esecuzione; se esiste
   soltanto `qa-submission-intent.json`, ricostruire l'esito prima di riprovare.
   Lo script ricontrolla configurazioni, dry_run, identita senza permessi FCM,
   assenza di scheduler QA e corsa uguale a quella appena verificata.
4. `python .tmp/read_icon_hotfix_results.py`; confrontare poi baseline e
   candidato localmente sugli stessi punti, dati e istante. Contare candidati
   cambiati, tolleranze utilizzate e non valutabili per causa/denominatore.
   Il confronto locale non e ancora eseguito. Se i punti del QA non esercitano
   tolleranze, integrare soltanto con dati gia pubblicati e dichiararlo.
5. Verificare zero invii e prenotazioni del QA tramite attempt_id. Le letture
   dell'audit/outbox sono delimitate nel tempo, ma l'attivita di altri job
   non va attribuita al QA solo per coincidenza temporale. Controllare anche
   il successo dell'esecuzione: la sola presenza del riepilogo non basta.
6. Ricontrollare letture FVG/nazionali, ed eventualmente il Galaxy se collegato,
   senza installazioni o invii. Aggiornare questo verbale e fermare il follow-up.

Gli script sono stati adattati e controllati sintatticamente. Non sono stati
eseguiti sulla nuova corsa ancora non disponibile. Gli invii del consumatore
nuovo restano subordinati alla verifica e a una successiva autorizzazione.

## Evidenze

[Riepilogo deploy](evidence/icon-checkpoint-hotfix-2026-10-20/deployment-checks.json),
[letture dopo il deploy](evidence/icon-checkpoint-hotfix-2026-10-20/post-deploy-readback.json),
[build](evidence/icon-checkpoint-hotfix-2026-10-20/build-summary.json),
[log dei test nell'immagine](evidence/icon-checkpoint-hotfix-2026-10-20/image-verification.txt),
[provenienza](evidence/icon-checkpoint-hotfix-2026-10-20/source-provenance.json),
[follow-up](evidence/icon-checkpoint-hotfix-2026-10-20/follow-up.json),
[hash](evidence/icon-checkpoint-hotfix-2026-10-20/SHA256SUMS.txt).
Risposte complete e helper restano in `.tmp/icon-checkpoint-hotfix-20261020`
e `.tmp` del workspace canonico; non sovrascrivono le evidenze del 19 ottobre.
Diagnosi e correzione: [verbale precedente](ICON2I_TOLERANCE_PHASE3_DEPLOY_20261019.md).

## Conservazione locale del 20 ottobre

Questo salvataggio versiona il verbale, il piano e le evidenze gia raccolte.
Gli [helper e gli input della build](evidence/icon-checkpoint-hotfix-2026-10-20/helper-inventory.json)
sono conservati anche sotto `evidence/icon-checkpoint-hotfix-2026-10-20/tools/`,
per non dipendere soltanto da `.tmp`. Sono copie storiche con percorsi e
identificativi fissati: archiviarle non autorizza a rieseguire build, deploy
o QA. Il follow-up usa ancora gli originali canonici previsti sopra.
Il controllo di questa conservazione riguarda JSON, sintassi, link e hash;
non ripete i test meteo e non completa la prova sulla nuova corsa.


## Esito della verifica serale del 20 ottobre

L'esecuzione `meteofriul-icon-knbcb` (18:00:13–18:03:14 UTC) usa il digest
atteso `e72f606f…`, ma termina con exit 1. L'acquisizione della corsa
`2026102012` è completa; la validazione fallisce in `snapshot_materializer.py`,
`_read_bounded`, riga 80: `SnapshotMaterializationError`,
`verified_pipeline_invariant_failed`, stato terminale `manual_review`.
I retry leggono lo stesso fallimento, senza una seconda acquisizione.

I log riportano `payload_bytes=34601901`, maggiore di
`MAX_ICON_JSON_BYTES=33554432` (32 MiB). Il superamento è dimostrato dal log;
il messaggio sanitizzato non identifica il file. Non è stata corretta qui
la gestione del limite e non sono stati scaricati nuovi dati grezzi.

Alle 18:27 UTC: checkpoint serale assente (404 al percorso con prefisso
effettivo `pilot`), outcome terminale presente e non retryable, nessun evento
`source_quality` nei 107 log letti con paginazione completa. Nessun oggetto
immutabile, outcome o scheduler è stato alterato per tentare il recupero.

Latest resta `20261019T120000Z`. Il comando HTTP con `--require-new`
termina prima del QA con «New source run is not published yet: do not execute QA».
**Nessun QA eseguito**, nessun invio o prenotazione del QA. Riletti manifest e
Pordenone/Udine/Gradisca con hash invariati: i due client storici restano
verificati sui 215 documenti di quel manifest, non sui dati nuovi.
La verifica nazionale resta quella delle 09:07 UTC; nessuna nuova prova
visiva o installazione sul telefono.

Evidenze: [readback finale](evidence/icon-checkpoint-hotfix-2026-10-20/evening-check/icon-final-readback.json),
[log completi](evidence/icon-checkpoint-hotfix-2026-10-20/evening-check/icon-complete-logs.json).
Al momento del riscontro il passo successivo era correggere localmente la
dimensione e verificarla (esito nella sezione seguente); il deploy resta
un'autorizzazione separata.
Non riaprire lo slot terminale e non dichiarare chiusa la verifica tolleranze.

La revisione automatica ha rifiutato la rimozione del follow-up perché manca
una richiesta esplicita dell'utente per eliminarlo. L'automazione resta
invariata; nessuna modifica diretta ai file di automazione ha aggirato il blocco.


## Correzione locale successiva del limite

Preparata e verificata la [correzione locale del limite payload](ICON2I_PAYLOAD_LIMIT_FIX_20261020.md):
64 MiB, lettura limitata e diagnostica esplicita. 183 test passati;
il caso completo sintetico da 37,2 MB supera validazione, checkpoint e
pubblicazione locale per 215 comuni. Non è il grezzo della corsa fallita.
Nessun deploy o nuova verifica cloud: l'esito operativo serale sopra resta
fallito e la verifica delle tolleranze sulla nuova corsa resta incompleta.
