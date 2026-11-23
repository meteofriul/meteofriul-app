# Eventi: margine di lettura Azalea e Barcolana — 23 novembre 2026

## Evidenza

Il job Eventi del 23 novembre è fallito per Azalea e Barcolana. Il catalogo
conserva i diagnostici ma le due fonti `stale` non compaiono nelle schede
visibili. Barcolana ha registrato un `ReadTimeout` del calendario al secondo
tentativo, dopo 16 secondi di lettura.

In prove locali di sola lettura, Azalea ha verificato 9 eventi, 3 pagine di
archivio e 17 dettagli in 26,2 secondi: il limite del job era 20 secondi.
Il calendario Barcolana una volta ha superato 16 secondi e una seconda volta
ha risposto in 3,5; il lettore completo ha poi verificato un evento in 4,9
secondi. Queste prove dal PC non dimostrano i tempi dal job Cloud.

L'[archivio Barcolana](https://www.barcolana.it/it/calendario-eventi) riguarda
principalmente l'edizione di ottobre, ma la
[fonte ufficiale di Barcolana Ski](https://www.barcolana.it/it/news/2026/barcolana58-presented-by-generali-iscrizioni-aperte)
documenta anche l'appuntamento del 9 gennaio 2027. La fonte non è stata messa
in pausa per nascondere il timeout.

## Modifica candidata

- Azalea legge i dettagli indipendenti a coppie e li verifica nell'ordine
  originale. Il lettore completo ha richiesto 9,5 secondi nella seconda prova
  locale, contro i 26,2 iniziali, con gli stessi 9 eventi e 17 dettagli.
- Barcolana usa 4 secondi per la prima lettura e fino a 20 per l'unico recupero,
  invece di 8 e 16. Il calendario lento può così recuperare senza prolungare
  il limite condiviso di 28 secondi.
- I processi restano limitati a 20 secondi per Azalea e 35 per Barcolana; la
  somma massima di tutte le fonti rimane 875 secondi, sotto i 900 del job
  Cloud. Una pagina obbligatoria mancante continua a far fallire la verifica
  della fonte; non viene pubblicato un programma parziale.

72 test mirati e 16 sottocasi superati, compreso un calendario che risponde
dopo 20 secondi; `compileall` e controllo del diff superati.

## Collaudo Cloud isolato

La CI della [PR 59](https://github.com/meteofriul/meteofriul-app/pull/59)
è verde per backend, frontend e anteprima hosting sul commit `e42e7e40`.
L'archivio Git del solo backend ha SHA-256
`22273A33C96F6C14E39790257E7EBEF650EC4FB0114CA17CD0E2E515A88F1B01`.
Cloud Build `d5bac9bb-3b46-47e7-bd03-2e91df65b777` è riuscito e ha
prodotto il digest QA
`sha256:d6ff27f255a0d969883beacb485fffdb4fdfcaa715c93f4f2744e6502a7952b7`.

Il job QA, senza scheduler, ha usato solo la chiave
`pilot/events/qa/source-read-20261123/catalog.json`. Le esecuzioni mirate
`meteofriul-events-sources-qa-20261123-gzvss` (Azalea) e `...-jcl6p`
(Barcolana) hanno entrambe terminato con successo. Nel catalogo QA Azalea
è `partial`: 3 pagine di archivio, 17 dettagli controllati, 9 eventi
inclusi, 2 cambi di programma da rivedere e nessuna pagina obbligatoria
saltata. Barcolana è `fresh`: 682 record di calendario esaminati e 1
evento futuro conservato. Sono state eliminate le due condizioni `stale`
che il catalogo pubblico registrava il 23 novembre. Questa prova mirata
non modifica il catalogo pubblico.

La prima prova completa sul medesimo catalogo QA è fallita: TurismoFVG è
scaduta e Pordenonelegge ha ricevuto il reindirizzamento di fine edizione
senza lo storico necessario per riconoscerlo. Quel catalogo era nato con
solo Azalea e Barcolana, senza i checkpoint delle altre fonti. Per una prova
equivalente al ciclo ordinario è stata copiata una volta la versione pubblica
in `pilot/events/qa/full-from-public-20261123/catalog.json`, senza scrivere
nella chiave pubblica. Il job QA è stato puntato solo a questa copia.

La seconda esecuzione completa
`meteofriul-events-full-qa-20261123-dq6hw` è terminata con successo: tutte le
14 fonti attive sono `fresh` o `partial`; Spazzapan resta in pausa. Azalea
è `partial` con 9 schede e 2 cambi da rivedere; Barcolana è `fresh` con 1
scheda; Pordenonelegge è `fresh` con 0 schede perché l'edizione è chiusa;
TurismoFVG è `partial` con 1.486 schede. Palazzo Attems e GiroFVG restano
`review_required` come monitor editoriali, mentre l'inventario annuale
TurismoFVG è `checked`. I job QA temporanei sono stati eliminati dopo il
readback. I log QA non possono attivare la policy email delle fonti candidate,
che filtra espressamente il job pubblico `meteofriul-events-refresh`.

## Stato e verifica ancora necessaria

La modifica è nel solo ramo Eventi, senza aggiornamenti al job, al catalogo
online, al pannello o all'app. Il collaudo completo QA è riuscito; dopo un
eventuale deploy resta da verificare la prima corsa ordinaria. Se Barcolana
continua a scadere anche con il nuovo limite, occorre
un lettore alternativo o una decisione editoriale sulla fonte, non un ulteriore
aumento indefinito dei tempi.
