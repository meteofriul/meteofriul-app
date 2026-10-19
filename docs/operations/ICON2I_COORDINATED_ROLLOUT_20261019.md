# Passaggio coordinato ICON-2I — preparazione locale

Stato al 19 ottobre 2026: tre commit tecnici creati nel ramo
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

La TEST ha letto i dati reali del formato attuale. Il nuovo formato è verificato
offline, non ancora su una corsa pubblicata. Prima di cambiare i documenti
condivisi, censire e rendere compatibili tutti i lettori distribuiti, comprese
app installate e validatori. Il vecchio client rifiuta chiavi aggiuntive.
La TEST da sola non chiude questo requisito; Android 15/16 e altri dispositivi
non sono stati collaudati. Nessun aggiornamento Android viene generato qui.

## Passaggio server, soltanto dopo autorizzazione

1. Rilevare immagini/configurazioni/policy effettive; archiviare il riferimento
   di partenza. Distribuire i lettori compatibili e conservare un'immagine di
   rollback costruita dalla fase 01. Il suo digest va registrato prima della 03.
2. Preparare il job distinto `meteofriul-local-notice-tolerance-qa` dalla fase 02:
   entrypoint `python -m app.jobs.send_local_weather_notices`,
   `LOCAL_NOTICE_DELIVERY_MODE=dry_run`, nessuno scheduler aggiunto. Il nome è
   proposto, non una risorsa già creata. Stabilire coorte autorizzata, credenziali
   e destinazione audit, poi rileggere la configurazione applicata.
   Non usare `deploy-local-notice-job.ps1`: configura `send` e lo scheduler operativo.
   `dry_run` può scrivere l'audit; non equivale a sola lettura. Non basta un
   esito `no_eligible_device`: occorre almeno un punto canonico valutato e zero invii.
3. Attivare la fase 03 su una nuova corsa ICON, senza riscrivere oggetti,
   manifest o checkpoint immutabili già pubblicati. Verificare prove e contatori.
4. Confrontare il candidato senza invii con la baseline sugli stessi punti,
   ore e `source_run_id`. Registrare candidati cambiati, tolleranze utilizzate,
   non valutabili per causa e denominatori; verificare zero invii e nessuna
   prenotazione di consegna. Solo dopo approvare gli invii del nuovo consumatore.

La fase 02 modifica anche codice condiviso dai riepiloghi mattutino e serale:
mantengono il rifiuto dei dati incompleti, senza usare la tolleranza per
descrivere una giornata come asciutta. Il nazionale v2 resta invariato.

## Monitoraggio ed esiti

L'inventario locale `scripts/cloud-run-job-monitoring-policies.json` contiene
`local-notice-failures` (due fallimenti in 4 ore) e `local-notice-last-success`
(nessun successo per 3 ore). Lo script di sincronizzazione usa
`run.googleapis.com/job/completed_execution_count` filtrando `result`.
Quindi esiste una dipendenza configurata dall'esito del job. Le policy live
non sono state interrogate né modificate in questa preparazione.

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
- Immagini, digest, configurazioni effettive e prova della nuova corsa sono
  ancora da raccogliere nel passaggio server autorizzato. Le caselle pendenti
  nel manifest non vengono presentate come verifiche già svolte.
