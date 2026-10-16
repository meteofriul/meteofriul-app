# Audit fonti Webcam — 19 settembre 2026

> **Aggiornamento 2 ottobre 2026 — Monfalcone, Marina Julia:** la
> [revisione puntuale](./WEBCAM_MONFALCONE_MARINA_JULIA_REVIEW_2026-10-02.md)
> distingue le due viste comunali dalla diversa Marina Monfalcone/Panzano.
> Il catalogo v31 attiva `monfalcone-marina-julia-1` e
> `monfalcone-marina-julia-2` come snapshot diretti del Comune, nello stesso
> cluster e con fallback locale. OSMER le indicizza ma non ne ospita oggi i
> byte. Le note legali comunali consentono il riuso con fonte e dichiarano CC
> BY 4.0 predefinita salvo diversa indicazione; non e' una licenza apposta sul
> singolo JPEG ne' una concessione privata, e la fonte resta revocabile.
> `monfalcone-marina` rimane invece solo link per i termini Marina/Panomax.
>
> **Aggiornamento 2 ottobre 2026 — Spilimbergo:** la
> [revisione puntuale](./WEBCAM_SPILIMBERGO_REVIEW_2026-10-02.md) separa le due
> viste OSMER. Il catalogo v30 attiva soltanto `spilimbergo-duomo` tramite il
> mirror JPEG HTTPS; `spilimbergo-municipio` resta esclusa perche' la scena e'
> capovolta mentre overlay e loghi sono dritti e il clock e' incoerente. Il
> Duomo mantiene credito PromoTurismoFVG/OSMER, fallback e revoca. Nessuna
> licenza o autorizzazione specifica e' stata individuata.
>
> **Aggiornamento 2 ottobre 2026 — Moruzzo:** la
> [revisione puntuale](./WEBCAM_MORUZZO_REVIEW_2026-10-02.md) conferma come
> fonte proprietaria la pagina WeatherCam del Comune di Moruzzo e distingue le
> coordinate del marker webcam OSMER da quelle della stazione meteo. Il catalogo
> v29 promuove `moruzzo-panorama` dal manifest candidato e usa il mirror JPEG
> HTTPS OSMER, con credito doppio, fallback e revoca per fonte. Il mirror e'
> stato osservato con un ritardo variabile fino a circa 15 minuti rispetto
> all'upstream. E' una scelta editoriale revocabile, non un'autorizzazione al
> riuso.
>
> **Aggiornamento 2 ottobre 2026 — Piancavallo Nevelandia:** la verifica del
> [mirror statico OSMER](./WEBCAM_OSMER_STATIC_PANEL_AUDIT_2026-10-02.md) e la
> [revisione puntuale](./WEBCAM_PIANCAVALLO_NEVELANDIA_REVIEW_2026-10-02.md)
> superano il precedente limite tecnico HTTP-only. Il catalogo v28 mantiene la
> pagina proprietaria Nevelandia e usa soltanto il JPEG HTTPS raccolto da
> OSMER, con attribuzioni distinte, fallback e revoca per fonte. E' una scelta
> editoriale revocabile, non una dichiarazione di licenza.
>
> **Aggiornamento 2 ottobre 2026:** la verifica corrente di Trieste - Colle di
> San Giusto e' documentata nella [revisione del 2 ottobre](./WEBCAM_TRIESTE_SAN_GIUSTO_REVIEW_2026-10-02.md).
> Il catalogo v27 promuove la fonte dal manifest candidato a quello attivo e
> usa lo snapshot ridotto Panomax, senza player in produzione. Il player resta
> disponibile soltanto nel pilot locale mediante il gate QA gia' usato per le
> altre prove Panomax.
>
> **Aggiornamento 1 ottobre 2026:** il refresh automatico degli snapshot passa
> da 5 a 10 minuti, sempre e soltanto con anteprima visibile e app in primo
> piano. Il refresh manuale e il relativo cooldown di 12 secondi restano
> invariati. Le indicazioni successive riferite ai 5 minuti descrivono lo stato
> storico delle revisioni in cui furono rilevate.
>
> **Contratto di spegnimento remoto:** il futuro comando globale o per singola
> webcam non deve eliminare automaticamente la card. Lo stato `fallback`
> impedisce qualsiasi richiesta al contenuto remoto e mostra la fotografia
> territoriale locale indicata da `fallbackImageUrl`, mantenendo identita',
> attribuzione e collegamento alla pagina sorgente. La rimozione completa resta
> un'azione distinta ed esplicita (`hidden`). Tutte le 33 webcam del catalogo
> v31 dispongono gia' di un fallback locale.
>
> **Aggiornamento 29 settembre 2026:** la conclusione operativa su Cividale,
> l'estensione automatica del limite OSMER di 24 ore alle immagini webcam e la
> voce Udine/Piazza Matteotti sono superate dalle revisioni puntuali di
> [Cividale](./WEBCAM_CIVIDALE_REVIEW_2026-09-29.md) e
> [Udine](./WEBCAM_UDINE_REVIEW_2026-09-29.md). Anche la conclusione operativa
> su Gemona è sostituita dalla [revisione corrente della fonte
> WeatherCam](./WEBCAM_GEMONA_REVIEW_2026-09-29.md). La verifica corrente delle
> anteprime dirette e del relativo comportamento nell'app è documentata nella
> [revisione del 29 settembre](./WEBCAM_DIRECT_PREVIEWS_REVIEW_2026-09-29.md).
> La verifica corrente di Marina Monfalcone e del relativo panorama Panomax è
> documentata nella [revisione del 30 settembre](./WEBCAM_MONFALCONE_REVIEW_2026-09-30.md).
> La verifica corrente dell'anteprima di Trieste - Parco di Miramare e'
> documentata nella [revisione del 30 settembre](./WEBCAM_MIRAMARE_REVIEW_2026-09-30.md).
> La verifica corrente di Trieste - Piazza della Borsa e' documentata nella
> [revisione del 1 ottobre](./WEBCAM_TRIESTE_PIAZZA_BORSA_REVIEW_2026-10-01.md):
> la fonte resta solo link per i termini espliciti WhatsUpCams.
> La verifica corrente del panorama Monte Zoncolan e' documentata nella
> [revisione del 1 ottobre](./WEBCAM_ZONCOLAN_REVIEW_2026-10-01.md): il catalogo
> v21 usa l'anteprima aggiornata Panomax, con link, attribuzione, fallback e
> revoca per fonte; il player resta disattivato.
> La verifica corrente di Forni di Sopra - Malga Varmost e' documentata nella
> [revisione del 1 ottobre](./WEBCAM_FORNI_DI_SOPRA_REVIEW_2026-10-01.md): il
> catalogo v22 applica lo stesso modello snapshot prudenziale di Zoncolan.
> La verifica corrente di Piancavallo - Panorama e' documentata nella
> [revisione del 1 ottobre](./WEBCAM_PIANCAVALLO_REVIEW_2026-10-01.md): il
> catalogo v23 usa lo snapshot ridotto di Panomax, senza player, mantenendo
> distinta questa ripresa dalla diversa Busa del Sauc.
> La verifica corrente di Sappada - Panorama e' documentata nella
> [revisione del 1 ottobre](./WEBCAM_SAPPADA_REVIEW_2026-10-01.md): il catalogo
> v24 usa lo snapshot ridotto di Panomax, senza player, con attribuzione, link,
> fallback e revoca per fonte.
> La verifica corrente di Sella Nevea - Monte Canin e' documentata nella
> [revisione del 1 ottobre](./WEBCAM_SELLA_NEVEA_REVIEW_2026-10-01.md): il
> catalogo v25 usa lo snapshot ridotto di Panomax, senza player, e registra
> separatamente i limiti di freschezza osservati nel controllo serale.
> La verifica corrente di San Daniele del Friuli - Centro e' documentata nella
> [revisione del 1 ottobre](./WEBCAM_SAN_DANIELE_REVIEW_2026-10-01.md): il
> catalogo v26 usa lo snapshot ridotto di Panomax, senza player; la modalita'
> interattiva resta censita come opzione tecnica inattiva.
> La verifica corrente di Tarvisio - Piazza Unita' e' documentata nella
> [revisione del 1 ottobre](./WEBCAM_TARVISIO_REVIEW_2026-10-01.md): la pagina
> comunale conferma la fonte, che resta solo link per i termini WhatsUpCams.
> Il testo seguente resta come fotografia verificabile dell'audit del 19 settembre.

