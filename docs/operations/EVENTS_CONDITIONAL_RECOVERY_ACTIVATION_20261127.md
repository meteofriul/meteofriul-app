# Eventi: attivazione della ripresa condizionale — 27 novembre 2026

## Decisione e perimetro

Il proprietario ha autorizzato la soluzione ricorrente dopo il recupero
pubblico del 27 novembre. La richiesta di saltare una pagina in timeout è
stata valutata solo concettualmente e **non** è stata implementata. La
[PR 71](https://github.com/meteofriul/meteofriul-app/pull/71) è stata unita
a `main` nel commit `6ae67c14f03265308375515bbfe36289930ff818` alle
09:59 UTC. La [CI di main](https://github.com/meteofriul/meteofriul-app/actions/runs/45978259706)
ha superato backend, frontend e controllo hosting. I file backend del merge
sono identici a quelli dell'immagine QA costruita dal commit `286567cd`:
`sha256:7e9f65565101737ab571358ef6c813a6082d5a3ca72766b2cdcfea33f9f36f5b`.
Nessuna versione, Web, Android, AAB o app pubblica è stata distribuita.

## Prove isolate prima dell'attivazione

La prima prova QA sul catalogo corrente è terminata `skipped/not_stale`,
senza nuova generazione o claim. Una seconda prova ha usato sotto una
chiave QA separata un catalogo precedente `stale` per `ReadTimeout`.
L'esecuzione `meteofriul-events-conditional-due-qa-20261127-xplnb` ha
preso un solo claim, eseguito solo TurismoFVG e salvato la generazione QA
`1795772954519643`. Dopo il budget restavano 552 dettagli pendenti:
47 letture strutturate, zero letture fallite. Il job è uscito con errore,
ha conservato le 1.498 schede precedentemente verificate, la diagnostica e
il checkpoint del tentativo; le altre 14 fonti sono rimaste identiche.
Questo prova il comportamento sicuro di un tentativo incompleto, **non** il
recupero in una sola corsa. I due job QA temporanei sono stati eliminati.
[Disegno e dati della prova](EVENTS_CONDITIONAL_RECOVERY_DESIGN_20261127.md).

## Risorse attive e readback

| Risorsa | Stato letto dopo l'attivazione |
| --- | --- |
| Job `meteofriul-events-conditional-recovery` | Generazione 1 in `europe-west1`, digest sopra, comando fisso `python -m app.events.pilot_cloud --recover-turismofvg-if-stale`, chiave `pilot/events/v1/catalog.json`, service account Eventi esistente, un task, zero retry, timeout 900 secondi, 1 vCPU e 1 GiB. |
| IAM | La service account Scheduler esistente ha `roles/run.invoker` sul solo nuovo job tramite binding dedicato; il binding preesistente sul refresh ordinario resta invariato. Non è stato concesso `run.jobs.runWithOverrides`. |
| Scheduler omonimo | `ENABLED`, `0 6 * * *` in `Etc/UTC`, OAuth verso `jobs/meteofriul-events-conditional-recovery:run`, body `{}`, zero retry. Primo slot registrato: **28 novembre 2026, 06:00 UTC** (07:00 CET), due ore dopo il refresh ordinario delle 04:00 UTC. |
| Monitoraggio | Quattro policy nuove, ciascuna applicata per chiave e poi letta come `unchanged`: `events-refresh-last-success` (25 ore), `events-refresh-scheduler-failures`, `events-conditional-failures`, `events-conditional-scheduler-failures`. Tutte abilitate sul canale email operativo già usato da altri allarmi. Le due policy Eventi precedenti non sono state modificate. |

L'avvio pubblico di controllo
`meteofriul-events-conditional-recovery-vthwm` è terminato `Completed=True`
alle 10:08 UTC. Il log strutturato riporta `action=skipped`,
`reason=not_stale`; il catalogo pubblico è rimasto alla generazione
`1795768491780598` e non esiste un claim pubblico. Il job ordinario Eventi
è rimasto alla generazione 50. Nel readback delle regioni `europe-west1`
e `europe-west8` risultano 17 Cloud Run Job; 13 Scheduler in west1, tutti
`ENABLED`. [Inventario aggiornato](JOBS_INVENTORY.md).

## Limiti e controllo successivo

La ripresa automatica fa una sola raccolta extra della sola TurismoFVG per
data italiana quando il lotto è incompleto per errore temporaneo o scaduto.
Se il sito resta lento, il job può fallire ancora: conserva i dati
verificati, registra il tentativo e lascia scattare l'allarme. La prova QA
con 552 pendenti mostra che un backlog vecchio può richiedere più giorni.
L'assenza di successi del refresh ordinario e gli errori Scheduler sono
monitorati; il successo di un job, da solo, non certifica la freschezza
delle schede servite dall'API. La consegna effettiva delle nuove email non
è stata provocata artificialmente.

Al primo slot del 28 novembre vanno controllati, nell'ordine: esecuzione
ordinaria delle 04:00 UTC e suo catalogo, invocazione condizionale delle
06:00 UTC, log `skipped` oppure `run`, eventuale claim, generazione e stato
TurismoFVG, quindi API pubblica. Se la fonte è sana, lo stato atteso è
`skipped/not_stale` senza nuova scrittura. Se è incompleta, va verificato
il progresso del checkpoint e la visibilità del lotto; un fallimento non
va presentato come recupero.

Il codice attuale, su timeout di una pagina numerata, tenta una raccolta
alternativa per intervalli di date con conteggi verificati. Passare alla
pagina successiva registrando un buco è tecnicamente possibile, ma quella
pagina deve restare pendente e l'inventario non può essere dichiarato
completo o sostituire le schede verificate. Nessuna modifica a questa
regola è stata fatta in questa attivazione.
