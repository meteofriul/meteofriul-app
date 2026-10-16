# Eventi — distribuzione Fase 0 e verifica della TEST

Data: 13 ottobre 2026. Ramo: `codex/events-card-quarantine`.
Commit distribuito: `9718e2bca062c1d42922558ce096f38b3cca92e0`.
Correzioni applicative: `27045887`; i commit successivi prima del deploy sono
solo documentazione. L'utente ha autorizzato aggiornamento worker/API,
esecuzione completa e verifica nella TEST con «procedi».

## Stato della verifica

**Worker e API aggiornati; catalogo recuperato e verificato nella TEST nativa.**
Il primo ciclo completo è fallito per inventario TurismoFVG incompleto. Un
secondo ciclo, autorizzato separatamente e limitato a TurismoFVG, è riuscito.
Quindi questa prova è un **ciclo completo fallito seguito da recupero mirato**,
non un ciclo integrale riuscito al primo tentativo.

Il catalogo finale contiene 15 fonti pubblicabili (11 `fresh`, 4 `partial`),
1.586 schede grezze e 6 schede in quarantena. Le schede in quarantena restano
escluse; non hanno fatto fallire il recupero. Nessuna fonte è rimasta `stale`.
Il risultato non dimostra ancora l'affidabilità del successivo ciclo giornaliero.

## 1. Candidato e build

- Repository del ramo pulito prima della build. Archivio prodotto da
  `git archive HEAD`, limitato al codice backend e ai file richiesti dal
  Dockerfile; non contiene file locali ignorati, chiavi o configurazioni private.
- Cloud Build `1076136f-7172-4eba-9afa-5ea360f4cc18`, regione `europe-west1`,
  progetto `meteo-friul`: **SUCCESS**, completata alle 18:41:34 UTC.
- Dockerfile `backend/Dockerfile.events-pilot`: 402 test `unittest` Eventi
  e 7 test Palazzo Attems passati nel container. Sono aggiuntivi ai controlli
  locali documentati nella Fase 0; non equivalgono alla CI GitHub completa.
- Immagine comune a worker e API:
  `europe-west1-docker.pkg.dev/meteo-friul/meteofriul/events-worker@sha256:b3f437dfd2d802e0ea1110edf43df9c9d2f8c0eaa17bb5b7780e58fdf0462891`.
- Etichetta dell'immagine `org.opencontainers.image.revision` impostata sul
  commit distribuito. Tag di costruzione: `phase0-9718e2bc-20261013`.

## 2. Distribuzione e invarianti

API aggiornata per prima: revisione `meteofriul-events-00013-zpm`, traffico
100%. `/health` HTTP 200; lettura del catalogo preesistente riuscita prima
di avviare la nuova raccolta. Pordenone, raggio 20 km: 281 schede; snapshot
precedente `2026-10-13T09:40:04.618654+00:00`.

Confrontati i documenti Cloud Run prima/dopo: le specifiche runtime di API
e job sono identiche tolto il campo immagine. Conservati:

- Worker: 1 task, 1 vCPU, 1 GiB, timeout 900 secondi, zero retry automatici,
  account `meteofriul-events-writer`.
- API: `gunicorn`, 1 worker e 4 thread, concorrenza 4, 1 vCPU, 256 MiB,
  timeout 30 secondi, account `meteofriul-events-reader`.
- Bucket `meteo-friul-weather-data`, oggetto `pilot/events/v1/catalog.json`;
  variabili d'ambiente invariate.
- Nessuna nuova installazione Android o build APK/AAB. Nessuna operazione
  GitHub, Firebase o Cloudflare. Nessuna promozione di questo candidato a `main`.

Il singolo ciclo completo autorizzato è stato avviato dopo aver verificato
l'assenza di esecuzioni attive dello stesso job. Nome:
`meteofriul-events-refresh-hbz5f`; creazione 18:45:13 UTC, avvio 18:45:18 UTC.

## 3. Allarme Eventi

