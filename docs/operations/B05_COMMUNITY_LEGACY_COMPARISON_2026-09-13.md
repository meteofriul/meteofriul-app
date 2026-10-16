# B05 — mutazioni community concorrenti

Data: 13 settembre 2026

Revisione dell'analisi legacy iniziale: `baef353e74a785c16228b38306c15c3ecb1b61a1`

Revisione di partenza della correzione: `04bb13af428f21b9048be0cc6c2b6979f1645ea3`
Diagnostiche originarie: `b851b09`; fixture affinato in `ce8cd3f`

Stato: **corretto e verificato localmente, non distribuito**

## 1. Esito

La correzione B05 riguarda esclusivamente il backend community condiviso. Sono
state chiuse le tre corse già riprodotte:

1. una conferma tardiva non ricrea un report eliminato;
2. un flag tardivo su un gruppo oscurato non ricrea report parziali;
3. un secondo undo di A non elimina il cooldown installato dal successivo
   report B della stessa fonte.

Le tre diagnostiche repository e le corrispondenti prove service end-to-end
sono verdi. Quattro casi positivi dimostrano inoltre che conferma, flag visibile,
flag su gruppo già nascosto e undo singolo continuano a funzionare. Le dieci
regressioni B05 sono ora incluse anche nella raccolta pytest ordinaria tramite
`backend/tests/test_community_b05_regressions.py`; il modulo diagnostico
complessivo resta opt-in perché contiene gruppi dell'audit ancora aperti.

## 2. Causa corretta

Il lock del repository protegge una sola istanza Python, non richieste su
istanze diverse né lo strumento di moderazione. Il service ricavava report e
metadati prima della transazione, poi il repository usava quegli ID diventati
potenzialmente vecchi:

- conferma e flag materializzavano campi con `set(..., merge=True)`, capace di
  creare un documento assente;
- l'undo eliminava alla cieca il documento cooldown indicizzato per fonte;
- il cooldown non registrava quale report lo avesse creato;
- alcuni mirror in memoria venivano aggiornati dopo il commit usando l'input
  stale invece dei target realmente verificati nella transazione.

La causa era nel percorso Firestore condiviso dalla community, non in una
seconda implementazione della pilota. Il repository associato alla release
legacy Play `300011`, all'artefatto registrato `300012` e alla revisione
inizialmente confrontata aveva lo stesso blob `209bb3e` nei punti interessati.
Non è stata fatta alcuna nuova verifica Play o cloud durante la correzione.

## 3. Correzione applicata

### 3.1 Conferma

`CommunityRepository.update_confirmation_strict` rilegge nella medesima
transazione:

- ogni report target;
- appartenenza al gruppo;
- scadenza del report;
- oscuramento sul report;
- gate durevole di moderazione del gruppo;
- voto e rate limit già previsti.

La scrittura dei contatori usa `transaction.update`, quindi non può creare un
documento assente. Se un target è assente, scaduto, appartiene a un altro gruppo
o è oscurato, il repository solleva
`CommunityMutationTargetUnavailable`; il service mantiene il contratto HTTP
di contenuto non più attivo con status `404`. Voto, rate limit e mirror non
vengono modificati. Dopo un commit valido, il mirror delle conferme e gli
eventuali report già presenti nel mirror ricevono soltanto i contatori
effettivamente materializzati.

### 3.2 Flag

`CommunityRepository.flag_group_strict` rilegge nello stesso confine atomico il
gate di moderazione e tutti i report target ricevuti. Identità del gruppo,
scadenza, esistenza e metadati dei target derivano dai documenti riletti, non
dallo snapshot del service. Gli aggiornamenti di un report già esistente usano
`transaction.update`.

Il contratto scelto è esplicito:

- target scomparso senza un gate amministrativo nascosto valido: `404`, senza
  flag, rate limit o report parziale;
- target scomparso ma gruppo già nascosto da un gate durevole valido: successo
  idempotente con `hidden_global=true`, senza creare flag, consumare rate limit
  o riscrivere il gate;
