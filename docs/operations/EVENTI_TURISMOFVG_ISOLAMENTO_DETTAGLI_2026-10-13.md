# TurismoFVG — isolamento degli errori dei dettagli

Data: 13 ottobre 2026. Ramo: `codex/events-card-quarantine`.
Base prima di questa correzione: `86b82003`.

**Stato: correzione locale, test automatici superati; non distribuita.**
La versione cloud verificata nell'ultimo collaudo resta `9718e2bc`.
Questo intervento non modifica main, GitHub, immagini online, scheduler,
policy email, app installate o il pilot condiviso sulla porta 5174.

## 1. Perché serve

L'[audit dei pendenti](EVENTI_TURISMOFVG_PENDING_AUDIT_2026-10-13.md)
ha riprodotto quattro difetti: un dettaglio irraggiungibile ferma tutta la
fonte; il rinnovo anticipato può rimuovere una verifica ancora valida;
i diagnostici del tentativo fallito perdono URL e stato intermedio;
pagine di manutenzione con HTTP 200 possono diventare un lotto vuoto.

Non abbiamo identificato a posteriori i sette URL realmente falliti nel
ciclo cloud: il checkpoint salvato allora non li conserva. I 58 URL stimati
nell'audit sono candidati, non sette errori identificati. Questa correzione
risolve comportamenti riprodotti e migliora le prove dei prossimi cicli;
non attribuisce una causa non dimostrata all'incidente precedente.

## 2. Regole della raccolta mobile di 45 giorni

Prima restano obbligatori gli stessi controlli di calendario, paginazione,
sitemap, firme, identità, date, copertura della finestra e freschezza.
Poi ogni dettaglio selezionato deve avere un esito esplicito.

| Caso | Comportamento |
| --- | --- |
| Lettura e scheda valide | Scheda eleggibile alla pubblicazione. |
| Timeout o errore HTTP isolato, inventario completo e prova corrente di funzionamento | Dopo i tentativi previsti, quarantena del solo URL; schede sane pubblicabili come `partial`. |
| Eccezione del parser su una pagina isolata, con prova corrente di funzionamento | Quarantena del solo URL, fase `parse`, senza riscaricare tre volte lo stesso contenuto. |
| HTML senza struttura riconoscibile, con altre pagine funzionanti | URL escluso e diagnosticato come `missing_structured_detail`. |
| Tutte le letture fallite, senza prova corrente di funzionamento | Fonte non verificata; nuovo lotto non pubblicato. |
| Tutti i dettagli restituiscono manutenzione HTTP 200 | Errore della fonte; non sostituisce il vecchio lotto con uno vuoto. |
| Inventario incompleto o URL non affidabile nella sitemap | Errore della fonte; URL non affidabile mai scaricato. |
| Tempo esaurito con URL mai tentati | Rimangono pendenti con `not_attempted_budget`; non sono quarantene inventate. |
| Tutte le schede attive escluse, nessuna pubblicabile | Errore e revisione; non si dichiara una stagione conclusa. |
| Inventario legittimamente vuoto e verificato | Lotto vuoto valido, come prima. |

### Prova corrente di funzionamento

Se vi sono errori di lettura serve **almeno un dettaglio letto nello stesso
ciclo** con titolo, data e località strutturati. Valgono anche i risultati
verificati dai recuperi specifici già esistenti, senza pretendere un'unica
classe CSS. Il gate ricontrolla firma, timestamp e campi della prova.
Un risultato precedente in cache, da solo, non prova che il sito funzioni ora.

Se sono fallite tutte le letture tentate e ci sono schede verificate riusate,
si provano al massimo **tre URL distinti** di quelle schede, uno per volta,
fermandosi alla prima prova riuscita o alla riserva di tempo già prevista.
Sono letture HTML dei dettagli, non PDF né una scansione aggiuntiva del sito.

Non viene introdotta una soglia percentuale di guasto: anche sette URL
falliti possono restare in quarantena con una scheda sana pubblicabile.
Questo criterio dimostra che la fonte risponde almeno in parte; non dimostra
che ogni sua sezione funzioni. Se i tre URL di controllo falliscono, la fonte
resta non verificata anche quando altre pagine potrebbero essere sane.
È una scelta conservativa esplicita, non una diagnosi certa di sito spento.

### Tentativi e budget