Aggiornata esclusivamente `documentation` della policy
`projects/meteo-friul/alertPolicies/13483592592255950505`, usando una PATCH
con `updateMask=documentation`. Confronto prima/dopo: condizioni, filtri,
soglie, destinatari e strategia di notifica invariati. L'audit dello script
`sync-cloud-run-job-monitoring.ps1 -Mode Audit -PolicyKey events-failures`
restituisce `unchanged`, `ready=true` dopo l'aggiornamento.

Il testo ora chiarisce che, dopo un fallimento, il catalogo può già contenere
aggiornamenti delle fonti sane; i vecchi lotti delle fonti fallite restano
conservati per diagnosi ma esclusi dall'API. Gli avvisi separati sui candidati
Palazzo Attems/GiroFVG non sono stati disattivati o modificati.

## 4. Riferimenti di ripristino

Solo immagini, senza cambiare la configurazione operativa:

- Worker precedente:
  `europe-west1-docker.pkg.dev/meteo-friul/meteofriul/events-worker@sha256:926f97d9a45df8f8845d89aaa4ab9c23c51893fc39f095a01e23f7ec102c89c4`.
- API precedente: revisione `meteofriul-events-00012-pfn`, immagine
  `europe-west1-docker.pkg.dev/meteo-friul/meteofriul/events-worker@sha256:3d6afce26fd089161047fc32b9d088365644a50328ccfeb4499b0066fddf3c6e`.
- Catalogo preesistente e relativi metadati salvati localmente prima del ciclo.
  Un rollback dell'immagine non ripristina automaticamente il catalogo;
  una riscrittura del JSON è una decisione separata, non eseguita qui.

## 5. Evidenze

Evidenze locali ignorate da Git in `.dev-logs/events-phase0-deploy-9718e2bc/`:
configurazioni prima/dopo, archivio/hash della build, log container, policy,
stato esecuzione e copie del catalogo. La sottocartella `phone/` contiene
le prove della TEST `0.1.14-tester` (`300031`) sul Samsung SM-A525F Android 14.
La cache Eventi è letta soltanto per verificare l'aggiornamento: nessuna
cancellazione dei dati app. I risultati finali sono riportati nelle sezioni successive.

Riferimenti: [correzioni Fase 0](EVENTI_FASE_0_CORREZIONI_AUDIT_2026-10-13.md),
[collaudo locale e pilot ripristinato](EVENTI_FASE_0_COLLAUDO_LOCALE_2026-10-13.md),
[architettura job e allarmi](EVENTI_ARCHITETTURA_JOB_E_ALLARMI_2026-10-13.md).


## 6. Ciclo completo e causa del fallimento

| Esecuzione | Avvio UTC | Fine UTC | Esito |
| --- | --- | --- | --- |
| `meteofriul-events-refresh-hbz5f` | 18:45:18 | 18:54:06 | Fallita, circa 8 min 48 s, exit 1 |
| `meteofriul-events-refresh-vc7lk` | 18:58:44 | 18:59:56 | Recupero TurismoFVG riuscito, 72,39 s, exit 0 |

Gli orari locali del 13 ottobre sono UTC + 2. Il primo ciclo ha salvato il
catalogo prima di terminare con
`event source verification failed: TurismoFVG`. Le altre 14 fonti sono state
aggiornate. Azalea, che aveva avuto un timeout nel collaudo locale, questa
volta è riuscita con 7 schede.

TurismoFVG aveva completato l'indice (190 pagine, 1.516 riferimenti nel
calendario; 1.216 URL nell'inventario risultante), ma restavano **7 risultati
pendenti**, con `source_complete=false`, `within_budget=true`. Le due schede
note da rivedere non sono il motivo del blocco: il controllo non aveva ancora
verificato tutte le pagine necessarie. Il lotto precedente, 1.167 schede,
è stato conservato come `stale` e temporaneamente escluso dall'API.

### Limite diagnostico rilevato

