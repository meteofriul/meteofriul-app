# Eventi: distribuzione Spazzapan e ciclo completo Cloud Run

15 ottobre 2026. **Distribuzione e ciclo completo riusciti al primo tentativo.**
L'utente ha autorizzato API e job Eventi, escludendo main, APK e Play.
Ramo: `codex/events-spazzapan-lifecycle`.

## Risultato

La mostra Pausig terminata l'11 ottobre e la relativa notizia ritirata sono
riconciliate con l'archivio. La fonte Spazzapan ora è `fresh`: la mostra
FVG70.02 e l'incontro del 28 ottobre sono pubblicati, Pausig è assente
anche dalla risposta dell'API pubblica. Non ci sono quarantene Spazzapan.

Il job completo `meteofriul-events-refresh-qklc5` ha verificato tutte le 15 fonti,
ha scritto un nuovo catalogo e si è concluso con successo. È stata richiesta
**una sola esecuzione**, senza override, recuperi mirati o nuovi tentativi.
Avvio 16:26:36, fine 16:32:59 italiane;
durata 383.276 secondi.

- Fonti pubblicabili: **15/15**; fonti fallite: **0**.
- Schede grezze nel catalogo: **1700**; quarantene: **18**.
- Snapshot: `2026-10-15T14:26:55.958729+00:00`.
- Generazione Storage: `1792074777181765`.
- Oggetto: `gs://meteo-friul-weather-data/pilot/events/v1/catalog.json`.

Le schede in quarantena delle altre fonti rimangono escluse dall'API;
`partial` indica che la fonte pubblica le schede verificate, non un fallimento
del job. Il conteggio grezzo non coincide con gli eventi visibili in una
specifica località e finestra temporale.
Le quarantene sono passate da 13 a 18: TurismoFVG ha sei nuovi elementi
da verificare (tre pagine HTTP 404 e tre dubbi su identità o calendario)
e una scheda precedente non risulta più in quarantena. Questi elementi
restano esclusi; non sono stati dichiarati risolti da questa distribuzione.

## Candidata e distribuzione

- Commit applicativo: `223422e1045dafa0ddc32316bd6ed6ea510aa1ea`.
- Immagine comune API/worker: `europe-west1-docker.pkg.dev/meteo-friul/meteofriul/events-worker@sha256:df00ef24aea6d6548a36be4a145db23a147972a2f3b4951d925ce708fe62cab1`.
- Cloud Build `b3812cc3-6409-4884-9b83-25dd9c42d3c7`: `SUCCESS`.
- Nel container Linux: **436 test Eventi + 7 Palazzo Attems passati**.
- Stesso insieme di test passato sul contesto esatto prima della build.
- Etichetta OCI del commit e digest dell'immagine verificati nel registry.
- API: `meteofriul-events-00015-j69`, traffico 100%; job generazione `39`.

Prima dell'aggiornamento del worker, la nuova API ha letto il vecchio
catalogo: confronto integrale con la candidata locale su 5 località e
15 pagine, tutte identiche. Dopo la raccolta il confronto è stato ripetuto
sul nuovo snapshot. Verificati anche `/health` HTTP 200, CORS Android,
paginazione e conflitto snapshot HTTP 409.

## Catalogo prodotto

| Fonte | Stato | Schede grezze | Quarantene |
| --- | --- | ---: | ---: |
| TurismoFVG | partial | 1316 | 14 |
| Pordenonelegge | fresh | 0 | 0 |
| Azalea | fresh | 7 | 0 |
| CSS Udine | partial | 155 | 1 |
| Pordenone Pensa | partial | 0 | 1 |
| Teatro Verdi Pordenone | fresh | 88 | 0 |
| Teatro Verdi Trieste | fresh | 69 | 0 |
| Le Giornate del Cinema Muto | fresh | 0 | 0 |
| Paesi in Festa | fresh | 17 | 0 |
| SagreFVG | partial | 24 | 2 |
| Villa Manin | fresh | 4 | 0 |
| Magazzino delle Idee | fresh | 0 | 0 |
| MESS | fresh | 17 | 0 |
| Galleria Spazzapan | fresh | 2 | 0 |
| Barcolana | fresh | 1 | 0 |

### API sul nuovo catalogo

