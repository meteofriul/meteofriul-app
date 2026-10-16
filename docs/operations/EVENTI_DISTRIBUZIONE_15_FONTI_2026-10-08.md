# Eventi: distribuzione diretta del catalogo a 15 fonti, 8 ottobre 2026

Questo documento conserva la cronologia delle prove dell'8 ottobre. Per lo
stato corrente del job, dell'API e della promozione del ramo consultare
[il resoconto di promozione](EVENTI_PROMOTION_SCOPE_2026-10-08.md).

## Stato verificato alle 09:55 UTC

Il catalogo ufficiale `gs://meteo-friul-weather-data/pilot/events/v1/catalog.json`
contiene **15 fonti `fresh` e zero revisioni**. L'API pubblica
`/api/local/events` con le 15 fonti: 292 schede entro 20 km da Trieste e 322
entro 20 km da Pordenone al controllo delle 09:55 UTC. A Trieste compare una
sola scheda Barcolana 2026, con immagine, descrizione e programma scorrevole.
TurismoFVG ha 1.462 schede, `source_complete=true`, 2.456 URL controllati,
zero sospesi, zero ambigui e 1.351 anteprime su 1.462 schede.

Il job ufficiale `meteofriul-events-refresh` usa l'immagine
`events-failure-tags-20261008-29ecb5b2` con 1 CPU e 1 GiB. Il servizio
`meteofriul-events` usa l'immagine
`events-sagra-numbered-20261008-6b916b39` (revisione
`meteofriul-events-00009-mt7`). La schedulazione ordinaria non e' stata
cambiata. Non sono stati creati job temporanei, APK o AAB per questa
distribuzione.

**Il job non e' ancora verde**: l'ultima esecuzione completa ha fallito su
TurismoFVG e Teatro Verdi Pordenone prima dei monitor. La precedente aveva
raccolto le 15 fonti, ma il monitor Anteprima Sagre aveva ricevuto HTTP 202
`text/html` dal runtime Cloud Run invece del JSON WordPress atteso. Il
monitor locale sul PC passa, ma questo non prova la copertura automatica dal
cloud. Anteprima Sagre non e' tra le 15 fonti pubblicate; resta un monitor
separato non concluso.

## Sequenza e ripristini

1. Prima dell'aggiornamento sono stati salvati catalogo e configurazioni in
   `.dev-logs/events-deploy-2026-10-08/` (ignorata da Git). Il catalogo aveva
   sette fonti `fresh`, 136 schede TurismoFVG, nessun checkpoint; generazione
   `1791432458724938`, SHA-256
   `7452a294e9060ca3edefc81d5fbf92479b27a1dafad45f498dc91e12d892b394`.
2. Il primo job diretto ha trovato una nuova scheda TurismoFVG ambigua
   (Cocambo Time, periodo lungo con `Calendario: QUI` in una foto Facebook) e
   tre righe Barcolana pubblicate nel calendario prima della sitemap. Il
   catalogo parziale e' stato ripristinato con controllo sulla generazione;
   il job e' stato riportato all'immagine precedente.
3. Il ramo ha distinto le esperienze prenotabili senza date leggibili dagli
   eventi con programma e ha accettato un ritardo limitato della sitemap
   Barcolana quando il calendario ufficiale contiene piu' righe. La raccolta
   live isolata Barcolana ha restituito 683 righe, 680 URL nella sitemap,
   675 voci nel programma dopo le integrazioni e zero revisioni.
4. Il ciclo locale completo con storage finto ha prodotto 15 fonti `fresh`,
   zero revisioni e 1.457 schede TurismoFVG. I quattro monitor hanno segnalato
   solo una nuova notizia di Palazzo Attems: la riapertura della biblioteca
   di Villa Manin con orari di consultazione, non un appuntamento Eventi.
   Esaminata la versione `2026-10-08T10:34:22`, Palazzo Attems e gli altri
   tre monitor non hanno rilevato nuove schede da integrare localmente.
5. Un secondo job cloud a 512 MiB ha prodotto un errore generico del
   sottoprocesso TurismoFVG. Dopo il ripristino del catalogo, l'esecuzione a
   1 GiB ha raccolto tutte le 15 fonti; l'aumento di memoria e' compatibile
   con la causa del precedente errore, senza provarla da solo.
6. La terza esecuzione (`meteofriul-events-refresh-dgbbf`) ha pubblicato il
   catalogo completo ma e' terminata con errore nel monitor Anteprima Sagre.
   Due esecuzioni diagnostiche di sola lettura sullo stesso job hanno misurato
   HTTP 202/HTML per API, feed, sitemap e homepage dal cloud. Il comando
   normale del job e' stato ripristinato e verificato dopo ciascuna prova.
   Le ultime esecuzioni con stato `SUCCESS` sono diagnostiche di sola lettura:
   non attestano il successo del ciclo completo programmato.

