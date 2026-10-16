# Audit fonti Accadde oggi / Memorie FVG

Data audit: 2026-07-06

## Obiettivo

Valutare i file scaricati in `F:\proggetto Meteo Friul App\scarica dati fvg` come bacino per:

- `Memoria del giorno`;
- archivio `Scopri`;
- future schede storiche/locali;
- copertura annuale 366 giorni.

Questi dati non entrano direttamente nella UI. Servono come indice di lavoro per scegliere, verificare, riscrivere e tradurre contenuti.

## File analizzati

| File | Stato | Nota |
| --- | --- | --- |
| `accadde_oggi_fvg.csv` | utile | Esporta 5039 record strutturati. |
| `accadde_oggi_fvg.json` | utile | Stesso contenuto in JSON, usato per normalizzazione. |
| `accadde_oggi_fvg_365giorni_esteso.csv` | molto utile come shortlist | Contiene 366 record, uno per giorno, gia arricchiti con punteggio/importanza e descrizione estesa. |
| `accadde_oggi_fvg_365giorni_esteso.json` | molto utile come shortlist | Versione JSON del file esteso; migliore base per la prima coda editoriale. |
| `fetch_accadde_oggi.ps1` | utile | Script SPARQL Wikidata che spiega come sono stati scaricati i dati. |
| `eventi_fvg.csv` | non utile ora | Contiene solo intestazione e una riga vuota. |
| `index.html` | non pertinente al database giornaliero | Sembra una pagina/landing Meteo Friul, non una fonte storica. |

## Fotografia dati

Dal file `accadde_oggi_fvg`:

| Indicatore | Valore |
| --- | ---: |
| Record totali | 5039 |
| Giorni coperti | 366/366 |
| Giorni mancanti | 0 |
| Nascite | 2498 |
| Morti | 1342 |
| Eventi | 1199 |

Dal file `accadde_oggi_fvg_365giorni_esteso`:

| Indicatore | Valore |
| --- | ---: |
| Record totali | 366 |
| Giorni coperti | 366/366 |
| Giorni mancanti | 0 |
| Nascite | 250 |
| Morti | 104 |
| Eventi | 12 |
| Internazionale | 18 |
| Nazionale | 83 |
| Regionale/Notevole | 169 |
| Locale/Conosciuto | 86 |
| Di nicchia | 10 |

Luoghi piu presenti:

| Luogo | Record |
| --- | ---: |
| Trieste | 1432 |
| Udine | 826 |
| Gorizia | 245 |
| provincia di Udine | 236 |
| Pordenone | 198 |
| Monfalcone | 123 |
| provincia di Pordenone | 108 |
| Cividale del Friuli | 98 |
| San Vito al Tagliamento | 71 |
| provincia di Gorizia | 66 |
| Aquileia | 47 |

## Valutazione

Il bacino e molto utile, ma non e pubblicabile direttamente.

Punti forti:

- copre tutti i giorni dell'anno;
- ogni record ha un link Wikidata tracciabile;
- permette ricerca per data, luogo, tipo e potenziale localita/provincia;
- puo alimentare la coda editoriale di `Memoria del giorno`.

Limiti:

- molte righe sono semplici nascite/morti enciclopediche;
- alcune descrizioni sono troppo fredde o poco interessanti per l'utente;
- Wikidata e una buona traccia, ma non sostituisce revisione editoriale;
- non esiste copy FUR;
- non esiste ancora scelta editoriale tra evento principale, biografia, ricorrenza o archivio.

Il file esteso e la base migliore per lavorare perche riduce il rumore a una proposta per giorno. Non va comunque accettato automaticamente:

- il criterio sembra premiare molto la visibilita Wikidata/sitelink;
- 354 record su 366 sono nascite o morti, quindi il rischio "calendario biografico" resta alto;
- alcuni eventi sono amministrativi o tecnici e non hanno ancora forma narrativa;
- il record scelto per un giorno puo essere famoso ma non necessariamente il piu adatto a Meteo Friul.

## Import controllato

Creato script:

- `scripts/import-fvg-daily-history-source.mjs`

Lo script legge:

- `F:\proggetto Meteo Friul App\scarica dati fvg\accadde_oggi_fvg.json`

oppure:

- `F:\proggetto Meteo Friul App\scarica dati fvg\accadde_oggi_fvg_365giorni_esteso.json`

e genera staging normalizzati:

- `backend_dryrun_staging/exports/discover_daily_history_wikidata_source.json`
- `backend_dryrun_staging/exports/discover_daily_history_wikidata_extended_source.json`

Lo staging assegna a ogni record:

- `dayKey`;
- `year`;
- `place`;
- `type`;
- `title`;
- `description`;
- `detail`;
- `siteLinksScore`;
- `importance`;
- `wikidataId`;
- `reviewStatus: raw_wikidata_candidate`;
- `reviewBucket`;
- `destinationHint`;
- `readyForUi: false`.

Il file generato resta in `backend_dryrun_staging/exports/`, quindi non finisce nel bundle app e non viene pubblicato per errore.

## Regola editoriale

Per diventare `Memoria del giorno`, un record deve passare questi stati:

1. `raw_wikidata_candidate`: import tecnico, non pubblicabile.
2. `source_candidate`: scelto come possibile tema, fonte ancora da verificare/rafforzare.
3. `source_verified`: fonte controllata, manca copy finale.
4. `copy_ready_it`: testo italiano umano, breve e leggibile.
5. `fur_review_needed`: FUR presente ma non approvato.
6. `ready_for_discover`: fonte, IT, FUR e revisione approvate.

Nessun record Wikidata deve entrare direttamente in `localMemory.json`.

## Strategia proposta

1. Usare Wikidata come indice per coprire i giorni mancanti.
2. Usare il file esteso come prima shortlist 366 giorni.
3. Dare priorita a:
   - eventi veri rispetto a semplici nascite/morti;
   - luoghi vicini alla localita utente quando possibile;
   - figure o fatti con identita FVG riconoscibile;
   - record con fonte secondaria verificabile.
4. Per nascite/morti, pubblicare solo se la persona ha un aggancio culturale/storico forte e comprensibile.
5. Ostermann resta fonte autonoma e prioritaria per tradizioni, detti, riti e cultura popolare.
6. Wikidata copre soprattutto cronaca storica, biografie e ricorrenze civili/culturali.

## Prossimi passi

- [x] Aggiungere staging normalizzato anche per il file esteso 366 giorni.
- [ ] Aggiungere audit automatico che classifica i 366 record estesi in A/B/C/D.
- [ ] Creare una coda `dailyHistoryCandidates` separata da `localMemory.json`.
- [ ] Selezionare 10 giorni pilota e lavorarli con fonte, copy IT, copy FUR.
- [ ] Solo dopo promuovere record uno alla volta in `localMemory.json`.
- [ ] Tenere distinta `Memoria del giorno` da `Archivio Scopri`.

## Coda canonica dei giorni senza memoria primaria - 2026-07-20

Il controllo conclusivo non si basa piu su una stima generica. La coda viene rigenerata con:

- `scripts/build-discover-missing-date-research-queue.mjs`;
- `frontend/src/data/discover/discoverMissingDateResearchQueue.json`;
- `frontend/src/data/discover/discoverMissingDateSecondPassReview.json`.

Risultato verificato:

- copertura primaria exact-date: `312/366`;
- giorni ancora scoperti: `54`;
- la verifica mirata su Ida Vallerugo conferma Meduno e il 1941, ma non il 13 maggio;
- tutti i `54` giorni richiedono quindi una fonte o un soggetto nuovo;
- nessun candidato eleggibile non ancora lavorato e disponibile nel master attuale;
- dieci candidati di classe B restano esclusi, sospesi o destinati all'archivio secondo decisioni gia motivate.

Il controllo ha inoltre trovato tre memorie secondarie gia approvate nei giorni mancanti: Spiridon Gopcevic il 9 luglio, Roberto Damiani il 26 maggio e Olga Brunner il 23 dicembre. Restano secondarie perche questa era una scelta esplicita dei rispettivi lotti editoriali. Non vengono promosse soltanto per coprire il calendario.

La coda non e letta dalla UI e ogni riga mantiene `readyForUi: false`. Le date sono espresse sia come `dateIt` (`DD-MM`) per la revisione italiana, sia come `dateAnchor` (`MM-DD`) per la sola chiave tecnica interna.
