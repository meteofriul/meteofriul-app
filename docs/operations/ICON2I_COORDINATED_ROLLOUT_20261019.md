# Passaggio coordinato ICON-2I — piano e stato operativo

> Aggiornamento 20 ottobre: la prima corsa ordinaria del produttore aggiornato
> e fallita prima della pubblicazione. Il nuovo metadato `packingError` veniva
> rifiutato dal checkpoint locale. La correzione e verificata sul ramo
> `codex/icon2i-checkpoint-metadata`, ma non ancora distribuita. Il QA sulla
> nuova corsa resta bloccato e il follow-up e in pausa. Prima di proseguire
> serve distribuire la correzione con autorizzazione separata, conservando
> gli oggetti immutabili e poi verificando una nuova corsa. Vedere il
> [verbale aggiornato](ICON2I_TOLERANCE_PHASE3_DEPLOY_20261019.md).


> **Stato operativo aggiornato, 19 ottobre 2026:** fase 01 HTTP pubblicata e rollback compatibile pronto.
> Verificate app installata e letture FVG/nazionali. Fase 02 QA completata senza invii.
> Fase 03: produttore aggiornato; verifica della nuova corsa attesa il 20 ottobre alle 08:00 italiane.
> Dettagli: [deploy produttore e controlli ancora pendenti](ICON2I_TOLERANCE_PHASE3_DEPLOY_20261019.md).
> Dettagli fase 02: [job QA e prova reale](ICON2I_TOLERANCE_PHASE2_QA_20261019.md).
> Dettagli: [verbale di distribuzione fase 01](ICON2I_TOLERANCE_PHASE1_DEPLOY_20261019.md).


> **Revisione successiva: compatibilità delle app installate.** Il piano sotto
> documenta i commit originari. Non attivare la fase 03 di quei commit da sola:
> la [revisione con metadato separato](ICON2I_INSTALLED_APP_COMPATIBILITY_20261019.md)
> mantiene pubblico il formato precedente e aggiunge il percorso per i job.
> Il kit aggiornato include questa revisione locale; hash e sorgenti non
> coincidono più con i tre alberi Git storici. Il servizio HTTP è stato aggiornato
> nella fase 01; aggiornare tutte le app non è un prerequisito.

## Preparazione locale originaria — storico

Questa sezione conserva la preparazione precedente ai deploy. Lo stato operativo
aggiornato è nel riepilogo iniziale e nella sequenza server più sotto.

Alla preparazione del 19 ottobre 2026: tre commit tecnici creati nel ramo
`codex/local-notice-icon2i-analysis`, base `main` `8497e773b1613312bb952236d72c074e22a7b1c6`.
Preparazione locale completata; nessuna promozione a main, immagine cloud,
AAB, push Git, deploy, esecuzione cloud o invio reale in questo passaggio.
Il [manifest operativo](ICON2I_TOLERANCE_HANDOFF_20261019.json) registra gli
identificativi e distingue i controlli locali dai passaggi ancora da autorizzare.

## Commit da mantenere in questo ordine

| Fase | Commit | Contenuto e condizione |
| --- | --- | --- |
| 01 — Lettori | `91913ad3ead9657952aed8a5414ecfb082b96a91` | Client e validatore accettano vecchio/nuovo formato; checkpoint 1/2 leggibili. Il worker, derive e materializzatore restano quelli della baseline. |
| 02 — Consumatore | `2daa9b6d1e268c820ad41ba931784a232d4e2d87` | Mancanti preservati, valutazione per fenomeno, tolleranza verificata, diagnostica e riepiloghi senza false rassicurazioni. Da verificare in un job separato senza invii. |
| 03 — Produttore | `d855e53df6ca8babc49a25325eb9043df29c89bc` | Guardia Q/packingError, informazioni pubbliche, diagnostica e checkpoint 2; include prototipo e regressione Ciampac. Da attivare solo dopo la compatibilità dei lettori e su una nuova corsa. |

Non distribuire direttamente il tip del ramo come prima fase. Ogni immagine
futura va costruita dal commit della fase prevista e identificata con digest.
Il primo commit abilita le API compatibili ma il vecchio worker non passa la
diagnostica allo scrittore: continua a creare checkpoint schema 1. La fase 03
attiva la scrittura schema 2. Un commit locale non modifica i job in esecuzione.

