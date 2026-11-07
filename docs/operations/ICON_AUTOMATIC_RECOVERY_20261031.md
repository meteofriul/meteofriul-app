# Recupero automatico ICON — preparazione locale del 31 ottobre 2026

**Aggiornamento successivo:** il proprietario ha autorizzato la distribuzione, completata sui due produttori ICON. [Verbale di deploy, immagini e prove reali](ICON_AUTOMATIC_RECOVERY_DEPLOY_20261031.md). Il testo seguente conserva lo stato e le autorizzazioni della precedente consegna del candidato.

Ramo `codex/icon-automatic-recovery-20261031`, partito da `main`
`e3527f73b19e13aa95b4b09bf04c1049eca91be3` in un worktree isolato.
Percorso locale, relativo alla radice canonica:
`.tmp/icon-automatic-recovery-20261031`.
Il proprietario ha autorizzato implementazione, prove locali e, dopo l'audit
dei costi, salvataggio, push e PR. Attivazione, immagini cloud, modifiche di
Scheduler e promozione in main restano separate.
Il workspace Mercati e i suoi servizi locali non vengono spostati o modificati.

## Obiettivo e confini

Quando il nuovo ciclo non è ancora disponibile, il controllo iniziale non
deve consumare il diritto a una successiva acquisizione. Quando invece una
acquisizione è già iniziata, nessun secondo worker deve scaricare lo stesso
ciclo o sottrarle il lavoro per il semplice trascorrere del tempo.

Il comportamento è attivabile separatamente per FVG e nazionale mediante
`WEATHER_ICON_AUTOMATIC_RECOVERY_ENABLED=true`. Il default resta disattivato.
Il percorso esistente resta disponibile senza la nuova configurazione;
non cambiano fonte ItaliaMeteo, validità dei dati o controlli di qualità.

La discovery legge gli indici HTML e verifica presenza/completa enumerazione
dei file richiesti. Non è ancora una verifica del contenuto GRIB: quella
rimane responsabilità dell'acquisizione e della validazione. Il ciclo scelto
viene fissato prima dell'acquisizione per evitare che cambi tra controllo
iniziale e download.

## Finestre e lavoro limitato

Il [piano macchina](../../experiments/weather_autonomy/icon-recovery-plan.json)
è marcato `LOCAL_REVIEW_ONLY_NOT_APPLIED` e non modifica la configurazione
produttiva attuale.

Nomi dei job e degli Scheduler, cron iniziale, timeout di 900/1800 secondi
e retry Cloud Run 2/0 sono confrontati con l'inventario locale raccolto il
31 ottobre alle 15:20:50 UTC. Non è stata effettuata un'altra chiamata cloud
durante questa implementazione; i valori andranno ricontrollati al deploy.

| Fase | Mattino UTC | Sera UTC |
| --- | --- | --- |
| Controllo principale | 06:00 | 18:00 |
| Recupero dopo un'ora | 07:00 | 19:00 |
| Recupero dopo due ore | 08:00 | 20:00 |
| Ultimo recupero dopo quattro ore | 10:00 | 22:00 |

La finestra mattutina attende almeno il ciclo 00 UTC del giorno, quella
serale almeno il ciclo 12 UTC. Un ciclo intermedio più nuovo del puntatore
ma precedente a quello atteso non viene acquisito da questi recuperi, anche
se ancora utilizzabile. Dopo l'ultimo controllo previsto si attende la
finestra successiva; non esiste un sondaggio continuo.

