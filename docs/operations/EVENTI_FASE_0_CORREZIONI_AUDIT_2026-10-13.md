# Eventi — Fase 0: correzioni dopo l'audit

Data: 13 ottobre 2026.
Ramo: `codex/events-card-quarantine`.
Base verificata all'inizio: `5a68de5dc1607105f921d4d2b731170f1a8a0446`,
coincidente con `main` locale. Worktree:
`C:/Users/LOCAL_USER/.codex/worktrees/events-card-quarantine/meteo FRIUL`.

**Seguito operativo:** le affermazioni su mancato deploy/prova nativa in
questo documento descrivono questa fase locale. La successiva distribuzione,
il fallimento del ciclo cloud, il recupero TurismoFVG e il collaudo TEST
sono documentati nel [resoconto deploy](EVENTI_FASE_0_DEPLOY_E_TEST_2026-10-13.md).

## 1. Perimetro autorizzato e stato della consegna

L'utente ha autorizzato la Fase 0 dopo l'audit in sola lettura, nell'ordine:
Villa Manin, diagnostica dei lotti falliti, `catalog_status` rispetto all'età,
test della cache, correzioni documentali.

Le modifiche sono locali al ramo. Nessun push GitHub, workflow Actions,
merge su `main`, build o distribuzione Cloud Run, modifica Storage o avvio
reale della raccolta è stato effettuato in questa fase. I test usano risposte
simulate e fixture locali; non dimostrano lo stato corrente dei siti.
Nessuna nuova APK/AAB, installazione o prova sul telefono in questa fase.

Il [documento di architettura](EVENTI_ARCHITETTURA_JOB_E_ALLARMI_2026-10-13.md)
resta il riferimento per l'intera struttura dei job, le 15 fonti, pubblicazione,
consultazione e allarmi. Le sue sezioni 11–13 sono evidenze storiche precedenti
alla Fase 0; non sono un collaudo delle nuove modifiche.

## 2. Villa Manin: conteggio degli scarti in revisione

### Problema riprodotto

Il collector divide i record API in attivi, inattivi e scartati. Per gli scarti
riconosceva già tre destinazioni: calendario passato, fuori dalle superfici
correnti, oppure revisione della scheda corrente/futura. La prova numerica
conteggiava soltanto le prime due. Il gate pretendeva che esaurissero tutti gli
scarti e rifiutava la fonte anche con un'altra scheda correttamente verificata.

Il nuovo test costruisce una scheda valida e una scheda corrente con titolo
della data «Prossimamente», su API, calendario e archivio coerenti. Prima del
fix il collector era `ok`, ma il gate dava `error` anziché `partial`.

### Correzione

- Il collector espone `rejected_review_count`.
- Il gate richiede un intero non negativo e riconcilia:
  `rejected_records = rejected_past_cards + rejected_outside_current_surfaces + rejected_review_count`.
- Il conteggio delle revisioni degli scarti non può superare il totale delle
  revisioni identificate; restano i controlli su URL, duplicati e separazione
  fra schede pubblicate e schede in revisione.
- Il caso riprodotto pubblica solo la scheda valida e lascia l'altra in
  `review_required`, con fonte `partial`.

Restano bloccanti l'inventario incoerente, la scomparsa non giustificata di una
scheda futura già verificata e il caso senza alcuna scheda verificata ma con
revisioni attive. Questo fix non introduce uno sblocco generale dei gate.

I nuovi collector producono la prova aggiornata. I vecchi cataloghi restano
leggibili dall'API, che non riesegue il gate sulle prove memorizzate; ripassare
manualmente nel nuovo gate un vecchio lotto privo del nuovo contatore richiede
una nuova raccolta, non un conteggio inventato.

File: [collector](../../backend/app/events/pilot_villa_manin.py),
[gate](../../backend/app/events/pilot_source_policy.py),
[test](../../backend/tests/test_pilot_villa_manin.py).

## 3. Report dei tentativi falliti

### Problema riprodotto

Quando una fonte fallisce, il merge mantiene internamente le schede e le
revisioni dell'ultimo lotto riuscito e salva il fallimento in `last_attempt_*`.
Il report del job leggeva la verifica dell'ultimo tentativo, ma i problemi e il
conteggio delle revisioni dal vecchio lotto. Poteva quindi indicare un problema
vecchio o zero revisioni mentre l'ultimo tentativo ne aveva altre.

### Correzione