## Verifiche e limiti

- 636 test backend `test_pilot_*.py` e 6 test Palazzo Attems passano.
- Il ciclo locale completo ha superato i gate delle 15 fonti. L'API cloud
  risponde con 15 stati `fresh`, zero revisioni e una sola Barcolana a Trieste.
- Le schermate dell'utente hanno confermato che 0.1.12 e la precedente
  0.1.13-tester ricevono la scheda Barcolana con immagine e anteprima, ma
  quelle build non mostravano il programma. L'8 ottobre e' stata installata
  in-place una nuova build della tester separata (`com.meteofriul.app.tester`,
  versione `0.1.13-tester`, codice `300030`), con la UI di questo ramo.
  Sul Samsung SM-A525F, impostando temporaneamente Trieste, la scheda unica
  Barcolana ha mostrato 386 appuntamenti futuri, elenco scorrevole e pulsanti
  sotto il programma. La localita' predefinita Urbino e' stata ripristinata.
  La data della prima installazione della tester e' rimasta invariata; la
  0.1.12 ufficiale ha conservato versione e data dell'ultimo aggiornamento.
  La build ha superato 27 test mirati, verifiche di pacchetto e firma ed
  `adb install -r`. Il ramo non e' stato promosso su `main`.
- Il monitor Anteprima Sagre non va considerato completo nel cloud finche'
  non dispone di una superficie pubblica accessibile in modo affidabile dal
  job, o di un meccanismo automatico separato approvato.

## Verifica Anteprima Sagre successiva

L'8 ottobre, dal PC, la REST API pubblica ha risposto `200` con 419 articoli
su 5 pagine: nessun nuovo candidato con data futura, una scheda senza anno gia'
nota. Nei log del job completo, la prima pagina e' stata letta, mentre la
seconda ha prodotto una risposta inattesa. Le due esecuzioni diagnostiche cloud
successive hanno ottenuto `202 text/html` su tutte le superfici pubbliche
provate (homepage, feed, sitemap e REST API). Il meccanismo che produce il 202
non e' stato identificato.