## Esito

Il controllo puntuale del 19 settembre 2026 porta il catalogo locale alla versione **10** con:

- **23 fonti attive**: 10 Costa, 7 Montagna e 6 Pianura;
- **6 candidate** in ombra, non pubblicate;
- **2 fonti sospese**: Aquileia e Val Saisera;
- nessun player video attivo nel catalogo: Gemona/WeatherCam usa lo snapshot ufficiale e conserva il video come opzione tecnica inattiva; alcuni HLS WUC sono tecnicamente video live ma restano bloccati dai diritti, mentre JPEG e panorami Panomax sono **anteprime aggiornate**, anche quando cambiano ogni pochi minuti;
- nessun nuovo player di terzi autorizzato automaticamente dal solo fatto di essere raggiungibile o incorporabile.

Le verifiche di freschezza sono osservazioni puntuali eseguite il 19 settembre 2026, in prevalenza tra le 17:05 e le 17:30 CEST. Non garantiscono continuità futura. La risposta HTTP, il CORS aperto, l'assenza di `X-Frame-Options` o un pulsante pubblico “Embed” dimostrano soltanto fattibilità tecnica: **non costituiscono una licenza di riutilizzo**.

Il catalogo risultante corregge tre problemi materiali:

1. la vecchia `zoncolan-baita-goles`, ferma dal 2022, è sostituita dalla diversa ripresa ufficiale `zoncolan-panorama`;
2. `piancavallo-sauc` era associata alla camera panoramica generale, non alla Busa del Sauc, ed è quindi sostituita da `piancavallo-panorama`;
3. `val-saisera`, ferma dal febbraio 2025, è sospesa e sostituita nel gruppo attivo da `piancavallo-nevelandia`, che è corrente e mantiene la propria identità.

## Lessico obbligatorio nell'app

| Etichetta | Significato | Fonti di questo audit |
| --- | --- | --- |
| **Anteprima aggiornata** | Fotogramma JPEG sostituito periodicamente o panorama composto da scatti. Non ha continuità video. | Lignano, Miramare, Udine, Cividale, Sacile, Panomax e gli snapshot WhatsUpCams. |
| **Panorama aggiornato** | Esperienza Panomax interattiva costruita da immagini successive. Non è un flusso video live. | Zoncolan, Forni/Varmost, Piancavallo, Sappada, Sella Nevea, San Daniele e San Giusto. |
| **Video in diretta** | Player con segmenti video continui, verificato come HLS o equivalente. | Nessuna fonte attiva. Il player Gemona è verificato e resta un'opzione inattiva; anche alcuni player WhatsUpCams e il player di Lignano espongono tecnicamente HLS, ma non vanno caricati nell'app finché restano i vincoli tecnici o di diritto indicati sotto. |
| **Collegamento esterno** | La card usa la foto territoriale locale e apre la pagina specifica del proprietario o della fonte. | Stato prudenziale per tutte le fonti senza permesso documentato. |