| Stato persistito | Conteggi e problemi usati nel report |
| --- | --- |
| `fresh`, `partial` | Lotto corrente: `review_required`, `detail_candidates`, `verification` |
| `stale`, `unavailable` | Ultimo tentativo: `last_attempt_review_count`, `last_attempt_pending_count`, `last_attempt_issues`, `last_attempt_verification` |

`pending_count` è un campo diagnostico aggiuntivo. `review_issues` conserva il
limite di 30 voci; per il fallimento comprende revisioni e dettagli pendenti,
come l'elenco `last_attempt_issues`. `review_count` conta solo le revisioni:
non va sommariamente confrontato con la lunghezza di un elenco troncato che
può includere anche i pendenti. Le voci espongono URL, motivo e, se presente,
la lista dei codici `reasons`; non il testo completo delle eccezioni.

I test coprono errore con vecchio lotto, errore senza vecchio lotto, recupero
a `partial`, conservazione interna della vecchia revisione e assenza dei
campi privati dal report. L'esito del job e la scrittura Storage non cambiano.

File: [job](../../backend/app/events/pilot_cloud.py),
[test](../../backend/tests/test_pilot_cloud.py).

## 4. API: stato coerente con l'età

### Problema riprodotto

La query escludeva già i lotti più vecchi di 48 ore, con data futura o timestamp
invalido. `catalog_status`, invece, guardava solo `fresh`/`partial`/`stale` e
poteva dichiarare `complete` una risposta vuota perché tutti i lotti erano
scaduti. Il test prima del fix falliva sui tag mancanti; la selezione degli
eventi era già corretta.

### Correzione

La funzione `source_age_failure` è condivisa fra query e metadati HTTP. Entrambe
usano un unico `now` nella stessa richiesta. Non cambia la policy di visibilità.

| Lotto | Schede della fonte | Tag API | Stato globale |
| --- | --- | --- | --- |
| `fresh`, età da 0 a 48 ore incluse | Soggette ai normali filtri | Nessuno | `complete` se nessun'altra fonte ha tag |
| `partial`, stessa età | Solo le verificate | `quarantined_cards` | `degraded` |
| `fresh`/`partial`, età oltre 48 ore | Escluse | `source_expired` | `degraded` |
| `fresh`/`partial`, timestamp futuro | Escluse | `source_timestamp_future` | `degraded` |
| `fresh`/`partial`, timestamp mancante, invalido o senza fuso | Escluse | `source_timestamp_invalid` | `degraded` |
| `stale`/`unavailable` | Escluse | Errore dell'ultimo tentativo, o `source_error` | `degraded` |

`source_status` conserva lo stato scritto dal collector: `fresh` significa
che la raccolta era riuscita, non che il lotto sia tuttora entro le 48 ore.
I nuovi tag spiegano questa differenza. Per un lotto `partial` scaduto il tag
principale è temporale; la quarantena resta visibile nello stato `partial`.
La scadenza di una fonte non nasconde le schede valide delle altre.

Una risposta vuota per assenza di eventi nel raggio, a fonti sane, resta
`complete`. Non è stato introdotto `empty_reason`: i diagnostici sono per
fonte e non provano da soli perché una specifica ricerca restituisca zero
schede. `status=ready` significa che la risposta è stata costruita, non che
ogni fonte sia completa. Nessun nuovo allarme cloud è introdotto per l'età.

Test: limite esatto di 48 ore e un microsecondo oltre, fusi equivalenti,
timestamp futuro o invalido, lotti `fresh` e `partial`, fonte sana insieme a
fonte scaduta, risposta valida vuota e filtro geografico.

File: [catalogo](../../backend/app/events/pilot_catalog.py),
[API](../../backend/app/events/pilot_http.py),
[test HTTP](../../backend/tests/test_pilot_http.py).

## 5. Cache: soli test, frontend operativo invariato

I test attraversano l'adattatore reale `fetchLocalEvents`, il controller e la
cache persistita usando un trasporto HTTP simulato. Coprono sia l'endpoint
ufficiale sia il proxy del pilot.

1. **Risposta vuota valida:** la cache piena viene già sostituita con `[]`.
   Il test verde conferma anche che una vecchia cache Home non ripopoli la
   schermata e che un successivo errore offline non faccia ricomparire le
   vecchie schede. Non è servito modificare il codice operativo.
2. **Risposta vuota con fonte scaduta:** test di caratterizzazione, verde sul
   comportamento esistente. I diagnostici restano in `raw`, mentre
   l'adattatore restituisce `cacheStatus=ready`; il controller scrive `[]` e
   mostra stato `fresh`. La Fase 0 documenta questa limitazione senza cambiare
   conservazione dei dati, messaggi o durata della cache.