- target ancora esistente: comportamento ordinario invariato.

Nel no-op amministrativo il mirror conserva esattamente il gate letto dallo
storage, incluso il suo timestamp; non genera una falsa riscrittura locale.
Negli altri rami vengono aggiornati dopo il commit soltanto gli ID realmente
verificati e materializzati.

### 3.3 Undo e cooldown

`create_report_strict` aggiunge al cooldown il campo additivo `report_id`.
`delete_report_and_cooldown_strict` è ora una transazione che legge insieme
report richiesto e cooldown corrente:

- elimina il report soltanto se appartiene alla fonte richiedente;
- elimina un cooldown nuovo soltanto quando il suo `report_id` coincide con
  quello dell'undo e non contraddice un report esistente di altro proprietario;
- per un cooldown legacy senza `report_id`, consente la cancellazione soltanto
  se A esiste ancora ed è della fonte richiedente;
- un retry tardivo con A già assente non può cancellare il cooldown di B.

La compatibilità dei documenti legacy è fail-safe e non richiede una migrazione.
Nel caso ambiguo A già assente + cooldown legacy non associato, il cooldown
rimane fino alla propria scadenza invece di rischiare di rimuoverne uno più
recente.

## 4. Prove deterministiche

Le prove service usano due repository distinti sullo stesso fake Firestore e
il vero `CommunityService`. Per conferma e flag, un hook interviene dopo la
lettura del gruppo del service ed esegue il vero `remove_group` prima della
transazione rigorosa. L'undo usa due chiamate service concorrenti coordinate
da barriere/eventi, senza `sleep`: entrambe superano il pre-check di A, la prima
elimina A, viene creato B, poi viene liberata la seconda.

Le asserzioni verificano:

- lettura del target e del gate/cooldown nella stessa transazione che decide la
  mutazione;
- nessuna `set` o `update` sul report eliminato;
- nessun voto, flag o rate limit derivato da un target stale;
- gate amministrativo e mirror invariati nel no-op;
- report B e relativo cooldown byte-per-byte invariati dopo il secondo undo;
- payload completi dei report positivi, consentendo soltanto i campi che la
  mutazione deve cambiare;
- coerenza fra documenti persistiti e mirror `_confirmations`, `_moderation`,
  `_flags`, `_reports` e `_cooldowns` pertinenti, inclusi i retry idempotenti;
- uso effettivo di `update`, e non di un merge-set, nelle materializzazioni dei
  report.

Il fake registra operazioni e letture transazionali. Non emula il protocollo di
conflitto/retry del servizio Firestore reale: la prova dimostra la topologia
atomica e gli esiti deterministici del codice locale, non sostituisce un test
con emulator o un collaudo live.

## 5. Compatibilità e sicurezza preservate

- I contratti pubblici di create, conferma, flag e undo non cambiano.
- La forma legacy `300011` della conferma `{client_id, vote}` resta accettata;
  la forma corrente continua a richiedere entrambi i campi di consenso.
- La nuova associazione `report_id` è un campo interno additivo del cooldown;
  nessun client deve inviarlo o leggerlo.
- Gli endpoint e `require_community_app_check` non sono stati modificati.
- Limiti globali/per-client, capacità, TTL, cooldown di 45 minuti, undo di 60
  secondi, fenomeni ammessi, Comune pubblicato e regole di moderazione restano
  invariati.
- Il percorso memory-only non è stato riscritto: B05 riguardava il percorso
  Firestore rigoroso concorrente.

La regola che impedisce a una fonte di confermare o segnalare il proprio
contenuto resta applicata dal pre-check del service come prima. Questo
intervento non la descrive come una verifica transazionale di tutti i report
che potrebbero aggiungersi al gruppo dopo lo snapshot: tale corsa distinta non
faceva parte delle tre riproduzioni B05 autorizzate e non è dichiarata risolta.

La localPilot e le build ordinarie continuano a condividere frontend, API,
service e repository community. Non è stata introdotta una variante pilota.

