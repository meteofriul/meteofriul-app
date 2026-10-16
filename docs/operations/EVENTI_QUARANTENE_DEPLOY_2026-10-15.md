# Eventi: distribuzione e collaudo delle regole di recupero

15 ottobre 2026, ramo `codex/events-quarantine-recovery`.
**Ciclo finale riuscito; tutti i nove eventi richiesti sono visibili nell'API.**
Il conteggio verificato è **7 nuove schede recuperate e 2 eventi già presenti con URL equivalenti**.
Non sono nove aggiunte nette. Nessuna modifica manuale del catalogo.

## Candidata e controlli

- Commit finale: `2a2a5f106b8185fd9a8f773b64552b20253df7a4`.
- Immagine: `europe-west1-docker.pkg.dev/meteo-friul/meteofriul/events-worker@sha256:529d93d115de05ff8d6039d09545d2d2e9da5fd87ace227b22f4be6e7b0c296b`.
- Cloud Build `8a55ce2d-7af7-4acb-8073-009bedfebaff`: SUCCESS; **476 test Eventi + 7 Attems nel container Linux**.
- Suite backend locale: 1.845 test, 1.844 passati e uno skip previsto per l'artefatto ISTAT opzionale.
- Digest del manifest e della configurazione, etichetta OCI e contenuto del pacchetto verificati.
- API `meteofriul-events-00018-2vz`, traffico 100%; job generazione `42`.
- Esecuzione finale `meteofriul-events-refresh-fqld9`: 19:07:27–19:12:12
  italiane, **284.293 secondi**, tutte le 15 fonti tentate e pubblicabili, zero fonti fallite.
- Catalogo: 1715 schede grezze; quarantene complessive **18 → 6**.
- Snapshot `2026-10-15T17:07:52.543611+00:00`, generazione Storage `1792084328436869`.

Il totale grezzo precede raggio geografico, aggregazione, intervallo temporale e paginazione dell'API.
Lo stato `partial` indica una fonte completata con singole schede escluse dalla pubblicazione.

## I tre collaudi e le correzioni emerse

1. `meteofriul-events-refresh-qjnd2`, candidata `d8fce73f`: fallimento dopo 493.258 secondi.
   TurismoFVG aveva verificato 1.296 pagine senza errori, ma restavano 40 dettagli per il limite interno.
   Il progresso parziale era salvato e non veniva riutilizzato. Dati precedenti conservati; fonte `stale`
   temporaneamente esclusa dall'API secondo la policy esistente. Le altre 14 fonti erano concluse.
2. `meteofriul-events-refresh-sjf4v`, candidata `c7f8579c`: job riuscito in 473.342 secondi.
   La ripresa automatica ha riutilizzato esattamente **1.289 risultati e letto le altre 47 pagine**,
   con controllo indipendente di pubblicazione superato. Il confronto successivo ha trovato tre
   regressioni: clausole ipotetiche di maltempo interpretate come variazioni effettive.
3. `meteofriul-events-refresh-fqld9`, candidata `2a2a5f10`: job e verifiche finali superati, incluse le tre regressioni.

La ripresa mantiene separati inventario verificato e risultati parziali: riusa solo prove recenti,
con firma identica e versione corretta. Non promuove l'inventario fallito e non rinnova artificialmente
le date di controllo. Test dedicati verificano scadenza, modifiche, indisponibilità della fonte e
preservazione delle schede attive non più elencate.

La regola meteo ora gestisce anche «rinviato o annullato» e «viene annullato in caso di...».
Restano bloccati annullamenti effettivi e comunicazioni indipendenti nella stessa descrizione.
Ripristinate nell'API **Decora la tua zucca** e le due date di **L'occasione del Borgo**.
Nessun aumento dei timeout: i risultati in revisione vengono sempre riletti, quindi questa
correzione non richiede una nuova invalidazione globale delle pagine già accettate (versione 11).

## Nove eventi verificati nell'API

