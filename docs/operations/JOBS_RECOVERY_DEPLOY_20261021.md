# Eventi e avvisi locali: deploy del 21 ottobre 2026

**Corse ordinarie di riepilogo serale, avvisi locali ed Eventi verificate. Recupero delle tre fonti Eventi confermato; restano le revisioni editoriali indicate sotto.**
Il proprietario ha autorizzato i commit separati, la promozione su main e il passaggio
operativo dei job. Nessuna AAB, installazione, emulatore, pubblicazione Web,
push Git o esecuzione/invio manuale. Sponsor invariati e disattivati.

## Codice e immagini

- Correzioni Eventi: `09514a2d`; regressione avvisi e monitoraggio: `58bc2f91`.
- Main candidato: `18b88049ff5d69f401da3aca491c5a0e1df302ca`.
- Cloud Build `d7be8c19-3a33-4aef-ab98-6bf76c9794ca`: SUCCESS.
- Eventi: `europe-west1-docker.pkg.dev/meteo-friul/meteofriul/events-worker@sha256:06e4b2fb4f0655eca4f416e503b16ff24616e178ed03c56f501b1a15f678b95e`.
- Avvisi: `europe-west1-docker.pkg.dev/meteo-friul/meteofriul/backend@sha256:3b0cac97d0bbf533916b74ec24fd632f5fbc9f54c2266746a85fb31613aa8f74`.

Digest del manifest/configurazione ed etichetta OCI del commit verificati nel registry.
Le immagini sono costruite da un archivio dei file Git del candidato, senza dipendenze
provenienti da altri worktree. Il container ha eseguito **525 test Eventi**
(503 pilot, 15 trasporto/recupero, 7 Attems) e **182 test avvisi/riepiloghi**.
Le regressioni locali precedenti erano 142 Eventi e 182 avvisi: sono verifiche
in ambienti diversi, non ulteriori casi distinti da sommare.

## Risorse aggiornate e invarianti

Progetto `meteo-friul`, regione `europe-west1`, account previsto verificato.

| Risorsa | Cambiamento | Verifica |
| --- | --- | --- |
| `meteofriul-events-refresh` | Sola immagine | Tutto il resto della specifica e Scheduler identici |
| `meteofriul-local-notice` | Immagine e `LOCAL_NOTICE_ICON_ACCUMULATION_SIDECAR_ENABLED=true` | Tutto il resto della specifica e Scheduler identici |
| Due policy avvisi | Titoli delle condizioni e documentazione | Soglie, finestre, canali, stato e strategia di notifica identici |

Gli invii ordinari restano `send`, con gli stessi destinatari e controlli.
Non sono stati avviati job tramite CLI, API o QA. Le ultime esecuzioni visibili
alla verifica del deploy sono ancora quelle precedenti: Eventi 06:00 e avvisi
20:00 usano i vecchi digest. Il fallimento degli avvisi alle 20:00 non appartiene
alla candidata appena distribuita.

L'aggiornamento Eventi conserva il catalogo corrente fino alla raccolta ordinaria.
CAMS, produttori meteo, allerte FVG/nazionali, API e riepiloghi non sono stati
ridistribuiti. La sintesi serale ha successivamente dimostrato il recupero
nella corsa ordinaria del 21 ottobre, descritta sotto.

## Compatibilità Eventi

Il lettore API effettivamente in servizio, commit
`2a2a5f106b8185fd9a8f773b64552b20253df7a4`, legge sia il catalogo precedente sia
quello proiettato localmente con Spazzapan recuperata. Il cambiamento di risultati
prodotto dal recupero è coerente su cinque località. Cinque risposte API reali
sono state confrontate integralmente con il lettore effettivamente distribuito;
HTTP 200, snapshot e CORS corretti. Nessun catalogo proiettato è stato pubblicato.

**Differenza preesistente da non confondere con la correzione:** il lettore su main
supporta gli eventi TurismoFVG `end_only`; quello attivo ne omette uno nel campione
di Tolmezzo. Inoltre l'API su main espone `source_updated_at`, assente nella vecchia.
Queste differenze non impediscono il recupero Spazzapan e non giustificano dichiarare
identici i due lettori in ogni campo. L'API è rimasta invariata; l'allineamento
completo di quelle funzionalità resta un intervento distinto.

## Verifica locale con dati pubblicati correnti

Dopo il deploy, sola lettura del consumatore candidato su Chions (093013) e Udine
(030129), con valutazione locale e senza chiamare il servizio di consegna:

- Corsa `20261021T120000Z`, sidecar verificato per entrambi.
- **6/6 fenomeni valutabili** per entrambi, tolleranze effettivamente usate.
- Nessun candidato, nessun errore strutturale, nessun audit/outbox scritto.

Questo è un campione su due comuni e un istante, non l'esito del prossimo job.
Il replay della vecchia corsa `20261021T000000Z` conserva il comportamento
5/6 su Chions: la temperatura percepita mancante non viene corretta artificialmente.
[Regressione e limiti](LOCAL_NOTICE_CHIONS_READINESS_20261021.md).

## Monitoraggio

Si conserva exit 1 per `data_degraded`: il passaggio non nasconde i dati incompleti.
Le email possono quindi continuare anche se cinque fenomeni su sei sono valutabili.
Le due policy ora chiedono esplicitamente di distinguere:

- `data_degraded` con `failed=0`: disponibilità incompleta, da leggere con denominatori,
  fenomeni, cause e classi esclusive `only_resolution`/`other_or_mixed`;
- errori di sorgente, contratto, sicurezza, persistenza o consegna;
- FCM accettato, deduplicazione e consegna non confermata.

Non è stato aggiunto un allarme numerico di qualità né modificato l'exit code.
Un loro eventuale cambiamento resta coordinato e separato: i soli contatori nei
log non sono già una nuova policy. Il `security_failed` delle 06:00 resta non
spiegato puntualmente e non è dichiarato risolto.

## Rollback pronto, senza esecuzione automatica

**Eventi:** immagine precedente ancora disponibile e verificata nel registry:
`europe-west1-docker.pkg.dev/meteo-friul/meteofriul/events-worker@sha256:529d93d115de05ff8d6039d09545d2d2e9da5fd87ace227b22f4be6e7b0c296b`.
Un ritorno alla sola immagine mantiene il formato del catalogo ma reintroduce
la revisione Spazzapan e i timeout senza ripetizione. Non ripristinare a mano
cataloghi vecchi e non avviare raccolte per forzare il ripristino.

**Avvisi:** ripiego conservativo sulla stessa immagine candidata verificata,
con il solo flag sidecar portato a `false`. Mantiene i mancanti come tali e la
valutazione per fenomeno, rinunciando al recupero tramite tolleranze. Il replay
Chions 17:00 con flag disabilitato dimostra 3/6 valutabili, senza conversioni in zero.
La vecchia immagine `7af9d579...` è conservata nelle evidenze ma non costituisce
il rollback consigliato: reintroduce il problema dei null e delle ore scartate.
Se il problema riguarda la logica nuova e non i sidecar, fermarsi per una decisione;
non nascondere un guasto con quel rollback parziale.

Operazioni di ripristino, solo se deliberate, usando il percorso locale del Cloud SDK:

```powershell
python $GcloudScript run jobs update meteofriul-events-refresh --project=meteo-friul --account=meteofriul@gmail.com --region=europe-west1 --image=europe-west1-docker.pkg.dev/meteo-friul/meteofriul/events-worker@sha256:529d93d115de05ff8d6039d09545d2d2e9da5fd87ace227b22f4be6e7b0c296b
python $GcloudScript run jobs update meteofriul-local-notice --project=meteo-friul --account=meteofriul@gmail.com --region=europe-west1 --image=europe-west1-docker.pkg.dev/meteo-friul/meteofriul/backend@sha256:3b0cac97d0bbf533916b74ec24fd632f5fbc9f54c2266746a85fb31613aa8f74 --update-env-vars=LOCAL_NOTICE_ICON_ACCUMULATION_SIDECAR_ENABLED=false
```

Le configurazioni complete precedenti e successive sono conservate nelle evidenze
locali. Il ripristino dei testi Monitoring può usare i due JSON originali, senza
alterare soglie o destinatari. Nessun rollback è stato eseguito.

## Verifiche delle corse ordinarie

| Job | Corsa Europe/Rome | Stato aggiornato |
| --- | --- | --- |
| Sintesi serale | 21 ottobre 20:45 | Verificata: 42 invii accettati, zero errori; immagine invariata |
| Avvisi locali | 21 ottobre 21:00 | Verificati: 7/7 punti con tolleranze, 42/42 valutazioni possibili; nessun invio dovuto |
| Eventi | 22 ottobre 06:00 | Verificata: tre fonti recuperate, catalogo fresco e API coerenti; 12 schede in revisione |

### Riepilogo serale: controllo richiesto dal proprietario