Cron proposto per i due Scheduler esistenti:
`0 6,7,8,10,18,19,20,22 * * *`, fuso `Etc/UTC`, retry Scheduler zero.
Gli orari italiani cambiano con l'ora legale; gli intervalli restano in UTC.
La scelta evita gli effetti dei cambi d'ora sugli intervalli, secondo la
[documentazione di Cloud Scheduler](https://docs.cloud.google.com/scheduler/docs/configuring/cron-job-schedules).

I ticket durevoli separano il controllo della fonte dal blocco di acquisizione.
Una consegna duplicata non autorizza una nuova discovery o un secondo
download. La protezione applicativa è necessaria perché Scheduler garantisce
consegna almeno una volta, non esecuzione esattamente una volta.
[Semantica ufficiale](https://docs.cloud.google.com/scheduler/docs/overview).

## Costi e limiti da approvare prima dell'attivazione

L'[audit successivo dello stesso giorno](JOBS_COST_AUDIT_20261031.md) confronta
consumi reali osservabili e tariffe pubbliche. Il costo marginale stimato non
giustifica da solo una grande riscrittura: il primo intervento è il
[riuso della verifica FVG nella stessa esecuzione](ICON_VERIFICATION_REUSE_20261031.md),
preparato e verificato nel candidato. La proposta di
16 avvii resta non applicata e il costo operativo della nuova versione non
è ancora misurato in cloud.

- Avvii programmati complessivi: da **4 a 16 al giorno**, otto per prodotto;
  dodici avvii supplementari. I controlli senza ciclo nuovo non devono
  scaricare i GRIB.
- Al massimo due tentativi per il sondaggio di rete associato a un ticket.
- I retry della piattaforma sono un conteggio distinto. Conservando i limiti
  osservati, FVG due retry e nazionale zero, il massimo teorico associato alle
  sole consegne programmate è **32 tentativi di task al giorno**.
- Le riconsegne eccezionali della piattaforma possono aggiungere avvii:
  la deduplicazione limita il lavoro utile ma non annulla i costi di avvio.
- Nessun processo deve restare in attesa per ore. Prima dell'attivazione
  vanno misurati avvio, letture Storage/discovery e acquisizioni in un ciclo
  controllato. Nessuna stima monetaria è presentata come misurata.

Il controllo di integrità della pubblicazione può leggere dati da Storage:
assenza di download GRIB non significa assenza di trasferimenti. Anche
queste letture rientrano nella misura prima dell'attivazione.

## Stati di errore e interruzioni

Fonte assente/incompleta, errore temporaneo di rete, esecuzione già attiva,
pubblicazione verificata e necessità di revisione devono restare distinguibili.
Un codice di uscita positivo del container non sostituisce il controllo del
puntatore pubblico e della freschezza da parte del monitor.

Gli esiti `pending` e `in_progress` non vengono dichiarati pubblicazioni
riuscite: il worker può terminare con errore e attivare i retry Cloud Run
già conteggiati nel budget. Prima dell'attivazione va valutato l'effetto
sulle policy esistenti di errore dei job, distinguendo il ritardo della fonte
dalla qualità dei dati pubblicati. Le policy non sono modificate da questo lavoro.

Un checkpoint completo e validato può essere ripubblicato senza un secondo
download, anche se la discovery della fonte è temporaneamente indisponibile.
Deve però mantenere la copertura contrattuale rispetto al momento corrente:
un checkpoint ormai scaduto richiede revisione e non viene ripubblicato.
Il percorso automatico FVG controlla la validità anche immediatamente prima
della scrittura condizionale del puntatore, per coprire una scadenza durante
l'upload. Il nazionale conserva il controllo corrente di `publish_bundle`.
Le soglie dei due prodotti restano distinte: FVG applica `icon2i_48h_v1`,
il nazionale richiede almeno dodici campioni orari da quel momento in poi.
Un'acquisizione interrotta prima di un checkpoint completo resta un caso
da revisione manuale. Non è ammesso liberare automaticamente un claim
ambiguo, cancellarlo o scavalcarlo in base a una scadenza.

I claim legacy del ciclo/slot coinvolto devono essere riconosciuti e
rispettati. Il nuovo stato non prova da solo la conclusione di un worker
vecchio, che non conosce le nuove guardie. Per questo il passaggio richiede
una verifica esplicita di quiescenza dei job legacy e non permette esecuzioni
contemporanee di vecchi e nuovi worker per lo stesso prodotto.

## Passaggio online proposto, non eseguito

1. Verificare progetto, identità, configurazione effettiva dei due job,
   target Scheduler, bucket e permessi Storage necessari alle scritture
   condizionali. Nessun nuovo privilegio Cloud Run di lettura è richiesto
   dai worker per stabilire se possono sottrarre un claim.
2. Salvare e verificare il candidato, preparare immagini nuove con digest
   immutabili dopo autorizzazione, controllare gli import e la provenienza.
   Le immagini oggi distribuite non contengono questa modifica.
3. Accertare che non ci siano esecuzioni legacy attive o stati ambigui.
   Rivedere eventuali claim incompleti; nessuna cancellazione automatica.
4. Aggiornare un prodotto per volta con l'immagine verificata e la sola
   variabile di attivazione, preservando le altre impostazioni. Verificare
   il worker prima di aumentare gli orari del suo Scheduler.
5. Osservare un ciclo con attesa della fonte e recupero, confrontare stato
   esecuzione, puntatore, manifest, campioni e monitor di freschezza.

Anche il rollback richiede quiescenza e lettura dello stato: ripristinare
cron e configurazione non deve creare un vecchio worker concorrente a uno
nuovo. I dati pubblicati validi, i claim e i checkpoint si conservano.

## Prima verifica locale, precedente all'ottimizzazione

Verifica del profilo nativo `build_verifica`, Python 3.13.5. Comandi, moduli,
conteggi e hash sono nella [ricevuta](evidence/ICON_AUTOMATIC_RECOVERY_20261031.json).

| Verifica | Esito |
| --- | --- |
| Suite di 12 moduli: stato, worker, discovery, checkpoint, pubblicazione e Storage | 241 test PASS, 156,198 secondi |
| Dopo l'ultima guardia del clock FVG: intero `test_cloud_worker` | 28 test PASS, 20,125 secondi, inclusi due casi nuovi |
| `test_icon_recovery*.py` con `python -S`, senza site-packages | 36 test PASS |
| `compileall` dei file coinvolti e `git diff --check` | PASS |

Sono **243 casi distinti coperti tramite verifica incrementale**, non una
singola esecuzione da 243. Dopo la suite ampia sono cambiati soltanto il
worker FVG e il suo test; entrambi sono stati ricontrollati integralmente.
I 36 test isolati sono già compresi nel perimetro, non vanno sommati di nuovo.

I casi coprono fonte assente senza consumo del claim, bootstrap, ciclo fissato,
retry della stessa esecuzione oltre il cambio d'ora, concorrenza, risposte perse
dopo una scrittura riuscita, stato corrotto, vecchi claim, recupero del checkpoint
prima della discovery, validità corrente e comportamento legacy disattivando
la nuova funzione. Le simulazioni usano SQLite e mock: non costituiscono una
prova distribuita su GCS o un ciclo operativo reale in Cloud Run.

## Verifica finale e consegna del candidato

Alla verifica iniziale è seguito il [riuso della verifica FVG](ICON_VERIFICATION_REUSE_20261031.md).
La [ricevuta finale](evidence/ICON_VERIFICATION_REUSE_20261031.json) registra la
nuova regressione completa e gli hash del codice; la ricevuta precedente
rimane una prova datata, non la descrizione del successivo stato Git.
Nel caso senza aggiornamento le letture comunali scendono da 645 a 215;
sia FVG sia nazionale forzano una nuova verifica dopo la pubblicazione.

La CI esistente include il gruppo puro `test_icon_recovery*.py` e i test
dell'identità dello snapshot verificato, senza nuove dipendenze, trigger o
job pianificati. L'esito remoto va consultato sul commit della PR; le ricevute
locali non lo attestano. Salvataggio, push e PR sono autorizzati; nessuna
promozione in main, build di immagini, deploy, nuova policy o modifica di
Scheduler è compresa nella consegna. Restano da autorizzare e misurare il
passaggio operativo, il costo e la migrazione senza worker legacy attivi.

Nessun pacchetto Web/Android di release, installazione su telefono o modifica
al pannello Mercati. Le compilazioni di controllo della CI non sono artefatti
di distribuzione. La funzione resta nel candidato, disattivata per default.