| Evento | Comune | Inizio / fine | Risultato rispetto al catalogo iniziale |
| --- | --- | --- | --- |
| Giro del Mondo in 80 libri - "Nero come il mare " di Charlotta Meconaghy | Moggio Udinese | 2026-10-16 / 2026-10-16 | Recuperata |
| Libri a merenda | Moggio Udinese | 2026-10-16 / 2026-10-16 | Recuperata |
| Il volto della Passione: la S.Sindone come specchio del Vangelo | Moggio Udinese | 2026-10-17 / 2026-10-17 | Recuperata |
| Campagna Amica Tour FVG | Trieste | 2026-10-18 / 2026-10-18 | Recuperata |
| Giangiacomo Feltrinelli - Rivoluzione permanente | Moggio Udinese | 2026-10-18 / 2026-10-18 | Recuperata |
| Smarrimenti e rinvenimenti | Udine | 2026-10-21 / 2026-10-21 | Già presente, URL equivalente |
| Digger | Cervignano del Friuli | 2026-10-25 / 2026-10-26 | Già presente, URL equivalente |
| 51ª Sagra della Madonna della Salute | San Quirino | 2026-10-14 / 2026-10-18 | Recuperata |
| Burnjak 2026 / Festa delle Castagne | Stregna | 2026-10-18 / 2026-10-18 | Recuperata |

Smarrimenti e Digger erano già nel catalogo iniziale rispettivamente sotto
`/eventi/smarrimenti-e-rinvenimenti` e `/eventi/digger-506889`.
Le pagine ufficiali vecchie e correnti rispondono HTTP 200, senza redirect, e hanno
identici titolo, data, Comune, sede, sito ufficiale e descrizione. Gli hash e le
identità sono archiviati: non sono stati aggiunti alias manuali all'applicazione o duplicati.

## Fonti e quarantene residue

| Fonte | Stato | Schede grezze | Quarantene |
| --- | --- | ---: | ---: |
| TurismoFVG | partial | 1328 | 4 |
| Pordenonelegge | fresh | 0 | 0 |
| Azalea | fresh | 7 | 0 |
| CSS Udine | partial | 155 | 1 |
| Pordenone Pensa | partial | 0 | 1 |
| Teatro Verdi Pordenone | fresh | 88 | 0 |
| Teatro Verdi Trieste | fresh | 69 | 0 |
| Le Giornate del Cinema Muto | fresh | 0 | 0 |
| Paesi in Festa | fresh | 17 | 0 |
| SagreFVG | fresh | 27 | 0 |
| Villa Manin | fresh | 4 | 0 |
| Magazzino delle Idee | fresh | 0 | 0 |
| MESS | fresh | 17 | 0 |
| Galleria Spazzapan | fresh | 2 | 0 |
| Barcolana | fresh | 1 | 0 |

L'elenco finale non coincide con quello previsto prima del ciclo: i vecchi URL 404
non più nell'inventario sono usciti dalla revisione senza essere forzati in pubblicazione;
la notizia ABC di Pordenone Pensa usa un nuovo URL ma richiede ancora l'estrazione delle sessioni.
Altri nuovi eventi o modifiche provenienti dalle fonti sono distinti dai sette recuperi
nel confronto del catalogo. Il caso Lipizer 506076 titolo/descrizione resta una segnalazione
separata, non corretta da questa distribuzione.

Revisioni attuali:

- `https://www.turismofvg.it/eventi/ciclo-autunnale-dell-associazione-biblioteca-austriaca`: `detail_identity_or_schedule_requires_review`.
- `https://www.turismofvg.it/eventi/1976-2026-50-anni-dal-terremoto`: `possible_schedule_change`.
- `https://www.turismofvg.it/eventi/autunno-musicale-2026`: `detail_not_resolved`.
- `https://www.turismofvg.it/eventi/inaugurazione-mostra-una-terra-una-storia-504353`: `detail_identity_or_schedule_requires_review`.
- `https://www.cssudine.it/stagione-contatto/2026/2940/itinerari-nel-teatro-contemporaneoterza-edizione`: `ambiguous schedule`.
- `https://www.pnpensa.it/abc-educazione-finanziaria-2026-appuntamenti-sulle-assicurazioni-pordenone-ottobre-novembre/`: `additional future date needs session extraction`.

Capuozzo resta escluso; i programmi con sessioni ambigue non vengono forzati.

