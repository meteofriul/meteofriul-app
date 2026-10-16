# Audit copertura Almanacco 365

Data audit: 2026-07-04

## Obiettivo

Verificare se l'Almanacco puo coprire tutti i giorni dell'anno con dati reali e controllati, senza inventare contenuti e senza usare materiale Ostermann non ancora pronto per la UI.

## Aggiornamento corrente 2026-07-20

- 105 proverbi pubblicati, di cui 96 `almanacEligible`;
- 32 date fisse in `schedule.json` piu fallback;
- 122 candidati estratti e revisionati;
- 43 date note contando schedule e candidati;
- 42/42 pagine del piano fonte Ostermann chiuse.

`almanacEligible` sostituisce il vecchio nome `homeEligible`: la Home non mostra il proverbio completo. Le tabelle successive conservano lo stato fotografato il 2026-07-04.

## Decisione editoriale 2026-07-21

La rotazione non costituisce il completamento del repertorio. Il requisito finale e:

- 366 proverbi distinti e approvati, uno per ogni data del calendario bisestile;
- testo IT e FUR revisionato per ogni proverbio;
- fonte e stato editoriale registrati;
- nessuna duplicazione mascherata tra archivio pubblicato e coda candidati.

Stato verificato:

| Indicatore | Valore |
| --- | ---: |
| Proverbi pubblicati distinti | 105 |
| Proverbi pubblicati `almanacEligible` | 96 |
| Nuovi proverbi necessari rispetto ai pubblicati | 261 |
| Divario effettivo rispetto agli idonei | 270 |
| Candidati estratti | 122 |
| Candidati gia presenti tra i pubblicati | 66 |
| Candidati non pubblicati | 56 |
| Record di lavoro univoci | 161 |

I 56 candidati non pubblicati non sono automaticamente pronti: comprendono varianti, testi da contestualizzare e record trattenuti. Il reperimento dei nuovi testi deve quindi proseguire con fonti controllate; la rotazione resta soltanto il comportamento temporaneo della UI.

## Fonti rilevate il 2026-07-04

| Fonte | File | Stato |
| --- | --- | --- |
| Santo del giorno | `frontend/src/data/almanac/saints.json` | Completo per calendario 366 giorni + default |
| Proverbi pubblicati | `frontend/src/data/almanac/proverbs.json` | 75 record, 66 `homeEligible` |
| Proverbi schedulati | `frontend/src/data/almanac/schedule.json` | 16 date fisse + default |
| Consigli della terra | `frontend/src/data/almanac/earthTips.json` | 12 mesi coperti, 2 consigli per mese + default |
| Tradizioni/Ostermann curato | `frontend/src/data/ostermannCulturalDiscover.json` | 49 record eleggibili per Almanacco |
| Backlog Ostermann | `frontend/src/data/discover/ostermannDiscoverBacklog.json` | Non pronto per UI, resta fuori |
| Coda fonte proverbi | `frontend/src/data/almanac/ostermannProverbSources.json` | 40/40 pagine chiuse: 37 candidati proverbio + 3 Scopri/contesto |

## Copertura numerica

| Blocco | Copertura reale | Note |
| --- | ---: | --- |
| Santi | 366/366 giorni | Copertura completa; FUR da mantenere sotto controllo editoriale. |
| Sole/luna | 365/366 giorni calcolabili | Derivati da funzioni astronomiche locali, non da archivio testuale. |
| Consigli terra | 12/12 mesi | Non giornalieri: vengono scelti dal mese e dal meteo. |
| Proverbi | 66 usabili + fallback | Non 365 unici: rotazione controllata da pool. |
| Proverbi a data fissa | 16 giorni | Date in `schedule.json`; copertura ancora minima. |
| Date note includendo candidati | 34 giorni | Anche contando i candidati restano 332 giorni non coperti da data propria. |
| Tradizioni a data esatta | 9 giorni | Date Ostermann realmente agganciate al calendario. |
| Tradizioni con intervalli | 8 record | Utili come materiale stagionale, non ancora calendario completo. |

