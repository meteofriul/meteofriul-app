# Barcolana: fase del programma e appuntamenti futuri — 28 ottobre 2026

## Perimetro e provenienza

Intervento locale sul ramo `codex/events-barcolana-seasonality`, creato dal
main verificato `9f81253e6b1832816e4032930b7b5eb64ebff6ad`.
Il ramo conserva tramite avanzamento fast-forward il lavoro locale precedente
fino a `8ac7ea6a6883d1dfce08430c7b3894826054fc73`, compresa la correzione CSS.
Gli agenti utilizzati sono `eventi` per il codice e `build_verifica` per revisione
e prove; il coordinatore cura questa documentazione.

Nessun push, promozione a main, deploy, avvio di job, modifica dello scheduler
o del monitoraggio. Nessuna modifica frontend, dipendenze, versione, AAB 300038,
artefatti Web o loro qualificazione. Il problema di timeout remoto resta aperto.

## Evidenze disponibili

- Il [controllo job del 28 ottobre](JOBS_READONLY_AUDIT_20261028.md) e la diagnosi
  locale successiva documentano errori di lettura del calendario, non una
  risposta valida che dichiari assenza di eventi.
- Il catalogo conservato nella diagnosi contiene appuntamenti fino al
  29 novembre 2026. Si tratta del programma precedentemente acquisito: non
  dimostra che una nuova lettura del sito sia riuscita il 28 ottobre.
