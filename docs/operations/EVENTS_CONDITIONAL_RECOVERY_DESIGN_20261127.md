# Eventi: ripresa condizionale TurismoFVG — proposta del 27 novembre 2026

## Stato e causa

Il recupero pubblico del 27 novembre è riuscito e documentato nel
[rapporto operativo](EVENTS_TURISMOFVG_TIMEOUT_REVIEW_20261127.md).
Questo documento riguarda la continuità successiva: nessun nuovo job,
Scheduler, allarme o immagine è stato distribuito da questo ramo.

Le corse del 26 e 27 novembre avevano concluso i 335 secondi assegnati a
TurismoFVG con dettagli ancora pendenti. Un successivo timeout del sito ha
interrotto la ripresa manuale. Il checkpoint permette già di riusare le
letture riuscite; manca un secondo avvio mirato e condizionale dopo il ciclo
ordinario. Ripetere automaticamente il job completo delle 15 fonti
aggiungerebbe traffico non necessario anche alle fonti sane.

## Comportamento candidato

Il comando `--recover-turismofvg-if-stale` legge il catalogo e i controlli
fonte esistenti. Senza scrivere il catalogo e senza interrogare TurismoFVG,
registra `action=skipped` quando la fonte è valida, in pausa oppure è
già stata tentata in automatico nella stessa data locale.

Esegue solo TurismoFVG nei seguenti casi:

- lotto `stale` con errore `incomplete_source` e dettagli pendenti;
- lotto `stale` dopo un errore di trasporto o pagina numerata temporaneamente
  indisponibile (`ReadTimeout`, `ConnectTimeout`, `ConnectionError`,
  `CalendarPageUnavailable`);
- lotto `fresh` o `partial` memorizzato ma scaduto oltre la soglia pubblica
  esistente di 48 ore, per esempio se il ciclo ordinario non è partito.

Non ripete automaticamente errori strutturali o editoriali. Il tentativo
usa il timeout di fonte già fissato a 360 secondi, i checkpoint e tutti i
gate di pubblicazione. Se resta incompleto, salva diagnostica e data del
tentativo, mantiene il lotto precedente e fa fallire il job.

