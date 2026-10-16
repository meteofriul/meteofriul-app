# Eventi — distribuzione dell'isolamento TurismoFVG

Data: 14 ottobre 2026. L'utente ha autorizzato esplicitamente la distribuzione
di job e API Eventi e la verifica di un ciclo completo, escludendo main, APK e
Play. Questo resoconto segue la [preparazione verificata](EVENTI_JOB_PREFLIGHT_2026-10-14.md).

**Job e API aggiornati e verificati. Il ciclo completo è terminato con
14 fonti pubblicabili su 15: fallisce soltanto Galleria Spazzapan.**
TurismoFVG e l'API funzionano con il nuovo codice; non si dichiara il ciclo
interamente verde. Nessun secondo tentativo è stato avviato.

## Identità e build

- Codice distribuito: `f7fe8e9696f5b61a54fda27617ec99834993f8b4`, estratto
  direttamente dal ramo Eventi, senza includere le modifiche Community.
- Cloud Build `4c3e4b44-9797-4c08-b38c-c672d61e3d10`, `europe-west1`,
  progetto `meteo-friul`: `SUCCESS`, conclusa alle 21:22:58 italiane.
- **421 test Eventi e 7 Palazzo Attems passati nel container Linux**.
  I log Cloud Build confermano entrambi i conteggi e gli esiti `OK`.
- Immagine immutabile:
  `europe-west1-docker.pkg.dev/meteo-friul/meteofriul/events-worker@sha256:7e78c5ce2ecc39fa28a5666ca8680c8d0302a4b3c534579109739ed7e62bf672`.
- Manifest e configurazione dell'immagine riletti dal registry con verifica
  SHA-256; etichetta `org.opencontainers.image.revision` uguale al commit.
  Piattaforma Linux amd64, utente non privilegiato `65532:65532`.

## Distribuzione verificata

Aggiornata prima l'API `meteofriul-events`, revisione
`meteofriul-events-00014-hs2`, pronta dalle 21:24:31 italiane, traffico 100%.
Prima di aggiornare il worker sono stati verificati `/health`, CORS Android,
conflitto snapshot HTTP 409 e tutte le pagine di cinque località sul catalogo
preesistente: 15 pagine identiche al candidato, con 306/431/264/184/72 schede
rispettivamente per Pordenone/Udine/Trieste/Gorizia/Tolmezzo entro 20 km.

Aggiornato poi `meteofriul-events-refresh`, generazione 38, allo stesso digest.
Il confronto delle specifiche prima/dopo ammette soltanto il cambio immagine
e i metadati generati dalla distribuzione. Conservati:

- Worker: un task, parallelismo uno, 1 CPU, 1 GiB, timeout 900 secondi,
  zero retry automatici, account `meteofriul-events-writer`.
- API: comando gunicorn, un worker e quattro thread, concorrenza quattro,
  1 CPU, 256 MiB, timeout 30 secondi, account `meteofriul-events-reader`.
- Variabili, bucket `meteo-friul-weather-data` e oggetto
  `pilot/events/v1/catalog.json`.
- Scheduler abilitato, `0 4 * * *`, `Etc/UTC`: alle 06:00 italiane il
  14 ottobre. Nessun nuovo scheduler o job temporaneo.
- Policy email e job legacy `meteofriul-event-source-publication-control`.

## Ciclo completo autorizzato

Avviata una sola esecuzione, `meteofriul-events-refresh-7bds5`, dopo avere
verificato l'assenza di raccolte concorrenti. Avvio alle 21:26:24 italiane;
nessun argomento di override e nessun `--retry-failed`.
Alle 21:31:23, durante la raccolta, salute e lista Eventi erano HTTP 200 e
continuavano a servire coerentemente il catalogo precedente.

Fine alle **21:33:47 italiane**, durata **7 minuti e 22,57 secondi**, exit 1.
Sono state tentate tutte le 15 fonti; i timestamp dei lotti e dei tentativi
falliti corrispondono allo snapshot di questa esecuzione.

Il job ha salvato il catalogo prima di segnalare il fallimento:

- Snapshot `2026-10-14T19:26:54.991503+00:00`.
- Generazione Storage `1792006423455620`, scrittura alle 21:33:43 italiane.
- Dimensione 2.871.231 byte, inferiore al limite di 8 MiB.
- 10 fonti `fresh`, quattro `partial`, una `stale`.
- 1.648 schede grezze conservate, comprese due della fonte `stale` escluse
  dall'API; 1.646 schede nei lotti pubblicabili, prima di filtri e deduplica.
- 19 quarantene nei lotti pubblicabili: 15 TurismoFVG, una CSS Udine,
  una Pordenone Pensa, due SagreFVG.

| Fonte | Stato | Schede grezze | Quarantene |
| --- | --- | ---: | ---: |
| TurismoFVG | partial | 1.263 | 15 |
| Pordenonelegge | fresh | 0 | 0 |
| Azalea | fresh | 7 | 0 |
| CSS Udine | partial | 156 | 1 |
| Pordenone Pensa | partial | 0 | 1 |
| Teatro Verdi Pordenone | fresh | 88 | 0 |
| Teatro Verdi Trieste | fresh | 70 | 0 |
| Le Giornate del Cinema Muto | fresh | 0 | 0 |
| Paesi in Festa | fresh | 17 | 0 |
| SagreFVG | partial | 23 | 2 |
| Villa Manin | fresh | 4 | 0 |
| Magazzino delle Idee | fresh | 0 | 0 |
| MESS | fresh | 17 | 0 |
| Galleria Spazzapan | stale | 2 conservate, non esposte | — |
| Barcolana | fresh | 1 | 0 |