## Kit locale riproducibile e controlli

[prepare-icon-tolerance-rollout.py](../../scripts/prepare-icon-tolerance-rollout.py)
esporta tre patch in ordine, 35 file, hash per file/pacchetto e manifest.
Richiede `--output` verso una directory nuova; rifiuta sovrascritture e un `main`
locale diverso dalla base. Usa indice e oggetti temporanei, non modifica
l'indice reale, non crea commit e non contiene comandi cloud o build.
`source_head` e `selected_sources_match_head` indicano la provenienza dei sorgenti.

Esempio solo locale, dalla radice di questo worktree:

```powershell
python -B scripts/prepare-icon-tolerance-rollout.py --output "$env:TEMP/icon-tolerance-kit-nuovo"
```

Verifiche di questa preparazione, con connessioni socket bloccate:

- 48 test sulla sola fase 01 esportata: contratto, checkpoint, diagnostica,
  vecchio worker. I tre file di pubblicazione restano identici alla baseline.
- 183 test sulla fase 01+02 esportata: sorgente, rilevatori, tolleranze,
  null, servizi/repository, outbox, ombra, riepiloghi e comandi dei job.
  Il produttore in questo export è ancora quello vecchio.
- 216 test sul produttore completo e sul prototipo: policy, derive, contratto,
  checkpoint, diagnostica, materializzazione, worker con sorgenti fittizie e Ciampac.

Le tre patch ricostruiscono esattamente gli alberi Git dei tre commit: hash
e riferimenti sono nel manifest operativo. Sintassi Python, JSON, link locali,
ordine dei commit, `diff --check` e canonical workspace cleanliness: PASS.

Sono esecuzioni di suite sovrapposte, non 447 casi distinti. I log di test che
riportano `published` o `acquisition` provengono da adapter fittizi: nessuna
acquisizione o pubblicazione reale. Il test materiale completo copre 215 × 73
ore. La suite storica `test_snapshot_materializer` resta non eseguibile per
fixture storiche assenti; non viene dichiarata superata. Non si ripete il
conteggio sul vecchio corpus senza metadati della guardia.

Evidenze private sotto `.tmp/icon-tolerance-rollout-20261019-commits` e
`.tmp/icon-tolerance-rollout-20261019-committed` del workspace canonico.
La [relazione tecnica](ICON2I_TOLERANCE_IMPLEMENTATION_20261019.md) descrive
regole e limiti; il [campione Ciampac](ICON2I_CIAMPAC_TOLERANCE_PROBE_20261019.txt)
dimostra il recupero di quantità non quantificabili, non una nevicata rilevante.

## TEST e altri lettori

La Full TEST .5 / 300036 sul Galaxy A52 ha il lettore compatibile (commit
`b25ddfe7` nel ramo `codex/full-test-qa`). Il difetto FVG della .3 è risolto
da `1b9dbad9`: Pordenone e Udine si aggiornano alla corsa del 19 ottobre,
con refresh, persistenza e cambio comune verificati. Eventi reali confermati.
I verbali aggiornati sono in quel worktree, sotto `docs/operations/`:
`FULL_TEST_FVG_REFRESH_20261019.txt` e `FULL_TEST_QA_TOLERANCE_20261019.txt`.

SHA-256 APK .5: `de6161527de039660f65f924888aa39108adb1e35a11bb9006ce14b81c2932a1`.
Quella APK include modifiche UI del ramo TEST ed è l'artefatto realmente
provato; non è una build di questo ramo dei job. Push e background restano
esclusi per scelta del proprietario; Community isolata QA, nessun invio.

La compatibilità è ottenuta mantenendo il formato pubblico v1 e pubblicando
le prove delle tolleranze in file separati. I vecchi client rifiutano chiavi
aggiuntive, che quindi non vengono inserite nei documenti letti dalle app.
La fase 01 ha verificato i lettori storici e l'app ufficiale già installata;
la fase 03 ha ricontrollato i 215 documenti FVG correnti e sei località nazionali.
La verifica sui dati della prima nuova corsa resta aperta. Android 15/16 e altri
dispositivi non sono stati collaudati; nessun aggiornamento Android è stato generato.

## Sequenza server e stato di avanzamento

