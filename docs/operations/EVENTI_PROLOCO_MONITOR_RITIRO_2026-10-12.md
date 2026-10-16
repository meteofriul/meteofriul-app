# Eventi: ritiro del monitor Pro Loco FVG, 12 ottobre 2026

## Decisione

Pro Loco FVG resta fuori dalle fonti pubblicate. La scansione del 12 ottobre
ha letto cinque pagine e 44 occorrenze, riferite a 25 URL di dettaglio
distinti. Ogni occorrenza ha trovato una corrispondenza univoca nel lotto
TurismoFVG del catalogo pubblicato la stessa mattina. L'[audit dei dettagli
del 7 ottobre](EVENTI_PROLOCO_FVG_AUDIT_2026-10-07.md) documenta inoltre
alcuni campi `Quando` che omettono l'ultimo giorno dell'evento.

## Modifica nel ramo

`pilot_cloud.publish` non scarica piu' l'indice Pro Loco durante il ciclo
ordinario e non fa fallire il job per una voce nuova o per un errore di accesso
al portale. La prossima pubblicazione del catalogo elimina anche l'eventuale
vecchia voce `Pro Loco FVG` da `monitors`, compresi i cicli `--retry-failed`.
Il modulo `pilot_proloco_watch.py` e lo strumento `audit_proloco_fvg.py`
restano disponibili per controlli manuali, senza essere chiamati dal job.
Le 15 fonti pubblicate e gli altri monitor non cambiano.

Questa modifica non e' operativa online finche' la nuova immagine del job
`meteofriul-events-refresh` non viene distribuita. Non richiede una nuova
esecuzione del job: il primo ciclo programmato usera' l'immagine aggiornata.
