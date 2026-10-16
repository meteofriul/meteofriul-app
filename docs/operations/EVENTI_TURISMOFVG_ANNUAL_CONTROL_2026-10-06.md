# TurismoFVG: controllo annuale del 6 ottobre 2026

**Stato conclusivo del 6 ottobre: `source_complete=true`.** La scansione ha
classificato 2.354 dettagli; la proiezione locale contiene 1.398 schede,
1.295 anteprime con descrizione e nessuna quarantena. Le sezioni seguenti
documentano le scansioni e le correzioni intermedie in ordine cronologico.

## Perimetro e risultato

Nella prima scansione è stata letta l'intera ricerca TurismoFVG dal 1° gennaio
al 31 dicembre 2026, la sitemap degli eventi e ogni dettaglio HTML nell'unione
dei due indici. I valori qui sotto precedono la correzione delle sette pagine
descritta più avanti. Non sono stati letti allegati PDF. Il controllo è locale
e non pubblica il catalogo.

| Misura | Risultato |
| --- | ---: |
| Risultati dichiarati dal calendario | 2.384 |
| Pagine del calendario | 299 |
| URL distinti nel calendario | 1.448 |
| URL nella sitemap | 2.223 |
| URL solo nel calendario | 131 |
| URL solo nella sitemap | 906 |
| Dettagli distinti da classificare | 2.354 |
| Dettagli classificati / richieste fallite | 2.354 / 0 |
| Dettagli allineati | 1.679 |
| Esclusioni motivate per l'anno corrente | 633 |
| Pagine non evento / esperienze senza programma | 21 / 3 |
| URL ancora ambigui / da verificare | 11 / 7 |
| Schede future nella proiezione locale | 1.392 |
| Schede con descrizione di anteprima | 1.289 |
| Errori di validazione, duplicati URL o ordinamento | 0 |

**`source_complete=false`.** Il calendario e la sitemap sono stati acquisiti
senza discrepanze di paginazione, ma 18 dettagli restano sospesi. Nessuna delle
18 pagine è stata promossa nella proiezione. Le schede proiettate sono un
*sottoinsieme verificato*, non una dichiarazione di copertura totale.

## Confronto con il 5 ottobre

Rispetto al [controllo precedente](EVENTI_TURISMOFVG_REVIEW_55_2026-10-05.md),
39 URL non compaiono più nei due indici. Tredici avevano un programma ancora
pertinente al 2026: per ciascuno è stata trovata **una sola** nuova scheda con
titolo, comune, data iniziale e data finale coincidenti, dopo l'ispezione del
nuovo HTML. Due altre URL riguardavano eventi che iniziano nel 2027 e non
bloccano il controllo del 2026. Nessuna rimozione pertinente al 2026 resta
senza sostituzione verificata.

Le 15 URL sospese il 5 ottobre non sono un elenco fisso: la pagina del ciclo
di incontri sulla sessualità non compare più nell'inventario del 6 ottobre;
le due schede “Radici nella pietra” e “Articolo 8” sono ancora sospese, mentre
sono comparse nuove incongruenze. Le undici pagine senza anno verificato sono
ancora nella sitemap e non nel calendario datato.

## Sette schede del calendario da correggere o chiarire

