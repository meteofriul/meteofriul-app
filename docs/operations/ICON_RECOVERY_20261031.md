# Recupero ICON e anteprima locale — 31 ottobre 2026

Attività successiva all'[audit dei job](JOBS_READONLY_AUDIT_20261031.md),
richiesta dal proprietario. L'audit precedente resta una fotografia fino
alle 16:20 italiane e non viene riscritto come se il recupero fosse già
avvenuto allora.

## Diagnosi della sorgente

Le GET dirette delle 15:30 UTC a
[MeteoHub ItaliaMeteo](https://meteohub.agenziaitaliameteo.it/nwp/ICON-2I_SURFACE_PRESSURE_LEVELS/)
mostrano i cicli `2026103100` e `2026103112`. Il codice corrente
`discover_complete_run` seleziona il secondo con tutti i 14 file richiesti.
GET normale, `Cache-Control: no-cache` e query diagnostica restituiscono
lo stesso indice e lo stesso hash. Nessun difetto del parser dimostrato,
nessun cambio fonte o soglia giustificato da questa prova.

La prima consultazione tramite indice web restituiva una versione non
aggiornata: non è stata usata come prova conclusiva di uno stallo attuale.
L'indice diretto attribuisce alla cartella del ciclo 00 il timestamp
`31-Oct 09:53`, compatibile con un arrivo successivo alla corsa delle 06 UTC.
Il timestamp della directory, privo di fuso esplicito, non prova l'istante
esatto della prima disponibilità. La verifica dei 14 nomi è soltanto un
controllo di discovery: il contenuto GRIB rimane da validare dal worker.

## Preparazione e autorizzazione operativa

Verificati account, progetto, immagini e generazioni dei due job esistenti,
bucket di stato/dati attesi, assenza dei due claim `20261031-pm` e assenza
di corse non terminate nelle dieci esecuzioni recenti per job. Il controllo
è stato ripetuto immediatamente prima degli avvii.

Il proprietario ha autorizzato tramite approvazione del comando
`python .tmp/recover-icon-20261031.py start` una sola esecuzione dei due job,
con aggiornamento dei dati pubblici dopo le verifiche dei worker.
Non è una pubblicazione di codice, dell'app o dei Mercati.

Richieste accettate il 31 ottobre alle **16:37:41/42 italiane**:

- FVG: `meteofriul-icon-h2hhk`.
- Nazionale: `meteofriul-national-icon-vg8wc`.

Nessun override di ambiente, claim rimosso, schedulazione cambiata o nuovo
deploy. L'anticipo usa lo slot PM: dopo un recupero riuscito, il trigger
ordinario delle 19:00 non avvia una seconda acquisizione dello stesso slot.
Il FVG verifica/recupera l'esito registrato; il nazionale riconosce lo slot
già rivendicato. Se l'acquisizione non arrivasse al checkpoint, non è
autorizzato cancellare il claim per introdurre una nuova corsa concorrente.

## Verifica del risultato

**Recupero completato.** Entrambe le esecuzioni terminano con una task
riuscita e nessun errore dell'operazione: FVG alle **16:41:03**, nazionale
alle **16:41:40** italiane. Il controllo pubblico successivo verifica il
ciclo `20261031T120000Z` su entrambi i prodotti.

- FVG: revisione **104**, manifest completo con 215 descrittori comunali;
  hash, byte, contratto e 73 campioni orari verificati per Udine, Pordenone
  e Trieste. Finestra client: fresco fino al 1 novembre alle 07:00 italiane,
  utilizzabile fino alle **13:00** dello stesso giorno.
- Nazionale: puntatore, manifest e indice completi con 7.894 comuni e
  642 blocchi. Verificati hash e contenuti di tre blocchi, con campioni
  Roma, Milano e Napoli, 73 ore ciascuno e copertura corrente valida.
- Si tratta di verifiche pubbliche campionate, non di una rilettura
  indipendente di tutti i 215 payload e 642 blocchi. I worker conservano
  i propri controlli di validazione/pubblicazione.

Il primo tentativo Python di lettura pubblica era bloccato dalla sandbox;
la ripetizione autorizzata passa. Non è stato trattato come errore del
servizio. [Ricevuta finale con hash](evidence/ICON_RECOVERY_20261031.json).

Il blocco iniziale di 5174 era confermato: nessun listener e ICON FVG ancora
alla revisione 103, ciclo del 30 ottobre 12Z, con validità client terminata
il 31 ottobre alle 13:00 italiane. Il launcher aveva arrestato i propri
processi dopo il controllo di freschezza. Il pannello 5182 e il servizio
bozze 8003 erano invece attivi. Nessun controllo di freschezza allentato,
nessuna fixture o data simulata usata per dichiarare l'app corrente.

Dopo il recupero, `.tmp/start-markets-local-20261031.ps1` richiama il
launcher canonico con `-WeatherCloud` e Node 22.17.1: **exit 0, pilota
locale pronto**. Il controllo finale delle **16:46:34 italiane** rileva:

- `http://127.0.0.1:5174/`: HTTP 200;
- backend tramite proxy: `status=ok`, `local_weather_pilot_ready=true`,
  `open_meteo_enabled=false`;
- proxy ICON: ciclo 31 ottobre 12Z, revisione 104 e validità corrente;
- pannello 5182: HTTP 200; bozze 8003: `ok`, pubblicazione Mercati disattivata.

Nessuna prova visiva tramite browser o telefono dichiarata. Il monitor
freschezza non è stato eseguito manualmente dopo il recupero: il successivo
slot naturale è alle 17:10 italiane. L'audit non dichiara già chiusi eventuali
incidenti o consegnate notifiche di ripristino.

## Punti ancora aperti

Il recupero dei dati non cambia la strategia automatica: un ritardo della
fonte oltre il tentativo del mattino può lasciare il prodotto in attesa
dello slot successivo. Un eventuale recupero differito e limitato richiede
una proposta separata, con verifica di costi, concorrenza e claim; nessuna
nuova pianificazione viene introdotta qui. Restano inoltre le quattro
fonti Eventi arretrate dell'audit precedente, indipendenti dal recupero ICON.

Le evidenze operative sono raccolte negli helper ignorati
`.tmp/icon-diagnosis-20261031/` e `.tmp/icon-recovery-20261031/`.
Le credenziali restano solo in memoria dei processi e non sono inserite
nelle ricevute. Nessun commit, push, nuova build Android o pubblicazione
dei Mercati richiesti da questa attività.