Esecuzione `meteofriul-evening-forecast-jxgnh`, avviata alle **20:45:01** e
conclusa alle **20:46:45 Europe/Rome** del 21 ottobre. Digest invariato e atteso.
Scheduler ha completato la chiamata al job con HTTP 200; esecuzione riuscita.
Risultato applicativo: **42 dispositivi idonei, 42 tentativi, 42 invii accettati
da FCM**, su 14 gruppi. Zero errori di sorgente, sicurezza, persistenza o
consegna; zero invii non confermati, retry e duplicati.

Il proprietario riferisce di aver ricevuto una notifica nell'app alle 20:46:
è coerente con la corsa, ma il contenuto non è stato ispezionato. I contatori
FCM non dimostrano la visualizzazione su tutti i dispositivi.

Il verificatore locale inizialmente richiedeva il campo Scheduler `status=OK`;
il log di successo reale lo omette e riporta HTTP 200 in `AttemptFinished`.
La verifica è stata corretta controllando anche identità esatta del job e URL,
poi l'esito è stato ricalcolato sulle stesse evidenze, senza altre chiamate cloud.
[Esito sintetico](evidence/jobs-recovery-20261021/evening-ordinary-verification.json).
Nessun job o invio manuale; al termine di quel controllo avvisi locali ed
Eventi erano ancora aperti.

### Avvisi locali delle 21:00: tolleranze esercitate nella corsa ordinaria

Esecuzione `meteofriul-local-notice-46tlr`, avviata alle **21:00:04** e conclusa
alle **21:00:52 Europe/Rome** del 21 ottobre. Scheduler HTTP 200, digest candidato
atteso e flag sidecar `true` verificati anche nella specifica dell'esecuzione.
Corsa meteo `20261021T120000Z`; 18 dispositivi idonei raggruppati in **7 punti
canonici di 7 comuni**, senza moltiplicare il denominatore per i dispositivi.

- Metadati sidecar verificati in **7/7** punti; zero assenti, invalidi o disabilitati.
- Tolleranze effettivamente utilizzate in **7/7** punti.
- Sei rilevatori per punto: **42/42 valutazioni possibili**, zero parziali e zero
  non valutabili. Classi `only_resolution` e `other_or_mixed` entrambe a zero.
- Sette audit persistiti riconciliati in sola lettura con i contatori del job.
- Zero errori di sorgente, sicurezza, persistenza, audit o consegna; zero invii
  non confermati, retry, deduplicazioni e tentativi di consegna.

| Rilevatore | Valutazioni | Con tolleranza | Non valutabili | Candidati rilevati prima del filtro temporale |
| --- | ---: | ---: | ---: | ---: |
| Pioggia | 7 | 7 | 0 | 1 |
| Neve | 7 | 7 | 0 | 0 |
| Temporali | 7 | 0 | 0 | 0 |
| Ghiaccio | 7 | 0 | 0 | 0 |
| Vento | 7 | 0 | 0 | 0 |
| Caldo | 7 | 0 | 0 | 0 |

**Perché nessun invio:** a Chions il rilevatore ha riconosciuto un candidato
pioggia per le **23:00**, 119 minuti dopo la valutazione. L'audit registra
`onset_beyond_notice_window`: l'anticipo massimo è 60 minuti. Quindi il candidato
è rinviato dal filtro temporale, senza blocchi dei dati; non è una deduplicazione
né un errore di consegna. Un eventuale invio dipenderà dalle successive valutazioni
ordinarie, dai dati e dalle regole allora vigenti.

**Limiti:** i campi tollerati osservati sono `precipitation_mm` e `liquid_rain_mm`.
Il rilevatore neve usa anche questi campi indirettamente; la tolleranza specifica
`snow_water_equivalent_mm` non è stata esercitata. Non è una prova su nevicata
né una misura su tutti i 215 comuni. Non essendoci candidati tempestivi, questa
corsa non verifica una consegna FCM degli avvisi locali.
[Esito sintetico e denominatori](evidence/jobs-recovery-20261021/notices-ordinary-verification.json).

### Eventi del 22 ottobre: recupero verificato

Controllo eseguito alle **07:15 Europe/Rome**, sulla sola esecuzione ordinaria
`meteofriul-events-refresh-wv7tm` delle 06:00: avvio **06:00:13**, conclusione
**06:10:52**, immagine candidata attesa, Scheduler HTTP 200 ed esito riuscito.
Nessuna esecuzione o acquisizione avviata dal controllo.