Non viene forzato un test rosso per un comportamento che si vuole mantenere.
La decisione se mostrare dati precedenti in caso di fonti scadute resta per
una fase successiva insieme a freschezza, persistenza e motivi di risposta vuota.

File: [test del controller](../../frontend/src/features/events/eventsDataController.test.js).

## 6. Documentazione e allarmi

Corrette le quattro affermazioni emerse dall'audit:

- `past_event` non crea automaticamente una quarantena con URL e motivo;
  il merge non conserva ogni `excluded` degli adapter.
- La soglia generica per esclusioni inattese riguarda le 12 `strict_source`;
  Pordenone Pensa e i due Verdi hanno altre verifiche ma non questa soglia.
- La precedente dipendenza dal deploy API per leggere tutte le fonti
  `partial` è indicata come risolta nell'evidenza storica; la Fase 0 resta locale.
- La descrizione dell'allarme `events-failures` non promette più che l'intero
  vecchio catalogo sia ancora visibile dopo un fallimento: le fonti sane
  possono essere aggiornate, quelle fallite restano escluse dall'API.

Nel JSON delle policy cambia solo `documentation` della voce
`events-failures`. Soglie, filtri, frequenze, destinatari e altre policy sono
invariati. Il nuovo testo non è stato sincronizzato sul cloud.

## 7. Verifica locale

| Controllo | Esito |
| --- | --- |
| Villa Manin, nuovo caso prima del fix | Fallisce: `error` anziché `partial` |
| Report fallito, nuovo caso prima del fix | Conteggio vecchio 1 o 0 anziché 2 |
| API, nuovi casi prima del fix | Tag di età assenti o sostituiti da `quarantined_cards` |
| Test mirati Villa Manin/job/catalogo/API | 78 passati, 32 sotto-casi |
| Suite backend Eventi `pytest tests -k pilot` | 764 passati, 2 saltati, 213 sotto-casi; 1.044 test estranei deselezionati |
| Frontend controller/API/cache, loader nativo | 42 passati in 3 file |
| ESLint del file frontend modificato | Passato |
| Contratti PowerShell dei job di produzione | Passati |
| Diff semantico JSON delle policy | Solo `events-failures.documentation` |
| `git diff --check` e link locali dei due MD | Passati |

Comandi eseguiti dai rispettivi percorsi `backend` e `frontend`:

```text
python -B -m pytest tests/test_pilot_villa_manin.py tests/test_pilot_cloud.py tests/test_pilot_catalog.py tests/test_pilot_http.py -q -p no:cacheprovider
python -B -m pytest tests -k pilot -q -p no:cacheprovider
npm test -- src/features/events/eventsDataController.test.js src/services/eventsApi.test.js src/services/eventsCache.test.js
npx --no-install eslint src/features/events/eventsDataController.test.js
```

Log della suite backend: `%TEMP%/events-phase0-backend-20261013.log`.
I test aggiornati backend sono già fra quelli copiati nel
`backend/Dockerfile.events-pilot`. La build Docker/Linux non è stata eseguita:
questo controllo locale non è una prova del container distribuito.

## 8. Passo successivo

Revisionare il diff e questo resoconto prima di intervenire online, come
richiesto dall'utente. Per rendere operative tutte le correzioni serviranno
il worker (Villa Manin e report) e il servizio API (diagnostica dell'età);
il solo aggiornamento del worker non aggiorna i metadati HTTP.

Al successivo collaudo verificare catalogo, tag, quarantene, esito del job e
consultazione nell'app TEST. La verifica reale richiesta da `AGENTS.md` resta
necessaria prima della nuova promozione a `main`; quella precedente non
certifica questi cambiamenti. GitHub resta sospeso su richiesta dell'utente.
La deduplica degli avvisi e le nuove policy per zero schede, freschezza e dati
stale appartengono alle Fasi 1 e 2 e non sono state implementate qui.

## 9. Collaudo successivo

La raccolta reale in sola lettura, il recupero mirato Azalea, i controlli API
su cataloghi reali, la prova browser sul telefono e il ripristino del pilot
sono registrati nel
[collaudo locale](EVENTI_FASE_0_COLLAUDO_LOCALE_2026-10-13.md). Questa evidenza
non modifica retroattivamente il risultato dei test o lo stato locale della
consegna iniziale.
