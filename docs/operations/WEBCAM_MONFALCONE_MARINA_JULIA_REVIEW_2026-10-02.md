# Webcam Monfalcone - Marina Julia — verifica 2 ottobre 2026

## Decisione operativa

Le due viste comunali `monfalcone-marina-julia-1` e
`monfalcone-marina-julia-2` sono tecnicamente idonee come snapshot e vengono
attivate nel catalogo v31 come un unico cluster editoriale **Monfalcone ·
Marina Julia**. La vista sud-est e' la prima; la sud-ovest e' la seconda.

La webcam gia' presente `monfalcone-marina` non viene sostituita: identifica
la diversa Marina Monfalcone/Panzano Panomax e resta solo collegamento con
fallback. Il vecchio ID Protezione Civile `9` e l'ID storico non suffissato
`monfalcone-marina-julia` non vengono riutilizzati.

## Tabella di verifica

| Campo | Marina Julia 1 | Marina Julia 2 |
| --- | --- | --- |
| Localita' e identita' | Monfalcone, Marina Julia, vista sud-est | Monfalcone, Marina Julia, vista sud-ovest |
| Coordinate OSMER | `45.77413, 13.52914` | `45.77274, 13.52759` |
| Sorgente ufficiale | [Comune di Monfalcone — Condizioni del vento, Marina Julia](https://www.comune.monfalcone.go.it/it/novita-220905/notizie-220906/condizioni-del-vento-marina-julia-21786) | Stessa pagina comunale |
| URL immagine | [`monfalcone-cam-marinaJulia1.php`](https://anemometro.comune.monfalcone.go.it/monfalcone-cam-marinaJulia1.php) | [`monfalcone-cam-marinaJulia2.php`](https://anemometro.comune.monfalcone.go.it/monfalcone-cam-marinaJulia2.php) |
| Stato corrente | `200 image/jpeg`, 1200×380, circa 83–84 KiB | `200 image/jpeg`, 1200×380, circa 127–130 KiB |
| Ultima verifica | 02/10/2026, 09:21–09:55 CEST | 02/10/2026, 09:21–09:55 CEST |
| Freschezza osservata | Timestamp sovraimpresso corrente; campioni successivi diversi | Timestamp sovraimpresso corrente; campioni successivi diversi |
| Modalita' tecnica | `<img>` HTTPS diretto, cache-buster applicativo, nessun iframe/player/proxy | Stessa modalita' |
| HTTPS / CORS / cache | HTTPS; nessun ACAO, ETag, `Cache-Control`, `Expires` o cookie immagine osservato | Stessi header |
| Attribuzione | Fonte `Comune di Monfalcone`, pagina proprietaria e collegamento visibile alle note legali | Stessa attribuzione |
| Licenza o permesso noto | [Note legali comunali](https://www.comune.monfalcone.go.it/it/note-legali-30726): riuso con fonte e CC BY 4.0 predefinita salvo diversa indicazione o contenuti di terzi; non e' una dichiarazione di licenza specifica del singolo JPEG | Stessa base pubblica e stessa cautela |
| Stato | **Attiva — vista principale** | **Attiva — vista secondaria** |
| Motivo e azione | Panorama marino utile; mantenere frame intero, fallback e revoca | Vista distinta ma piu' debole per vegetazione e controluce; mantenere come seconda scelta |

## Fattibilita' tecnica

Il [feed OSMER](https://www.meteo.fvg.it/ajax/webcamList.php) identifica le
due viste, le direzioni e le coordinate, ma oggi non ne ospita una copia: sia
`url` sia `local_url` puntano direttamente al sottodominio del Comune. OSMER
e' quindi indice e corroborazione tecnica, non il fornitore dei byte.

La pagina comunale incorpora `https://anemometro.comune.monfalcone.go.it/`;
il pannello tecnico contiene esattamente i due JPEG e li ricarica ogni otto
secondi. Meteo Friûl non incorpora quel pannello: carica solo lo snapshot
selezionato. Restano il refresh automatico comune di 10 minuti, soltanto con
anteprima visibile e app in primo piano, e il tasto manuale con cooldown di 12
secondi.

`Last-Modified` coincide con l'ora della risposta PHP e cambia a ogni
richiesta: non viene interpretato come ora certificata dello scatto. La
freschezza e' attestata nel campione dal timestamp impresso nel fotogramma e
dal cambiamento del contenuto tra richieste successive. Non esiste uno SLA
pubblico.

L'assenza di CORS impedisce `fetch`, canvas e lettura degli header dal
frontend, ma non il normale caricamento in `<img>`. Non sono necessari
updater, cache o proxy di Meteo Friûl.

Durante il collaudo la vista 2 ha impiegato piu' volte fra circa 6,2 e 8,4
secondi a completare il JPEG; con una richiesta `HEAD` concorrente il GET ha
raggiunto circa 10,1 secondi. Il precedente limite frontend di 6,5 secondi
scambiava quindi una sorgente lenta ma valida per una sorgente guasta e
passava prematuramente al fallback. Soltanto il limite degli snapshot live e'
stato portato a 15 secondi; immagini non-snapshot e fallback conservano 6,5
secondi. Inoltre il controllo metadata `HEAD` ora parte soltanto dopo l'evento
`load` del JPEG, quindi non compete piu' con l'immagine sul percorso critico.
Non sono stati introdotti proxy, eccezioni specifiche per Monfalcone o retry
aggressivi.

## Autorizzazione e attribuzione

Le [note legali del Comune](https://www.comune.monfalcone.go.it/it/note-legali-30726)
consentono la riproduzione e l'impiego di informazioni testuali e
multimediali con indicazione della fonte e dichiarano CC BY 4.0 come licenza
predefinita, salvo contenuti diversamente specificati o incorporati da terzi.
La pagina webcam parla del “nostro rilevatore”, l'host e' un sottodominio
comunale e non e' stata trovata una diversa titolarita' o restrizione sulla
risorsa.

Questa e' una base pubblica di riuso ragionevolmente forte, distinta da un
accordo privato e da una dichiarazione di licenza apposta specificamente sui
due JPEG. Non viene estesa a Panomax, a OSMER o ad altre webcam. Nell'app sono
visibili sia la fonte e la pagina proprietaria sia `CC BY 4.0 predefinita`,
collegata alle note legali comunali. Si mantengono fallback e futura revoca per
singola fonte.

## Qualita', privacy e banda

- La vista 1 mostra mare, spiaggia, frangiflutti, dati del vento e coordinate;
  e' la vista predefinita.
- La vista 2 mostra parco e litorale; e' valida ma parzialmente coperta dalla
  vegetazione e piu' esposta al controluce.
- Nei campioni non risultano volti o targhe leggibili. La scena resta uno
  spazio pubblico: niente zoom, riconoscimento, archivio o timelapse.
- I JPEG non hanno impostato cookie. La pagina HTML comunale gestisce il
  consenso cookie, ma non viene incorporata nell'anteprima.
- Il rapporto 1200×380 va conservato senza ritagliare timestamp, stemma e dati
  anemometrici. Si scarica soltanto la vista selezionata.

## Identita' distinte da non unire

La Panomax `cam10949`, descritta come spiaggia di Marina Monfalcone/Panzano,
e' geograficamente e contrattualmente diversa. I termini di Marina Monfalcone
e Panomax non autorizzano la visualizzazione pubblica senza consenso: il
record `monfalcone-marina` resta link/fallback e non entra nel cluster Marina
Julia.

La vecchia API Protezione Civile espone ancora i metadati dell'ID `9`, ma la
camera e' `status: N` e l'elenco immagini e' vuoto. Quelle coordinate e
quell'identita' non vengono riciclate.

## Fallback e revoca

Entrambe le viste usano
`/municipalities/photos/031012-photo.webp`. Il futuro interruttore remoto deve
poter passare ogni vista o l'intero cluster a `fallback`, evitando ogni
richiesta ai JPEG comunali ma mantenendo identita', credito e link. `hidden`
resta una decisione separata.

## Collaudo eseguito

Il 2 ottobre 2026 il pilot canonico avviato esclusivamente con
`scripts/start-local-weather-pilot.ps1` e
`-WeatherTestNow 2026-09-04T12:00:00Z` sulla porta `5174` ha confermato:

- catalogo v31 con 33 webcam attive, 28 snapshot e 5 card link/fallback;
- cluster `1 di 2` / `2 di 2`, distinto dalla Marina Monfalcone/Panzano;
- entrambe le viste caricate dalla sorgente live a 1200×380 senza fallback;
- titoli, localita', attribuzione e collegamento alla pagina comunale corretti;
- nessun iframe o video;
- refresh manuale della vista 2: nuovo `mf_snapshot`, comando disabilitato
  durante il caricamento e ritorno allo stato `loaded` senza fallback;
- refresh manuale della vista 2 su rete mobile: nuovo `mf_snapshot`, JPEG
  1200x380 completato in circa 5,6 secondi e Wi-Fi ripristinato al termine;
- regressioni automatiche che mantengono lo snapshot in caricamento oltre i
  vecchi 6,5 secondi, accettano un `load` valido a 9 secondi e usano il
  fallback soltanto allo scadere dei 15 secondi se l'immagine non arriva;
  il fallback e le immagini non-snapshot mantengono il limite di 6,5 secondi;
- collaudo sul telefono reale Samsung SM-A525F con Brave: vista `2 di 2`
  lasciata in background per 631 secondi, nessuna richiesta webcam e nessuna
  navigazione documento durante il periodo nascosto;
- alla ripresa, stesso `performance.timeOrigin`, pannello, tab e indice
  conservati; un solo nuovo ciclo di aggiornamento ha caricato il JPEG
  1200x380 e, dopo il suo `load`, ha eseguito la richiesta `HEAD` gia'
  prevista per leggere `Last-Modified`; non si e' verificato un reload
  dell'app;
- suite webcam backend e frontend, manifest, lint e controllo diff eseguiti
  localmente.

Il precedente reload osservato con il server Vite di sviluppo era prodotto
dal client HMR che ricarica la pagina dopo una lunga disconnessione, non dal
ciclo webcam. Per separare il comportamento dell'app da quello dello
strumento di sviluppo, il launcher canonico dispone ora dell'opzione locale
`-StableFrontend`: genera una build statica in una directory temporanea
verificata, mantiene le sole semantiche del pilot locale e la serve sulla
porta prescritta `5174` senza HMR. L'opzione e' riservata al collaudo, non
modifica il prodotto distribuito e non abilita Firebase o Web Push di
produzione.

Nessun deploy, intervento Cloud, build Android o modifica a scheduler e'
parte di questa revisione.