Raggio 20 km, pagine di 100 risultati; confronto dell'intero JSON con il
backend della candidata sul medesimo catalogo.

| Località | Risultati | Pagine | Risposte |
| --- | ---: | ---: | --- |
| Pordenone | 338 | 4 | Identiche |
| Udine | 454 | 5 | Identiche |
| Trieste | 271 | 3 | Identiche |
| Gorizia | 196 | 2 | Identiche |
| Tolmezzo | 74 | 1 | Identiche |

Verifica aggiuntiva a Gradisca d'Isonzo: HTTP 200, fonte Spazzapan `fresh`,
ID `232202` e `234126` presenti, `232607` assente, nessun tag di errore
Spazzapan. La nuova scheda del 28 ottobre non riprende il testo errato
copiato dall'incontro del 14 ottobre.

## Monitor e limiti della prova

- **Palazzo Attems**: `review_required`, controllo `2026-10-15T14:26:55.958729+00:00`.
- **GiroFVG**: `review_required`, controllo `2026-10-15T14:26:55.958729+00:00`.
- **TurismoFVG annual inventory**: `checked`, controllo `2026-10-12T04:00:40.511589+00:00`.

I monitor dei siti candidati Attems e GiroFVG rimangono separati dalle
15 fonti pubblicate; i loro avvisi non vengono eliminati da questa modifica.
Il monitor annuale TurismoFVG è settimanale: il risultato precedente viene
conservato quando il controllo non è previsto, senza dichiararlo rieseguito.
Il dettaglio delle condizioni è registrato nelle evidenze.

La prova dimostra il successo di questo ciclo reale e la gestione della
mostra terminata. Non garantisce che futuri cambiamenti degli inventari
ufficiali possano essere accettati senza verifica: le incoerenze continuano
a essere rilevate e isolate secondo le regole del job.

## Perimetro e ripristino

Il confronto prima/dopo delle specifiche Cloud Run conferma che sono
cambiate soltanto le immagini. Invariati risorse, account di servizio,
comandi, variabili d'ambiente, timeout e retry (zero). Scheduler abilitato
`0 4 * * *`, `Etc/UTC`, invariato. Nessun job residuo in esecuzione.
Policy di monitoraggio e destinatari non modificati.

Main rimane `5a68de5dc1607105f921d4d2b731170f1a8a0446`. Il checkout canonico resta sul ramo
segnalazioni `codex/community-reports-simplification`, commit `696cf0f5`.
Nessun push GitHub, modifica/installazione APK, AAB o operazione Play.
L'anteprima locale conserva il backend e il catalogo che stava usando.

Immagine precedente, disponibile come riferimento per un eventuale rollback:
`europe-west1-docker.pkg.dev/meteo-friul/meteofriul/events-worker@sha256:7e78c5ce2ecc39fa28a5666ca8680c8d0302a4b3c534579109739ed7e62bf672`. Un rollback dell'immagine non ripristina
automaticamente il catalogo; le copie prima/dopo sono conservate localmente.

## Evidenze

- [Riepilogo distribuzione](evidence/events-spazzapan-deploy-2026-10-15/deployment-summary.json)
- [Analisi ciclo completo](evidence/events-spazzapan-deploy-2026-10-15/cycle-analysis.json)
- [Verifica Spazzapan e API](evidence/events-spazzapan-deploy-2026-10-15/spazzapan-verification.json)
- [Confronto API](evidence/events-spazzapan-deploy-2026-10-15/api-after-collection-pass.json)
- [Quarantene e avvisi dei monitor](evidence/events-spazzapan-deploy-2026-10-15/post-cycle-observations.json)
- [Invarianti finali](evidence/events-spazzapan-deploy-2026-10-15/final-invariants.json)
- [Digest ed etichetta immagine](evidence/events-spazzapan-deploy-2026-10-15/image-verification.json)
- [Manifest dei file locali](evidence/events-spazzapan-deploy-2026-10-15/local-evidence-manifest.json)
- [SHA-256](evidence/events-spazzapan-deploy-2026-10-15/SHA256SUMS.txt)
- [Correzione e collaudo locale precedente](EVENTI_SPAZZAPAN_FINE_MOSTRA_2026-10-15.md)

Log integrali, configurazioni e cataloghi sono conservati in
`.tmp/spazzapan-deploy-2026-10-15/` nel worktree dedicato.
