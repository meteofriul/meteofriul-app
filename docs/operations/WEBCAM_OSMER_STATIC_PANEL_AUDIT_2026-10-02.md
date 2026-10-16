# Audit del pannello webcam statico OSMER — 2 ottobre 2026

> **Aggiornamento operativo 2 ottobre 2026 — Marina Julia:** il catalogo v31
> attiva `monfalcone-marina-julia-1` e `monfalcone-marina-julia-2` come
> snapshot diretti del Comune di Monfalcone, dopo la
> [verifica puntuale](./WEBCAM_MONFALCONE_MARINA_JULIA_REVIEW_2026-10-02.md).
> OSMER oggi funge da indice: il feed punta direttamente al sottodominio
> comunale, non a un mirror. Le due viste formano un cluster separato dalla
> Marina Monfalcone/Panzano Panomax. Il catalogo corrente contiene 33 webcam,
> 28 snapshot e 5 card solo link/fallback; i record che usano copie OSMER
> restano sei.
>
> **Aggiornamento operativo 2 ottobre 2026 — Spilimbergo:** il catalogo v30
> attiva soltanto `spilimbergo-duomo`, dopo la
> [verifica puntuale](./WEBCAM_SPILIMBERGO_REVIEW_2026-10-02.md). La vista
> Municipio resta esclusa: scena capovolta con overlay gia' dritto e clock
> incoerente. Il catalogo v30 conteneva 31 webcam, 26 snapshot e 5 card
> solo link/fallback; sei record usano direttamente copie OSMER.
>
> **Aggiornamento operativo 2 ottobre 2026:** il catalogo v29 promuove anche
> `moruzzo-panorama`, dopo la [verifica puntuale](./WEBCAM_MORUZZO_REVIEW_2026-10-02.md).
> Il catalogo v29 conteneva 30 webcam, 25 snapshot e 5 card solo
> link/fallback; cinque record usano direttamente copie OSMER. La promozione
> mantiene pagina proprietaria, credito distinto, fallback e revoca per fonte.
> Non modifica le conclusioni sui diritti.

## Esito operativo

