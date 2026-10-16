# Paesi in Festa: date finali e schede in revisione

Verifica del 11 ottobre 2026, ramo `codex/events-paesi-card-quarantine`.

## Caso osservato

La scheda «Un giorno con Napoleone» a Campoformido indica 9–11 ottobre 2026.
L'11 ottobre la pagina di archivio la marca `category-eventi-passati`. Il
precedente controllo trattava quella categoria come un conflitto anche
nell'ultimo giorno indicato. La data è ancora valida quel giorno: la scheda
deve essere verificata nel dettaglio e può restare nel catalogo.

Una lettura integrale in sola lettura del sito, con data 11 ottobre 2026, ha
prodotto 22 eventi, zero schede in revisione e gate di pubblicazione superato.
L'esecuzione ha letto 24 schede negli elenchi, 21 dettagli FVG e tre URL fuori
regione; ha controllato cinque superfici di scoperta e le sitemap. Il controllo
è stato ripetuto dopo l'implementazione con lo stesso risultato.

## Regola di pubblicazione

- Se la categoria «passati» compare nel giorno finale dell'intervallo, decidono
  le date concordanti fra elenco e dettaglio. Un evento con fine oggi resta
  eleggibile.
- Se una scheda porta «passati» ma la sua data finale è futura, la scheda viene
  registrata in `review_required` e non pubblicata.
- Se il dettaglio di una singola scheda contraddice l'elenco o non supera
  l'estrazione, viene registrato il motivo e la scheda non viene pubblicata.
- Quando le altre schede superano i controlli, Paesi in Festa viene pubblicata
  con stato `partial` e tag `quarantined_cards`. Il job conserva URL e motivo
  per la revisione successiva; l'API pubblica soltanto il tag, non il dettaglio
  diagnostico.
- Errori della struttura di scoperta, sitemap e assenza di qualsiasi evento
  verificato restano errori di fonte. In questi casi i dati precedenti non
  vengono ripubblicati come correnti.

Verifiche locali: 666 test `test_pilot_*.py` superati, uno ignorato; test
dedicati per categoria «passati» nell'ultimo giorno, quarantena di una scheda
conflittuale, pubblicazione delle schede valide e tag dell'API.

Questa modifica non è distribuita finché il ramo non supera i controlli di
promozione previsti da `AGENTS.md`.
