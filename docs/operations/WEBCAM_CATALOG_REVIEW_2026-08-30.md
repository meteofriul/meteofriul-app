# Revisione catalogo Webcam — 30 agosto 2026

> Stato locale successivo: su richiesta esplicita dell'utente, il manifest **versione 6** configura i JPEG di Sacile e Cividale/Piazza Duomo e il resolver della foto corrente di Udine/Piazza Matteotti, con riferimenti alla fonte. **Udine resta da collaudare visivamente: nell'ultima prova l'app è passata alla foto di riserva.** Le altre 16 voci restano solo collegamenti. Vedere le ultime sezioni: questa scelta non certifica una licenza sulle immagini e non è stata distribuita all'app pubblicata. Le prime fasi sotto documentano i precedenti manifest versione 3, 4 e 5.

## Checkpoint e sospensione — 30 agosto 2026

L'utente ha chiesto di salvare il lavoro in un commit e sospendere temporaneamente le webcam per riprendere Scopri/editoriale. Il checkpoint conserva il collaudo riuscito di Sacile e Cividale, la preparazione di Udine con collaudo ancora aperto e la procedura di rimozione delle singole fonti. Non certifica il catalogo come pronto per una nuova distribuzione. Nessun push o deploy autorizzato da questa richiesta. Le note "nessun commit" nelle fasi sotto descrivono il loro stato al momento della verifica, precedente a questo salvataggio.

## Esito e perimetro

Sistemazione locale successiva agli audit del [27 agosto](./WEBCAM_SOURCE_AUDIT_2026-08-27.md) e del [pannello video OSMER del 29 agosto](./WEBCAM_OSMER_VIDEO_AUDIT_2026-08-29.md). Nessun contatto con proprietari, acquisto di servizi, commit, push o deploy eseguito in questa revisione.

- Manifest attivo versione **3**: **19 webcam**, di cui 7 Montagna, 6 Pianura e 6 Costa. Il gruppo Vicino è una selezione, non un catalogo aggiuntivo.
- **6 candidate** ancora in ombra, senza pubblicazione automatica.
- **1 sospesa**, Aquileia, conservata in `backend/app/data/webcams_suspended.json` con `mode: shadow` e `publish: false`.
- Tutte le 19 voci attive mantengono **foto territoriale locale e collegamento esterno**. Nessun `imageUrl`, `playerUrl` o `mediaType` abilitato nel manifest attivo.
- Le foto locali già approvate e i loro crediti non sono stati sostituiti con fotogrammi di terzi.

Il catalogo è attivo nel repository e nell'API locale; queste modifiche non sono ancora distribuite all'app pubblicata. Le evidenze sotto sono puntuali, non una garanzia di disponibilità futura o una verifica continuativa di tutti i flussi.

## Correzioni delle fonti

