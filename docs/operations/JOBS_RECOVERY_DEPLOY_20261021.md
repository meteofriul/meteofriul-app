# Eventi e avvisi locali: deploy del 21 ottobre 2026

**Deploy completati e configurazioni verificate; corse ordinarie successive ancora da verificare.**
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
ridistribuiti. In particolare la sintesi serale deve ancora dimostrare il recupero.

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

## Corso ordinario da verificare

| Job | Corsa Europe/Rome | Stato a fine deploy |
| --- | --- | --- |
| Sintesi serale | 21 ottobre 20:45 | Attesa, immagine invariata |
| Avvisi locali | 21 ottobre 21:00 | Attesa, prima candidata |
| Eventi | 22 ottobre 06:00 | Attesa, prima candidata |

Follow-up `verifica-job-eventi-e-avvisi-dopo-aggiornamento`, ogni ora al minuto 20;
primo controllo utile serale alle 21:20, Eventi alle 06:20 con ultimo controllo
alle 07:20. Rimane silenzioso durante attesa o stato invariato; non avvia esecuzioni.
Si elimina dopo tutti gli esiti, oppure al termine della finestra dichiarando i limiti.

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
