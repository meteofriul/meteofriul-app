# Preparazione 0.1.15 / 300034 — 23 ottobre 2026

## Stato

Candidata preparata localmente su `codex/release-0.1.15`: nome **0.1.15**,
`versionCode` **300034**. Il numero è configurato, non riservato né consumato.
**Nessuna nuova AAB/APK generata.** La 300033 già nel test interno rimane
immutata. Nessun upload, installazione, push, deploy, invio o job manuale.
Sponsor disattivati; pannello e allineamento dati sponsor non avviati.

Il proprietario ha chiesto di proseguire con la preparazione senza altre prove
nel browser. Non sono state eseguite prove browser o telefono. La consultazione
Play è stata esclusivamente in lettura per identificare codici e canale.
La verifica della nuova release sul dispositivo rimane aperta; questa scelta
non viene interpretata come PASS runtime o autorizzazione a promuovere main.

## Sorgenti e contenuto

- Sorgente comune Android/Web: `c30cfe332769248b62b810cb17da86a4d7ca4b4b`.
- Main incorporato e lasciato invariato: `f9e178b2`.
- Correzione CAMS al rientro: `53aba4ff`, incorporata nella sola release dal
  merge `da5b4d25`; i dati assenti dalla cache non diventano un falso esito
  finale durante una richiesta. Errori, revoche e indisponibilità reali restano
  distinti; regressioni in italiano e friulano.
- Restano incluse configurazione nativa Capacitor/Cordova, conservazione della
  preferenza Posizione, mappa bollettino, barra fissa Bollettino/Eventi, Vite
  8.1.6, Indietro nelle Impostazioni e precedenti correzioni approvate.
- Nessuna impostazione speciale della TEST, variazione di toolchain o backend.

## Numero versione verificato

Play Console, lettura del 23 ottobre: bundle più recente **300033 / 0.1.15**,
test interno attivo con una lista selezionata e un utente; produzione
**300031 / 0.1.14**. Nessuna modifica alla Console.
Registro Play: 49 record, immutabilità PASS. Massimo della cronologia combinata
Play e APK privati letta dalle guardie: 300033. Entrambe le guardie accettano
**300034 / 0.1.15**; package, lock e Gradle conservano lo stesso versionName.
Prima della futura build rileggere Play/registro se intervenissero altri upload
o riserve. Le vecchie riserve e la vecchia AAB non sono riscritte.

## Controlli automatici

| Controllo | Esito sulla candidata |
| --- | --- |
| Regressioni CAMS IT/FUR, cache/revoche/errori, posizione e layout Android | 162 PASS in 18 file; 0 falliti, 0 saltati |
| Lint dei tre file CAMS | PASS |
| Guardie frontend API, Carto e versioni | 9 PASS |
| Contratti builder, senza Gradle | PASS; controllo Gradle esplicitamente saltato |
| Contratti configurazione nativa | 40 asserzioni PASS; nessun bundle reale generato o verificato |
| Contratti R8 | PASS; non è una prova minificata sul telefono |
| Dipendenze | 363 versioni conformi al lock; directory fisica; nessuna installazione |
| Pulizia workspace canonico / ledger | PASS |
| Asset privati, ledger e precedenti artefatti protetti | 58 file con hash invariati |
| Build Web protetta `-BuildOnly` | PASS, con preflight API prima/dopo e service worker |
| Build dei soli asset Web in modalità Android | PASS; binding API e Carto verificati |

La suite completa precedente (5.039 PASS, 13 saltati) appartiene alla base
`cda576e7`. Non è presentata come nuova suite completa della 300034: sul nuovo
delta sono stati eseguiti i 162 test pertinenti riportati sopra.

## Web dalla stessa base

Archivio locale: `release-artifacts/web-candidates/20261023-0.1.15-c30cfe33/`.
Web: 506 file, 76.030.169 byte. Asset Web Android: 505 file, 75.977.501 byte.
Manifest SHA256:
`792a7f9c39b0ea7b13fec84daa22bb63432b739eab4eeb87112064fc48044e38`.
Albero frontend: `d4bf47fc45e474af952932942ea88c87fd438a90`.
Hash, dimensioni e sorgenti dell'archivio ricontrollati. Gli archivi precedenti
restano conservati; questo archivio sostituisce quello `cda576e7` come candidata.
Nessuna pubblicazione Web. Ultima verifica del sito pubblico: 22 ottobre,
versione 0.1.14. Safari/iPhone/PWA e aggiornamento cache restano non verificati.

API/tag/revisione/digest invariati e verificati in lettura dal preflight:
`play-b6fbe4d`, `meteofriul-api-00251-jow`, backend `599aea2f` e digest
`sha256:5522b4cfc15076a9f93e838e3643b35e1aa5ad4ce0bf5bca4851997ea94c2ae8`.
Sponsor: `enabled=false`, zero campagne, revisione 117.
Questa correzione frontend non richiede aggiornamenti dei job. Non è un nuovo
audit complessivo delle esecuzioni cloud.

## Passaggi ancora necessari

1. Salvare/pubblicare i sorgenti della candidata e ottenere la CI: il builder
   richiede il commit remoto allineato. Nessun push autorizzato in questa fase.
2. Con autorizzazione distinta, generare la AAB con il builder protetto; verificare
   firma, codice, JSON Capacitor, risorsa Cordova e mapping R8 nel bundle reale.
3. Con autorizzazione distinta, caricare sul solo test interno personale e
   verificare l'aggiornamento sul telefono. Acquisire Posizione prima e subito
   dopo l'aggiornamento, prima di azioni che ne cambino la preferenza.
4. Promuovere il codice su main solo dopo i controlli runtime pertinenti.
   Edge-to-edge/inset Android 15/16, API deprecate, tablet/multi-window e R8
   minificato mantengono i limiti del runbook: nessun PASS implicito.

[Ricevuta e hash](evidence/release-0.1.15-300034-preparation-20261023/verification.json).
Log completi locali: `.tmp/release-0115-next-code-20261023/`.
[Stato release](RELEASE_0.1.15_STATUS_20261021.md) ·
[Runbook Play](PLAY_AAB_RUNBOOK.md) · [Parità Web](WEB_ANDROID_RELEASE_PARITY.md).