Magazzino delle Idee, fallito per timeout nel ciclo delle 06:00, è riuscito.
Anche Azalea, fallita nella raccolta locale pomeridiana, è riuscita.
Gli zeri verificati non sono stati sostituiti con eventi inventati.

### Verifica TurismoFVG

Inventario completo e nel budget: 199 pagine calendario, 1.282 URL di
inventario, 1.263 schede proiettate, 1.171 con anteprima. Nessun dettaglio
pendente o ambiguo. Il checkpoint decodificato supera il controllo delle
prove con il codice distribuito e il checkpoint precedente.

`detail_health` è presente e coerente: **682 letture strutturate, zero letture
fallite, zero quarantene dovute a errori di lettura, zero rinnovi conservati,
stop_reason=complete**. I diagnostici sono persistiti e coerenti con il
checkpoint. Le 15 quarantene finali non vanno confuse con i dieci risultati
da rivedere del controllo regionale intermedio.

Questo ciclo cloud verifica il percorso sano della nuova raccolta. Non ha
incontrato errori HTTP isolati: il relativo comportamento rimane coperto dai
test nel container, senza presentarlo come riprodotto su un errore reale oggi.

### Galleria Spazzapan: causa del fallimento

Log e catalogo riportano `Spazzapan current_exhibitions inventory changed`.
Una lettura aggiuntiva in sola lettura delle API ufficiali alle 21:36 ha
confermato che la categoria delle mostre in corso contiene tre ID anziché
quattro: manca `232607`, **FVG70.03 - Sergio Pausig**.
La scheda rimane nell'inventario generale delle mostre, che coincide con
quello atteso; anche la categoria Eventi coincide con l'inventario atteso.

Il testo della scheda indica 11 settembre–11 ottobre 2026, mentre i campi
data generici riportano il periodo più ampio del progetto. La transizione
tra mostra in corso e archivio richiede una riconciliazione esplicita: non
sono stati cambiati gli ID attesi né allentati i controlli durante il deploy.
Il problema era già riprodotto nella TEST pomeridiana; l'adattatore Spazzapan
è identico fra vecchia immagine e candidato, come documentato nel preflight.

Le due schede precedenti rimangono nel catalogo per diagnosi ma sono escluse
dall'API. Il gate non le trasforma automaticamente in dati correnti.
Il fallimento resta registrato e può attivare la policy email esistente;
la consegna dell'email non è stata verificata.

I monitor Palazzo Attems e GiroFVG non sono stati rieseguiti: il worker
termina dopo aver salvato le fonti quando una è fallita. Conservano il
controllo del 13 ottobre; il monitor annuale TurismoFVG conserva quello del
12 ottobre. Non sono presentati come collaudati nuovamente in questo ciclo.

## Controllo del catalogo esposto dall'API

Tutte le 15 pagine di cinque località sono state lette di nuovo sullo snapshot
finale e confrontate con il WSGI del commit distribuito: payload completi
identici, totale coerente, ultimo cursore nullo e nessuna scheda della fonte
Spazzapan nei risultati verificati.

| Località, raggio 20 km | Schede API | Pagine |
| --- | ---: | ---: |
| Pordenone | 318 | 4 |
| Udine | 448 | 5 |
| Trieste | 271 | 3 |
| Gorizia | 186 | 2 |
| Tolmezzo | 72 | 1 |

`/health` HTTP 200, CORS Android presente, snapshot incompatibile respinto
con HTTP 409. `catalog_status=degraded` è coerente con quarantene e fonte
`stale`; non è stato forzato a `complete`.

Confronto finale di job/API/scheduler: soltanto le immagini aggiornate,
nessuna raccolta ancora attiva. Nessun rollback, retry mirato o modifica
dei parser eseguiti. Il prossimo intervento da valutare riguarda la
riconciliazione delle mostre concluse di Spazzapan, con test dedicati.

## Ripristino e confini

Digest precedente comune a job e API, conservato per un eventuale ripristino:
`europe-west1-docker.pkg.dev/meteo-friul/meteofriul/events-worker@sha256:b3f437dfd2d802e0ea1110edf43df9c9d2f8c0eaa17bb5b7780e58fdf0462891`.
Il catalogo precedente e la generazione Storage sono salvati localmente.
Il ripristino di un'immagine non ripristina il catalogo: non è stata
predisposta né eseguita una riscrittura automatica dei dati.

Main resta `5a68de5dc1607105f921d4d2b731170f1a8a0446`. Nessuna build o
installazione Android, nessuna AAB, operazione Play o push GitHub.
La verifica Eventi non chiude i rilievi Android/R8 della candidata APK.

Evidenze operative locali: `.tmp/events-job-update-2026-10-14/deployment/`.
Il [riepilogo versionato](evidence/events-deploy-2026-10-14/deployment-summary.json)
contiene identità, risultati e invarianti; il relativo
[manifest SHA-256](evidence/events-deploy-2026-10-14/SHA256SUMS.txt) protegge
le evidenze sintetiche. Cataloghi completi e log rimangono nella cartella
locale, identificati dal manifest delle evidenze.