Per gli errori di trasporto rimangono fino a tre tentativi del collector;
il client HTTP esistente può fare due tentativi per ciascuna chiamata.
Il contatore diagnostico misura le chiamate del collector, non tutti i GET.
Per un'eccezione del parser basta una lettura: ripetere il download non
corregge quel contenuto o quel codice. Le sonde di salute non rilanciano gli
altri URL già falliti. Limiti di tempo e concorrenza restano quelli esistenti.

`within_budget=true` non equivale da solo a fonte completa: il collector
può essersi fermato alla riserva di 20 secondi. Lo stato dei singoli URL e
`detail_health.stop_reason=budget_reserve` distinguono questo caso.

## 3. Rinnovo anticipato e freschezza

Il collector tenta già il rinnovo a metà della validità del risultato.
Se quel tentativo facoltativo fallisce per timeout, connessione o HTTP
408/429/500/502/503/504, può conservare il risultato precedente soltanto se:

- era stato riusato con la stessa firma dell'inventario;
- è ancora entro il limite di età esistente alla fine della raccolta;
- un dettaglio corrente prova che la fonte risponde;
- il gate lo ritrova identico nel checkpoint precedente.

`checked_at` rimane quello originale. Il rinnovo fallito è visibile con
`disposition=retained_valid` e `original_checked_at`. Non si conservano dati
scaduti, firme cambiate o un vecchio risultato dopo un nuovo HTML ambiguo.
Un errore 403 non è incluso nel recupero transitorio del risultato precedente.

I limiti restano 48 ore per dettagli prossimi, 96 per quelli più lontani e
7 giorni per gli esiti inattivi previsti dal codice. Non si cambia la policy
API che nasconde lotti `stale` o troppo vecchi.

## 4. Prove e diagnostici persistenti

Il controllo TurismoFVG registra:

- `detail_observations`: URL, firma, data della lettura e prova strutturata,
  esclusione riconosciuta, pagina mancante o tentativo fallito;
- `detail_diagnostics`: fase, motivo, codice HTTP quando disponibile,
  numero di tentativi, timestamp e destinazione della scheda;
- `detail_health`: conteggi ricalcolabili, pendenti, recuperi di prove valide
  e motivo di arresto;
- `detail_candidates`: URL realmente ancora pendenti con motivo esplicito.

Non si salva il testo libero delle eccezioni di lettura dei dettagli: la
classe dell'errore e i campi strutturati bastano per questa diagnostica.

Nel catalogo un lotto riuscito conserva `detail_diagnostics`; uno fallito
conserva `last_attempt_detail_diagnostics`, contatori e problemi del tentativo.
Quando esiste un checkpoint verificato, esso resta in `control_checkpoint`,
mentre il tentativo fallito è salvato separatamente in
`last_attempt_control_checkpoint`. Il recupero continua a partire dal
checkpoint verificato: il nuovo checkpoint fallito serve alla diagnosi,
non è un'autorizzazione a riusarne i dati come verificati.

Al primo avvio, senza checkpoint precedente verificato, resta il comportamento
esistente di salvataggio del progresso in `control_checkpoint`; lo stato
`unavailable` impedisce di trattarlo come catalogo pubblicabile.
Se il processo viene terminato dall'esterno prima di restituire il risultato,
il merge non può salvare progressi mai ricevuti: questa modifica non aggiunge
checkpoint remoti durante ogni singolo download.

Il report del job include al massimo 30 righe diagnostiche, oltre ai
contatori. Il catalogo conserva la mappa completa entro i limiti esistenti.
L'API pubblica non espone questi dettagli interni; restituisce le schede
ammesse e il tag `quarantined_cards` per un lotto parziale.

Stima locale, non verifica della fonte: aggiungendo 1.216 osservazioni
sintetiche strutturate al checkpoint del catalogo salvato dopo il recupero,
il controllo non compresso misura 3.605.676 byte (limite 6 MiB), il checkpoint
aggiuntivo 810.680 byte codificati (limite 2 MiB), il catalogo con entrambi i
checkpoint 3.388.840 byte (limite 8 MiB). Sono dimensioni di quel campione,
non una garanzia per ogni crescita futura. I limiti continuano a essere imposti.

## 5. Pubblicazione, allarmi e altri percorsi

Un lotto `partial` verificato viene salvato e non fa fallire il job per quelle
sole quarantene. Un inventario incompleto, una fonte non verificabile o gli
altri errori operativi continuano a produrre il fallimento previsto.
Una prova precedente conservata correttamente può lasciare il lotto `fresh`,
con il problema di rinnovo nei diagnostici e senza quarantena pubblica.