| Scheda ufficiale | Motivo della sospensione |
| --- | --- |
| [Articolo 8 e dintorni](https://www.turismofvg.it/eventi/esposizione-fotografica-articolo-8-e-dintorni-l-altra-faccia-della-ricostruzione) | L'HTML non attribuisce un anno certo al periodo esposto. |
| [Gruppi di Cammino, Autunno 2026](https://www.turismofvg.it/eventi/gruppi-di-cammino-autunno-2026) | Il calendario conserva un badge di settembre fuori dal periodo aggiornato della scheda. |
| [L'ora del racconto](https://www.turismofvg.it/eventi/l-ora-del-racconto-503710) | Il calendario conserva un badge di settembre fuori dal periodo aggiornato; il testo elenca anche una data non rappresentata dai badge. |
| [Lo scrigno del Doge](https://www.turismofvg.it/eventi/lo-scrigno-del-doge-in-villa-manin-mercatino-dell-antiquariato-e-modernariato) | Il programma elenca date separate nel 2026 e una nel 2027; l'estrattore non le riconcilia ancora senza assumere una continuità. |
| [Radici nella pietra](https://www.turismofvg.it/eventi/radici-nella-pietra) e [seconda scheda](https://www.turismofvg.it/eventi/radici-nella-pietra-490917) | Una pagina dichiara maggio–dicembre 2026, l'altra solo “anno 2026”; serve una scheda con precisione mensile e una deduplicazione provata. Il badge di maggio/giugno non è la fine della mostra. |
| [Residenze a Stavoli, RISVEGLI](https://www.turismofvg.it/eventi/residenze-a-stavoli-risvegli) | La riga data dà solo ottobre 2026; la descrizione indica il momento pubblico dell'11 ottobre, da riconciliare senza attribuire date inventate alle residenze. |

Le altre undici quarantene sono pagine solo nella sitemap con `year_missing`:
[Casetta di Natale](https://www.turismofvg.it/eventi/creiamo-la-casetta-di-natale),
[Ferragosto Moggese](https://www.turismofvg.it/eventi/ferragosto-moggese-350873),
[Giochi per bambini](https://www.turismofvg.it/eventi/giochi-per-bambini-aspettando-natale),
[Il Pacchetto Rosso](https://www.turismofvg.it/eventi/il-pacchetto-rosso),
[Mostra Presepi](https://www.turismofvg.it/eventi/mostra-presepi-a-moggio-a-moggio-la-stella-327907),
[Pellegrinaggio](https://www.turismofvg.it/eventi/pellegrinaggio-notturno-in-occasione-della-festa-di-santa-chiara),
[Bandiere Verdi](https://www.turismofvg.it/eventi/presentazione-del-volume-dossier-delle-bandiere-verdi),
[Sui siti della grande Guerra](https://www.turismofvg.it/eventi/sui-siti-della-grande-guerra),
[Teatro Positivo](https://www.turismofvg.it/eventi/teatro-positivo),
e le due schede [Viva viva la Befana](https://www.turismofvg.it/eventi/viva-viva-la-befana-328296)
e [Viva Viva la Befana](https://www.turismofvg.it/eventi/viva-viva-la-befana-365911).
L'assenza dal calendario 2026 non prova da sola che siano storiche.

## Correzione delle sette schede sospese

Il riconoscitore versione 8 distingue le date del dettaglio dal badge della
ricerca. Un badge passato viene ignorato soltanto se la riga data ufficiale
specifica un periodo nell'anno corrente, altri badge futuri vi ricadono e
titolo e comune coincidono. È il caso di **Gruppi di Cammino** e **L'ora del
racconto**; i loro periodi restano periodi, senza fabbricare incontri quotidiani.

**Lo scrigno del Doge** viene letto come elenco completo di cinque giorni del
2026 e uno del 2027. La scheda 2026 contiene solo i cinque giorni verificati;
il vecchio badge del 6 gennaio 2026 non la fa apparire come aperta senza
interruzione. **Risvegli** espone solo il momento pubblico di domenica 11
ottobre, verificato anche nel giorno della settimana. **Radici nella pietra**
espone il periodo ufficiale **maggio–dicembre 2026** con precisione mensile:
gli estremi tecnici del mese servono alla ricerca, non vengono mostrati come
giorni di apertura.

La seconda pagina di Radici e Articolo 8 restano sospese. La prima non prova
l'intervallo della propria programmazione e la seconda non dà l'anno della
mostra. Restano sospese anche le undici pagine della sitemap senza anno
verificabile. Nessuna di queste tredici pagine è proiettata come nuova scheda.

La riproiezione locale dai sette HTML ufficiali già acquisiti dava **1.397
schede**, **1.294 con descrizione**, **13 URL in quarantena**, nessuna scheda
invalida o fuori ordine e `source_complete=false`.

La successiva **scansione annuale completa con riconoscitore versione 8** ha
riletto calendario, sitemap e tutti i 2.354 dettagli HTML, senza richieste
fallite. L'impronta dell'inventario coincide con la prima scansione. Ha
classificato **1.684 dettagli allineati**, **633 esclusioni motivate**, **21
pagine non evento**, **3 esperienze senza programma**, **11 pagine ambigue** e
**2 da verificare**. Solo le cinque pagine citate sopra sono passate da
`review_required` a `detail_aligned`; nessun'altra classificazione è cambiata.
La proiezione derivata esclusivamente da questa seconda scansione conferma
**1.397 schede**, **1.294 anteprime**, **13 quarantene**, nessun conflitto di
validazione, URL duplicato o errore d'ordine. Date, tipi di programma e URL
delle schede coincidono con la riproiezione locale. Tre etichette di altre
schede sono passate dall'inglese all'italiano nel nuovo HTML, senza cambiare
giorno o tipo di programma. **`source_complete=false`** era il risultato
corretto di questa scansione prima dell'ulteriore verifica delle tredici
pagine.

## Controllo ripetibile

`pilot_regional_year_control` ora può raccogliere i due indici e completare
automaticamente la lettura dei dettagli con `--run`. Ogni blocco salva un
checkpoint; un'interruzione può essere ripresa con `--finish`. Ogni richiesta
fallita viene ritentata al massimo tre volte. `--previous` confronta le URL
scomparse e accetta una nuova URL solo dopo una corrispondenza unica di titolo,
comune e intervallo. La verifica dei dettagli usa solo HTML.

Esempio, dalla directory `backend`:

```powershell
python -m app.events.pilot_regional_year_control --run --snapshot ..\tmp\turismofvg-year-control-2026-10-07.json --previous ..\tmp\turismofvg-year-control-2026-10-06.json
python -m app.events.pilot_regional_local_preview --prepare --control ..\tmp\turismofvg-year-control-2026-10-07.json --display ..\tmp\turismofvg-local-preview-2026-10-07.json
```

Questa procedura locale resta disponibile per gli audit manuali. L'integrazione
nel job comune è documentata in fondo alla pagina; non è stata creata
un'automazione separata né promossa una raccolta incompleta.

## Stato dopo la verifica supplementare

La [verifica dettagliata delle tredici pagine](EVENTI_TURISMOFVG_PENDING_REVIEW_2026-10-06.md)
ha prima risolto tre casi con il riconoscitore versione 10. Una nuova scansione
completa ha confermato 1.398 schede locali e 1.295 anteprime. Le dieci pagine
ancora senza anno nel dettaglio sono poi state trovate per URL esatta nel
calendario storico ufficiale, con titolo e comune corrispondenti. Il controllo
automatico legge solo le finestre storiche necessarie, raggruppate per mese;
una ricerca incompleta, una data di modifica corrente o un'identità diversa
non viene promossa né esclusa senza prova. La riproiezione locale dei tredici dettagli
salvati conferma **zero quarantene**, **zero conflitti** e
**`source_complete=true` al 6 ottobre 2026**. Non sono stati letti PDF e il
catalogo non è stato pubblicato.

## Integrazione nel job comune del pilot

Nel ramo `codex/events-discovery-audit`, `pilot_cloud.publish` usa ora il
controllo annuale come adattatore TurismoFVG. A ogni esecuzione legge l'intero
calendario dell'anno e la sitemap, verifica il numero di pagine e occorrenze e
confronta l'impronta di ogni URL. Poi legge i dettagli HTML mancanti o da
rinnovare, riconcilia le schede storiche e proietta le anteprime. Le richieste
alle schede sono indipendenti: il riuso di una sessione HTTP durante un batch
aveva prodotto classificazioni diverse per undici pagine speciali. La rilettura
parallela indipendente delle stesse URL ha restituito le classificazioni attese;
la seconda scheda di “Radici nella pietra” viene risolta solo dopo il confronto
con la prima.

Il checkpoint del controllo è compresso nel catalogo pilot (circa 0,75 MB per
la scansione completa). Una lettura parziale lo aggiorna, ma restituisce zero
eventi TurismoFVG. Il gate riproietta autonomamente le schede dal controllo:
una URL mancante, una data non dimostrata o una scheda in revisione impediscono
la pubblicazione della fonte. Le vecchie schede TurismoFVG non vengono mostrate
mentre la fonte è stale. Non è stato aggiunto un job o scheduler separato.

La prova locale senza checkpoint ha richiesto tre esecuzioni entro il limite
esistente di 360 secondi per fonte. Durante la calibrazione del rinnovo, gli
URL mancanti sono scesi da 2.354 a 1.202, poi a 194 e infine a **zero**.
L'ultima esecuzione ha impiegato 183,4 secondi, ha prodotto **1.398 schede** e
**1.295 anteprime**, senza URL ambigui o in revisione; anche il gate del job ha
restituito `ok`. La ricerca annuale con 16 richieste concorrenti ha riconciliato
**2.384 occorrenze su 299 pagine** in 101,4 secondi. Le misure sono locali e
possono variare con la risposta del sito.

La politica finale rinnova in anticipo i dettagli più vecchi. Conserva per al
massimo **48 ore** quelli degli eventi che iniziano entro sette giorni,
**96 ore** quelli più lontani e **sette giorni** le esclusioni motivate. Un
cambiamento del calendario o della sitemap invalida subito il risultato della
URL interessata. Il controllo esige la freschezza di ogni risultato prima di
pubblicare la fonte e non legge allegati PDF. Il ramo non è stato distribuito:
la prima esecuzione del job cloud e il controllo sul dispositivo restano da
verificare prima della promozione a `main`.