1. **Fase 01 eseguita:** lettore HTTP compatibile distribuito, configurazioni
   iniziali conservate e immagine di rollback compatibile identificata con digest.
   Riscontri e verifica dell'app installata nel verbale della fase 01.
2. **Fase 02 eseguita:** creato `meteofriul-local-notice-tolerance-qa`,
   entrypoint `python -m app.jobs.send_local_weather_notices`,
   `LOCAL_NOTICE_DELIVERY_MODE=dry_run`, nessuno scheduler cloud dedicato.
   La prova reale ha valutato 16 dispositivi su sei punti canonici, senza invii
   né prenotazioni. L'audit usa `local_notice_pilot_runs`, distinguendo modalità
   e identificativo di tentativo; `dry_run` può scrivere l'audit.
   Non usare `deploy-local-notice-job.ps1` per questo QA: configura `send`.
3. **Fase 03 distribuita, prima nuova corsa fallita:** il job ordinario
   del 20 ottobre alle 08:00 `Europe/Rome` si e fermato prima di pubblicare.
   Il difetto del checkpoint locale e corretto e verificato sul ramo
   `codex/icon2i-checkpoint-metadata`; l'immagine cloud non e ancora aggiornata.
   Dopo un deploy separatamente autorizzato, verificare una nuova corsa senza
   cancellare esiti terminali o riscrivere gli oggetti immutabili.
4. **Confronto bloccato sulla nuova corsa:** finche manca la nuova pubblicazione
   non eseguire il QA e non usare i vecchi dati come prova delle tolleranze.
   Il follow-up e in pausa. Dopo 215 letture legacy e sidecar validi,
   confrontare candidato senza invii e baseline sugli stessi punti, ore e
   `source_run_id`: candidati cambiati, tolleranze utilizzate, non valutabili
   per causa e denominatori, zero invii e prenotazioni. Gli invii del nuovo
   consumatore richiedono successiva autorizzazione dopo questi controlli.

La fase 02 modifica anche codice condiviso dai riepiloghi mattutino e serale:
mantengono il rifiuto dei dati incompleti, senza usare la tolleranza per
descrivere una giornata come asciutta. Il nazionale v2 resta invariato.

## Monitoraggio ed esiti

L'inventario locale `scripts/cloud-run-job-monitoring-policies.json` contiene
`local-notice-failures` (due fallimenti in 4 ore) e `local-notice-last-success`
(nessun successo per 3 ore). Lo script di sincronizzazione usa
`run.googleapis.com/job/completed_execution_count` filtrando `result`.
Quindi esiste una dipendenza configurata dall'esito del job. Nella fase 02
sono state lette le 23 policy live senza modificarle: gli allarmi degli avvisi
locali filtrano il nome del job operativo e non includono il QA.

Gli exit code restano invariati: `data_degraded`, `partial`, errori di sorgente
e rifiuti non diventano successi. Un eventuale passaggio del solo parziale a 0
richiede un cambiamento coordinato del monitoraggio; i contatori nei log non
sono già un allarme attivo. Prima dell'invio operativo, valutare nel dry-run
anche l'effetto dei parziali su questi allarmi. Nessuna soglia viene ricavata
dalle percentuali autunnali del corpus.

Leggere `quality_tolerance_expected_*`, `quality_tolerance_verified_*`,
`quality_guard_*` nel produttore e `data_quality.by_source_run` nel consumatore.
Conservare cause e denominatori per fenomeno, aggregare per `source_run_id`,
non sommare retry come nuove corse e non contare i dispositivi come punti distinti.

## Ritorno alla versione precedente

- Produttore: usare l'immagine compatibile della fase 01; deve leggere
  checkpoint 1/2 e documenti con la nuova estensione. Vietato tornare al vecchio
  lettore rigido dopo una scrittura schema 2. Non eliminare checkpoint o
  riscrivere dati per forzare un ripristino.
- Consumatore: in caso di problemi fermare gli invii candidati e conservare
  diagnostica e dati. Non ripristinare silenziosamente il null trasformato in zero.
- Immagini, digest e configurazioni effettive sono registrati nei verbali
  delle fasi 01–03. La prova sulla nuova corsa e il confronto senza invii
  restano pendenti; non vengono presentati come verifiche già svolte.