| Voce precedente | Scelta corrente | Evidenza e limite |
| --- | --- | --- |
| Sacile — Protezione Civile FVG | [SacileMeteo](https://sacilemeteo.altervista.org/hik/webcam_hik.html) | L'API PC `/api/webcams/55/images?last=1` restituisce `images: []`, `count: 0`, `total: 0`. La pagina SacileMeteo identifica la webcam di Sacile; HEAD di `hik/webcam_r.jpg` restituisce JPEG con Last-Modified 30/08/2026 14:09:11 UTC, verificato alle 14:11:20 UTC. Nessuna copia o incorporazione dell'immagine. |
| Monfalcone — Marina Julia, PC FVG | [Spiaggia di Marina Monfalcone](https://marinamonfalcone.com/it/webcam/) | Anche l'API PC `/api/webcams/9/images?last=1` restituisce un elenco vuoto. La nuova pagina del proprietario descrive esplicitamente la spiaggia di Marina Monfalcone: è una webcam diversa, quindi ID, nome e area sono cambiati. Il consenso al player resta sul sito esterno. |
| Piancavallo — Nevelandia | [Piancavallo — Sauc](https://piancavallo.panomax.com/) | La camera indicata da Nevelandia non risponde al controllo diretto entro 12 secondi. La pagina Panomax identifica Sauc, coerente con il [catalogo PromoTurismoFVG](https://www.turismofvg.it/en/webcam). Solo collegamento alla pagina pubblica. |
| Forni di Sopra — loc. Chianeit | [Forni di Sopra — Malga Varmost](https://fornidisopra.panomax.com/) | Il [sito di Forni di Sopra](https://fornidisopra.it/webcam-forni-di-sopra) distingue il panorama Panomax di Malga Varmost a 1750 m da Chianeit/Clap Varmost. L'associazione precedente del player DEV a Chianeit era errata. |
| Cividale — Ponte del Diavolo | [Cividale — Piazza Duomo](https://www.cividale.com/it/web_cam) | Il JPEG del Ponte ha Last-Modified 16/08/2025; quello di Piazza Duomo restituisce 30/08/2026 13:58:49 UTC. Due controlli HEAD concordano, ma non è stato osservato un avanzamento temporale tra i due. La pagina esterna è una raccolta: non è stato inventato un anchor diretto alla camera. Provider corretto in Cividale.com. |
| Val Saisera | [Jôf di Montasio — Val Saisera](https://www.radiopuntozero.it/cam/) | Il proprietario usa questo nome e l'immagine associata `rpzcam_lussari_4.jpg` risulta aggiornata al 30/08/2026 14:00:45 UTC. Non è giustificato considerarla spenta solo dal nome del file. La posizione esatta della camera non è confermata: nessuna coordinata precisa aggiunta. |

Sono stati rimossi da Sacile e Monfalcone i vecchi identificativi API e le coordinate PC: non appartengono automaticamente alle nuove riprese. Le distanze senza coordinate della camera usano il Comune e restano contrassegnate con `~`. I vecchi ID nel mapping frontend rimangono supportati per payload già in cache, ma non generano voci di catalogo.

## Due candidate promosse

- [Sappada — Panorama](https://sappada.panomax.com/), ID `sappada-panorama`.
- [Sella Nevea — Monte Canin](https://sellanevea.panomax.com/), ID `sella-nevea-canin`.

Entrambe hanno pagina pubblica specifica coerente con il catalogo turistico, foto locale approvata e crediti già presenti. Sono state rimosse dal manifest candidate per evitare duplicati. L'accesso alle pagine è risultato pubblico; ciò non costituisce una licenza per incorporarle nell'app.

Restano candidate: Val Settimana/Rifugio La Pussa, Monte Matajur, Moruzzo, Cervignano del Friuli, Piazza della Transalpina e Trieste/San Giusto.

## Aquileia sospesa, non cancellata

La [pagina WhatsUpCams](https://www.whatsupcams.com/it/webcams/italia/friuli-venezia-giulia-it/aquileia-it/aquileia-piazza-capitolo/) è raggiungibile, ma il widget `services.whatsupcams.com/wgt/it_aquileia01` non presenta un player; il manifest `cdn-007.whatsupcams.com/hls/it_aquileia01.m3u8` risponde HTTP 404. La miniatura disponibile ha Last-Modified **17/05/2026 05:06:44 UTC**.

Il record completo e la motivazione sono recuperabili nel manifest sospese; la foto locale è rimasta al suo posto. Il servizio rifiuta i manifest `shadow`, anche se configurati come sorgente locale o ricevuti dalla sorgente remota. Aquileia potrà rientrare solo dopo una verifica e una promozione esplicita.

## Interfaccia

- Sulla foto locale, azione **“Guarda la webcam” / “Cjale la webcam”** con icona di collegamento esterno. Apertura in nuova scheda con `noopener noreferrer`; nessuna icona Play per i collegamenti esterni.
- Eliminata la duplicazione dello stesso collegamento nel footer della card normale. Il link di riserva resta se la foto non si carica, e come alternativa al player DEV.
- Rimossa l'etichetta visibile “Foto statica del territorio”, come richiesto; il testo alternativo dell'immagine continua a descriverla correttamente.
- Un errore della foto locale mostra “Immagine non disponibile”, non “Webcam temporaneamente non disponibile”. L'errore della foto non dimostra che la fonte esterna sia spenta.
- I due player Panomax restano esclusivamente DEV, dietro `webcamPlayerQa=panomax` e caricati dopo il tocco. Il mapping di Forni ora è `forni-varmost`; `forni-chianeit` non riceve più il player di un'altra ripresa. Nessun ampliamento dell'allowlist e nessuna abilitazione in produzione.

## Controllo automatico: cosa certifica

`backend/tools/check_webcams.py --timeout 6` sul nuovo catalogo: **19/19 OK** per asset configurati e raggiungibilità delle pagine. Il report ora dichiara:

```json
{
  "verification_scope": "configured_assets_and_source_reachability",
  "not_verified": ["stream_freshness", "viewpoint_identity", "embedding_permission"]
}
```

Ogni risultato contiene inoltre `stream_freshness: "not_verified"`. Né `health: ok` né `checkedAt` garantiscono fotogrammi correnti, corrispondenza geografica o diritti di incorporamento. Lo stato `N` dei metadati PC non è stato interpretato come “disabilitata”, perché tale significato non è stato accertato.

## Compatibilità e cache

- Contratto dell'endpoint Webcam invariato; cambia il contenuto del manifest, non il formato. Nessuna modifica a notifiche, segnalazioni o versione Android.
- Il manifest remoto configurato con `LIVE_WEBCAMS_MANIFEST_URL`, se presente, continua ad avere precedenza sul file locale: va considerato prima di una futura distribuzione.
- Backend e frontend possono mantenere il catalogo precedente fino al normale refresh (cache Webcam 10 minuti); offline una copia sul dispositivo può restare disponibile fino a 7 giorni. Non è una riattivazione di Aquileia dal file sospese. Il refresh esplicito dell'app ricarica i dati, senza cambiare questa politica.
- API locale e proxy Vite verificati: versione **3**, `count: 19`, sorgente `local`.

## Verifiche locali

- Suite frontend mirata Live, liveApi e AppRoutes: **226 test superati**, inclusi 7 test d'integrazione sul manifest reale (identità, esclusione delle sospese/candidate, distanze municipali indicative in IT/FUR).
- Backend catalogo, servizio, checker e CLI: **43 test superati**.
- Lint frontend e build Web di produzione superati. Output della build in una directory temporanea del sistema; warning preesistente sulla dimensione dei chunk non bloccante.
- Browser: anteprima normale senza flag player; gruppi 7/6/6, nuove voci nel selettore, URL SacileMeteo e Sappada corretti. A 360×800 nessun overflow orizzontale; azione leggibile in IT/FUR, tema chiaro/scuro. Nessun elemento iframe/video nella pagina normale.
- Nessuna prova su dispositivo Android fisico in questa revisione. Le modifiche preesistenti al footer versione delle Impostazioni sono rimaste separate e intatte.

## Riuso fonte per fonte — 1. SacileMeteo

Verifica aggiuntiva del **30/08/2026, 16:39–16:40 CEST**. Obiettivo: valutare una futura visualizzazione della ripresa dentro l'app, distinta dal collegamento esterno già funzionante. Nessun contatto, costo, download/salvataggio di media o attivazione di immagini nel manifest.

| Aspetto | Esito verificato |
| --- | --- |
| Sorgente | [Pagina webcam Sacile](https://sacilemeteo.altervista.org/hik/webcam_hik.html), con copyright intestato a Luigi Carbonera. Non è una fonte comunale. |
| Tipo di contenuto | JPEG aggiornato periodicamente. La pagina dichiara uno scatto ogni 5 minuti; i video delle ore precedenti sono collegamenti ad archivi, non uno streaming continuo nella pagina. |
| Endpoint ridotto | `https://sacilemeteo.altervista.org/hik/webcam_r.jpg`: HEAD 200, `image/jpeg`, 761126 byte, Last-Modified 30/08/2026 14:39:11 GMT. Il valore precedente delle 14:09:11 GMT conferma che il file è avanzato tra i controlli, non misura la frequenza di acquisizione. |
| Endpoint originale | Il link della pagina usa `http://sacilemeteo.altervista.org/hik/webcam.jpg`: HEAD 200, `image/jpeg`, 1461353 byte, Last-Modified 14:39:09 GMT. Non usare questa variante HTTP nell'app HTTPS. |
| Dimensioni | La pagina presenta la ridotta a 1280×720 e dichiara l'originale 3840×2160. Sono indicazioni HTML, non dimensioni dei file accertate con HEAD. |
| Cache e richieste | Entrambi i JPEG dichiarano `Cache-Control: max-age=2592000` e un ETag. La pagina richiede il JPEG ridotto con timestamp ogni 60 secondi e ricarica il documento ogni 300 secondi. Un'integrazione non deve confondere il refresh della richiesta con l'ora di acquisizione della foto. |
| Header | Nelle risposte osservate non risultano CSP, X-Frame-Options o Access-Control-Allow-Origin. L'assenza di blocchi non certifica un permesso; non sono stati tentati aggiramenti o proxy. |
| Licenza pubblica | La [homepage](https://sacilemeteo.altervista.org/) contiene un link `rel="license"` a **CC BY-SA 3.0 Italia**, insieme a una nota sulla titolarità di marchi, foto e loghi. La pagina specifica della webcam contiene il copyright, ma non un riferimento CC o un testo che ne definisca l'applicazione ai fotogrammi. |
| Decisione iniziale, prima della successiva richiesta dell'utente | **Tecnica favorevole; ambito della licenza sulle immagini non confermato in questa verifica.** Proposto di conservare `sourcePage` e foto locale senza impostare `imageUrl` o dichiarare la singola ripresa CC BY-SA nel catalogo sulla sola base del footer generale. Non classificare la fonte come vietata o a pagamento. |

### Come leggere la licenza senza introdurre divieti inesistenti

Una licenza CC valida può già autorizzare la condivisione senza un accordo individuale aggiuntivo. **Un avviso di copyright non annulla da solo la CC**, né la nota sui rispettivi proprietari costituisce automaticamente un divieto. Il punto ancora incerto è quali contenuti del sito siano coperti dalla dichiarazione generale, dato che sono presenti anche materiali e collegamenti di terzi.

La [CC BY-SA 3.0 Italia](https://creativecommons.org/licenses/by-sa/3.0/it/deed.it) consente la condivisione dei materiali coperti, con attribuzione e collegamento alla licenza; eventuali adattamenti richiedono le condizioni ShareAlike. Creative Commons raccomanda di [identificare chiaramente il materiale coperto](https://creativecommons.org/faq/#how-do-creative-commons-licenses-and-public-domain-tools-work-technically). Questa è una valutazione operativa prudente, non un accertamento legale che la ripresa sia esclusa dalla CC.

### Requisiti tecnici prima di un'eventuale abilitazione

- Usare il JPEG HTTPS, non un iframe dell'intera pagina con servizi pubblicitari/consenso e non gli archivi video di terzi.
- Presentarlo come **foto aggiornata**, non come streaming video; non scrivere “adesso” usando soltanto l'ora dell'ultima richiesta.
- Evitare cache di 30 giorni per una ripresa attuale; ricaricare al massimo secondo il ciclo dichiarato di 5 minuti, solo mentre la ripresa è aperta e visibile. Nessun polling in background o sincronizzato su tutte le webcam.
- Conservare immagine intera e scritte originali; attribuzione, fonte e licenza devono essere consultabili. Il backend accetta già `attribution` e `attributionUrl`, ma il view model e la card attuali non li visualizzano: il semplice inserimento di `imageUrl` non completa l'integrazione.
- Verificare HTTPS, cache, ripresa dopo background, consumo e fallback su Web e Android fisico. Queste prove di visualizzazione integrata non sono state eseguite in questa passata.

Per le prossime fonti mantenere tre esiti distinti: **integrabile** quando funzionamento e base di riuso sono verificati; **solo collegamento** quando il riuso rimane incerto o non compatibile; **sospesa** quando manca una ripresa utilizzabile. L'assenza di un prezzo, da sola, non determina l'esito.

## Sacile — visualizzazione locale richiesta dall'utente

L'utente ha successivamente richiesto di mostrare comunque il fotogramma, mantenendo il collegamento alla fonte. È stato chiarito che tale collegamento non elimina l'incertezza sul riuso; non sono emerse nuove evidenze di licenza. La richiesta è stata implementata **localmente**, senza contatti, accordi, push, deploy o build Android.

- Manifest versione **4**, invariato nel numero di voci: soltanto Sacile riceve `imageUrl` HTTPS e `mediaType: snapshot`. Le altre 18 non ricevono immagini o player incorporati.
- Credito **© Luigi Carbonera**, provider SacileMeteo e collegamento alla pagina specifica della webcam. Nessuna dichiarazione CC BY-SA attribuita al singolo fotogramma.
- Immagine intera con `object-fit: contain`: nessun ritaglio o pulsante sovrapposto alle scritte originali. Il comando **Apri la fonte / Vierç la font** resta sotto la ripresa.
- Prima richiesta quando la card entra nell'area visibile; poi controllo ogni **5 minuti**. Timer sospeso se la card esce dallo schermo o la pagina passa in background, e rimosso al cambio di webcam. Se manca IntersectionObserver, il fallback controlla almeno la visibilità del documento.
- Il parametro di richiesta `mf_snapshot` evita di riusare il JPEG dalla cache dichiarata di 30 giorni. È un timestamp della richiesta, non un orario di acquisizione da presentare all'utente.
- Nessun iframe, player video, richiesta agli archivi o proxy. Il browser richiede direttamente l'immagine HTTPS al gestore; `referrerPolicy: no-referrer` evita di trasmettere l'URL della pagina dell'app, non l'indirizzo IP necessario alla connessione.
- In caso di errore o timeout resta la foto territoriale approvata. Il credito del fotogramma remoto non viene erroneamente applicato alla foto locale. Il recupero degli snapshot segue il controllo visibile ogni 5 minuti, non il vecchio tentativo dopo 60 secondi.
- Test aggiornati: **267 frontend** (inclusi controller visibilità/refresh, URL, attribuzione e manifest reale), **43 backend**; lint e build Web di produzione superati. Output build in directory temporanea del sistema, non in `frontend/dist`.
- Verifica Browser successiva al refresh della cache: API locale versione **4**; JPEG caricato realmente nella card (`naturalWidth: 1920`, `naturalHeight: 1080`), immagine intera, autore e collegamento alla fonte presenti. Controllo visivo IT/chiaro e FUR/scuro a 649×930, senza overflow orizzontale né iframe/video. Cambio a Piancavallo/Sauc e ritorno a Sacile verificati: la foto territoriale dell'altra webcam non eredita il credito di Carbonera. Nessuna simulazione di errore di rete o prova Android fisica durante questa verifica Browser; fallback e sospensione/ripresa del timer sono coperti dai test automatici.

### Prima di distribuire questa modifica

La prova locale non equivale a un'approvazione legale o a una verifica su Android. Prima di un futuro deploy occorre riesaminare l'ambito della licenza, aggiornare le informazioni sui caricamenti diretti da terzi e verificare anche i client Android già installati: i precedenti frontend non hanno il nuovo controllo snapshot/cache. Non distribuire il solo manifest assumendo che le vecchie app gestiscano automaticamente il nuovo comportamento.

## Gestione fonte per fonte e rimozione remota

L'utente ha chiesto di proseguire con fonti tecnicamente accessibili, fonte/crediti visibili e rimozione successiva in caso di richiesta del titolare, senza contattare preventivamente i gestori. È una scelta operativa dell'utente, non una verifica dei diritti e non un'autorizzazione implicita a deploy o pubblicazione. Non viene assunto che contenuto gratuito o assenza di blocchi tecnici equivalgano a permesso di riuso.

La rimozione di una **singola fonte** non richiede un nuovo APK/AAB: l'app riceve elenco e URL da `/api/live/webcams`. Per conservare il solo collegamento si eliminano `imageUrl`, `mediaType`, eventuali `snapshotResolver` e `playerUrl` e i crediti esclusivi del fotogramma; per togliere completamente la fonte si rimuove la voce dal catalogo attivo, documentandola nel catalogo sospese. La modifica deve arrivare al backend in uso, non soltanto restare nel repository locale.

Precauzioni operative verificate nel codice:

- Se è configurato un manifest remoto, aggiornare **anche il manifest locale di riserva del backend**, altrimenti un guasto della sorgente remota può riproporre la voce precedente. Una copia già salvata sul telefono viene sostituita quando arriva un nuovo catalogo valido.
- **10 minuti non sono un termine massimo di spegnimento.** Backend e client hanno ciascuno una cache di 10 minuti; il client rivaluta il caricamento all'apertura/ritorno in primo piano e con il ciclo di 5 minuti mentre Territorio è montato. Le attese si possono sommare. Nessuna garanzia di revoca istantanea o esattamente entro 10 minuti è stata introdotta.
- Offline o in caso di errori prima di ricevere il nuovo catalogo, il telefono può conservare quello precedente fino a 7 giorni. Dopo un caricamento riuscito della rimozione, i successivi fallback offline usano invece il catalogo già aggiornato.
- Non usare `webcams: []` come interruttore globale: attualmente il backend/client lo trattano come elenco non utilizzabile e possono ricorrere alle copie di riserva. La procedura qui verificata riguarda singole fonti con catalogo restante valido.
- Nessun nuovo pannello amministrativo, endpoint di spegnimento o cambiamento dei tempi di cache è stato introdotto.

Test di regressione aggiunti: soglia esatta dei 10 minuti, rimozione di una webcam, disattivazione del solo JPEG, sostituzione della cache persistente e successivo uso offline del catalogo aggiornato; lato backend rimozione da manifest remoto dopo la scadenza della cache con mantenimento delle altre fonti.

## Riuso fonte per fonte — 2. Cividale / Piazza Duomo

Verifica tecnica del **30/08/2026, 17:12–17:15 CEST** sulla [pagina Cividale.com](https://www.cividale.com/it/web_cam), seguita dall'inserimento nel solo manifest locale versione **5** secondo la richiesta dell'utente.

- JPEG esatto incluso nella pagina: `https://www.meteo.fvg.it/ext/webcams/webcams/CividalePiazzaDuomo-cividale_piazzaduomo.jpg`. HEAD 200, `image/jpeg`, 64953 byte, Last-Modified `Sun, 30 Aug 2026 14:58:49 GMT`; ETag presente, nessun Cache-Control/Expires osservato.
- Browser sulla sorgente: immagine **704×576**, con data/ora impressa `30-August-2026 16:58:48`, ripresa del Palazzo Comunale e fascia inferiore con loghi istituzionali/finanziamento. L'immagine viene mantenuta intera, senza ritagli o sovrapposizioni.
- La pagina Cividale.com raccoglie cinque JPEG ospitati da meteo.fvg.it; non espone un endpoint proprio della camera. La descrizione HTML cita webcam a cura di turismofvg.it, ma non identifica con certezza il titolare della singola foto. Non è stato attribuito il copyright fotografico a Cividale.com, Start 2000 o al Comune.
- Fonte della card: **Cividale.com**, collegamento alla raccolta; riferimento al fornitore del file **ARPA FVG - OSMER e GRN**, con collegamento `https://www.meteo.fvg.it/`. Non dichiarata una licenza specifica del fotogramma.
- La pagina non dichiara la cadenza di acquisizione. Il controllo frontend ogni 5 minuti è una frequenza delle nostre richieste mentre la card è visibile, **non** una promessa di uno scatto ogni 5 minuti. Nessun video continuo, iframe, archivio o proxy.
- Il vecchio Ponte del Diavolo (`CividalePontedelDiavolo-cividale_strettasanmartino.jpg`) risulta fermo al 16/08/2025; l'altra immagine Natisone/Ponte al 24/05/2026. Non sono state riattivate.
- Le [note legali ARPA/OSMER](https://www.osmer.fvg.it/note-legali.php) riportano una restrizione alla ripubblicazione dei dati real-time prima di 24 ore, salvo deroga. Il caricamento tramite Cividale.com non dimostra una deroga trasferibile alla nostra app. Questo limite è stato comunicato durante il lavoro; l'inserimento locale su richiesta non viene classificato come riuso autorizzato. Nessun contatto né pubblicazione effettuati.

Verifiche automatiche dopo l'inserimento: **270 test frontend** Live/liveApi/AppRoutes e **44 backend** catalogo/servizio/checker/CLI superati; lint e build Web di produzione superati (directory temporanea del sistema, warning chunk preesistente non bloccante). Nessuna modifica di runtime frontend aggiuntiva rispetto al supporto snapshot già provato con Sacile; le nuove modifiche riguardano catalogo, test e documentazione.

Browser dell'app locale dopo il normale rinnovo della cache backend e svuotamento della cache Web tramite Impostazioni: API versione **5** alle 17:20 CEST, foto Cividale caricata (`data-state: loaded`, `data-source: live`, dimensioni naturali 704×576), `object-fit: contain`, collegamenti Cividale.com e ARPA corretti e nessun overflow orizzontale. Controllo visivo IT/chiaro a 1280×720, card con larghezza compatta dell'app; il supporto condiviso IT/FUR/chiaro/scuro era stato verificato nella fase Sacile. Nessun riavvio backend, modifica dei tempi di cache o deploy usato per forzare il passaggio. Nessuna nuova prova Android fisica.

## Riuso fonte per fonte — 3. Udine / Piazza Matteotti

Preparazione locale del **30/08/2026, dalle 19:29 CEST**, manifest versione **6**. Fonte: [Corte San Giacomo](https://cortesangiacomo.udine.it/webcam/). Non viene presentata come fonte comunale né come video continuo. Nessun contatto, commit, push, deploy o build Android.

### Fonte e indirizzo variabile

- La pagina dichiara una foto ogni **30 minuti** e manutenzione notturna dalle 03:44 alle 03:50. Il refresh HTML osservato è di 1800 secondi.
- Il fotogramma è indicato da `div.snap img`, con un nome contenente il timestamp: non è stato trovato nella pagina un JPEG stabile da inserire nel catalogo.
- Alle 17:29:49 UTC il file pubblicato era `https://www.cortesangiacomo.udine.it/webcam/snapshot//192.168.1.105_01_20260830192740708_TIMING.jpg`: HTTP 200, JPEG **1920×1080**, **437171 byte**, Last-Modified `Sun, 30 Aug 2026 17:27:41 GMT`. Questi dati attestano la verifica puntuale iniziale, non disponibilità continua.
- Il riferimento numerico privato compare nel **nome del file pubblico**, non nell'host contattato. Non sono richieste risorse di rete locale.
- La fonte rimane **Corte San Giacomo**, con collegamento alla pagina specifica. Non si ripete lo stesso nome in una seconda riga di attribuzione e non si inventano titolarità fotografica o licenza.

### Implementazione e isolamento dei guasti

- Il manifest contiene `snapshotResolver: corte-san-giacomo` e `mediaType: snapshot`, **senza un `imageUrl` datato**. Il backend legge l'indirizzo corrente dalla pagina pubblica e lo restituisce nel normale campo `imageUrl` dell'API; il metadato del resolver non viene serializzato al client.
- Resolver ammesso soltanto per l'ID Udine, la pagina esatta e il percorso JPEG verificato. Niente endpoint arbitrari, redirect, URL relativi, credenziali, porte, query o percorsi alternativi provenienti dall'HTML.
- Una sola immagine nel contenitore atteso; HTML ambiguo o struttura cambiata producono fallback. Limite corpo **128 KiB**, richiesta senza compressione e rifiuto delle risposte compresse. Controllo del tempo tra singoli byte per evitare che una risposta continua ma molto lenta nasconda il superamento del budget nel buffer.
- Timeout di connessione/lettura massimo di **2 secondi**, più controllo del tempo durante il corpo: **non è una garanzia di scadenza assoluta dell'intera richiesta durante DNS o intestazioni HTTP**.
- Il rinnovo del catalogo è serializzato per istanza e usa la cache esistente di **10 minuti**: richieste concorrenti non moltiplicano le letture della pagina. Non è una cache condivisa fra tutte le istanze Cloud Run.
- Il backend non scarica, salva o ridistribuisce JPEG. È il browser a richiedere la foto alla fonte, tramite il supporto snapshot già presente: controllo ogni 5 minuti solo quando la card è visibile. Questo non cambia la cadenza degli scatti della webcam.
- Se la risoluzione fallisce, Udine mantiene foto territoriale e collegamento, senza impedire di restituire le altre voci. Un errore successivo dell'immagine è gestito dal fallback frontend già esistente.
- Per spegnere il solo fotogramma di Udine, rimuovere **`snapshotResolver` e `mediaType`** dal catalogo effettivo e da quello locale di riserva; togliere soltanto un `imageUrl` dalla risposta non disattiva il resolver. Rimozione e scadenze seguono i limiti già documentati sopra.
- Per la futura pubblicazione serve anche questo backend aggiornato: il vecchio backend non risolve il nuovo metadato. Nessuna pubblicazione del solo manifest è stata eseguita.

### Verifica locale e limite ancora aperto

L'API locale è stata riavviata con lo script del repository perché il processo precedente non ricaricava il codice Python. Frontend e servizi pubblicati non sono stati riavviati. `/api/live/webcams` ha restituito versione **6**, **19 voci**, sorgente locale e l'URL corrente risolto di Udine, senza esporre `snapshotResolver`.

Nell'app locale, sezione Pianura, Udine è stata selezionata correttamente ma il JPEG non si è caricato: è intervenuto il fallback, con foto territoriale **960×720** e collegamento alla fonte. Anche un successivo HEAD diretto ha terminato per timeout. La visita di controllo alla pagina originale è stata poi **bloccata dalla policy dello strumento Browser**; nessun aggiramento o accesso alternativo è stato tentato dopo quel blocco. Non si attribuisce con certezza il mancato caricamento a un guasto del sito, né si dichiara completato il collaudo visivo della ripresa. Nessuna nuova prova Android fisica.

Verifica finale: **272 test frontend** Live/liveApi/AppRoutes e **85 backend** catalogo/servizio/checker/resolver/API superati; lint frontend e `git diff --check` superati. Test di regressione coprono risoluzione, cambio del timestamp, pagina non valida/oversize/lenta, fallback, cache, richieste concorrenti, spegnimento e rimozione remota. Nessuna nuova build Web in questa fase, che non modifica il runtime frontend. Resta necessaria una prova riuscita del fotogramma nell'app prima di considerare Udine pronta per la distribuzione. L'ultimo affinamento dei timeout Python richiede un successivo riavvio del processo locale senza hot reload; non è stato forzato un ulteriore caricamento della fonte dopo il blocco Browser.
