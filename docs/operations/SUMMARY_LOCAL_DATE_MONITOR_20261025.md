# Sintesi per data locale — preparazione del 25 ottobre 2026

Stato: **sorgenti integrate in main e CI superata; non attive nel cloud**.
Ramo `codex/summary-local-date-monitor`, derivato da main
`e601510659387783d975b9cf62eb77328d78eae5`. Controllo, diagnostica e verbali
consolidati nel commit locale di questo ramo, autorizzato il 25 ottobre.
Revisione e promozione completate tramite PR 24 il 25 ottobre;
il loro esito è distinto dall’attivazione cloud. Nessun deploy, esecuzione cloud,
acquisizione o invio manuale in questo lavoro.
Sponsor disattivati; Android, Web e i relativi pacchetti non cambiano.

## Comportamento implementato

Il valutatore `backend/app/services/summary_slot_monitor.py` identifica ogni
sintesi con tipo (mattino/sera) e **data di invocazione Europe/Rome**.
La data del giorno successivo descritta dalla sintesi serale non è la sua data
operativa. Gli orari restano 07:30 e 20:45, costruiti per ciascun giorno nel fuso:
nessuna somma fissa di 24 ore. Il margine locale iniziale è 15 minuti.

Prima della corsa di oggi, il controllo mantiene la corsa precedente come ultima
attesa: un errore non scompare a mezzanotte. Dall'orario di oggi controlla invece
quella di oggi; il successo di ieri non la copre. Una corsa manuale non sostituisce
quella ordinaria. Un completamento dopo il margine risolve l'allarme corrente ma
resta registrato come `completed_late`.

| Stato | Significato |
| --- | --- |
| not_due / waiting | Prima dell'orario o entro il margine; niente allarme di assenza |
| running / running_late | Esecuzione esatta ancora attiva, entro/oltre il margine |
| missing | Inventario completo, corsa ordinaria assente oltre il margine |
| completed / completed_late | Esito terminale coerente, puntuale/tardivo |
| partial / failed | Esito parziale o fallimento; le accettazioni FCM già avvenute restano contate |
| delivery_pending | Invio in corso o retry previsto; non è completamento |
| inactive / no_forecast | Invii disabilitati/dry-run o previsione assente; non è successo ordinario |
| origin_unverified / ambiguous | Origine non dimostrata o più esecuzioni per lo stesso slot |
| check_unavailable | Lettura incompleta, scaduta, contatori incoerenti o dati non validi |

Nessun destinatario idoneo, deduplicazione, rinuncia e ritiro di una destinazione
sono esiti distinti; non vengono presentati come notifiche consegnate. `sent`
indica accettazione FCM, non visualizzazione sul telefono. Exit code dei due job
di invio, deduplica, testi, soglie meteo e destinatari restano invariati.

## Diagnostica preparata nei due job

Il risultato JSON conserva tutti i contatori e aggiunge `execution_context`:
ID esecuzione validato, tipo, avvio, completamento e data locale di invocazione.
Il worker dichiara esplicitamente di **non attestare da solo l'origine Scheduler**.

La diagnostica `source_trace`, condivisa dal mattino e dalla sera, registra
corsa ICON, numero di gruppi e prima/ultima lettura. I gruppi non raddoppiano
quando più dispositivi usano la stessa località. Se cambia corsa durante il giro,
le due identità restano distinte. Metadati assenti o non validi sono contati,
mai ricostruiti. Massimo 64 identità con conteggio degli ulteriori gruppi.
Nessun token, ID dispositivo, coordinate, comune o testo della notifica nel trace.
È solo diagnostica: non modifica validità o contenuto della previsione.

## Uso locale ed evidenze

Dalla directory `backend`:

```powershell
python -B -m app.jobs.inspect_summary_slots --evidence <file-locale.json> --local-date 2026-10-25
```

