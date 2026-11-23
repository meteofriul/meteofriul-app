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

## Stato e verifica ancora necessaria

La modifica è nel solo ramo Eventi, senza aggiornamenti al job, al catalogo
online, al pannello o all'app. Prima del deploy servono CI, prova del lettore
nel contesto Cloud con controllo del catalogo e verifica della prima corsa
ordinaria. Se Barcolana continua a scadere anche con il nuovo limite, occorre
un lettore alternativo o una decisione editoriale sulla fonte, non un ulteriore
aumento indefinito dei tempi.