## API e Spazzapan

Confrontate le risposte JSON integrali del backend candidato con l'API distribuita,
prima e dopo ogni aggiornamento, per cinque località. Dopo il ciclo finale:

| Localita' | Risultati | Pagine identiche |
| --- | ---: | ---: |
| Pordenone | 338 | 4 |
| Udine | 456 | 5 |
| Trieste | 274 | 3 |
| Gorizia | 196 | 2 |
| Tolmezzo | 78 | 1 |

Verificati health HTTP 200, CORS Android, paginazione e conflitto snapshot HTTP 409.
Tutti i nove eventi richiesti e le tre schede ripristinate sono stati verificati anche
nell'API nella propria zona. Spazzapan resta fresh: la mostra Pausig scaduta resta esclusa,
FVG70.02 e l'incontro del 28 ottobre sono presenti. Una mostra terminata non blocca il job.
I monitor Attems/GiroFVG mantengono le proprie revisioni; il controllo annuale TurismoFVG
resta settimanale e non viene dichiarato rieseguito in questo giovedì.

## Perimetro e ripristino

Cambiate soltanto le immagini di API e worker. Invariati variabili, account di servizio,
comandi, risorse, timeout e retry. Scheduler abilitato `0 4 * * *`, `Etc/UTC`, invariato.
Tre esecuzioni complete richieste e tracciate, senza override o esecuzioni duplicate residue.

Main resta `5a68de5d`; checkout canonico segnalazioni a `696cf0f5`.
Nessun push GitHub, APK, installazione, AAB, Play o aggiornamento dei servizi TEST locali.
I commit sono locali sul ramo dedicato. Controlli di pulizia del workspace canonico e del ramo candidato superati. Non sono state modificate le policy dei monitor.

Immagine prima dell'intero intervento: `europe-west1-docker.pkg.dev/meteo-friul/meteofriul/events-worker@sha256:df00ef24aea6d6548a36be4a145db23a147972a2f3b4951d925ce708fe62cab1`.
Immagine immediatamente precedente: `europe-west1-docker.pkg.dev/meteo-friul/meteofriul/events-worker@sha256:d66acfd960b1f0604b28e776243541333a3cb2d29526110dcff9fbf06970ad6e`.
Un rollback dell'immagine non ripristina automaticamente il catalogo. Copie prima/dopo e log
sono conservati nel worktree in `.tmp/quarantine-deploy-2026-10-15/`,
`.tmp/quarantine-resume-deploy-2026-10-15/` e `.tmp/quarantine-final-deploy-2026-10-15/`.

## Evidenze

- [Riepilogo](evidence/events-quarantine-deploy-2026-10-15/deployment-summary.json)
- [Ciclo finale](evidence/events-quarantine-deploy-2026-10-15/cycle-analysis.json)
- [Nove eventi](evidence/events-quarantine-deploy-2026-10-15/nine-recoveries-verification.json)
- [Tre regressioni risolte](evidence/events-quarantine-deploy-2026-10-15/weather-regression-verification.json)
- [Identità degli URL equivalenti](evidence/events-quarantine-deploy-2026-10-15/official-url-identity.json)
- [Confronto catalogo](evidence/events-quarantine-deploy-2026-10-15/catalog-diff.json)
- [Confronto API](evidence/events-quarantine-deploy-2026-10-15/api-after-collection-pass.json)
- [Spazzapan](evidence/events-quarantine-deploy-2026-10-15/spazzapan-verification.json)
- [Primo ciclo](evidence/events-quarantine-deploy-2026-10-15/first-cycle-analysis.json)
- [Secondo ciclo e ripresa](evidence/events-quarantine-deploy-2026-10-15/second-cycle-analysis.json)
- [Invarianti](evidence/events-quarantine-deploy-2026-10-15/final-invariants.json)
- [Hash](evidence/events-quarantine-deploy-2026-10-15/SHA256SUMS.txt)
- [Regole e collaudo iniziale](EVENTI_RECUPERO_QUARANTENE_REGOLE_2026-10-15.md)

Questo esito riguarda il ciclo verificato; futuri cambiamenti delle fonti restano soggetti ai controlli.