Il [`robots.txt`](https://www.anteprimasagre.it/robots.txt) dichiara
`Crawl-delay: 10` per `User-agent: *`; il monitor prima inviava le richieste
alle pagine REST in successione immediata. Il ramo ora attende 10 secondi tra
le pagine e un test verifica la sequenza. Il test locale del monitor ha letto
419 articoli in 5 pagine con la pausa prevista.

## Distribuzione e verifica della pausa (8 ottobre)

Con autorizzazione dell'utente e dopo 23 test mirati passati, la correzione e'
stata distribuita nell'immagine
`events-audit-20261008-e4a23fed` del solo job `meteofriul-events-refresh`.
La build Cloud Build `c35f4771-3d7b-43bf-a84b-381c625181af` e' riuscita;
configurazione del servizio API e schedulazione non sono state cambiate.

L'unica esecuzione completa autorizzata, `meteofriul-events-refresh-dfbt9`,
e' terminata con errore prima di raggiungere il monitor Anteprima Sagre:
`TurismoFVG` e `Teatro Verdi Pordenone` hanno restituito `source_error`.
Il sottoprocesso di raccolta non conserva il dettaglio dell'eccezione, quindi
non e' possibile dedurre la causa dai log di questo ciclo. La pausa di 10
secondi **non e' stata verificata nel cloud** e il monitor rimane aperto.

Il job ha pubblicato un catalogo parziale prima di segnalare l'errore:
13 fonti `fresh` e le due fonti citate `stale`. Il catalogo precedente,
salvato prima della prova, e' stato ripristinato con controllo della
generazione e verifica byte per byte. La successiva lettura dell'API pubblica
ha restituito `ready`, 15 fonti `fresh` e nessuna `stale`, con snapshot
`2026-10-08T09:49:40.835901+00:00`. Il ramo non e' stato promosso su `main`.

Al momento della prova, il flusso pubblicava un catalogo parziale prima di
segnalare il gate di completezza. Prima di una nuova esecuzione occorre
rendere diagnosticabili gli errori dei sottoprocessi delle due fonti e
verificarne la causa. Un secondo ciclo cloud completo non e' stato avviato.

## Decisione sulla pubblicazione delle fonti fallite

Il criterio concordato successivamente distingue il catalogo live dal
risultato del job: una fonte che fallisce deve ricevere un tag diagnostico e
non deve fornire eventi all'API, mentre le fonti verificate possono essere
aggiornate. La copia precedente della fonte fallita resta nello stato interno
per confronti e recupero; non e' una scheda pubblicata nell'app. Un retry
successivo della sola fonte puo' sostituirla dopo gli stessi controlli.

Il ramo applica questa regola a tutte le fonti, comprese quelle che prima
restavano visibili con stato `stale`. Il comando `python -m
app.events.pilot_cloud --retry-failed` seleziona solo le fonti registrate con
stato fallito e conserva il checkpoint TurismoFVG; non avvia i monitor.
Resta un intervento esplicito, da eseguire solo dopo aver esaminato il tag.
I tag distinguono almeno timeout,
uscita inattesa del worker, risultato invalido, eccezione dell'adapter e
fallimento dei gate di verifica. L'API espone i tag e lo stato `degraded`
separatamente dagli eventi; non espone il dettaglio diagnostico delle
eccezioni. Se tutte le fonti falliscono, il job pubblica gli stati di errore
e nessun evento live, invece di continuare a servire come corrente il
catalogo precedente. Il job segnala comunque il fallimento.

La build Cloud Build `d1f410f5-e14e-492d-b224-741e3199bfc1` ha completato
con successo i test nell'immagine. Il nuovo lettore e' stato distribuito
prima sul servizio API (revisione `meteofriul-events-00007-nsh`, 100% del
traffico), poi sul job. Nell'API il catalogo ripristinato risponde `ready`,
`catalog_status=complete`, 15 fonti `fresh`, zero tag di errore; l'immagine
del job e' l'unica impostazione del container cambiata. L'ultima esecuzione
del job resta `meteofriul-events-refresh-dfbt9`: **non e' stato avviato un
nuovo ciclo**. La protezione delle fonti fallite e il recupero mirato sono
distribuiti, ma il loro comportamento su un errore cloud reale non e' ancora
verificato. I tag sono operativi, senza nuova UI nell'app.

## Filtro Sagre nella tester e nella 0.1.12

La segnalazione dell'utente ha mostrato che le tre schede "Sagra del Rosario"
comparivano in "Tutti" ma sparivano nel filtro "Sagre". Il catalogo sorgente
le classificava `musica` tramite TurismoFVG; dopo la fusione con SagreFVG e
Paesi in Festa, la categoria sbagliata rimaneva anche nella scheda unica.
Il commit `0e826d7e` assegna `sagra` alle schede il cui titolo inizia con
"Sagra" dopo la deduplicazione, mantenendo `musica` per un concerto che si
svolge alla sagra. Trentadue test mirati e la build Cloud Build
`6077e245-837b-4bfc-98d3-e74b4e1da4b6` sono passati.

Con autorizzazione dell'utente e senza avviare la raccolta, e' stato
aggiornato solo il servizio API alla revisione `meteofriul-events-00008-29t`
(100% del traffico). L'API online restituisce ora tre schede Rosario distinte:
Pordenone, San Quirino e Caneva, tutte `category=sagra` e ciascuna con una
sola scheda e i link delle fonti conservati. Il catalogo conserva 15 fonti
`fresh`, `catalog_status=complete`; l'immagine del job e' invariata.

Il precedente [controllo preliminare](EVENTI_PREFLIGHT_DISTRIBUZIONE_2026-10-08.md)
documenta lo stato prima di questa distribuzione; le sue indicazioni sul
collaudo con un job separato sono state superate dalla scelta di aggiornare
direttamente il sistema esistente durante il test.

## Sagre numerate nel filtro

Un controllo successivo di 1.742 schede visibili nel catalogo locale ha
individuato due titoli con un numero prima di "Sagra" che la prima regola non
classificava come `sagra`. Il commit `6b916b39` riconosce anche questa forma
senza cambiare la categoria di un concerto svolto durante una sagra. Trentatre
test mirati passano; nel campione non restano titoli contenenti "Sagra" fuori
dalla categoria. I titoli che iniziano con "Festa" non sono stati classificati
in blocco, perche' comprendono tipi di evento differenti.

Su autorizzazione dell'utente, la build Cloud Build
`d7548da7-f476-4997-a7df-d1b01f037d35` ha creato con successo l'immagine
`events-sagra-numbered-20261008-6b916b39`. E' stato aggiornato solo il
servizio API alla revisione `meteofriul-events-00009-mt7` con il 100% del
traffico. La risposta pubblica per Polcenigo classifica "40ª Sagra della
Castagna" come `sagra`; quella per Talmassons classifica "1ª Sagra da la
Cjavrute" come `sagra`. "Sagra del Rosario" a Caneva resta `sagra`.
L'API riporta `ready`, `catalog_status=complete`, 15 fonti `fresh` e zero tag
di errore. L'immagine e l'ultima esecuzione del job di raccolta sono rimaste
invariate.
