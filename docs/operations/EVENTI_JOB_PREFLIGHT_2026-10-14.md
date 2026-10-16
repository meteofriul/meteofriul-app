# Eventi — confronto online e aggiornamento preparato

Verifica del 14 ottobre 2026, circa 21:03 Europe/Rome. Preparazione locale
sul ramo `codex/community-reports-simplification`; codice da distribuire
preso esattamente da `f7fe8e9696f5b61a54fda27617ec99834993f8b4`, ramo
`codex/events-card-quarantine`.

**Preparazione completata; nessuna nuova build cloud o distribuzione eseguita.**
Il «procedi» segue la proposta di confrontare le versioni e preparare
l'aggiornamento. Non viene interpretato come autorizzazione a modificare
la produzione, che nelle istruzioni dell'utente è un passaggio separato.

**Seguito autorizzato:** l'utente ha successivamente autorizzato esplicitamente
job, API e un ciclo completo. La [distribuzione e verifica](EVENTI_DEPLOY_ISOLAMENTO_2026-10-14.md)
registra l'aggiornamento a `f7fe8e96`, 14 fonti pubblicabili e il fallimento
separato di Spazzapan. Le indicazioni «non distribuito» qui sotto descrivono
esclusivamente il momento del preflight.

## Versione realmente in uso

La chat **Audita la ricerca eventi** e il [resoconto Fase 0](EVENTI_FASE_0_DEPLOY_E_TEST_2026-10-13.md)
documentano un aggiornamento precedente del 13 ottobre. Le letture Cloud Run
odierne confermano che job e API usano ancora quella versione `9718e2bc`:

- Job `meteofriul-events-refresh`, generazione 37.
- API `meteofriul-events`, revisione `meteofriul-events-00013-zpm`, traffico 100%.
- Immagine comune:
  `europe-west1-docker.pkg.dev/meteo-friul/meteofriul/events-worker@sha256:b3f437dfd2d802e0ea1110edf43df9c9d2f8c0eaa17bb5b7780e58fdf0462891`.
- Cloud Build originaria `1076136f-7172-4eba-9afa-5ea360f4cc18`: `SUCCESS`,
  etichetta revision `9718e2bca062c1d42922558ce096f38b3cca92e0`.
- Scheduler abilitato, `0 4 * * *`, `Etc/UTC` (06:00 italiane il 14 ottobre).
- Account attivo `meteofriul@gmail.com`, progetto `meteo-friul`, regione
  `europe-west1`.

Non è quindi corretto dire che i job Eventi non siano mai stati aggiornati:
manca la distribuzione dell'ultima correzione TurismoFVG `f7fe8e96`.
Il job legacy `meteofriul-event-source-publication-control` non raccoglie
le 15 fonti e rimane fuori da questa preparazione.

## Ultimo ciclo e differenza rispetto alla TEST

Esecuzione schedulata `meteofriul-events-refresh-d6zqm`: avvio
`2026-10-14T04:00:09Z`, fine `04:07:13Z`, **fallita**. Il catalogo è stato
comunque scritto, generazione `1791950831552254`, snapshot
`2026-10-14T04:00:26.735899+00:00`.

La fonte fallita è **Magazzino delle Idee**, per `ReadTimeout` di 15 secondi;
il suo lotto è `stale`. Le altre 14 fonti sono `fresh`/`partial`.
TurismoFVG contiene 1.220 schede e tre quarantene: non è la causa del
fallimento di questo ciclo.

Nel [collaudo locale del pomeriggio](COMMUNITY_EVENTS_TEST_INTEGRATION_2026-10-14.md)
Magazzino è invece riuscito; Azalea e Galleria Spazzapan sono state respinte
per inventari non riconosciuti/modificati. Questa differenza non prova da
sola una regressione: orario e ambiente di raccolta sono differenti.
I tre adattatori risultano identici byte per byte fra `9718e2bc` e `f7fe8e96`.
La correzione riguarda TurismoFVG e non risolve automaticamente questi tre
problemi indipendenti. I gate rimangono attivi, senza forzare la pubblicazione.

## Candidato e verifiche

Il pacchetto è estratto dal commit Eventi, non dal contenuto corrente del
ramo Community. Include solo `backend/app`, il Dockerfile e i test/fixture
che il Dockerfile richiede; nessun asset locale, APK o chiave privata.
Le cartelle Eventi e la nuova suite corrispondono al codice della candidata
Android `92eb9337` già [provata sul telefono](COMMUNITY_EVENTS_ANDROID_TEST_2026-10-14.md).

| Controllo | Esito |
| --- | --- |
| Pulizia workspace canonico | PASS, 3.239 file tracciati |
| Suite selezionata dal Dockerfile, sul pacchetto esatto | 421 test Eventi + 7 Palazzo Attems PASS |
| API `/health` online | HTTP 200 |
| API online confrontata con WSGI candidato sul medesimo catalogo | Payload completi identici su cinque località, 15 pagine |
| Pordenone / Udine / Trieste / Gorizia / Tolmezzo, raggio 20 km | 306 / 431 / 264 / 184 / 72 schede |
| CORS Android `http://localhost` | PASS su tutte le pagine |
| Snapshot incompatibile | HTTP 409, come previsto |
| Immagine container nuova | NON costruita: test eseguiti su Windows Python 3.13 |

I 428 test non sono una nuova esecuzione cloud. La raccolta reale e la prova
TEST del 14 ottobre restano quelle documentate nei resoconti collegati;
qui non sono state ripetute né dichiarate integralmente verdi.

Pacchetto locale:
`.tmp/events-job-update-2026-10-14/events-f7fe8e96-build-context.tar.gz`
(2.016.524 byte), SHA-256
`58ccb2f9a24312eca52392277820e9b81a2cd6dd84148a1092eb175ae8a7fb02`.
Configurazione pronta: `.tmp/events-job-update-2026-10-14/context/cloudbuild.json`.
Tag proposto: `events-worker:detail-isolation-f7fe8e96-20261014`;
un tag preparato non equivale a un'immagine già presente nel registry.

## Passaggio online predisposto

1. Rileggere configurazioni e assenza di esecuzioni attive, quindi costruire
   il pacchetto isolato con Cloud Build e i test del Dockerfile. Identificare
   il digest risultante e l'etichetta del commit.
2. Aggiornare prima l'API e verificarne salute e lettura del catalogo
   preesistente. Aggiornare poi il solo job `meteofriul-events-refresh`.
3. Confrontare le specifiche prima/dopo, ammettendo il solo cambio immagine:
   account, variabili, chiave Storage, risorse, timeout, retry e scheduler
   devono rimanere invariati.
4. Eseguire un ciclo completo autorizzato e leggere esito, quarantene,
   diagnostici, catalogo e tutte le pagine API. Non rilanciare automaticamente
   un ciclo fallito né trattare un lotto `stale` come quarantena di una scheda.
5. Per il ripristino delle immagini conservare il digest attuale sopra.
   Il ripristino di un catalogo è un'operazione distinta: la copia locale
   non viene caricata automaticamente nello Storage.

I problemi Android/R8 riguardano la promozione dell'APK e non certificano né
invalidano automaticamente il worker Eventi. Questa preparazione non cambia
`main` (`5a68de5dc1607105f921d4d2b731170f1a8a0446`), produzione, policy email,
GitHub, telefono o Play.

[Riepilogo delle evidenze](evidence/events-job-preflight-2026-10-14/preflight-summary.json).
Configurazioni complete, catalogo, log dei test e archivio sono conservati
localmente in `.tmp/events-job-update-2026-10-14/`.