Senza `--local-date` controlla l'ultima corsa attesa per ciascun tipo all'istante
`observed_at` dell'evidenza. Non usa l'orologio corrente per fingere un controllo
live di un export vecchio. Il comando non acquisisce credenziali, non legge il
cloud, non scrive metriche e non invia notifiche. Restituisce JSON e codice locale
1 se un controllo richiede attenzione: **non cambia gli exit code dei job reali**.

Il contratto dell'input è documentato nella docstring del valutatore ed esercitato
nei test: versione, intervallo completo di inventario, istante di osservazione,
esecuzioni con riepilogo applicativo e collegamenti esatti Scheduler/RunJob.
`basis=scheduler_run_job_audit` è una dichiarazione del lettore fidato, non una
prova crittografica né un permesso: non va inventata a partire da orari vicini,
`creator_matches_scheduler`, stato verde o variabili del container.
Un inventario troncato o una lettura fallita deve usare `complete=false`.

Replay locale dei tre esiti salvati (mattino 24/25, sera 24): tutti sono
`origin_unverified`, perché gli export precedenti non contengono il collegamento
esatto. I conteggi di 48/50/50 accettazioni FCM restano nell'evidenza originale;
non si conclude che i job siano falliti. Si conclude che il nuovo controllo non
può certificare da quegli export l'origine richiesta. Nessun collegamento fittizio
è stato aggiunto per ottenere un esito verde.

