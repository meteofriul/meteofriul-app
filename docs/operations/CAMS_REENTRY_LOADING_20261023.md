# Aria e pollini: caricamento al rientro — 23 ottobre 2026

## Esito locale

Corretto sul ramo esistente `codex/cams-loading-state`, dalla base main
`f9e178b2`. Il rientro nelle previsioni ora mostra “Caricamento…” o
“In cjariament…” durante la richiesta, poi i valori. È la continuazione del
[lavoro CAMS](CAMS_LOADING_STATE_20261022.md), riferita al rilievo
CAMS-TRANSITION-01 della preparazione release del 23 ottobre.

Main, release 0.1.15 e i loro archivi compilati non sono modificati da questa
correzione. Nessuna AAB/APK, installazione, emulatore, push, deploy, esecuzione
di job o invio. Sponsor confermati in sola lettura: `enabled=false`, zero
campagne, revisione 117. Pannello e allineamento sponsor non avviati.

## Causa e correzione

La diagnostica temporanea ha riprodotto questa sequenza reale:

1. Stato iniziale dalla cache con `fromCache=true`, `cams_status=unavailable`,
   diagnostica assente e richiesta ancora in corso (`loading=true`).
2. Risposta meteo con CAMS esplicitamente `pending`.
3. Arrivo dei valori verificati di aria e pollini.

Il modello di presentazione trattava il primo stato come un esito finale,
facendo apparire per un istante l'indisponibilità. Ora solo lo stato recuperato
dalla cache, privo di errori o diagnostiche e mentre la richiesta è in corso,
viene presentato come caricamento. Nessuna modifica ai valori o alla cache.

Gli esiti reali restano distinti: a richiesta conclusa il dato assente è
indisponibile; errori e diagnostiche, comprese revoche in data_quality, source
o pollen_data, non vengono nascosti. I valori validi, incluso lo zero, restano
visibili; aria e pollini mantengono stati indipendenti. La diagnostica temporanea
è stata rimossa dal codice finale.

## Verifiche

- Regressione della vera route e delle card IT/FUR: entrambi i casi fallivano
  prima della correzione sull'attesa al rientro; entrambi passano dopo.
- 102 test mirati in 10 file, zero fallimenti e zero saltati. Coperti rientro,
  caricamento differito, recupero, fallimento reale, revoche all'avvio,
  candidato attivo, cache e valori zero. Non è una nuova suite completa.
- Lint dei tre file modificati e `git diff --check`: PASS.
- Anteprima con il launcher canonico `-NationalCloud`, porta 5174, browser
  integrato 661×902. Rientro da Bollettino e da Impostazioni, IT/FUR.
  Screenshot e gerarchia confermano due “Caricamento…” in italiano e due
  “In cjariament…” in friulano, poi il recupero dei dati reali senza svuotare
  la cache: PM2.5 6,4 µg/m³, PM10 8 µg/m³, Artemisia 0,02 grani/m³.
- Ripristinati italiano e tema chiaro; località, posizione, notifiche e alias
  non modificati. Anteprima lasciata nelle previsioni.

La regressione controllata verifica anche la fase troppo breve per affidarsi
al solo screenshot. Nessun errore è stato indotto nei servizi reali.
[Ricevuta e hash](evidence/cams-reentry-loading-20261023/verification.json).
Evidenze complete locali in `.tmp/cams-reentry-loading-20261023/` nella radice
canonica, senza token o identificativi dispositivo nella ricevuta condivisibile.

## Limiti e integrazione

La verifica corrente è nel browser integrato, non sul Galaxy, in Safari o
nel runtime Android minificato. Non si riutilizza la precedente prova sul
Galaxy come prova di questo nuovo codice. Prima della promozione su main resta
la prova reale richiesta da AGENTS.md; poi la release e la candidata Web
potranno incorporare la correzione e rigenerare gli asset autorizzati.
Il numero 0.1.14 mostrato dal ramo di main non modifica la versione 0.1.15
della release né il pacchetto già nel test interno.

## Integrazione successiva nella candidata

Il proprietario ha scelto di preparare la nuova 0.1.15 senza altre prove browser.
Correzione salvata in `53aba4ff` e integrata nella sola release con `da5b4d25`;
main resta invariato. La candidata 300034 include il fix e regressioni automatiche,
ma non ha una nuova prova sul dispositivo. La ricevuta precedente descrive
l'esito originale prima dell'integrazione. [Preparazione corrente](RELEASE_0.1.15_300034_PREPARATION_20261023.md).