## Date con tradizione esatta

| Giorno | Contenuti |
| --- | --- |
| 01-06 | I fuochi dell'Epifania; Il fumo del Midili; L'acqua dell'Epifania |
| 02-02 | La Candelora e il cuore dell'inverno |
| 04-23 | San Giorgio e il pascolo |
| 06-11 | San Barnaba e la vite |
| 06-24 | Il tempo di San Giovanni |
| 07-12 | La settimana delle disgrazie |
| 07-21 | Orione, Sirio e le Pleiadi |
| 09-01 | Il tempo di San Giovanni |
| 12-25 | Natale, Pasqua e il fieno |

## Regola attuale di selezione

La funzione `buildAlmanacData` compone il giorno cosi:

1. santo esatto da calendario;
2. sole e luna calcolati;
3. proverbio schedulato se esiste, altrimenti selezione mirata mensile/stagionale/meteo/lunare o fallback generico `almanacEligible`;
4. consigli terra dal mese e, se disponibile, dal meteo;
5. tradizione esatta se esiste;
6. altrimenti tradizione coerente con meteo;
7. altrimenti tradizione stagionale;
8. altrimenti fallback dal pool Almanacco.

Questa regola permette all'Almanacco di mostrare sempre contenuti, ma non significa che abbiamo 365 tradizioni/proverbi unici.

## Valutazione

L'Almanacco e gia utilizzabile come pagina quotidiana perche ha:

- santo sempre presente;
- sole/luna calcolabili;
- consigli terra mensili;
- proverbio con fallback;
- tradizione stagionale/Ostermann con fallback.

Non e ancora un calendario editoriale completo 365 perche mancano:

- 365 proverbi o pillole uniche;
- tradizioni locali datate per la maggior parte dei giorni;
- stato FUR completamente certificato per ogni blocco testuale;
- regole editoriali esplicite su quando mostrare tradizione, proverbio o pillola.

## Matrice proverbiale 2026-07-04

`getProverbRepertoireMatrix` conferma:

| Indicatore | Valore |
| --- | ---: |
| Proverbi pubblicati | 75 |
| Candidati estratti | 111 |
| Repertorio di lavoro totale | 186 |
| Target archivio | 500 |
| Gap archivio contando anche i candidati | 314 |
| Slot schedulati | 16 |
| Date note con candidati | 34 |
| Gap date note | 332 |
| Pagine Ostermann nel piano fonte | 40 |
| Pagine Ostermann chiuse come Scopri/contesto | 3 |
| Pagine Ostermann ancora da estrarre | 0 |

Quindi il calendario editoriale non puo essere risolto solo con i candidati gia estratti: la coda Ostermann 2026-07-04 ha prodotto 11 candidati aggiuntivi in due tranche e ha chiuso 3 pagine come materiale Scopri/contesto, ma finche i candidati non vengono revisionati e promossi non aumentano la copertura reale dell'app.

## Decisione progettuale

Non forzare Scopri o Ostermann a coprire 365 giorni.

Il passo corretto e creare un contratto `dailyEditorialCalendar` separato, con record giornalieri o semi-giornalieri, che possa usare:

- santo del giorno come base sempre presente;
- proverbio se esiste;
- tradizione datata se esiste;
- pillola stagionale se manca una tradizione;
- riferimento a contenuti Scopri quando pertinenti;
- stato editoriale/FUR per ogni campo.

## Prossimi passi

1. Creare una matrice 366 giorni con colonne: santo, proverbio schedulato, tradizione esatta, tradizione stagionale, consiglio terra, FUR status.
2. Aggiungere test che impediscano regressioni sulla copertura: santo 366/366, earth tips 12/12 mesi, nessun uso del backlog Ostermann in UI.
3. Decidere il contratto `dailyEditorialCalendar` prima di aggiungere altri testi.
4. Solo dopo valutare se popolare i buchi con nuove pillole curate.
