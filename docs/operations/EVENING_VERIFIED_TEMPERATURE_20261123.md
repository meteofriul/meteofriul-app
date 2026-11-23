# Anticipazione serale: testo ridotto verificato — 23 novembre 2026

## Problema e scelta

Le corse serali del 20–22 novembre hanno fallito prima dell'invio: alcuni
valori orari di pioggia ICON erano incerti (`null`), pur avendo temperature
complete. Un campo assente non equivale a zero pioggia. Il compositore attuale
scarta tutti i gruppi; il nuovo candidato usa soltanto la temperatura quando
la giornata locale successiva è interamente coperta da ore consecutive.

Il testo ridotto non fa affermazioni su cielo, precipitazioni o vento e non
espone all'utente i campi mancanti. Se la temperatura è assente, un valore
presente è malformato, la corsa ICON è vecchia o la giornata ha buchi, non
produce alcun messaggio. Il riepilogo interno conta il gruppo in
`quality_limited_groups`. Il testo completo richiede ora anch'esso l'intera
giornata locale, inclusi i giorni di 23 o 25 ore del cambio d'ora.

## Prove

- 59 test mirati in `test_evening_forecast*`, `test_local_notice_missing_data`
  e `test_local_notice_tolerance` superati; compilazione Python e
  `git diff --check` superati. Sono coperti valori assenti, malformati, buchi,
  conteggio del testo ridotto e cambio d'ora.
- Prova in sola lettura sul documento ICON pubblico immutabile di Pordenone
  `20261122T120000Z`: 24 ore locali del 23 novembre, temperature complete
  5–11 °C e sei ore con pioggia incerta. Il compositore candidato produce
  «Temperature tra 5 e 11 °C. Apri e guarda.» e marca il testo come ridotto.
  Nessuna notifica è stata inviata nella prova.
- CI della [PR 58](https://github.com/meteofriul/meteofriul-app/pull/58):
  backend, frontend e anteprima hosting superati sul commit `5f98b8b5`.

## Collaudo isolato del 23 novembre

Da un archivio del solo backend del commit `5f98b8b5` è stata costruita
un'immagine QA con un modulo temporaneo di replay. Il modulo fissa il ciclo
ICON immutabile `20261122T120000Z`, verifica il messaggio ridotto e mostra
«TEST Meteo Friûl · dati 23/11» nel titolo. Cloud Build
`9961dae3-7fa1-46e5-a24f-4b17bab5011e` è riuscito; digest QA
`sha256:0604c7b7caa8ce3b331a2c49baca4659143310a8e0ca21dbe7a4bedd8b677da8`.

Il primo tentativo del job temporaneo è fallito perché la configurazione QA
non abilitava Firestore: nessuna lettura di destinatari o invio. Dopo aver
corretto solo quel flag nel job QA, l'esecuzione in modalità `dry_run` ha
letto 60 Android idonei e il gate obbligatorio di un singolo destinatario ha
interrotto la prova prima dell'invio (`attempted=0`, `sent=0`). Il filtro del
telefono già usato nel TEST del 12 novembre è stato ritrovato nei log
amministrativi; le due esecuzioni precedenti usavano lo stesso identificativo.
La revisione automatica ha però respinto la sua memorizzazione nei metadati
del job QA perché è un identificativo sensibile non coperto
dall'autorizzazione alla singola notifica. Nessun aggiramento è stato tentato.
Il job QA, privo di scheduler, è stato eliminato. Il test su dispositivo
resta aperto; nessuna notifica di questo collaudo è stata inviata.

## Stato

Questo ramo è solo una proposta backend. Job distribuito, Scheduler, destinatari,
app Web/Android e policy email non sono cambiati. Prima di distribuire servono
una prova isolata riuscita e la verifica del messaggio su dispositivo;
poi si potrà aggiornare il solo job serale con un digest identificato.
