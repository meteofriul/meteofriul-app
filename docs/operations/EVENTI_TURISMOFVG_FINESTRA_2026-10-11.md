# TurismoFVG: finestra mobile verificata (ramo, 11 ottobre 2026)

## Motivo

Il controllo annuale iniziale ha stabilito una base affidabile, ma rileggerne
calendario e dettagli ogni giorno non è proporzionato alla vista Eventi, che
mostra 15 giorni. Il ciclo quotidiano TurismoFVG del 9, 10 e 11 ottobre è
fallito come `incomplete_source`; il recupero mirato dell'11 ottobre è poi
riuscito. Il vecchio log non distingueva i dettagli pendenti dal limite di
tempo, perché stampava la verifica precedente della fonte stale.

## Contratto del ramo

- Il job comune continua a raccogliere le altre fonti. Per TurismoFVG legge
  una finestra inclusiva da oggi a oggi + 45 giorni. A dicembre spezza la
  ricerca al 31 dicembre e continua nell'anno successivo.
- Ogni tratto del calendario conserva i controlli sul totale dichiarato,
  sulla paginazione e sulle tessere. La sitemap completa viene letta come
  indice; si aprono i suoi URL nuovi o con `lastmod` cambiato, oltre ai
  dettagli delle tessere datate.
- Le schede già verificate e ancora pertinenti alla finestra vengono
  ricontrollate anche se sono sparite dalla ricerca corrente. Se manca pure
  la sitemap, la pagina ufficiale è letta direttamente. Una pagina non
  risolta rimane in revisione e blocca la fonte.
- Le prove delle schede già verificate ma ancora oltre i 45 giorni restano
  nel checkpoint, non nel catalogo visibile. Quando la finestra avanza,
  rientrano nel controllo anche se la ricerca e la sitemap non le hanno
  ripubblicate. Per le ricorrenze serve almeno una data esplicita dentro la
  finestra: una data successiva resta conservata per il ciclo futuro.
- Descrizione, immagine, località e date continuano a provenire dalle
  schede dettaglio. Il gate riproietta le schede dal controllo salvato e
  verifica finestra, inventario, sitemap, freschezza e assenza di revisioni.
  `source_complete=true` significa copertura verificata della finestra,
  **non** dell'intero anno.
- Un tentativo fallito rende la fonte stale e non mostra quelle schede.
  Conserva il checkpoint dell'ultima raccolta verificata per la successiva
  finestra. Il riepilogo del job usa i diagnostici del tentativo fallito.
- Il lunedì, nello stesso job, un controllo separato legge l'indice
  dell'intero anno e confronta gli URL del tratto corrente. Un problema
  segnala il job ma non cambia lo stato fresh della finestra già verificata.
  Questo audit settimanale non apre tutti i dettagli dell'anno.
- Il monitor Pro Loco confronta solo le date entro la stessa finestra.

## Prova in sola lettura

L'11 ottobre la ricerca ufficiale di 45 giorni ha restituito 1.530 tessere
in 283 pagine, senza date esplicite fuori finestra. La raccolta completa
locale dal checkpoint pilot, senza scritture cloud, è terminata in 110,6
secondi: 1.219 dettagli nell'inventario, 1.214 schede proiettate, zero
pendenti, ambigui o revisioni, gate `ok`. La sitemap conteneva 2.405 URL;
1.199 erano pertinenti alla raccolta corrente. Nove URL attivi sono stati
portati dalla prova precedente; uno, “La tavola storica delle Valli del
Natisone”, era assente sia dalla ricerca sia dalla sitemap ma la pagina
ufficiale confermava il 24 ottobre 2026.

Una prova successiva ha scoperto che il “Mercatino dell'usato” conserva nel
controllo annuale date il 4 ottobre e il 6 dicembre, ma nessuna nella
finestra 11 ottobre–25 novembre. Il ramo ora rinvia le ricorrenze senza date
nella finestra e conserva l'evidenza della prossima data. La scansione reale
ripetuta ha impiegato 123,2 secondi: 1.214 schede, 200 prove future
conservate, zero revisioni, gate indipendente `ok`. Il catalogo calcolato in
memoria occupa 2.691.646 byte, sotto il limite di 8 MiB. Dopo
l'integrazione con il `main` che ritira Anteprima Sagre, i 662 test pilot
passano (uno ignorato).

La prova riguarda il ramo e una singola esecuzione locale. Non prova ancora
la stabilità di più cicli giornalieri nel job Cloud Run né il controllo
settimanale dell'indice annuale. Nessun catalogo online è stato pubblicato
da questa prova.

## Collaudo cloud e app (11 ottobre 2026)

- La build Cloud Build `35cf4b16-3af9-42cb-8771-31e29bd77e79` ha usato `backend/Dockerfile.events-pilot`, compresi i test eseguiti durante la build. L'immagine immutabile del collaudo è `sha256:5fdff17048005dc1a3d405af5397151eee4ca784c0f290fd509315b4083dad45`.
- Un primo tentativo (`meteofriul-events-refresh-v6jp5`) ha usato per errore il Dockerfile del backend web e avviato Uvicorn. È stato annullato prima del timeout; la generazione del catalogo è rimasta `1791707321735781`.
- Il ciclo corretto (`meteofriul-events-refresh-whkqs`) ha pubblicato la generazione `1791724931338324` in circa quattro minuti. TurismoFVG è `fresh`: 1.214 schede, finestra 11 ottobre–25 novembre, 1.530 tessere lette in 283 pagine, 1.219 URL nell'inventario, nove URL attivi riportati dal checkpoint e 200 prove future conservate. Il gate dichiara `source_complete=true`, zero revisioni, zero pendenti e 1.127 anteprime con descrizione.
- L'esecuzione complessiva è risultata fallita perché **Paesi in Festa** ha segnalato una tessera attiva marcata come archiviata (`adapter_exception`). Le sue 22 schede precedenti restano nel catalogo come prova, con stato `stale`, e non sono pubblicate. Le altre 14 fonti sono `fresh`. L'API pubblica `catalog_status=degraded` e identifica Paesi in Festa fra le fonti fallite. Il catalogo è di 2.692.003 byte, sotto il limite di 8 MiB.
- Sul telefono Samsung SM-A525F, l'app ufficiale 0.1.14 ha mostrato la scheda TurismoFVG “Famiglie al Museo... Archeologico” con data 11 ottobre 2026, Museo Archeologico di Pordenone, immagine, descrizione, fonte e pulsante per la pagina ufficiale. La stessa scheda e gli stessi campi sono presenti nel catalogo cloud. Non è stato installato alcun APK.
- Dopo il collaudo, l'immagine del job è stata riportata al digest di `main`, `sha256:7a60b0d3f8855edbea073db53d0a447a090ba0899ecfc81c0265fd25a2b83692`. Il catalogo pubblicato dal collaudo è rimasto online. La PR #39 resta in bozza; il controllo settimanale dell'inventario annuale, previsto il lunedì, non è ancora stato provato sul cloud.
