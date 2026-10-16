# Eventi: ciclo locale unico delle 15 fonti, 8 ottobre 2026

## Esecuzione

Il percorso reale `app.events.pilot_cloud.publish` e' stato eseguito con i
15 adattatori registrati e con uno storage **solo locale** che conserva il
checkpoint annuale TurismoFVG. Il checkpoint non contiene schede pubblicate:
ognuna delle 15 fonti ha dovuto produrre un lotto nuovo. Nessuna scrittura
cloud, APK o distribuzione e' stata eseguita. I file di prova sono ignorati da
Git in `.dev-logs/events-girofvg-2026-10-07/`:
`preflight_full_job.py`, `full-job-catalog.json` e `full-job-report.json`.

Il primo ciclo dell'8 ottobre, durato **473,24 secondi**, ha superato i gate
con 15/15 fonti `fresh`, ma la revisione del programma Barcolana ha trovato
un titolo tecnico pubblicato dal sito ufficiale:
`OfficeOpenXml.Style.ExcelRichTextCollection`. La relativa [pagina
ufficiale](https://www.barcolana.it/it/eventi/2026/officeopenxml-style-excelrichtextcollection)
descrive la stessa gara della scheda ufficiale
[Barcolana Ski - Coppa d'Autunno](https://www.barcolana.it/it/eventi/terra/2026/barcolana-ski-coppa-d-autunno).
La [scheda TurismoFVG](https://www.turismofvg.it/it/barcolana-ski)
conferma data, luogo e programma. Il lettore elimina soltanto questa copia
con titolo errato quando trova anche la scheda corretta e quando coincidono
data, luogo e orario attesi; se l'anomalia cambia, la fonte si ferma per
revisione. Il test isolato live ha restituito 670 voci distinte, dieci
doppioni e nessun titolo tecnico.

Il **secondo ciclo completo**, con la correzione, e' terminato con codice 0
in **443,61 secondi**. Le 15 fonti sono `fresh`, tutte con zero revisioni:

| Fonte | Schede |
| --- | ---: |
| TurismoFVG | 1.441 |
| Pordenonelegge | 0 |
| Le Giornate del Cinema Muto | 34 |
| Azalea | 7 |
| CSS Udine | 161 |
| Pordenone Pensa | 1 |
| Teatro Verdi Pordenone | 88 |
| Teatro Verdi Trieste | 72 |
| Paesi in Festa | 22 |
| SagreFVG | 30 |
| Villa Manin | 5 |
| Magazzino delle Idee | 1 |
| MESS | 19 |
| Galleria Spazzapan | 4 |
| Barcolana | 1 |

Pordenonelegge e' a zero perche' l'edizione 2026 si e' conclusa il
20 settembre. Il suo programma di 447 appuntamenti e' stato comunque
ricontrollato dal job. TurismoFVG ha riconciliato 2.433 URL, con
`source_complete=true`, zero sospesi e 1.330 schede con anteprima su 1.441.
Barcolana ha letto 680 righe del calendario e ne presenta 670 distinte,
piu' tre voci regionali verificate: **673 appuntamenti** nella scheda unica,
con immagine e descrizione. Nel catalogo interrogato per Trieste entro 20 km
ci sono 291 schede e una sola Barcolana; per Pordenone 322 schede e una sola
scheda del Cinema Muto.

## Monitor del job

I quattro monitor successivi alla raccolta non hanno rilevato novita' da
esaminare:

- Palazzo Attems: 27 record API, una mostra corrente, tre blocchi gia' noti.
- Pro Loco FVG: sei pagine, 58 schede, 32 URL distinti.
- Anteprima Sagre: 419 post, nessun nuovo candidato futuro; resta il caso
  gia' noto della Sagra del Pan Zal senza data direttamente provata.
- GiroFVG: 12.297 URL sitemap, 89 pagine di categoria su 90; la pagina
  `/fiere-e-mostre?start=168` continua a rispondere HTTP 500 ed e' un
  blocco gia' noto.

Palazzo Attems e GiroFVG riportano ancora `source_complete=false`;
Palazzo Attems, Pro Loco, Anteprima Sagre e GiroFVG sono monitor e non fanno
parte dei 15 adattatori pubblicati. Il risultato 15/15 riguarda quindi il
job attuale, non una garanzia che questi siti aggiuntivi siano raccolti
integralmente.

## Verifiche e limite di rilascio

I 635 test `test_pilot_*.py` passano; `git diff --check` e' pulito. Il
controllo successivo sul catalogo del secondo ciclo conferma schema valido,
15 fonti fresche, zero revisioni, una sola scheda Barcolana per Trieste e
nessun titolo `OfficeOpenXml` nel programma. La correzione visiva delle righe
senza orario nella preview era gia' stata verificata con 16 test frontend.

Questa e' una prova locale del job. La versione installata `0.1.13-tester`
legge ancora i dati distribuiti precedentemente. La promozione richiede
preparare una versione tester collegata al nuovo catalogo, provarla sul
telefono e poi seguire il flusso di release del ramo.