Cloud Scheduler usa una consegna [almeno una volta](https://docs.cloud.google.com/scheduler/docs/configuring/deduplicate-job-requests),
anche se il numero di retry pianificati è zero. Prima di leggere il sito,
il worker crea una piccola prova di presa in carico sotto
`pilot/events/v1/recovery-claims/turismofvg/<data>.json` con la precondizione
Storage `if_generation_match=0`: [solo il primo oggetto può essere creato](https://docs.cloud.google.com/storage/docs/request-preconditions).
Il prefisso deriva dalla chiave del catalogo: una prova QA crea claim
solo sotto la propria chiave QA, senza interferire con la produzione.
Una consegna duplicata nella stessa data locale non interroga la fonte e
non riscrive il catalogo. Il marcatore `last_automatic_recovery_date` nel
lotto protegge anche i successivi avvii dopo un salvataggio. Se il processo
si interrompe dopo il claim e prima del catalogo, la ripresa automatica
aspetta il giorno successivo; un operatore può sempre usare il comando
manuale `--source TurismoFVG` dopo verifica. La concorrenza di lettura e
la regola compare-and-swap del catalogo restano quelle esistenti.

Questa modalità non crea un timer da sola. Per attivarla, la proposta è
un **job Cloud Run distinto**, con lo stesso digest del worker Eventi, la
stessa identità di scrittura, la chiave del catalogo pubblico, argomento
fisso `--recover-turismofvg-if-stale`, un task, zero retry e timeout 900
secondi. Uno Scheduler dedicato lo avvierebbe alle 06:00 UTC, due ore dopo
il ciclo ordinario delle 04:00 UTC e oltre il suo timeout massimo di 15
minuti. Lo Scheduler avrebbe zero retry e userebbe OAuth verso l'API Cloud
Run, come l'attuale Scheduler Eventi. Un job separato evita di concedere
all'identità dello Scheduler `run.jobs.runWithOverrides` per sostituire
gli argomenti del job pubblico: l'API richiede quel permesso per gli
[override](https://docs.cloud.google.com/run/docs/reference/rest/v2/projects.locations.jobs/run),
mentre la [pianificazione dei job](https://docs.cloud.google.com/run/docs/execute/jobs-on-schedule)
usa un target HTTP autenticato. Prima dell'attivazione va verificato il
permesso dell'identità Scheduler sul nuovo job.

La chiamata Scheduler all'API avvia un'esecuzione e riceve un'operazione:
il successo dell'invocazione non dimostra che il job abbia verificato i dati.
Serve quindi un controllo distinto della freschezza del lotto pubblicato.
Quattro policy Eventi sono ora preparate nella configurazione del ramo:
assenza di un refresh ordinario riuscito per 25 ore, errore di invocazione
dei due Scheduler e fallimento del job di ripresa condizionale. Usano il
canale email esistente `Meteo Friul - notifiche operative`. L'audit cloud
le trova tutte mancanti; non sono ancora attive. Le policy di errore Eventi
già distribuite non hanno un canale di notifica. Il controllo di ultimo
successo rileva anche un refresh ordinario che non parte, ma non sostituisce
la verifica della freschezza del lotto TurismoFVG servito dall'API.

## Prove e limiti

I 38 test di `test_pilot_cloud.py`, gli 811 test `test_pilot_*.py`
(uno saltato), `compileall`, l'help del comando e `git diff --check` sono
passati. La CI della PR 71 sul commit `286567cd` è verde nei tre job.
Cloud Build ha prodotto dal medesimo commit il digest candidato
`sha256:7e9f65565101737ab571358ef6c813a6082d5a3ca72766b2cdcfea33f9f36f5b`.
Un controllo senza rete sui due cataloghi reali salvati il 27
novembre ha classificato come dovuta la ripresa del lotto pubblico
precedente `stale` e come `not_stale` quello recuperato `partial`. I test
esercitano il mancato accesso alla fonte e la mancata scrittura quando la
fonte è sana, la selezione della sola fonte quando la ripresa è dovuta e il
claim atomico, il marcatore giornaliero anche dopo un tentativo fallito e
l'assenza di richieste quando il claim esiste già.

Il job QA temporaneo `meteofriul-events-conditional-qa-20261127` ha usato
quel digest con una copia del catalogo pubblico in un prefisso separato.
L'esecuzione `meteofriul-events-conditional-qa-20261127-qrjs5` è terminata
con successo il 27 novembre alle 09:06 UTC; il log strutturato registra
`action=skipped`, `reason=not_stale`. La generazione QA
`1795770227005336`, l'MD5 `4q0q60/0VH1VNW4D5/Ky2Q==` e la dimensione
3.252.924 byte sono rimasti identici; non è stato creato alcun claim QA.
Il job temporaneo è stato eliminato. La prova copre il caso sano in cloud,
non la ripresa dovuta né un errore reale futuro.

La prova QA del caso dovuto ha riusato un catalogo pubblico precedente,
`stale` per `ReadTimeout`, sotto la nuova chiave QA
`pilot/events/qa/conditional-due-286567cd-20261127/catalog.json`.
L'esecuzione `meteofriul-events-conditional-due-qa-20261127-xplnb` ha
registrato `action=run` il 27 novembre alle 09:43 UTC. Dopo il budget
della fonte ha salvato la generazione QA `1795772954519643` e un solo
claim giornaliero; il lotto è rimasto `stale` con 552 dettagli pendenti,
47 letture strutturate e zero letture fallite. Il job è uscito con errore,
senza presentare il lotto incompleto come riuscito. Ha conservato le 1.498
schede verificate in precedenza, la diagnostica e il checkpoint del
tentativo; le altre 14 fonti sono identiche alla copia iniziale. La
generazione pubblica `1795768491780598` non è cambiata. Il job QA è stato
eliminato. Questa prova dimostra il percorso di errore e la continuità del
checkpoint, non un recupero concluso in una sola corsa: un catalogo molto
arretrato può richiedere più giorni.

Il job pubblico è ancora alla generazione 50, con un task, zero retry,
timeout 900 secondi, 1 vCPU e 1 GiB. L'attuale identità Scheduler ha il
solo ruolo `roles/run.invoker` sul job Eventi; per il nuovo job serve un
binding altrettanto circoscritto. Il nuovo Scheduler userebbe la medesima
identità e zero retry.

Per il caso sano, il container QA è durato circa 26 secondi. Cloud Run
fattura i job per almeno un minuto: usando le [tariffe pubblicate](https://cloud.google.com/run/pricing)
per 1 vCPU e 1 GiB, 31 avvii sani valgono circa 0,026 USD prima della
franchigia condivisa, rete e log esclusi. Cloud Scheduler costa al massimo
[0,10 USD ogni 31 giorni per un job fatturabile](https://cloud.google.com/scheduler/pricing);
la franchigia di tre job è condivisa a livello di account. Una ripresa
dovuta dura di più e consuma anche richieste alla fonte; il massimo del
job resta 900 secondi. Questa è una stima, non una lettura della fattura.

Prima di attivare una pianificazione restano merge e CI su `main`, il
readback finale del binding IAM e l'applicazione mirata delle sole quattro
nuove policy dopo audit. Dopo l'attivazione vanno verificati log, dati e
allarme. Il
caso senza lavoro utile comporta comunque l'avvio giornaliero di un container;
quando la fonte è incompleta, il traffico aggiuntivo è limitato a una
raccolta della sola TurismoFVG per giorno. Nessuna di queste risorse
operative è stata attivata da questa proposta.