Evidenze locali ignorate da Git: `.tmp/summary-local-date-monitor-20261025/`
con input e replay storico, esiti test e inventario hash. Precedenti verifiche:
[incastro ICON–sintesi](ICON_SUMMARY_DST_REVIEW_20261025.md) e
[audit del cambio d'ora](SUMMARY_JOBS_DST_AUDIT_20261025.md).

## Verifiche locali completate

Preparazione iniziale: 82 test. Revisione successiva: **84 test**, zero errori/fallimenti, zero saltati. Accesso socket bloccato durante i
test; servizi, sorgenti, storage e FCM sostituiti da simulazioni locali.

- Giorni da 23/24/25 ore, primavera 2026/2027, autunno 2026 e mezzanotte.
- Successo di ieri, invocazione manuale, origine incerta, target errato,
  duplicati dello stesso log e due esecuzioni distinte.
- Fine del margine, ritardo, fallimento, parziale, FCM non confermato,
  retry/in-progress, assenza destinatari, deduplica e rinunce.
- Contatori mancanti/invalidi e tentativi senza esito non diventano successo.
- Trace con dati mancanti, rotazione corsa, limite dimensionale e dati privati.
- Regressioni delle due sintesi, delle consegne e della compatibilità dei log.

Un primo test serale usava per errore la corsa 00 UTC, oltre il limite di età
serale: corretta la fixture con quella valida 12 UTC, senza allentare la regola
applicativa. Un lancio dalla radice senza il percorso `backend` è stato corretto;
la sessione finale completa è quella registrata nell'evidenza test.

## Revisione per main del 25 ottobre

Commit iniziale revisionato: `06aa2016`. Due casi corretti prima della PR:

- una sintesi non è completa se un destinatario idoneo non ha ricevuto neppure
  un tentativo e non esiste un esito che spieghi l’assenza;
- i vecchi log senza `source_trace` restano compatibili, ma un trace presente
  con tipo/struttura invalidi diventa `check_unavailable`, mai ignorato per ottenere verde.

Regressioni mirate aggiunte; 84 test locali superati con rete bloccata.
Evidenze: `.tmp/summary-local-date-review-20261025/` nel worktree dedicato.
Diff, collegamenti e scopo controllati: nessuna variazione a frontend, AAB,
endpoint, orari, policy attive, job cloud, invii o destinatari.
La prova sul dispositivo non è pertinente a questo diff backend: i test dei
servizi simulati verificano che contenuti, deduplica ed esiti restino invariati;
non viene dichiarata una nuova prova reale di ricezione o del runtime cloud.

Pubblicazione del ramo, PR verso main e CI sono state le sole azioni remote
in questa fase. L’integrazione operativa descritta sotto resta da completare.

## Promozione verificata su main

- [PR 24](https://github.com/meteofriul/meteofriul-app/pull/24) integrata il 25 ottobre 2026 alle 09:22 UTC.
- Commit revisionato della PR: `8feff27f74e28fe4b11a6ace1fcc4fe0dbf169e5`,
  comprendente il lavoro iniziale `06aa2016` e le due correzioni di revisione.
- Merge del codice su main: `8a47c75216f350fc541c03916bdc54350acb49a3`.
- [CI della PR](https://github.com/meteofriul/meteofriul-app/actions/runs/40179943732): **success**, backend/frontend/hosting-preview-tool verdi.
- [CI di main](https://github.com/meteofriul/meteofriul-app/actions/runs/40180348224): **success** sul merge esatto,
  stessi tre controlli verdi, nessuna esecuzione duplicata da cancellare.

Le protezioni di main sono state rispettate: merge tramite PR, nessun push diretto
né bypass amministrativo. Il checkout locale di main è stato aggiornato mediante
fast-forward. Questo aggiornamento finale di README e verbali passa tramite PR
solo Markdown; la CI completa lo salta per configurazione, e il codice resta
identico a quello verificato nella CI sopra. Evidenze dettagliate e hash restano
in `.tmp/summary-local-date-review-20261025/`.

La promozione non attiva nuovi controlli nel cloud. Orari, policy operative,
immagini distribuite, invii e pacchetti Web/Android rimangono invariati.

## Prima di attivare: passaggio ancora necessario

Questo ramo prepara il **motore locale e la diagnostica**, non sostituisce ancora
l'allarme operativo. Non è sufficiente distribuire soltanto questi file:

1. Completare e verificare l'adattatore di sola lettura che ricava da evidenze
   fidate il collegamento esatto Scheduler → RunJob → esecuzione. Gli export
   attuali non consentono di attestarlo; mantenere lo stato esplicito di incertezza.
   Nessuna modifica agli orari o aggiunta di dispatcher è autorizzata da questo lavoro.
2. Collegare il risultato al monitoraggio operativo, con un segnale separato
   per errore del controllo. Verificare IAM e disponibilità dei log prima del deploy.
   I dati delle due sintesi non devono consumare il budget già assegnato al monitor
   ICON. Per questo non è stato aggiunto un aggancio improvvisato al suo runner.
3. Dichiarare la latenza: con il monitor esistente ai minuti 10/40, le scadenze
   locali 07:45 e 21:00 verrebbero viste alle 08:10 e 21:10, più i tempi del
   monitoraggio. Non promettere un allarme alle 07:45 se manca un controllo a quell'ora.
4. Conservare le policy su errori del job e invocazione Scheduler. Rimuovere o
   sostituire il vecchio controllo a 25 ore soltanto dopo prova del nuovo segnale.
   Nessun allarme è stato disabilitato, duplicato o modificato in questo ramo.

Per la sola diagnostica il rollback è il codice precedente: nessuno schema
persistito o contratto dell'app cambia; i vecchi log senza trace restano leggibili.
L'integrazione operativa richiede una revisione e autorizzazione separata; non
richiede AAB. La pubblicazione di sorgenti/GitHub resta distinta dal deploy.

## Eventi e stato del lavoro

Il follow-up `verifica-eventi-pordenone-pensa-e-barcolana` resta ACTIVE e punta
alla corsa del **26 ottobre 04:00 UTC = 05:00 Europe/Rome**, controllo dalle 05:15.
Rimane sul worktree Eventi originale; i suoi script e documenti non sono spostati.
Il lavoro non committato precedente su quel ramo è preservato. Nessuna prova
sul telefono, installazione, emulatore, AAB, deploy o invio manuale qui.