- La [notizia ufficiale dell'edizione](https://www.barcolana.it/it/news/2026/barcolana58-presented-by-generali-tutto-pronto-per-la-grande-regata)
  descrive la manifestazione principale del 2–11 ottobre. La sua conclusione
  non prova la fine degli appuntamenti collegati.
- Il [calendario pubblico](https://www.barcolana.it/it/calendario-eventi), letto
  tramite servizio Web durante questo intervento, mantiene riferimenti al 2026;
  il titolo generico della pagina riporta ancora un numero di edizione diverso.
  Questa lettura non è un replay dell'endpoint dinamico usato dal collector e
  non certifica la sua disponibilità, completezza o il recupero del job.
- Non abbiamo un segnale ufficiale verificato di «programma in preparazione»
  o «stagione conclusa». Non introduciamo interpretazioni automatiche di una
  pagina vuota, un titolo generico o una richiesta fallita.

Evidenze locali riusate, fuori dai file versionati:
`tmp/events-source-diagnosis-20261028/`, in particolare
`barcolana-stored-event.json`, `source-logs.json` e `source-diagnostics.json`.
Per budget e retry già distribuiti valgono il
[verbale del 26 ottobre](EVENTS_BARCOLANA_RECOVERY_20261026.md) e il relativo
[deploy](EVENTS_BARCOLANA_RECOVERY_DEPLOY_20261026.md).

SHA-256 delle evidenze locali riusate:

| File | SHA-256 |
| --- | --- |
| `barcolana-stored-event.json` | `9e3dc06d73ccebdd9e41145c64dbe3680a0bfc7d79a427f9502e9c81f0c017db` |
| `source-logs.json` | `3e87ebe4ead87426ed7ca0e1bf9002ecdf9f2ecf53365f78a7c81df98de83064` |
| `source-diagnostics.json` | `9cffcd9038ff98541c74044fe68beccd3057d8aa461848f076f69a5733b87be6` |

## Modifica locale

La fase del programma viene calcolata **dopo** i controlli completi della fonte,
prima di eliminare dalla pubblicazione la scheda ormai trascorsa. È conservata
nella prova interna del lotto, senza cambiare le schede dell'app.

| Fase interna | Significato |
| --- | --- |
| `programme_upcoming` | Il programma completo è verificato, ma la sua prima data deve ancora arrivare. Non significa «programma in preparazione». |
| `programme_active` | È iniziato il programma e non è ancora terminata la manifestazione principale. |
| `post_regatta_events` | La manifestazione principale è passata, ma restano appuntamenti verificati, anche nel giorno corrente. |
| `verified_programme_elapsed` | Il programma completo appena verificato non contiene più date correnti o future. Non certifica la chiusura ufficiale della stagione. |

La prova riporta anche il numero degli appuntamenti rimanenti e la prossima
data. Questi valori sono ricalcolati dalle sessioni verificate; valori
precompilati nel lotto non costituiscono evidenza.

Il confronto con il precedente programma della stessa edizione protegge ogni
appuntamento ancora futuro usando data, titolo, sede e orari. Perdere un solo
appuntamento resta bloccante anche se il conteggio totale scende meno del 10%.
Le soglie complessive già presenti restano attive. Una modifica ufficiale a
titolo, sede, data o orario può richiedere revisione: il controllo non decide
automaticamente che si tratti di una cancellazione o dello stesso appuntamento.
Il confronto resta attivo anche se il precedente lotto è diventato obsoleto.
Un primo tentativo fallito senza alcun programma verificato non impedisce invece
la prima acquisizione riuscita.

Dal 2027, l'archivio dell'edizione 2026 non può attestare una fonte corrente:
il gate restituisce `edition_not_current`. Il passaggio alla nuova edizione
richiede la verifica delle sue fonti e configurazioni; non viene dedotto dal
solo anno del calendario locale. Gli errori di trasporto restano errori.

## Verifica locale

**156 test distinti PASS**, con Python `3.13.5`, senza installazioni o accessi
alla rete durante i test. Il requisito Python `3.13` è rispettato.

- Regressione prima della modifica: FAIL atteso. La rimozione della sola
  premiazione futura, inferiore al 10% del programma, restituiva erroneamente
  `ok` invece di `error`. Dopo la modifica: PASS.
- Modulo `tests.test_pilot_barcolana`: **28 test PASS**, inclusi calendario
  sintetico, letture simulate, budget e comportamento di trasporto preesistente.
- Suite comuni di policy, raccolta, catalogo, health, cloud, HTTP e CSS:
  **127 test PASS**; il test specifico di riconciliazione annuale Barcolana
  aggiunge **1 PASS**. Il singolo before/after non è contato nuovamente.
- Coperti il 24/25 settembre, l'11/12 ottobre, il 29/30 novembre, il 31 dicembre
  e il 1 gennaio 2027; perdita di sessioni future/odierne, uscita delle sessioni
  passate, precedente obsoleto, primo recupero dopo `unavailable`, dati malformati,
  ricalcolo dei metadati e conservazione della prova con elenco eventi vuoto.
- Compilazione mirata dei due file Python: PASS, cache in directory temporanea
  del sistema operativo. Nessun output generato aggiunto al repository.
- Revisione indipendente `build_verifica`: nessun difetto bloccante rilevato.
- Controllo canonico dopo staging: PASS, 4004 file tracciati, nessun output
  generato, segreto locale o riferimento operativo a workspace obsoleti tracciato.
  Diff e collegamenti documentali aggiunti verificati localmente.

[Ricevuta, comandi e hash dei byte verificati](evidence/events-barcolana-seasonality-20261028/verification.json).
I comandi unittest usano `python -B -m unittest ... -v`, con cwd `backend/`.
La ricevuta identifica il candidato tramite hash dei sorgenti prima del commit.
I log completi restano in `tmp/events-barcolana-seasonality-20261028/`.
Le fixture sono sintetiche: i test non sono un replay integrale della corsa
cloud fallita e non provano i tempi di risposta del sito reale.

Nessuna suite frontend, build Android o suite backend completa eseguita:
la verifica è limitata al cambiamento backend e ai suoi contratti condivisi.

## Limiti e passaggio successivo

Questa modifica rende più preciso il controllo stagionale. **Non risolve il
timeout remoto e non considera una fonte irraggiungibile come «fuori stagione».**
Rimangono invariati richieste HTTP, timeout, retry, budget per fonte, controlli
di completezza, esclusione dei lotti obsoleti e validità temporale del catalogo.

L'assenza di date future era già pubblicabile dopo la verifica di un programma
completo; ora viene distinta esplicitamente dalla mancanza di dati e protetta
dalla perdita silenziosa di appuntamenti. Un calendario svuotato dall'editore
continuerà a richiedere una prova ufficiale adeguata e una verifica del parser.

Prima di dichiarare il recupero pubblico servono promozione con PR/CI, deploy
separatamente autorizzato e riscontro della corsa ordinaria, del catalogo salvato
e delle API Eventi. Nessuna di queste attività è attestata dalle prove locali.