Il pannello statico [ARPA FVG - OSMER e GRN](https://www.meteo.fvg.it/webcam_img.php?ln=it)
può essere usato come **indice e alternativa tecnica per singola webcam**, non
come catalogo da importare automaticamente.

La verifica del **2 ottobre 2026, 07:42–07:49 CEST** ha rilevato:

- **194** immagini nel pannello completo;
- **129** webcam nelle nove sezioni territoriali FVG;
- **118/129** immagini territoriali replicate come JPEG HTTPS sotto
  `www.meteo.fvg.it/ext/webcams/webcams/`;
- **11/129** immagini ancora caricate direttamente dal gestore esterno;
- **103/118** mirror aggiornati da meno di 60 minuti;
- mediana dell'eta' dei mirror: circa **15,3 minuti**;
- **6** fonti territoriali chiaramente stale da giorni o mesi;
- **9** fonti oltre un'ora da ricontrollare in pieno giorno, per distinguere un
  guasto da una normale pausa notturna.

Quindi l'alternativa OSMER e' reale soprattutto quando l'origine e' ancora
HTTP, instabile o scomoda da usare in una pagina HTTPS. Il mirror non rende
pero' OSMER proprietaria delle immagini e non trasferisce automaticamente a
Meteo Friûl il permesso del gestore originario.

Questo documento e' un audit in sola lettura. Non modifica cataloghi, codice,
servizi Cloud, scheduler o app Android.

## Fonti verificate

| Risorsa | Funzione osservata |
| --- | --- |
| [Pannello statico](https://www.meteo.fvg.it/webcam_img.php?ln=it) | Elenco per zone; ogni riquadro espone origine e immagine mostrata. |
| [Mappa webcam](https://www.meteo.fvg.it/webcam.php?ln=it) | Rappresentazione geografica delle fonti. |
| [Feed JSON della mappa](https://www.meteo.fvg.it/ajax/webcamList.php) | 208 record al controllo; include 14 varianti panoramiche Panomax non presenti come riquadri distinti nel pannello statico. Non e' documentato come API pubblica con SLA. |
| [Pannello video](https://www.meteo.fvg.it/webcam_img.php?ln=it&video=on) | Risorsa distinta: player di terzi e 28 clip autostradali A23. Non e' una sostituzione neutra dei JPEG statici. |
| [Note legali](https://www.meteo.fvg.it/note-legali.php?ln=it) | Licenza generale del sito e avvertenze sui diritti di terzi. |

## Perimetro del censimento

| Sezione | Webcam |
| --- | ---: |
| Alpi Carniche | 27 |
| Alpi Giulie | 12 |
| Prealpi Carniche | 15 |
| Prealpi Giulie | 5 |
| Pianura Pordenonese | 8 |
| Pianura Udinese | 23 |
| Pianura Goriziana | 8 |
| Costa ovest e Laguna | 16 |
| Carso e Trieste | 15 |
| **Totale territoriale FVG** | **129** |

Il pannello contiene inoltre 5 immagini A4, 1 A23 e 13 A28; l'ancora SR354
oggi e' vuota. Le **19 immagini stradali** sono escluse dalla shortlist
editoriale: identita', finalita', titolarita' e continuita' sono diverse dalle
webcam territoriali dell'app. Sono presenti anche 46 voci di Veneto, Austria,
Slovenia e Croazia, fuori dal perimetro FVG corrente.

## Come funziona la copia OSMER

Nel markup di ogni riquadro:

- `data-url` indica l'URL del gestore originario;
- `data-src` indica l'immagine effettivamente mostrata dal pannello;
- per 118 webcam FVG `data-src` e' una copia HTTPS OSMER;
- il numero aggiunto in query cambia a ogni caricamento e serve da
  cache-buster; il percorso sottostante e' stabile al controllo, ma non e'
  documentato come contratto pubblico.

I 118 mirror hanno restituito `200`, `image/jpeg`, `Last-Modified` ed `ETag`.
Nei campioni controllati la richiesta condizionale con ETag ha restituito
`304`. Non sono stati osservati `Access-Control-Allow-Origin`, `Cache-Control`
o `Expires` sulle immagini.

Conseguenze per Meteo Friûl:

- un normale elemento `<img>` puo' visualizzare il JPEG cross-origin;
- il frontend non puo' affidarsi a `fetch()`, canvas o lettura di
  `Last-Modified` perche' manca CORS;
- il timestamp HTTP e' verificabile da un controllo server-side, non sempre
  dal WebView;
- il query-buster forza il trasferimento completo anche se l'immagine non e'
  cambiata;
- deve essere caricata soltanto la webcam selezionata, mai l'intero catalogo.

Per le 148 immagini FVG incluse le strade, il peso aggregato osservato era
circa 45,7 MiB; mediana circa 161 KiB, 95° percentile circa 1,39 MiB e massimo
circa 3,49 MiB. Questo conferma che un ingest o preload del pannello completo
sarebbe inutile e costoso.

## Freschezza osservata

`Last-Modified` prova quando la risorsa esposta e' cambiata; non certifica da
solo l'ora dello scatto, l'identita' della scena o una frequenza garantita.
OSMER non pubblica in questa pagina un intervallo di aggiornamento o uno SLA.

### Da non usare ora

| Webcam | Ultima modifica osservata | Esito |
| --- | --- | --- |
| Aquileia - Basilica | 17/05/2026 | Stale; coincide con la fonte gia' sospesa nel repository. |
| Monte Canin 2 | 04/06/2026 | Stale. |
| Monte Canin 1 | 02/09/2026 | Stale. |
| Trieste - Dal Colle di San Giusto, Radio Punto Zero | 18/09/2026 | Stale e diversa dalla Panomax San Giusto attiva. |
| Tarcento - Monte Bernadia 2 | 23/09/2026 | Stale. |
| Premariacco - Aviosuperficie | 29/09/2026 | Circa 68 ore; origine in errore, mirror ancora raggiungibile ma non corrente. |

### Da ricontrollare di giorno

| Webcam | Eta' approssimativa al controllo | Motivo |
| --- | ---: | --- |
| Forni di Sopra - Casera Varmost | 11 h 43 min | Possibile pausa notturna Meteomont. |
| Sappada - Rifugio Calvi | 11 h 43 min | Possibile pausa notturna Meteomont. |
| Lignano Sabbiadoro 1 | 9 h 15 min | Possibile pausa notturna. |
| Lignano Sabbiadoro 2 | 9 h 15 min | Possibile pausa notturna. |
| Lignano Riviera | 9 h 15 min | Possibile pausa notturna. |
| Barcis 2 | 6 h 17 min | Ricontrollo diurno necessario. |
| Sacile panoramica | 3 h 44 min | L'app usa gia' la fonte diretta; verificare solo come fallback. |
| Grado - Lega Navale - Sede | 84 min | Scarto limitato, ma oltre il gruppo principale. |
| Carlino | 79 min | Scarto limitato, ma oltre il gruppo principale. |

Tutte le altre copie OSMER territoriali erano entro 60 minuti al controllo.
Questo e' un esito puntuale, non un'autorizzazione o una promessa di
continuita'.

## Le 11 fonti non replicate da OSMER

| Webcam | Modalita' | Valutazione tecnica |
| --- | --- | --- |
| Monte Tenchia | JPEG diretto INOGS | Fresca; dipendenza diretta dal gestore. |
| Monte Zoufplan | JPEG diretto INOGS | Fresca; dipendenza diretta dal gestore. |
| Paularo | JPEG diretto INOGS | Fresca; dipendenza diretta dal gestore. |
| Val Pesarina - Forcella Lavardet | JPEG diretto INOGS | Fresca; dipendenza diretta dal gestore. |
| Altopiano del Montasio NNE | JPEG diretto INOGS | Fresca; dipendenza diretta dal gestore. |
| Monte Acomizza 1 | JPEG diretto INOGS | Fresca; dipendenza diretta dal gestore. |
| Monte Lussari - Panoramica | Feratel diretto | GET immagine riuscito, HEAD `405`; redirect finale HTTP osservato. Non consigliata come alternativa Web sicura. |
| Budoia - Dardago 2 | JPEG diretto del gestore | Fresca al controllo. |
| Cimolais | JPEG diretto Parco Dolomiti Friulane | Fresca al controllo. |
| Claut - Rifugio Pradut | JPEG diretto Parco Dolomiti Friulane | Fresca al controllo. |
| Cervignano del Friuli | JPEG diretto Cervignano Meteo | `200` e CORS `*`, ma nessun `Last-Modified`; path nel markup con spazio/slash anomalo. Fragile. |

Queste voci non costituiscono una vera alternativa OSMER: il pannello fa
soltanto da indice e il telefono contatta il terzo.

## Diritti e attribuzione

La pagina OSMER afferma di raggruppare immagini liberamente disponibili in
rete, ma specifica che webcam e parametri sovraimpressi **non sono gestiti
dall'Agenzia** e restano sotto la gestione dei rispettivi proprietari.

Le note legali applicano in generale la CC BY-SA 3.0 IT ai contenuti non
diversamente indicati, ma avvertono anche che diritti di terzi, diritto
all'immagine, privacy e diritti morali possono limitare il riuso. Poiche' le
webcam sono esplicitamente attribuite a proprietari terzi, la licenza generale
del sito non viene considerata in questo audit una licenza automatica dei
fotogrammi.

La clausola OSMER sulla ripubblicazione dei dati real-time prima di 24 ore e'
ambigua rispetto ai fotogrammi webcam: non va estesa automaticamente alle
immagini, ma neppure interpretata come un'autorizzazione. Il punto decisivo
resta la titolarita' dichiarata del singolo gestore.

Se viene adottata editorialmente una copia OSMER, la formula consigliata e':

> Immagine resa disponibile da **[proprietario indicato]**, raccolta nel
> pannello **ARPA FVG - OSMER e GRN**.

Devono restare accessibili sia la pagina del proprietario sia il pannello
OSMER. Non va usata la dicitura “webcam OSMER” se OSMER svolge soltanto il
ruolo di raccolta tecnica.

## Confronto con il catalogo Meteo Friûl

Il catalogo v31 contiene 33 webcam: 28 snapshot e 5 card solo link/fallback.
Sei record usano direttamente copie OSMER:

- Veduta dal campanile dell'ex Monastero Maggiore;
- Piazza Duomo;
- Piazza Paolo Diacono.
- Piancavallo - Nevelandia.
- Moruzzo - panorama verso ovest.
- Spilimbergo - Duomo.

Non esiste uno scraper OSMER nel repository. Il backend distribuisce URL
dichiarativi; il WebView carica direttamente il JPEG selezionato, con refresh
automatico ogni 10 minuti soltanto quando visibile e in primo piano. Il tasto
manuale ha cooldown di 12 secondi. Il checker locale verifica raggiungibilita'
e firma immagine, non freschezza, identita' o autorizzazione.

### Fonti gia' dirette da non sostituire senza un vantaggio concreto

Le Panomax attive, Lignano, Grado-Al Bosco, Gemona, Sacile, Miramare e CISAR
hanno gia' una sorgente diretta curata. Passare al mirror OSMER aggiungerebbe
un intermediario senza risolvere un problema corrente. Il mirror puo' essere
registrato in futuro come fallback tecnico, non come sostituzione automatica.

### Card solo link per cui il mirror risolve la tecnica ma non i diritti

| Card attiva | Copia OSMER | Esito |
| --- | --- | --- |
| Duino Aurisina - Sistiana | Fresca, HTTPS, 1280×720 | Tecnicamente collegabile; resta una fotografia WhatsUpCams. |
| Tarvisio - Piazza Chiesa | Fresca, HTTPS, 1920×1080 | Tecnicamente collegabile; resta una fotografia WhatsUpCams, anche se il Comune collega la pagina. |
| Trieste - Piazza della Borsa | Fresca, HTTPS, 1280×720 | Tecnicamente collegabile; i termini WhatsUpCams non diventano irrilevanti perche' OSMER ne conserva una copia. |
| Gorizia - Piazza della Vittoria | Nord e sud sono due viste fresche e distinte | Va scelta l'identita' corretta; entrambe restano fotografie WhatsUpCams. |

## Shortlist raccomandata

La tabella distingue fattibilita', permesso e continuita'. “Collegabile” qui
significa soltanto che il JPEG e' adatto all'architettura corrente.

| Priorita' | Localita' e identita' | Fonte originaria e URL ufficiale | Stato al controllo | Freschezza | Integrazione OSMER | HTTPS / CORS / cache | Autorizzazione nota | Stato proposto | Azione |
| ---: | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | Cividale, tre viste gia' attive | PromoTurismoFVG; [pannello OSMER](https://www.meteo.fvg.it/webcam_img.php?ln=it) | `200`, tre JPEG | 12–14 min | Mirror HTTPS gia' in uso | `<img>` si'; CORS no; ETag/LM | Nessun accordo privato dichiarato | **Attiva** | Non cambiare; aggiornare controllo/fonte in audit periodico. |
| 1 | Piancavallo - Nevelandia | [Nevelandia](https://www.nevelandia.com/webcam-piancavallo/) / Piancavallo 1265 S.C.A.R.L.; PromoTurismoFVG indicata dal pannello OSMER | `200`, 1280×960, circa 118 KiB | 5 min al controllo finale | Mirror HTTPS OSMER | `<img>` si'; CORS no; ETag/LM | Da chiarire con proprietario/PromoTurismoFVG | **Attiva nel catalogo v28** | Prima adozione proposta da questo audit, completata localmente con fonte proprietaria, credito OSMER, fallback e revoca; collaudo indicato nella revisione puntuale. |
| 2 | Moruzzo - panorama ovest | [WeatherCam - Comune di Moruzzo](https://www.weathercam.it/webcam/moruzzo) / Meteo-Project | `200`, 1920×1080, circa 730–758 KiB | Mirror osservato con ritardo variabile circa 0–15 min; upstream piu' frequente | Mirror HTTPS OSMER | `<img>` si'; CORS no; ETag/LM; nessun cookie immagine | Nessuna licenza o autorizzazione individuata | **Attiva nel catalogo v29** | Promozione completata localmente con marker OSMER dichiarato, pagina proprietaria, credito doppio, fallback e revoca; dettagli nella revisione puntuale. |
| 3 | Spilimbergo - Duomo | PromoTurismoFVG indicata dal [pannello OSMER](https://www.meteo.fvg.it/webcam_img.php?ln=it); origine legacy HTTP | `200`, 704×576, circa 46 KiB | Mirror circa 10–11 min dietro l'upstream nel campione; overlay non locale | Mirror HTTPS OSMER | `<img>` si'; CORS no; ETag/LM; nessun cookie immagine | Nessuna licenza o autorizzazione specifica individuata | **Attiva nel catalogo v30** | Promossa con nuovo ID, coordinate OSMER, credito doppio, fallback e revoca; monitorare continuita' medio-bassa. |
| 4 | Spilimbergo - Municipio | PromoTurismoFVG indicata dal pannello OSMER; origine legacy HTTP | `200`, 768×576 | Mirror fresco nel campione, ma clock sovraimpresso quasi un'ora avanti | Mirror HTTPS OSMER | `<img>` si'; CORS no; ETag/LM | Nessuna licenza o autorizzazione specifica individuata | **Bloccata** | Scena capovolta di 180 gradi con overlay/loghi dritti: non pubblicare e non ruotare lato client; ricontrollare dopo correzione alla fonte. |
| 5 | Monfalcone - Marina Julia 1 | [Comune di Monfalcone](https://www.comune.monfalcone.go.it/it/novita-220905/notizie-220906/condizioni-del-vento-marina-julia-21786) | `200`, 1200×380, circa 83–84 KiB | Timestamp impresso corrente e contenuto variabile nei campioni | JPEG HTTPS comunale diretto; OSMER e' indice | `<img>` si'; CORS no; nessun ETag/cache/cookie; `Last-Modified` non misura la cattura | [Note legali comunali](https://www.comune.monfalcone.go.it/it/note-legali-30726): riuso con fonte e CC BY 4.0 predefinita salvo eccezioni; non e' una licenza apposta sul singolo JPEG | **Attiva nel catalogo v31** | Vista sud-est principale; fonte, link alle condizioni di riuso, fallback e revoca; nessun iframe o archivio. |
| 6 | Monfalcone - Marina Julia 2 | [Comune di Monfalcone](https://www.comune.monfalcone.go.it/it/novita-220905/notizie-220906/condizioni-del-vento-marina-julia-21786) | `200`, 1200×380, circa 127–130 KiB | Timestamp impresso corrente e contenuto variabile nei campioni | JPEG HTTPS comunale diretto; OSMER e' indice | `<img>` si'; CORS no; nessun ETag/cache/cookie; `Last-Modified` non misura la cattura | Stessa base pubblica della vista 1 | **Attiva nel catalogo v31** | Seconda vista del cluster; qualita' inferiore per vegetazione/controluce ma scena valida. |
| 7 | Udine - OGS | OGS / CRS | `200` | Entro 60 min | Mirror HTTPS OSMER | `<img>` si'; CORS no; ETag/LM | Da chiarire con OGS | **Da chiarire** | Possibile seconda camera di Udine; non sostituisce la Specola Panomax. |
| 8 | Cormons - Borgnano | Borgnano Meteo | `200` | Entro 60 min | Mirror HTTPS OSMER | `<img>` si'; CORS no; ETag/LM | Da chiarire | **Da chiarire** | Copre una localita' oggi assente; audit puntuale. |
| 9 | Ronchi dei Legionari | Meteo Ronchi dei Legionari | `200` | Entro 60 min | Mirror HTTPS OSMER | `<img>` si'; CORS no; ETag/LM | Da chiarire | **Da chiarire** | Copre una localita' oggi assente; audit puntuale. |
| 10 | Trieste - Basovizza | Meteobridge / gestore non indicato chiaramente nel titolo | `200` | Entro 60 min | Mirror HTTPS OSMER | `<img>` si'; CORS no; ETag/LM | Titolare e permesso da chiarire | **Da chiarire** | Prima identificare il proprietario e una pagina fonte. |
| 11 | Trieste - Chiadino | VP44 | `200` | Entro 60 min | Mirror HTTPS OSMER | `<img>` si'; CORS no; ETag/LM | Da chiarire | **Da chiarire** | Audit puntuale prima del catalogo. |
| 12 | Cimolais | Parco Naturale Dolomiti Friulane | `200`, JPEG diretto | 0–4 min | Nessun mirror; OSMER e' solo indice | HTTPS; dipendenza diretta dal Parco | Da chiarire | **Collegabile tecnicamente** | Preferire pagina e JPEG primari del Parco; OSMER non aggiunge resilienza. |
| 13 | Claut - Rifugio Pradut | Parco Naturale Dolomiti Friulane | `200`, JPEG diretto | 0–4 min | Nessun mirror; OSMER e' solo indice | HTTPS; dipendenza diretta dal Parco | Da chiarire | **Collegabile tecnicamente** | Preferire fonte primaria; distinta dalla Pussa candidata WUC. |

Le copie fresche di Sistiana, Tarvisio, Piazza Borsa, Gorizia e delle altre
fonti WhatsUpCams non entrano nella prima tranche: migliorano la tecnica, ma
non la base di riuso. Le copie Panomax fresche restano utili come confronto o
fallback, non come sostituzione delle sorgenti dirette gia' curate.

## Inventario completo: regola di classificazione

Le 129 voci sono tutte censite nel pannello ufficiale. Per rendere verificabile
la selezione senza trasformare questo audit in un secondo catalogo non
sincronizzato, si applicano queste regole esaustive:

1. le **6 voci stale** nominate sopra sono `da rimuovere/non collegare`;
2. le **9 voci notturne** nominate sopra sono `da ricontrollare di giorno`;
3. le **11 dirette** sono classificate singolarmente nella tabella dedicata;
4. le restanti **103 copie OSMER fresche** sono `tecnicamente collegabili a un
   normale <img>`, ma `autorizzazione da chiarire` e `audit puntuale
   obbligatorio` prima di entrare nel catalogo;
5. una voce gia' presente nell'app con la stessa identita' non diventa una
   nuova webcam; il mirror e' al massimo un fallback;
6. viste diverse della stessa localita' devono condividere un cluster, non un
   ID o un nome ambiguo.

In questo modo ogni riquadro territoriale appartiene a una e una sola classe,
pur lasciando il pannello OSMER come inventario corrente di riferimento.

## Politica di refresh consigliata

Non emerge alcun motivo per buttare il lavoro gia' fatto:

- mantenere il refresh automatico corrente di **10 minuti** soltanto per la
  webcam selezionata, visibile e con app in primo piano;
- mantenere il tasto di refresh manuale e il cooldown corrente;
- non promettere all'utente uno scatto nuovo a ogni refresh: OSMER sembra
  aggiornare molti mirror attorno ai 15 minuti, ma non pubblica una cadenza;
- non precaricare immagini delle card o dell'elenco;
- in futuro, se serve ridurre banda, introdurre un intervallo per fonte senza
  cambiare l'esperienza delle webcam gia' attive.

Con un mirror OSMER il telefono contatta `meteo.fvg.it`, non il server
originario del proprietario. Nei due JPEG campione non e' stato osservato
`Set-Cookie`; l'apertura della pagina HTML OSMER puo' invece impostare una
sessione. Nessun player, iframe o script OSMER deve essere incorporato per la
sola anteprima.

## Video

Il pannello video territoriale contiene HLS e iframe di WhatsUpCams, SVBG,
RTSP.me e IPCamLive; alcuni player impostano cookie. Sono presenti inoltre 28
MP4 A23. La disponibilita' tecnica non riduce i problemi di diritti, privacy,
banda e continuita'. Il video resta quindi un'opzione separata e attivabile
soltanto dopo un audit specifico; non va usato come fallback automatico del
JPEG.

## Ordine proposto

1. **Piancavallo - Nevelandia**: alternativa OSMER adottata localmente;
   risolve il problema HTTPS concreto sulla card gia' presente.
2. **Moruzzo**: candidata promossa localmente nel catalogo v29; monitorare il
   ritardo del mirror e consolidare il permesso del proprietario.
3. **Spilimbergo**: Duomo promosso localmente nel catalogo v30; Municipio
   bloccato fino alla correzione alla fonte di rotazione e orologio.
4. **Monfalcone Marina Julia 1/2**: entrambe promosse localmente nel catalogo
   v31 come cluster comunale diretto; mantenere distinta Marina Monfalcone e
   monitorare qualita', privacy e continuita'.
5. **Nuove coperture**: Udine OGS, Cormons, Ronchi, Basovizza e Chiadino, una
   per volta.
6. Solo dopo una decisione esplicita sui diritti, rivalutare i mirror delle
   card WhatsUpCams oggi solo link.

Per ogni promozione restano necessari: nome e coordinate coerenti, pagina
fonte, proprietario, attribuzione doppia quando si usa il mirror, fallback
locale, spegnimento per singola fonte, test automatici, prova Web e prova
Android reale di foreground/background. Nessun deploy o build Android e'
necessario per questo audit.