## 6. Verifiche eseguite

I comandi backend sono stati eseguiti dalla cartella `backend` con:

```powershell
$backendPython = Join-Path (Resolve-Path '.').Path 'venv\Scripts\python.exe'
```

### Prima della correzione

- Le tre diagnostiche repository originarie: **0 superati, 3 falliti, 0
  saltati**.
- Le tre nuove corse attraverso il service: **0 superati, 3 falliti**.
- I quattro controlli positivi corrispondenti: **4 superati, 0 falliti**.

Questi esiti sono stati osservati in esecuzioni mirate separate; non vengono
presentati come un unico comando da dieci test.

### Stato finale

| Comando | Esito |
| --- | --- |
| `& $backendPython -m pytest -q -c pytest.social-geo-diagnostics.ini <i 10 node-id B05 di social_geo_structural_audit_diagnostic.py>` | **10 superati, 0 falliti, 0 saltati** in 0,91 s |
| `& $backendPython -m pytest -q tests/test_community_b05_regressions.py` | **10 superati, 0 falliti, 0 saltati** in 0,89 s; raccolta ordinaria |
| `& $backendPython -m pytest -q tests/test_community_repository.py tests/test_community_service.py tests/test_live_api.py tests/test_community_moderation_tool.py tests/test_community_moderation_logging.py tests/test_community_moderation_digest.py tests/test_emit_community_moderation_digest_job.py tests/test_community_ttl_evidence_seed.py tests/test_pilot_security.py tests/test_community_b05_regressions.py` | **160 superati, 0 falliti, 0 saltati**, più **29/29 subtest**; un warning Starlette/httpx preesistente |
| `& $backendPython -m pytest -q tests/test_community_service.py::CommunityServiceTests::test_confirmation_accepts_the_exact_play_300011_legacy_contract tests/test_live_api.py::LiveApiTests::test_confirmation_accepts_the_exact_play_300011_legacy_payload tests/test_pilot_security.py` | **23 superati, 0 falliti, 0 saltati**, più **13/13 subtest**; stesso warning preesistente |
| `npx vitest --configLoader native run src/services/liveApi.test.js src/features/live/liveReportController.test.js src/features/live/LiveView.test.jsx src/services/firebaseAppCheckAdapter.test.js --reporter=dot` | **4 file, 76/76 test superati**, 0 falliti, 0 saltati |

Il warning backend completo è:

```text
StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
```

Una prima esecuzione della raccolta repository/service/API dopo l'introduzione
dell'autorità transazionale ha rilevato tre fixture storiche che invocavano
conferma o flag rigorosi senza predisporre il report target. Erano assunzioni
dei test incompatibili con il nuovo vincolo, non regressioni del prodotto: le
fixture ora creano target completi e la raccolta finale è verde.

Non sono state abilitate prove live. In particolare
`test_community_moderation_live_smoke.py` non è stato eseguito, perché richiede
un ambiente esterno escluso dall'incarico. Non sono stati eseguiti emulator
Firestore, richieste cloud o test sul telefono.

## 7. Limiti residui e dipendenze

- La garanzia locale si basa su transazioni e `update` dell'SDK Firestore, ma
  non è stata verificata contro un emulator o una revisione cloud.
- I cooldown legacy senza `report_id` restano supportati con la regola
  conservativa descritta sopra; nel caso ambiguo possono durare fino al TTL.
- Il pre-check contro conferma/flag del proprio contenuto non è stato esteso a
  una query transazionale di report aggiunti al gruppo dopo lo snapshot; è un
  confine distinto e non una delle tre corse chiuse qui.
- Nessuna evidenza di questo rapporto identifica il backend oggi distribuito.
- B06 e tutti gli altri punti del registro restano separati e invariati.

## 8. Esclusioni rispettate

Nessun push remoto, deploy, accesso a cloud o dati reali, modifica Firebase,
build/installazione Android o accesso al Samsung. Nessuna modifica a UI,
scheduler, frequenze, soglie, meteo, B01, REG-03 o bundle.
