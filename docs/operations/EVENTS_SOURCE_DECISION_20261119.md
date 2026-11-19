# Eventi: verifica fonti e pausa Spazzapan, 19 novembre 2026

## Decisione operativa

La Galleria Spazzapan è stata registrata come fonte in pausa a tempo
indeterminato nel controllo online `pilot/events/v1/source-controls.json`:
revisione 1, generazione GCS `1795100724520163`. Il motivo salvato è il cambio
dell'inventario ufficiale delle mostre, che il lettore non riesce ancora a
riconciliare. La scrittura ha usato `if-generation-match=0` e il contenuto è
stato riletto: soltanto `Galleria Spazzapan` ha `enabled=false`.

**La pausa è preparata, non ancora applicata dal traffico pubblico.** Il job
ordinario conserva l'immagine `sha256:1923bb40…` e il lettore pubblico resta
alla revisione `meteofriul-events-00018-2vz`: nessuno dei due legge ancora il
controllo nuovo. Le sue schede erano già escluse perché la fonte è `stale`.
Non attribuire a questa scrittura il successo del job né una modifica
dell'app pubblicata.

## Prove delle fonti

- Teatro Verdi Trieste: il 19 novembre il lettore XML corretto nel ramo
  `codex/events-source-controls-20261115` ha letto la fonte ufficiale senza
  scritture cloud: 56 schede, una pagina in revisione per date dei biglietti
  assenti e gate della fonte superato contro il lotto pubblico precedente.
  La prova cloud isolata del 15 novembre aveva prodotto 59 schede, ma non
  certifica il risultato del 19 novembre. Il job pubblico continua a fallire
  con `XML or text declaration not at start of entity`.
- CSS Udine: una nuova lettura ufficiale del 19 novembre produce 128 schede e
  tre pagine in revisione; il confronto con il lotto pubblico precedente non
  passa. Cinque occorrenze future già conservate non compaiono nel nuovo
  risultato: *SDENG!* (22 novembre), *La foresta dei no* (23 novembre),
  *Dialoghi Open Lab / Giorgio Barberio Corsetti* (17 dicembre) e
  *I Sette a Tebe* (19 e 20 marzo 2027). Le quattro pagine ufficiali
  rispondono HTTP 200; le date sono presenti nei testi. Il gate evita una
  perdita silenziosa. Il recupero del parser e il confronto completo restano
  su un ramo CSS dedicato.
- Il catalogo pubblico letto il 19 novembre ha 6 fonti `stale` su 15;
  CSS Udine, Teatro Verdi Trieste e Galleria Spazzapan non sono esposte dal
  lettore perché il gate ammette solo `fresh` e `partial` entro 48 ore.

## Verifiche e limiti

Nel ramo controlli Eventi sono passati 60 test mirati per controllo fonti,
API amministrativa, job, lettore HTTP e Verdi Trieste. La precedente prova
combinata e la CI della PR 48 sono documentate in
[EVENTS_SOURCE_CONTROLS_20261115.md](EVENTS_SOURCE_CONTROLS_20261115.md).
Il pannello online non contiene ancora i comandi Eventi del ramo della
[PR pannello 2](https://github.com/meteofriul/meteofriul-inserzioni/pull/2).
L'accesso e una scrittura tramite login del titolare restano da collaudare.

Prima di promuovere il lettore pubblico: collaudo autenticato nel pannello,
verifica della nuova immagine del job e delle schede nel client Web/Android.
Il job, il lettore e le policy di monitoraggio non sono stati cambiati in
questa verifica. Gli allarmi Eventi possono continuare per Barcolana e
Le Giornate del Cinema Muto anche dopo la pausa di Spazzapan.

## Allarme operativo

La policy online `projects/meteo-friul/alertPolicies/13483592592255950505`
è attiva: una condizione metrica segnala almeno un'esecuzione fallita del job
nelle ultime due ore a un canale email, con sola notifica di apertura. Il
messaggio è quindi generico. Il worker registra già nel log
`event_source_verification` lo stato di ogni fonte e nell'errore finale i
nomi delle fonti incomplete; la condizione metrica non incorpora quei campi
nella mail. Una modifica del solo testo statico della policy non risolverebbe
il problema.

La correzione dell'avviso richiede un flusso separato: un riepilogo strutturato
dei nomi dopo il salvataggio del catalogo e una notifica che estragga tali
nomi dal log. Va mantenuta una copertura distinta per i crash che avvengono
prima del riepilogo e va evitata una doppia email per lo stesso fallimento.
Preparare e collaudare questa modifica dopo l'attivazione dei controlli per
fonte, su un ramo di monitoraggio dedicato; la policy online non è stata
modificata oggi.