La parola generica “webcam” può restare nel nome della sezione, ma un JPEG non deve essere presentato con badge Play, “live” o “diretta”. Anche un `Last-Modified` recente prova soltanto che il file è cambiato, non che sia video.

### Regola per fonti con più formati

Quando la stessa webcam ufficiale offre sia uno snapshot sia un vero video, le
due risorse devono restare entrambe censite e verificabili. Non si elimina il
video soltanto perché lo snapshot è la scelta prudenziale corrente, e non si
perde lo snapshot quando viene selezionato il video.

L'app espone una sola modalità principale per volta: normalmente lo snapshot;
il controllo webcam può sostituirlo con il video dopo i relativi gate tecnici,
privacy e diritti. Il catalogo pubblico non deve inviare contemporaneamente
`imageUrl` e `playerUrl`. URL, fonte, data della verifica e condizioni della
modalità inattiva restano documentati, così il passaggio non richiede una nuova
ricerca della sorgente. Gemona/WeatherCam è il primo caso applicato di questa
regola.

## Vincoli comuni di diritti

- **WhatsUpCams (WUC):** le condizioni d'uso non autorizzano la ripubblicazione o il framing da parte di Meteo Friûl senza permesso scritto. Questa regola vale per JPEG, widget e HLS, inclusi Grado, Sistiana, Trieste/Borsa, Tarvisio, Gorizia, Claut, Matajur e Transalpina. Fino all'autorizzazione: solo collegamento esterno. Riferimento: [termini WhatsUpCams](https://www.whatsupcams.com/it/terms-of-use/).
- **ARPA FVG — OSMER:** il catalogo OSMER non trasferisce i diritti delle webcam gestite da terzi; le [note legali OSMER](https://www.osmer.fvg.it/note-legali.php) vietano inoltre la ripubblicazione dei dati in tempo reale prima di 24 ore salvo deroga. Il JPEG di Cividale non va distribuito come dato corrente senza una deroga applicabile a Meteo Friûl.
- **Panomax / PromoTurismoFVG:** il player pubblico e la funzione embed non equivalgono all'autorizzazione per un'app. La [distribuzione Panomax](https://www.panomax.com/en/content-distribution) per app e partner richiede approvazione; un iframe comporta anche una verifica privacy per i servizi caricati. Fino all'accordo: pagina specifica esterna; anteprima/player solo come candidato tecnico.
- **JPEG proprietari:** CORS `*`, URL pubblico e cache-busting consentono il caricamento tecnico, non assegnano una licenza. Lignano, Miramare, Udine, Sacile, Moruzzo e Cervignano richiedono attribuzione corretta e conferma del proprietario prima di considerare definitivo il riuso in produzione. Marina Julia e' distinta: il Comune pubblica le due immagini sul proprio sottodominio e le proprie note legali applicano CC BY 4.0 di default, salvo eccezioni non osservate su questa risorsa.

## Catalogo attivo — Costa (13)

| ID e ripresa | Proprietario / pagina prioritaria | Tipo e freschezza | Riuso tecnico | Stato diritti e azione consigliata |
| --- | --- | --- | --- | --- |
| `grado-al-bosco` — Grado Pineta, Isolotto Sacca dei Moreri | Il portale ufficiale del [Consorzio Grado Turismo](https://grado.it/it/scoprire-grado/webcam) pubblica direttamente il fotogramma ospitato dal Residence Hotel Al Bosco e fornito da [Kite Life FVG](https://www.kitelifefvg.it/webcam/). | PNG corrente `cam.kitelifefvg.it/webcam_grado.php`; **ultima immagine disponibile**, non video. | Il PNG HTTPS è configurato come snapshot nel manifest v10, con aggiornamento visibile ogni 5 minuti, refresh manuale e fallback locale. Non espone `Last-Modified` né CORS leggibile dal browser: l'app non mostra un orario verificato o il punto verde. | Fonte e luogo sono verificati. Il file pesa circa 4 MB: evitare refresh aggressivi, archiviazione e proxy. Conservare entrambi i crediti e **ottenere conferma per il riuso durevole prima della produzione**. La vecchia `grado-spiaggia` WUC è un'altra inquadratura e non viene riutilizzata come alias canonico. |
| `lignano-punta-faro` — Lignano, Punta Faro | Pagina del gestore [LignanoSabbiadoro.com](https://www.lignanosabbiadoro.com/webcam/webcam-spiaggia-punta-faro). | JPEG corrente `images/webcam6.jpg`; **anteprima aggiornata**. È stato individuato anche HLS, che sarebbe vero video. | Il JPEG HTTPS accetta richieste cross-origin ed è configurato nel manifest v10. Il player/HLS della pagina è limitato da `SAMEORIGIN`/CORS e non è un embed affidabile. | CORS non è licenza. Conservare attribuzione e fallback locale; **usare la dicitura “anteprima aggiornata” e ottenere conferma del gestore per il riuso durevole**. Non presentare il JPEG come live e non incorporare HLS. |
| `lignano-spiaggia-centrale` — Spiaggia centrale / Terrazza a Mare | Pagina specifica [LignanoSabbiadoro.com](https://www.lignanosabbiadoro.com/webcam/webcam-spiaggia-lignano-sabbiadoro). | JPEG `images/webcam3.jpg`, osservato aggiornato entro pochi minuti; **anteprima aggiornata**. Le viste `webcam3-1.jpg` e successive sono direzioni della stessa camera, non nuove webcam. | Snapshot HTTPS cross-origin configurato nel manifest v10. HLS escluso per `SAMEORIGIN`/CORS. | Stesso gate di Punta Faro: attribuzione visibile e **permesso del gestore prima della produzione**. |
| `lignano-piazza-fontana` — Piazza Fontana | Pagina specifica [LignanoSabbiadoro.com](https://www.lignanosabbiadoro.com/webcam/webcam-piazza-fontana-centro). | JPEG `images/webcam4.jpg`, corrente al controllo; **anteprima aggiornata**. | Snapshot HTTPS cross-origin configurato nel manifest v10; HLS non incorporato. | CORS non è licenza: conservare la fonte e **ottenere autorizzazione per il riuso durevole**. |
| `lignano-pineta-pontile` — Pineta, Pontile Pagoda | Pagina specifica [LignanoSabbiadoro.com](https://www.lignanosabbiadoro.com/webcam/webcam-spiaggia-lignano-pineta). | JPEG `images/webcam2.jpg`, corrente al controllo; **anteprima aggiornata**. | Snapshot HTTPS cross-origin configurato nel manifest v10; HLS non incorporato. | CORS non è licenza: conservare la fonte e **ottenere autorizzazione per il riuso durevole**. |
| `lignano-riviera` — spiaggia Riviera | [Indice webcam ufficiale](https://www.lignanosabbiadoro.com/webcam), che identifica la vista Riviera. | JPEG `images/webcam.jpg`, corrente al controllo; **anteprima aggiornata**. | Snapshot HTTPS cross-origin configurato nel manifest v10. Pineta e Riviera condividono la coordinata pubblicata, ma restano due inquadrature distinte nel ventaglio editoriale. | CORS non è licenza: conservare la fonte e **ottenere autorizzazione per il riuso durevole**. |
| `duino-sistiana` — Sistiana | Pagina specifica [WhatsUpCams](https://www.whatsupcams.com/it/webcams/italia/friuli-venezia-giulia-it/sistiana-it/webcam-sistiana/). | Snapshot e HLS correnti. Il JPEG è un'anteprima; HLS è tecnicamente video live. | Widget, JPEG e manifest HLS risultano raggiungibili. | **Link esterno soltanto** finché WUC non concede per iscritto framing/ripubblicazione. |
| `monfalcone-marina` — Spiaggia di Marina Monfalcone | Pagina del proprietario [Marina Monfalcone](https://marinamonfalcone.com/it/webcam/), che incorpora Panomax `cam10949`. | Panorama Panomax corrente; **panorama aggiornato**, non video live. | Player e anteprima Panomax sono tecnicamente disponibili; il sito proprietario carica l'iframe soltanto dopo consenso. | La [revisione del 30 settembre](./WEBCAM_MONFALCONE_REVIEW_2026-09-30.md) conferma il blocco autorizzativo: i termini Marina vietano la visualizzazione pubblica senza consenso scritto e Panomax richiede partner/app approvati. **Mantenere solo pagina proprietaria e fallback.** |
| `monfalcone-marina-julia-1` — Marina Julia, vista sud-est | [Pagina proprietaria del Comune](https://www.comune.monfalcone.go.it/it/novita-220905/notizie-220906/condizioni-del-vento-marina-julia-21786); il feed OSMER identifica direzione e coordinate. | JPEG comunale 1200×380 corrente, circa 83–84 KiB; timestamp, vento e coordinate impressi. | Il catalogo v31 usa il JPEG HTTPS diretto in `<img>`, senza iframe/proxy/archivio, nel cluster Marina Julia. CORS e cache esplicita assenti; `Last-Modified` coincide con la risposta PHP e non certifica lo scatto. | **Attiva come vista principale.** Le [note legali comunali](https://www.comune.monfalcone.go.it/it/note-legali-30726) consentono il riuso con fonte e indicano CC BY 4.0 predefinita, senza apporla specificamente al JPEG; l'app mostra fonte, pagina e condizioni di riuso. Mantenere frame intero, fallback e revoca. |
| `monfalcone-marina-julia-2` — Marina Julia, vista sud-ovest | Stessa [pagina comunale](https://www.comune.monfalcone.go.it/it/novita-220905/notizie-220906/condizioni-del-vento-marina-julia-21786), endpoint distinto e marker OSMER a circa 196 m dalla vista 1. | JPEG comunale 1200×380 corrente, circa 127–130 KiB; qualita' inferiore per vegetazione e controluce. | Seconda vista dello stesso cluster; viene caricata soltanto quando selezionata. Nessun player o cookie immagine. | **Attiva come vista secondaria** con la stessa attribuzione e base pubblica della vista 1; monitorare esposizione, privacy e continuita'. |
| `trieste-miramare` — Parco di Miramare | Pagina del gestore [Meteo System](https://www.meteosystem.com/stazione/trieste-miramare/webcam.php). | JPEG `https://www.meteosystem.com/webcam/miramare/parco_miramare.jpg` corrente; **anteprima aggiornata**. | Snapshot HTTPS diretto nel manifest v18, senza proxy, archivio o player; fallback locale e revoca per fonte. | Nessuna licenza pubblica specifica osservata. La [revisione del 30 settembre](./WEBCAM_MIRAMARE_REVIEW_2026-09-30.md) registra l'anteprima come scelta editoriale revocabile concordata, con attribuzione e pagina ufficiale sempre visibili; richiedere conferma al gestore per consolidarne il riuso. |
| `trieste-piazza-borsa` — Piazza della Borsa | Pagina specifica [WhatsUpCams](https://www.whatsupcams.com/it/webcams/italia/friuli-venezia-giulia-it/trieste-it/piazza-della-borsa/). | Snapshot e widget correnti al controllo del **01/10 17:05 CEST**. JPEG = anteprima; il player resta tecnicamente distinto. | Widget e JPEG raggiungibili; dettagli nella [revisione puntuale](./WEBCAM_TRIESTE_PIAZZA_BORSA_REVIEW_2026-10-01.md). | I termini WUC vietano riproduzione, visualizzazione pubblica e framing senza autorizzazione. **Link esterno soltanto** fino ad autorizzazione scritta; nessun preload del player. |
| `trieste-san-giusto` — Colle di San Giusto | [Panomax Trieste](https://trieste.panomax.com/), `cam6949`, elencata come `Trieste San Giusto` nel [catalogo ufficiale PromoTurismoFVG](https://www.turismofvg.it/it/webcam). | Entrambi i JPEG riportavano `Last-Modified` **02/10 07:10:14 CEST**, circa 48 secondi prima del controllo; **panorama aggiornato**, non video live. | Il catalogo v27 usa il JPEG ridotto `preview_og.jpg`; nessun proxy, archivio o player in produzione. Il panorama interattivo resta disponibile soltanto nel gate QA locale. Dettagli nella [revisione puntuale](./WEBCAM_TRIESTE_SAN_GIUSTO_REVIEW_2026-10-02.md). | Scelta editoriale revocabile: attribuzione e link sempre visibili, refresh moderato e fallback. La disponibilita' pubblica non costituisce licenza; autorizzazione PromoTurismoFVG/Panomax ancora da consolidare. |

## Catalogo attivo — Montagna (7)

| ID e ripresa | Proprietario / pagina prioritaria | Tipo e freschezza | Riuso tecnico | Stato diritti e azione consigliata |
| --- | --- | --- | --- | --- |
| `zoncolan-panorama` — Monte Zoncolan, quota 1.750 m | Ripresa elencata dal [catalogo ufficiale PromoTurismoFVG](https://www.turismofvg.it/it/webcam); pagina specifica [Panomax Zoncolan](https://zoncolan.panomax.com/). | Panomax `cam1988`, ultimo panorama osservato **01/10 18:28 CEST**; **panorama aggiornato**. | Il catalogo v21 usa il JPEG ridotto `preview_og.jpg`; nessun proxy, archivio o player. Dettagli nella [revisione puntuale](./WEBCAM_ZONCOLAN_REVIEW_2026-10-01.md). | Identita' attiva corretta. Scelta editoriale revocabile: attribuzione e link sempre visibili, refresh moderato e fallback. L'autorizzazione resta da consolidare con PromoTurismoFVG/Panomax. Il vecchio ID Baita Goles non deve restare alias canonico perche' era un'altra camera. |
| `tarvisio-piazza-chiesa` — Piazza Unita' / Chiesa SS. Pietro e Paolo | La [pagina webcam del Comune di Tarvisio](https://tarvisio.comune.digital/webcam) rimanda alla [ripresa WhatsUpCams](https://www.whatsupcams.com/it/webcams/italia/friuli-venezia-giulia-it/tarvisio-it/tarvisio-piazza-unita-parrocchia-sspietro-e-paolo-apostoli/). | JPEG WUC corrente, `Last-Modified` **01/10 17:06:56 CEST**; **anteprima aggiornata**. | JPEG e widget caricano tecnicamente; dettagli nella [revisione puntuale](./WEBCAM_TARVISIO_REVIEW_2026-10-01.md). | Provenienza ufficiale verificata, ma i termini WUC vietano la ripubblicazione senza autorizzazione. **Mantenere come link esterno**; anteprima/player solo con permesso scritto. |
| `forni-varmost` — Malga Varmost | [Panomax Forni di Sopra](https://fornidisopra.panomax.com/), corroborata dal [catalogo PromoTurismoFVG](https://www.turismofvg.it/it/webcam). | Panomax `cam1987`, ultimo panorama osservato **01/10 18:39 CEST**; **panorama aggiornato**. | Il catalogo v22 usa il JPEG ridotto `preview_og.jpg`; nessun proxy, archivio o player. Dettagli nella [revisione puntuale](./WEBCAM_FORNI_DI_SOPRA_REVIEW_2026-10-01.md). | Identita' verificata come Malga Varmost, non Chianeit. Scelta editoriale revocabile con attribuzione, link, refresh moderato e fallback; autorizzazione PromoTurismoFVG/Panomax ancora da consolidare. |
| `piancavallo-panorama` — Piancavallo, quota 1.625 m | [Panomax Piancavallo](https://piancavallo.panomax.com/), elencata come Piancavallo nel catalogo PromoTurismoFVG. La pagina Panomax usa anche il titolo `Sauc`, ma non coincide con la diversa Busa del Sauc `cam2448`. | Panomax `cam1981`, ultimo panorama osservato **01/10 19:29:53 CEST**; **panorama aggiornato**. | Il catalogo v23 usa il JPEG ridotto `preview_og.jpg`; nessun proxy, archivio o player. Dettagli nella [revisione puntuale](./WEBCAM_PIANCAVALLO_REVIEW_2026-10-01.md). | Identita' mantenuta come `Piancavallo - Panorama` per evitare l'omonimia. Scelta editoriale revocabile: attribuzione e link sempre visibili, refresh moderato e fallback. Autorizzazione PromoTurismoFVG/Panomax ancora da consolidare. |
| `piancavallo-nevelandia` — Nevelandia, quota 1.265 m | Pagina proprietaria [Nevelandia](https://www.nevelandia.com/webcam-piancavallo/); il [pannello OSMER](https://www.meteo.fvg.it/webcam_img.php?ln=it) identifica PromoTurismoFVG come fonte della camera. | Il mirror JPEG riportava `Last-Modified` **02/10 08:01:21 CEST**, circa cinque minuti prima del controllo; **anteprima aggiornata**, non video. | Il catalogo v28 usa il mirror HTTPS OSMER, 1280×960, mantenendo pagina proprietaria, attribuzione doppia, fallback e nessun player. Dettagli nella [revisione puntuale](./WEBCAM_PIANCAVALLO_NEVELANDIA_REVIEW_2026-10-02.md). | **Attiva come scelta editoriale revocabile.** La disponibilita' pubblica e il mirror non costituiscono licenza; autorizzazione da consolidare con proprietario/PromoTurismoFVG. |
| `sappada-panorama` — Sappada | [Panomax Sappada](https://sappada.panomax.com/), elencata nel [catalogo ufficiale PromoTurismoFVG](https://www.turismofvg.it/it/webcam). | Panomax `cam1894`, ultimo panorama osservato **01/10 19:29:14 CEST**; **panorama aggiornato**, non video. | Il catalogo v24 usa il JPEG ridotto `preview_og.jpg`; nessun proxy, archivio o player. Dettagli nella [revisione puntuale](./WEBCAM_SAPPADA_REVIEW_2026-10-01.md). | Scelta editoriale revocabile: attribuzione e link sempre visibili, refresh moderato e fallback. La disponibilita' pubblica non costituisce licenza; autorizzazione PromoTurismoFVG/Panomax ancora da consolidare. |
| `sella-nevea-canin` — Sella Nevea / Monte Canin | [Panomax Sella Nevea](https://sellanevea.panomax.com/), elencata nel [catalogo ufficiale PromoTurismoFVG](https://www.turismofvg.it/it/webcam). PromoTurismo descrive Sella Nevea nel Comune di Chiusaforte, tra Canin e Montasio. | Panomax `cam1984`, ultimo panorama osservato **01/10 19:06:39 CEST**, circa 86 minuti prima del controllo serale; **panorama periodico**, non video. | Il catalogo v25 usa il JPEG ridotto `preview_og.jpg`; nessun proxy, archivio o player. Dettagli nella [revisione puntuale](./WEBCAM_SELLA_NEVEA_REVIEW_2026-10-01.md). | Scelta editoriale revocabile: attribuzione e link sempre visibili, refresh moderato e fallback. La disponibilita' pubblica non costituisce licenza; autorizzazione PromoTurismoFVG/Panomax ancora da consolidare. Monitorare la continuita' anche in orario diurno. |

## Catalogo attivo — Pianura (riepilogo per identita')

| ID e ripresa | Proprietario / pagina prioritaria | Tipo e freschezza | Riuso tecnico | Stato diritti e azione consigliata |
| --- | --- | --- | --- | --- |
| `udine-piazza-matteotti` — Piazza Matteotti | Pagina proprietaria [Corte San Giacomo](https://cortesangiacomo.udine.it/webcam/). | La pagina dichiara una foto ogni 30 minuti; **anteprima aggiornata**, non video. Nel controllo corrente la fonte/resolver è risultata intermittente e soggetta a timeout. Windy mostra una copia corrente ma è un aggregatore, non la fonte da preferire. | Il resolver locale trova l'URL datato nella pagina, ma il collaudo resta fragile; fallback e isolamento del guasto sono necessari. | **Mantenere la pagina del proprietario e il fallback; non sostituirla con Windy.** Richiedere permesso e considerare la preview non pronta finché il caricamento reale non è stabile. |
| `cividale-piazza-duomo` — Piazza Duomo | Raccolta locale [Cividale.com](https://www.cividale.com/it/web_cam); JPEG ospitato da [ARPA FVG — OSMER](https://www.meteo.fvg.it/). | JPEG corrente al controllo; **anteprima aggiornata**, non video. | L'URL diretto funziona ed è configurato come snapshot nel manifest. | **Vincolo bloccante OSMER:** la visualizzazione real-time prima di 24 ore richiede deroga e i diritti della camera possono essere di terzi. Tenere attribuzione; prima della distribuzione corrente ottenere deroga/permesso oppure tornare a foto locale + link. |
| `gemona-centro` — Gemona centro | Pagina [WeatherCam / Meteo System](https://www.weathercam.it/webcam/gemona). | JPEG corrente `gemona.jpg`; **anteprima aggiornata**, dichiarata dalla fonte ogni 1 o 20 minuti. Il player HLS resta disponibile come opzione tecnica inattiva. | JPEG HTTPS diretto, senza CORS ma visualizzabile in `<img>`; cache esplicitamente disabilitata dal server. Player pubblico/embed disponibile ma non inviato nel record attivo. | Voce storica sostituita dalla [revisione del 29 settembre](./WEBCAM_GEMONA_REVIEW_2026-09-29.md), che registra verifica, limiti e scelta snapshot/video correnti. |
| `gorizia-piazza-vittoria` — Piazza della Vittoria | [WhatsUpCams](https://www.whatsupcams.com/it/webcams/italia/friuli-venezia-giulia-it/gorizia-it/piazza-vittoria-gorizia/); una pagina ufficiale GO!2025 propone anche un'altra inquadratura/widget WUC. | Snapshot WUC corrente; **anteprima aggiornata**. | JPEG/widget tecnicamente disponibili. La fonte GO!2025 è evidenza editoriale, non un trasferimento di licenza. | **Link esterno soltanto** fino a permesso scritto WUC. Non unire le due inquadrature sotto la stessa identità. |
| `moruzzo-panorama` — panorama verso ovest | [WeatherCam - Comune di Moruzzo](https://www.weathercam.it/webcam/moruzzo); raccolta tecnica [OSMER](https://www.meteo.fvg.it/webcam_img.php?ln=it). | JPEG 1920×1080 corrente; il mirror e' stato osservato con aggiornamento circa ogni 15 minuti, mentre l'upstream Meteo-Project era piu' frequente. | Il catalogo v29 usa il mirror HTTPS OSMER, senza player o proxy, con coordinate del marker OSMER, pagina proprietaria, fallback e revoca. Dettagli nella [revisione puntuale](./WEBCAM_MORUZZO_REVIEW_2026-10-02.md). | **Attiva come scelta editoriale revocabile.** Comune indicato come proprietario; nessuna licenza o autorizzazione per Meteo Friûl individuata. |
| `sacile` — Sacile | Pagina proprietaria [SacileMeteo](https://sacilemeteo.altervista.org/hik/webcam_hik.html), autore indicato Luigi Carbonera. | JPEG HTTPS corrente, aggiornato circa ogni 5 minuti; **anteprima aggiornata**. | `webcam_r.jpg` funziona, ma richiede cache-buster controllato per mostrare il nuovo fotogramma. È configurato come snapshot. | Il credito © Luigi Carbonera non è una licenza. **Conservare attribuzione/fallback e ottenere conferma per il riuso in produzione.** |
| `spilimbergo-duomo` — Piazza Duomo | Il [pannello OSMER](https://www.meteo.fvg.it/webcam_img.php?ln=it) indica PromoTurismoFVG; il catalogo webcam PromoTurismoFVG corrente non espone piu' Spilimbergo. | JPEG 704×576 corrente; mirror osservato circa 10–11 minuti dietro l'upstream. L'overlay non usa l'ora locale e non e' una misura affidabile di freschezza. | Il catalogo v30 usa il mirror HTTPS OSMER, senza player/proxy, con coordinate dichiarate, fallback e revoca. La vista Municipio resta fuori per rotazione e clock errati. Dettagli nella [revisione puntuale](./WEBCAM_SPILIMBERGO_REVIEW_2026-10-02.md). | **Attiva come scelta editoriale revocabile.** Nessuna licenza o autorizzazione specifica individuata; continuita' medio-bassa per origine legacy HTTP e assenza dal catalogo PromoTurismoFVG corrente. |
| `san-daniele-centro` — San Daniele del Friuli, centro | [Panomax San Daniele](https://sandanieledelfriuli.panomax.com/), `cam9495`, elencata nel [catalogo ufficiale PromoTurismoFVG](https://www.turismofvg.it/it/webcam). | Ultimo panorama osservato **01/10 19:42:33 CEST**, circa 63 minuti prima del controllo; **panorama periodico**, non video live. | Il catalogo v26 usa il JPEG ridotto `preview_og.jpg`; nessun proxy, archivio o player. Il player Panomax resta una possibilita' tecnica inattiva. Dettagli nella [revisione puntuale](./WEBCAM_SAN_DANIELE_REVIEW_2026-10-01.md). | Scelta editoriale revocabile: attribuzione e link sempre visibili, refresh moderato e fallback. La disponibilita' pubblica non costituisce licenza; autorizzazione PromoTurismoFVG/Panomax ancora da consolidare. |

## Candidate in ombra (4)

Nessuna candidata è pubblicata automaticamente. La promozione richiede identità geografica verificata, foto locale e crediti, assenza di duplicati, diritti sufficienti e aggiornamento esplicito del manifest.

| ID | Fonte proprietaria / ufficiale | Feed e freschezza | Diritti e raccomandazione |
| --- | --- | --- | --- |
| `claut-val-settimana` — Rifugio La Pussa | Il sito del Rifugio La Pussa rimanda alla [pagina WUC specifica](https://www.whatsupcams.com/it/webcams/italia/friuli-venezia-giulia-it/claut-it/val-settimana-rifugio-la-pussa/). | JPEG corrente, `Last-Modified` **19/09 15:17:53 UTC**; widget disponibile, nessun HLS stabile verificato. | Candidata valida come **link esterno**; anteprima solo con permesso WUC. |
| `savogna-matajur` — Dom na Matajure | Turismo Benečija rimanda alla [pagina WUC Matajur](https://www.whatsupcams.com/it/webcams/italia/friuli-venezia-giulia-it/savogna-sovodnje/webcam-matajur-dom-na-matajure/). | JPEG corrente, `Last-Modified` **19/09 15:16:10 UTC**; widget disponibile. | Candidata valida come **link esterno**; anteprima solo con permesso WUC. |
| `cervignano-meteo` — area urbana | Pagina proprietaria [Cervignano Meteo](https://www.cervignanometeo.org/). | Snapshot corrente e tecnicamente cross-origin; **anteprima aggiornata**. | CORS non è licenza. Promuovere come link; preview solo dopo permesso del gestore. |
| `gorizia-transalpina` — Piazza della Transalpina | L'inquadratura è corroborata da GECT GO; [pagina WUC specifica](https://www.whatsupcams.com/it/webcams/slovenia-it/goriska-it/nova-gorica-it/piazza-della-transalpina-gorizia-piazza-europa-nova-gorica/). | Feed WUC corrente; snapshot e widget tecnicamente disponibili. | Candidata valida come link esterno; framing/ripubblicazione richiedono permesso WUC. |

## Sospese e altre evidenze utili

| Fonte | Evidenza | Decisione |
| --- | --- | --- |
| `aquileia-basilica` | Pagina WUC raggiungibile, ma HLS HTTP 404, widget senza player e miniatura ferma al **17/05/2026**. | **Resta sospesa.** Ricontrollare feed e diritti prima di una promozione esplicita. |
| `val-saisera` — Radio Punto Zero | JPEG `rpzcam_lussari_2.jpg` ferma al **08/02/2025**. | **Sospesa.** Non presentare come corrente. |
| `spilimbergo-municipio` — Palazzo di Sopra | JPEG corrente ma scena capovolta di 180 gradi con overlay/loghi gia' dritti; clock quasi un'ora nel futuro al controllo del 02/10. | **Bloccata e non pubblicata.** Nessuna rotazione CSS; ricontrollare dopo correzione alla fonte. |
| Vecchia `zoncolan-baita-goles` | Snapshot WUC `it_zonc5.jpg` fermo al **31/01/2022**. | Ritirata. La nuova `zoncolan-panorama` è un'altra camera e usa un nuovo ID, non un semplice cambio di URL. |
| Busa del Sauc | Panomax reale `cam2448` (`/busadelsauc`) con ultimo panorama osservato **14/09/2026 09:30 CEST**. | Non usare per giustificare il vecchio nome Sauc. Tenere fuori dal catalogo finché non torna fresca e finché non è approvato il riuso. |
| Piani/Plan di Montasio 2 — OGS CRS | JPEG ufficiale OGS `https://www.crs.ogs.it/ipcam/pmnt2/pmnt2.jpg`, corrente **19/09 17:15 CEST**, 1920×1080; pagina con refresh ogni 3 minuti. | Buona nuova candidata, ma è **un luogo diverso da Val Saisera**. Creare un ID/nome autonomo e usare inizialmente solo il collegamento OGS; preview dopo permesso. |
| Vecchia Nevelandia del controllo di agosto | La pagina attuale [Nevelandia](https://www.nevelandia.com/webcam-piancavallo/) e il JPEG sono tornati correnti; l'origine resta HTTP-only, mentre OSMER ne espone una copia HTTPS aggiornata. | Riammessa inizialmente come solo link; il catalogo v28 usa ora il mirror OSMER verificato, con fonte proprietaria, attribuzione distinta, fallback e revoca. Nessun proxy Meteo Friûl. |

## Azioni operative ordinate

1. **Mantenere il catalogo v31 coerente con le identita' verificate:** 33 attive, 4 candidate, 2 sospese; le cinque viste di Lignano e le due viste Marina Julia condividono soltanto i rispettivi cluster editoriali; non reintrodurre gli ID `grado-spiaggia`, `zoncolan-baita-goles`, `piancavallo-sauc`, `val-saisera` o il vecchio `monfalcone-marina-julia` tra le attive.
2. **Bloccare semanticamente i falsi live:** snapshot e Panomax devono apparire come “anteprima aggiornata” o “panorama aggiornato”; nessuna fonte del catalogo attivo va proposta come “video in diretta”. Gemona può tornare video soltanto con una selezione esplicita della modalità e dopo il gate dei diritti.
3. **Applicare i gate proprietario per proprietario:** permesso scritto WUC; deroga OSMER per Cividale real-time; approvazione PromoTurismoFVG/Panomax per player/preview; conferma dei gestori per i JPEG proprietari.
4. **Preferire sempre la pagina ufficiale o del proprietario:** la pagina WUC/Panomax è secondaria quando un Comune, GIT, Marina Monfalcone, Nevelandia, Corte San Giacomo, Cividale.com, SacileMeteo o altro gestore espone una pagina specifica verificabile.
5. **Conservare fallback, attribuzione e revoca per fonte:** una preview guasta o scaduta deve degradare alla foto territoriale e al link esterno senza bloccare l'intero catalogo.
6. **Ricontrollare prima di ogni promozione o release:** freschezza del contenuto, identità della camera, HTTPS/CORS, caching, accessibilità, privacy del player, licenza/permesso e comportamento su Android reale.

## Documenti precedenti

Questo audit sostituisce, per lo stato corrente del catalogo, le conclusioni operative del [27 agosto](./WEBCAM_SOURCE_AUDIT_2026-08-27.md) e della [revisione del 30 agosto](./WEBCAM_CATALOG_REVIEW_2026-08-30.md). L'[audit del pannello video OSMER del 29 agosto](./WEBCAM_OSMER_VIDEO_AUDIT_2026-08-29.md) resta valido come inventario storico: la raggiungibilità tecnica delle fonti non equivale a un diritto di incorporamento.
