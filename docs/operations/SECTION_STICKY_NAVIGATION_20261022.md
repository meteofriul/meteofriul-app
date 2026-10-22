# Navigazione fissa nelle sezioni Bollettino ed Eventi

Stato: modifica locale sul ramo `codex/section-sticky-navigation`, basato su
`main` `3da1db2d4d2f1de4bd14745ef7fd078ec8d399dd`. Non promossa su main.

## Perimetro approvato

- Bollettino: località e menù meteo esistenti restano visibili durante lo
  scorrimento. Le pill dei giorni e il contenuto continuano a scorrere.
- Eventi: località e filtri esistenti restano visibili nella lista.
  Il dettaglio evento resta sovrapposto alla schermata, barra compresa.
- Nessun nuovo controllo, testo o cambio di grafica. Previsioni e Tempo reale
  mantengono lo scorrimento precedente.
- L'apertura di un'ancora nel Bollettino tiene conto dell'altezza effettiva della
  barra, così il contenuto richiesto può apparire sotto i controlli.

## Verifiche del 22 ottobre 2026

- Vitest con `--configLoader native`: 82 test superati in 8 file, relativi a
  composizione/navigazione meteo, route, Eventi e dettaglio, CSS del layout.
  Il test di composizione esistente è stato adeguato al contenitore della barra,
  conservando i controlli sui pulsanti e sull'isolamento dei gesti.
- ESLint sui componenti e sul test modificati: superato.
- `git diff --check`: superato.
- Browser integrato, anteprima del ramo avviata esclusivamente con
  `scripts/start-local-weather-pilot.ps1 -WeatherCloud` su porta 5174;
  provata anche la modalità prevista `-StableFrontend`.
- Controllo visivo a 390 × 844: Bollettino ed Eventi mantengono località e menù
  visibili durante lo scorrimento in italiano/tema chiaro e friulano/tema scuro.
  Coperto il margine superiore per non lasciar comparire frammenti del contenuto
  dietro la barra. Screenshot osservati nella chat.
- Eventi: aperta una scheda dalla lista scorsa; il dettaglio copre anche la barra.
  Alla chiusura tornano lista e filtri. Nessuna modifica al comportamento del
  dettaglio o alle sue azioni.

## Limiti e lavoro ancora da verificare

Il launcher ha infine fermato i propri processi perché il controllo del reader
meteo corrente non è passato, sia in modalità Vite sia stabile. Il successivo
`-WeatherCloud -CheckOnly` ha confermato il controllo non superato. Questa nota
non attribuisce una causa al servizio: non è stata eseguita una diagnosi cloud.
La build Web locale della modalità stabile è riuscita (restano gli avvisi
preesistenti sulla dimensione dei chunk e sull'import Almanac).

Il percorso Home/Sintesi → allerta nel Bollettino non è stato completato nel
browser con un'allerta corrente: nella sessione non era presente il relativo
blocco. L'offset è implementato ma la prova visiva di quel percorso resta aperta.
Nessuna verifica su telefono o Safari/iPhone in questa attività. Prima della
promozione su main restano da completare il percorso dell'allerta e la verifica
su dispositivo prevista dalle regole del repository.

Nessuna AAB, installazione, emulatore, push, deploy, esecuzione di job o invio
manuale. Sponsor e altri lavori (posizione Android, configurazione nativa,
sovrapposizioni della mappa) non modificati.