Nel tentativo fallito `last_attempt_verification.pending=7`, mentre
`last_attempt_pending_count=0`. I due campi provengono da strutture diverse:
il primo dal controllo TurismoFVG, il secondo dai `detail_candidates` restituiti
dall'adapter. Questo percorso di errore non restituisce i sette URL pendenti
come `detail_candidates`; la loro identità e il relativo errore non sono
conservati nel catalogo. Il checkpoint precedente verificato è mantenuto
intenzionalmente. Non si può quindi attribuire con certezza il problema a
sette errori HTTP, a sette schede non conformi o a un timeout soltanto da
questo catalogo. Non è stato dichiarato un guasto generale del sito senza prova.

Il recupero riuscito dimostra che il problema non era persistente in quel
secondo tentativo; non identifica la causa del primo. Da correggere in un
intervento successivo: registrare URL, stato e motivo dei risultati pendenti,
poi distinguere i problemi di singole pagine dai guasti dell'intera fonte.
Nessun gate è stato indebolito in questa distribuzione.

## 7. Recupero autorizzato e catalogo finale

L'utente ha autorizzato separatamente «Sì, recupera solo TurismoFVG».
Il comando `--retry-failed` è stato passato come override dell'esecuzione
`vc7lk`, dopo la conclusione di `hbz5f`. Nessun terzo ciclo è stato avviato.

Verifiche su JSON e configurazione prima/dopo:

- Tutti i 14 lotti diversi da TurismoFVG sono identici, inclusi metadati e
  diagnostici. I monitor sono anch'essi identici: il recupero non li esegue.
- Il comando permanente del job non ha acquisito `--retry-failed`.
  Il prossimo avvio pianificato farà ancora la raccolta completa.
- Scheduler `meteofriul-events-refresh`: `0 4 * * *`, `Etc/UTC`, abilitato;
  confronto del documento prima/dopo identico. Il 14 ottobre corrisponde
  alle 06:00 italiane. Non è stato creato un job temporaneo.
- Snapshot finale: `2026-10-13T18:58:54.788167+00:00`.
- Scrittura Storage: 18:59:54 UTC; generazione `1791917994265502`.
- TurismoFVG: `source_complete=true`, `pending=0`, `ambiguous=0`,
  1.209 schede, 1.121 con anteprima, 3 quarantene. Il controllo regionale
  riporta 2 revisioni prima della proiezione; il conteggio finale delle
  quarantene è 3 e non va sostituito con quel contatore intermedio.

| Fonte | Stato | Schede grezze | Quarantene |
| --- | --- | ---: | ---: |
| TurismoFVG | `partial` | 1209 | 3 |
| Pordenonelegge | `fresh` | 0 | 0 |
| Azalea | `fresh` | 7 | 0 |
| CSS Udine | `partial` | 157 | 1 |
| Pordenone Pensa | `partial` | 0 | 1 |
| Teatro Verdi Pordenone | `fresh` | 88 | 0 |
| Teatro Verdi Trieste | `fresh` | 70 | 0 |
| Le Giornate del Cinema Muto | `fresh` | 0 | 0 |
| Paesi in Festa | `fresh` | 17 | 0 |
| SagreFVG | `partial` | 14 | 1 |
| Villa Manin | `fresh` | 4 | 0 |
| Magazzino delle Idee | `fresh` | 0 | 0 |
| MESS | `fresh` | 17 | 0 |
| Galleria Spazzapan | `fresh` | 2 | 0 |
| Barcolana | `fresh` | 1 | 0 |

Le 1.586 schede sono il totale grezzo del catalogo, non un totale già
filtrato e deduplicato dell'app. Alcune fonti verificate hanno zero schede;
la pubblicabilità dipende dalla relativa verifica, non dal semplice zero.
I monitor Palazzo Attems e GiroFVG conservano `review_required` del controllo
delle 09:40 UTC; l'inventario annuale TurismoFVG conserva la verifica del
12 ottobre. Non sono stati ricontrollati dal recupero.

## 8. API e prova sul telefono reale

L'API online è stata letta fino all'ultima pagina per cinque località.
Per ciascuna, la concatenazione delle risposte è identica alla query locale
sullo stesso catalogo, con snapshot costante e totale coerente.

