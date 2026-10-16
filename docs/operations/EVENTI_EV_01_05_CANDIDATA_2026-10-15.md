# Candidata integrata EV-01–EV-05

15 ottobre 2026. Ramo locale: `codex/events-ev01-05-candidate`.
Base: `main`, commit `5a68de5dc1607105f921d4d2b731170f1a8a0446`.
Worktree isolato: `C:\Users\LOCAL_USER\.codex\worktrees\events-ev01-05-candidate\meteo FRIUL`.

Le cinque correzioni sono ora presenti in una sola candidata. Restano
riconoscibili i calendari di apertura incerti, gli orari verificati e le
mostre con sola scadenza; il degrado è visibile in Home/Eventi e persiste
nella cache; l'archiviazione verificata di Spazzapan non blocca gli eventi
ancora attivi.

## Commit integrati

Cherry-pick con riferimento al commit originale:

| Ambito | Commit originale | Commit nella candidata |
| --- | --- | --- |
| EV-01/02/03: calendari, orari, sola scadenza | `1bd61ae0` | `43ea9693` |
| EV-04: degrado, API e cache | `0055d104` | `cd8a2eb4` |
| EV-05: archiviazione delle mostre | `70c9c894` | `4a41f590` |
| EV-05: notizia ritirata e incontro del 28 ottobre | `223422e1` | `c89d2567` |

Sono stati selezionati i quattro commit applicativi EV-01–EV-05.
Gli altri interventi indipendenti nella storia del ramo Spazzapan
(quarantena regionale, contatori Villa Manin, monitoraggio e note dei deploy
precedenti) non fanno parte di questa integrazione. La candidata parte da
main: non rappresenta l'allineamento completo a tutte le modifiche già
presenti nell'immagine cloud.

Non sono emersi conflitti testuali. I file comuni di catalogo, vista e
modello Eventi, gate delle fonti e Dockerfile sono stati riconciliati da Git
e riesaminati. Il collector, le fixture e i test Spazzapan coincidono con
quelli del ramo collaudato; anche la funzione del gate di Spazzapan è
identica, verificata mediante confronto dell'AST.

## Compatibilità risolta e test aggiunti

Il test HTTP EV-01/02/03 aggiungeva `now` a un wrapper di `query_catalog`.
EV-04 passa ora esplicitamente lo stesso istante al filtro e alla diagnostica:
il wrapper generava un doppio argomento e un HTTP 503 nei test. Il problema
è stato riprodotto e corretto fissando l'orologio dell'API. Il filtro reale
viene ora eseguito direttamente; il contratto di produzione non è stato
indebolito per soddisfare il test.

Una nuova regressione backend combina proiezione regionale, validazione,
fixture Spazzapan del 15 ottobre, gate, catalogo misto e WSGI. Verifica
periodo con aperture sconosciute, ora 17:00, mostra senza data iniziale,
mostra attiva e incontro Spazzapan alle 18:00, esclusione di Pausig,
degrado delle altre fonti e scadenza del lotto oltre 48 ore.

La regressione frontend combinata verifica nello stesso catalogo la
classificazione temporale, le anteprime con orari e sola scadenza, il
messaggio di degrado, la cache, la riapertura e il fallback offline.

Il Dockerfile include anche il test del contratto calendario nelle suite
delle eventuali build future. Non è stata eseguita alcuna build.

## Regressioni eseguite sulla candidata

Ambiente: Windows, Python 3.13.5, Node 22.17.1, Vitest 4.1.9.
Dipendenze frontend esistenti riutilizzate mediante junction ignorata da Git.

| Verifica | Risultato |
| --- | --- |
| Suite backend `test_pilot_*.py` | `Ran 709 tests`, `OK (skipped=1)` |
| Palazzo Attems | 7 test passati |
| Frontend Eventi/Home, API/cache/programmi, copy e navigazione | 500 test passati in 42 file |
| ESLint sui file JS/JSX modificati rispetto a main | Passato |
| `git diff --check` | Passato |
| Controllo workspace cleanliness | Passato |

Il solo gruppo saltato è `PilotCommunityRealGeographyTests`: manca
l'archivio ISTAT locale opzionale. Non è un caso EV-01–EV-05.
I 39 test backend iniziali mirati sono compresi nella suite estesa,
non vanno sommati.

Comandi backend, dalla directory `backend`:

```text
python -B -m unittest discover -s tests -p 'test_pilot_*.py' -v
python -B -m unittest tests.test_attems_audit
```

Comando frontend, dalla directory `frontend`:

```text
npm test -- src/features/events src/features/home src/services/eventsApi.test.js src/services/eventsCache.test.js src/services/pilotProgrammeProjection.test.js src/services/runtimeDeviceCache.test.js src/copy/eventsViewCopy.test.js src/app/AppRoutes.test.jsx src/app/AppRoutes.refreshNavigation.test.jsx src/app/AppRoutes.activeCandidate.test.jsx
```

Lo script npm usa `--configLoader native`.

## Limiti e consegna

Test con fixture e servizi simulati, rendering React statico e test DOM
di navigazione. Nessuna nuova sessione browser, prova sul telefono,
raccolta reale o ciclo cloud. Non è stata eseguita l'intera CI remota.

Nessun deploy, push, merge su main, build Android, build Web/Docker,
installazione o modifica del catalogo cloud. Main, rami originali e checkout
canonico rimangono invariati. EV-06 e successivi restano fuori dal perimetro.
Il rapporto finale e i log delle regressioni sono salvati fuori dal repository.

Le note [EV-01/02/03](EVENTI_EV_01_03_2026-10-15.md) e
[EV-04](EVENTI_EV_04_2026-10-15.md) descrivono i collaudi separati precedenti;
questo documento registra la successiva integrazione.
