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

## Stato

Questo ramo è solo una proposta backend. Job distribuito, Scheduler, destinatari,
app Web/Android e policy email non sono cambiati. Prima di distribuire servono
CI della PR, prova isolata del job e verifica del messaggio su dispositivo;
poi si potrà aggiornare il solo job serale con un digest identificato.