| Località | Raggio | Schede API | Pagine da massimo 100 |
| --- | ---: | ---: | ---: |
| Pordenone | 20 km | 299 | 3 |
| Caneva | 50 km | 400 | 4 |
| Udine | 50 km | 1185 | 12 |
| Trieste | 50 km | 579 | 6 |
| Gorizia | 50 km | 1031 | 11 |

Ulteriori controlli: `/health` HTTP 200; richiesta con snapshot incompatibile
respinta con HTTP 409; una sola Sagra del Rosario a Caneva, categoria `sagra`,
fonte preferita TurismoFVG; una sola Barcolana nella query Trieste. Non è una
prova esaustiva di tutti i possibili doppioni.

`catalog_status=degraded` è coerente con le quattro fonti `partial`: i tag
sono esclusivamente `quarantined_cards`. Non è rimasto `incomplete_source`
o un lotto scaduto. I controlli preservano il significato dei campi: un
recupero riuscito non rende tutte le schede automaticamente conformi.

### TEST nativa già installata

Samsung SM-A525F, Android 14; package `com.meteofriul.app.tester`, versione
`0.1.14-tester`, codice `300031`. Nessuna nuova installazione, build o
cancellazione dati. La località Pordenone e la posizione automatica sono
state mantenute durante tutta la prova.

Un osservatore delle richieste della WebView ha registrato il caricamento
reale dal servizio Eventi online: **100 + 100 + 99 schede**, tutte HTTP 200,
nessuna da cache HTTP o service worker, stesso snapshot finale del bucket.
La cache applicativa passa dal totale precedente 281 a 299. Non sono state
iniettate richieste di rete, risposte o modifiche della cache tramite debug.
I primi tentativi di gesto sulla scheda non hanno prodotto una richiesta
osservata; la riapertura della sezione ha permesso di completare e verificare
il caricamento. Non si usa questa prova per certificare il gesto di refresh.

Verifica visiva e gerarchia UI:

- “Feste e sagre”, oggi: Sagra del Rosario presente una volta.
- Anteprima: copertina 2026 caricata, descrizione leggibile, date 2–18 ottobre,
  Via Roma 1 a Caneva, fonte TurismoFVG e pulsanti presenti.
- “Prossimi”: Sagra delle Castagne e Pan Zal, entrambe dal 15 ottobre.
- Ripristinati “Oggi” e “Tutti”; app lasciata sulla lista Eventi. La sola
  porta di debug creata per la prova (`tcp:51015`) è stata rimossa, così come
  il dump temporaneo sul dispositivo.

Questa è una verifica dell'app TEST esistente contro il backend aggiornato.
Non è una nuova certificazione Android release, non include una nuova prova
visiva del programma di tutti i festival e non autorizza una AAB.

## 9. Allarmi, rischi residui e seguito

Il fallimento `hbz5f` è reale e può generare l'email Eventi anche se il
catalogo è stato recuperato poco dopo. La policy conta esecuzioni fallite
nella finestra di due ore: il successo `vc7lk` non cancella subito la metrica
del precedente fallimento. Un'email di recupero indica il rientro della
condizione del monitor, non dimostra da sola il successo di una nuova raccolta.

Il deploy e il recupero sono conclusi. Resta da valutare:

1. Il prossimo ciclo completo già pianificato: non c'è ancora un ciclo
   completo interamente verde con questa immagine. Non è stata aggiunta una
   nuova automazione di monitoraggio o una nuova esecuzione in questa prova.
2. La diagnostica dei sette risultati TurismoFVG rimasti pendenti nel primo
   tentativo; occorre renderli identificabili prima di decidere se trattarli
   come quarantene o come guasto di fonte. Non si deduce l'una o l'altra
   causa dal solo contatore.
3. Le sei quarantene e i due monitor candidati sono lavoro separato e restano
   tracciati; non bloccano le schede sane già pubblicate.
4. Promozione del ramo a `main` locale e futura sincronizzazione GitHub:
   non effettuate da questa distribuzione. Nessun workflow GitHub avviato.

Conservati separatamente catalogo e controllo API del ciclo fallito e del
recupero, per evitare che il risultato positivo cancelli la diagnosi.
`manifest.json` elenca file, dimensioni e SHA-256 delle evidenze locali.