Il catalogo ha snapshot `2026-10-22T04:01:32.873155+00:00` e generazione
`1792642249377461`; aggiornamento Storage compreso nella stessa esecuzione.
Tutte le **15 fonti** hanno dati aggiornati in quella corsa: **10 fresh** e
**5 partial**, nessuna stale o con errore di acquisizione. Sono presenti
**1.703 schede**, da non interpretare come totale univoco regionale deduplicato.

| Fonte oggetto della correzione | Stato | Schede pubblicate | Revisioni |
| --- | --- | ---: | ---: |
| Le Giornate del Cinema Muto | fresh | 0 | 0 |
| Barcolana | fresh | 1 | 0 |
| Galleria Spazzapan | fresh | 2 | 0 |

Cinema Muto ha completato la lettura del calendario ufficiale (97 record esaminati):
zero schede pubblicabili non equivale a un timeout. Barcolana ha esaminato 682 record;
Spazzapan conferma la raccolta riconciliata di eventi, mostre e notizie, senza revisioni.

Le API rispondono HTTP 200 e con CORS corretto sui tre punti di controllo:
Gradisca **294**, Udine **497**, Pordenone **358** risultati nel raggio configurato.
Snapshot e stati delle 15 fonti corrispondono al catalogo appena pubblicato.
È una verifica delle risposte API; non attesta la visualizzazione sull'app.

**Residui espliciti:** 12 schede restano escluse e in revisione su cinque fonti:
TurismoFVG 7, Azalea 1, CSS Udine 1, Pordenone Pensa 2, SagreFVG 1. Le API
espongono `quarantined_cards`; il catalogo salvato prima del deploy ne contava 15.
Le revisioni riguardano dettagli non risolti, calendari/date da verificare o
località non riconciliate e non sono state corrette automaticamente.

I monitor separati segnalano inoltre `review_required` per **Palazzo Attems**
(5 cambiamenti) e **GiroFVG** (19). Sono rilievi da esaminare separatamente;
il recupero dei tre connettori non li dichiara risolti e non abilita nuove fonti.
[Esito, contatori e limiti](evidence/jobs-recovery-20261021/events-ordinary-verification.json).

Pianificazione applicata al follow-up `verifica-job-eventi-e-avvisi-dopo-aggiornamento`,
ogni ora al minuto 20. Il controllo Eventi è completato; il follow-up è stato
eliminato il 22 ottobre dopo il salvataggio degli esiti. Le regole seguenti documentano la finestra
autorizzata, non controlli ancora pendenti.
Il proprietario accenderà il PC dopo l'orario inizialmente previsto: la verifica
può partire dalle 06:20 e resta valida **per tutta la giornata del 22 ottobre**,
al primo passaggio disponibile con PC e app aperti. La scadenza delle 07:20
è rimossa. Si legge sempre la corsa ordinaria delle 06:00; non se ne avvia un
altra e non la si sostituisce con una successiva. Il job cloud è indipendente
dall'accensione del PC.

Prima della finestra, durante l'attesa e su stato invariato il follow-up resta
silenzioso. Si elimina dopo esito completo o problema che richiede decisione;
fuori dal 21-22 ottobre si elimina senza esecuzioni e dichiara l'eventuale
verifica rimasta incompleta. Nessuna scadenza mancata equivale a un esito positivo.

Dalla radice canonica, lo script locale `.tmp/job-recovery-deploy-20261021/verify_ordinary.py`
legge soltanto: esecuzioni con digest atteso, log Scheduler, risultato applicativo,
qualità e consegne; per Eventi anche generazione/catalogo e risposte API. Riusa i
risultati completi. Conserva distinto il parziale da guasti e successo completo.
Non dedurre la visualizzazione sul telefono dall'accettazione FCM.

## Evidenze

[Manifest pubblico](evidence/jobs-recovery-20261021/deployment-checks.json),
[configurazione Cloud Build](evidence/jobs-recovery-20261021/cloudbuild.json),
[Dockerfile avvisi](evidence/jobs-recovery-20261021/Dockerfile.notices),
[runner dei test](evidence/jobs-recovery-20261021/run_notice_tests.py).
Configurazioni complete, log, cataloghi e script operativi sono in
`.tmp/job-recovery-deploy-20261021` della radice canonica, fuori da Git.
Una prima richiesta REST di aggiornamento Eventi è stata rifiutata con HTTP 400;
il job è stato riletto invariato prima del successivo aggiornamento riuscito via
`gcloud run jobs update`. Non ci sono state esecuzioni duplicate o manuali.