Non sono state modificate le policy email, la deduplica degli avvisi o il
monitor dei siti candidati. La relazione tra esito del job e allarmi rimane
quella descritta nell'[architettura](EVENTI_ARCHITETTURA_JOB_E_ALLARMI_2026-10-13.md).
Questa correzione è specifica della raccolta mobile TurismoFVG; non allenta
i gate degli altri siti. Il percorso annuale storico mantiene il comportamento
precedente. Il monitor annuale operativo confronta l'inventario e può ancora
fallire per indisponibilità o discordanza: non è la nuova quarantena dettagli.

## 6. File modificati

| File | Responsabilità |
| --- | --- |
| `backend/app/events/pilot_regional_health.py` | Prove correnti, diagnostici, decisioni sulle letture fallite e controllo indipendente. |
| `backend/app/events/pilot_regional_year_control.py` | Separazione download/parser e registrazione delle osservazioni, attiva solo su richiesta del collector mobile. |
| `backend/app/events/pilot_regional_verified.py` | Sonde limitate, conservazione dei rinnovi validi, quarantena e protezione dal lotto vuoto ingiustificato. |
| `backend/app/events/pilot_source_policy.py` | Gate indipendente che ricalcola e confronta le prove prima della pubblicazione. |
| `backend/app/events/pilot_catalog.py` | Diagnostici persistenti e checkpoint fallito separato. |
| `backend/app/events/pilot_cloud.py` | Report limitato e coerente con il tentativo corrente. |
| `backend/tests/test_pilot_regional_failure_isolation.py` | Regressioni e integrazione locale collector → gate → catalogo → pubblicazione simulata → API. |
| `backend/Dockerfile.events-pilot` | Include la nuova suite nel controllo unittest della futura immagine. |

## 7. Verifiche eseguite

Ambiente locale Windows, senza accessi ai siti o scritture cloud nelle prove.
I casi principali sono stati prima riprodotti con test falliti; dopo il fix:

- nuova suite: **19 test e 7 sottocasi passati**;
- suite backend selezionata con `-k pilot`: **783 test passati, 220 sottocasi
  passati, 2 saltati, 1.044 deselezionati**, in 39,43 secondi;
- l'orologio della nuova suite è fissato al 13 ottobre 2026, così i test non
  dipendono dalla data reale di esecuzione;
- `git diff --check` superato;
- il test di integrazione usa collector, gate, merge, writer e API reali nel
  codice, ma HTML e Storage sono simulati: non è un'esecuzione Cloud Run.

Copertura nuova: timeout/403/429/503 isolati; eccezione del parser; sette
errori e una scheda sana; timeout generale; manutenzione HTTP 200 generale;
singola pagina senza struttura; rinnovo valido/scaduto/firma cambiata;
contenuto ambiguo dopo rinnovo; budget terminato; inventario vuoto valido;
tutte le pagine attive 404; URL inattendibile; gate con prove alterate;
recupero specifico senza CSS legacy; salvataggio dei diagnostici, pubblicazione
parziale e visibilità nell'API.

Nel primo lancio esteso un test delle segnalazioni non trovava `app` nel suo
sottoprocesso. Ripetendo con `PYTHONPATH` impostato alla directory backend,
passa anche quel test, senza modifica del codice delle segnalazioni.
I due test saltati e quelli deselezionati non sono dichiarati verificati.
Non è una CI GitHub né una build container o un nuovo collaudo del telefono.

Comandi dalla radice del worktree in PowerShell:

```powershell
$env:PYTHONPATH = Join-Path (Get-Location) 'backend'
python -B -m pytest backend/tests/test_pilot_regional_failure_isolation.py -q -p no:cacheprovider --tb=short
python -B -m pytest backend/tests -k pilot -q -p no:cacheprovider --tb=short
```

Log locale ignorato da Git:
`.dev-logs/events-turismofvg-isolation-fix/backend-pilot-tests.txt`.
I test e questo documento sono conservati nel ramo.

## 8. Cosa manca prima di andare online

1. Collaudo della nuova raccolta con dati reali, inizialmente in sola lettura,
   controllando dimensioni, durata, gate, elenco esclusioni e anteprime.
2. Verifica del candidato nell'app TEST sul dispositivo, come richiesto da
   `AGENTS.md`; il telefono verificato nel deploy precedente usava altro codice.
3. Promozione locale e distribuzione concordate separatamente, con revisione
   delle immagini e un ciclo autorizzato seguito dal controllo di catalogo/API.

GitHub resta fuori da questi controlli locali. Fino alla distribuzione,
il job online conserva il comportamento della versione `9718e2bc`.
