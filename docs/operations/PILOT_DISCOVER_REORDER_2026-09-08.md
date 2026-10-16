# Pilota: Home e primo riordino di Scopri — 8 settembre 2026

## Perimetro

Primo passaggio della proposta `sistemare scopri.DOCX`, dopo la correzione
prioritaria annotata sulla Home. Modifiche abilitate solo da
`isLocalWeatherPilot()`. Nessun deploy, nuova APK, modifica cloud, Firebase,
scheduler o installazione della beta.

## Modifiche

- Home: rimossa la fascia duplicata dei dati locali, conservando hero,
  bollettino/allerta e quattro scorciatoie. Commit separato `44aea1e`.
- Scopri: calendario/santo e memorie secondarie sempre visibili nella pilota.
  Solo il testo lungo degli altri santi conserva il pulsante di espansione.
- Un solo detto quotidiano in “Si diceva che…”: selezione Discover prioritaria,
  proverbio già selezionato dall'Almanacco come ripiego, mai entrambi.
- “Tradizioni del Friûl” riunisce riti, archivio e tradizione dell'Almanacco,
  mantenendo distinti i contenuti originali, le fonti e i metadati temporali.
- Deduplica tramite identità editoriale (`contentKey`/ID), anche tra riassunto
  breve e testo completo; confronto testuale esatto normalizzato quando
  significativo. Nessuna equivalenza dedotta dal solo tema o da titoli generici.
- Consigli della terra in una sola lista compatta, senza falsa attribuzione
  a una fonte storica. Nessuna modifica ai cataloghi o ai selettori condivisi.

## Verifiche

- 161 test superati in 12 file: Home, Scopri, composizione giornaliera,
  integrazione editoriale meteo e modello Almanacco. Inclusi IT/FUR, identità
  duplicate, input immutabili, casi vuoti, santi del 7 settembre e memoria
  secondaria di Trieste del 1 gennaio; conservati i gruppi e accordion legacy.
- Build Vite di produzione riuscita in una directory temporanea del sistema;
  restano i warning di dimensione bundle/import dinamico già noti.
- ESLint sui file JavaScript/JSX modificati: zero errori; warning preesistente
  Fast Refresh sull'helper esportato `calendarWithoutExternalProfiles`.
- Browser locale: Home senza fascia, Scopri IT/FUR con gruppi aperti,
  fonti e consiglio pratico leggibili; scorciatoia Home “Memoria del giorno”
  verificata fino al focus sulla scheda corretta. Lingua ripristinata in IT.

## Passaggio successivo

Al termine del primo riordino, “I perché del Friûl” era ancora da implementare
e la scorciatoia Calendario era invariata. Il primo inserimento è documentato
più sotto; resta da preparare un catalogo per una vera rotazione quotidiana.

## Secondo passaggio: gerarchia editoriale

Applicata la prima parte visuale della proposta incollata, dopo approvazione:

- Wrapper e renderer editoriali esclusivi della pilota; markup della beta,
  cataloghi e selettori condivisi invariati.
- Memorie senza riquadro-icona, data prima della categoria, titolo distinto dal
  corpo e fonte discreta. La categoria originale `musica` viene presentata come
  “Musica” / “Musiche”, senza cambiare il modello utilizzato dalla Home.
- Proverbi in forma di citazione, senza categoria ridondante. I detti con titolo
  tematico e commento restano titoli e paragrafi: non vengono spacciati per
  citazioni letterali e non si importano nuove trascrizioni storiche.
- Tradizioni con accenti derivati dal tipo: oro, verde, azzurro o neutro.
  Altezza determinata dal contenuto, senza altezze fisse o nuovi troncamenti.
- Consiglio della terra con bordo verde e germoglio in linea; lista semantica
  conservata anche senza pallini. Calendario con icona più compatta.
- Card bianche in tema chiaro, superfici scure coerenti nel tema scuro.
  Testi e fonti completi, nessuna freccia o interazione fittizia.
- Foto del Comune, timeline, approfondimenti e “I perché” non modificati in
  questo passaggio. Nessuna APK generata, nessun deploy o intervento cloud.

### Verifica del secondo passaggio

- 179/179 test in 13 file, inclusi i due formati reali dei proverbi,
  San Macario IT/FUR, fonte con nota FUR in revisione, gruppi e ancore.
- ESLint sui quattro JSX: zero errori, solo il warning Fast Refresh già noto.
- Build Web di produzione riuscita con configurazione nativa e output in una
  directory temporanea di sistema; warning di bundle/import dinamico invariati.
  Il tentativo `build --mode local-pilot` è stato rifiutato dalla protezione
  esistente: quella modalità ammette solo il server di sviluppo. Nessuna
  protezione aggirata; non è una verifica della compilazione Android.
- Anteprima locale verificata in IT e FUR, tema chiaro e scuro, larghezze
  390 e 320 px: nessun overflow delle nuove card né della pagina. Fonti e testi
  rimangono leggibili; dimensioni browser, lingua IT e tema chiaro ripristinati.
- Scorciatoia Home → Glauco Venier verificata fino al focus sull'ancora originale
  della memoria in Scopri. Nessun errore console rilevato durante la verifica.

### Rifiniture puntuali successive

- Solo CSS sotto il wrapper editoriale della pilota: virgoletta serif arrotondata
  al 38% di opacità e proverbio corsivo; nessun nuovo asset o cambiamento ai testi.
- Terra conserva il raggio di 10 px e il bordo verde di 4 px; `overflow: hidden`
  e `background-clip: padding-box` evitano sporgenze e aloni bianchi sul raccordo.
- Spazio prima della rubrica da 24 a 29 px, titolo–card da 8 a 6 px. Intervalli
  tra card e tra tradizioni e Terra invariati; calendario escluso dal ritocco.
- 42/42 test mirati (renderer, DiscoverView, ordine CSS), build Web riuscita;
  misure DOM e controllo visivo chiaro/scuro, anche a 390 px. Tema e viewport
  ripristinati. Beta, cloud e APK non modificati.

## Primo inserimento di “I perché del Friûl”

Recepita l'ultima indicazione dell'utente: testata Home coerente con le altre
tre tessere, con bussola a contorno nel riquadro soft, titolo e freccetta.
Il corpo è allineato a sinistra: domanda e CTA “Scopri →”, senza data, santo,
micro-tag duplicato o anticipazione della risposta. Nessuna immagine aggiunta.

- Solo la pilota sostituisce la quarta tessera; la beta mantiene l'Almanacco.
- Primo contenuto: “Perché Palmanova ha la forma di una stella?”. Risposta
  completa in Scopri, dopo il Santo e prima della località, con fonti del Comune:
  https://www.visitpalmanova.it/passeggiata-nel-parco-dei-bastioni/ e
  https://www.visitpalmanova.it/bastione-garzoni/ .
- Domanda, risposta e fonti sono in un unico record locale e vengono lette
  dallo stesso presenter, con l'ancora `discover-card-why-palmanova-star`.
  Nessun download, timer, aggiornamento meteo o scelta casuale aggiunti.
- È un primo record statico, non un catalogo quotidiano: non si simula il cambio
  di domanda ogni giorno. Una futura rotazione richiederà più record verificati
  e la conservazione dell'ID cliccato anche durante un cambio di giornata.
- Versione IT/FUR; terminologia e forma interrogativa confrontate con il quaderno
  ARLeF https://arlef.it/app/uploads/materiali/pianura-e-costa-friulane-quaderno.pdf
  (pp.58 e87). Revisione assistita, non dichiarata certificazione umana.
- Domanda senza troncamenti; CTA omessa se manca il gestore di navigazione.
  Un contenuto incompleto o privo di fonti non sostituisce il Calendario.
- 204/204 test in17 file, inclusi Home/Scopri, contenuto incompleto, identità
  tra lingue e oltre mezzanotte, callback di navigazione e isolamento beta.
- Build Web in directory temporanea riuscita; lint senza errori, unico warning
  Fast Refresh già noto. Nessuna compilazione/installazione Android.
- Browser: tap reale IT/FUR verificato fino al focus sulla risposta corretta;
  3 righe di domanda a larghezza standard e390px, nessun overflow, griglia2x2
  mantenuta (tessera184px standard/189px nel caso mobile verificato).
  Controllati Home e risposta nel tema scuro; nessun errore console rilevato.
  Lingua IT, tema chiaro e viewport iniziale ripristinati.
- Nessun deploy, modifica cloud, Firebase, beta, sito o altra frequenza.

### Home: testata editoriale essenziale (indicazione successiva)

- La successiva scelta dell'utente elimina la bussola e la freccetta superiore
  solo dalla tessera “I perché”. Rubrica in maiuscolo, 12 px, oro scuro nel tema
  chiaro; resta una sola CTA “Scopri →” in basso. Domanda e risposta invariati.
- `decoratedHeader` resta attivo per default: altre tre tessere e Almanacco
  della beta conservano icone e frecce. Nessuna modifica a Scopri o ai contenuti.
- 61/61 test mirati, lint senza errori/warning e build Web riuscita. Nel browser
  verificati assenza di icona/freccia superiore, una CTA, nessun overflow e
  altezza standard invariata a 184 px. Nessuna nuova APK.

### Scopri: risposta narrativa e fonti compatte

- Apertura autonoma in grassetto: “Per difendersi.” / “Par difindisi.”, seguita
  dalla spiegazione narrativa completa. Domanda e linea oro conservate.
- Una sola fonte primaria cliccabile nel footer, preceduta da “Fonti” / “Fonts”;
  entrambi i riferimenti del Comune rimangono nel record per tracciabilità.
  Il testo cita numero e dimensioni dei bastioni, supportati dalla fonte,
  senza aggiungere il riferimento alla distanza proposto nell'esempio.
- Sequenza Santo → I perché → località → hero comunale invariata; nessuna
  modifica alla tessera Home, alla CTA o all'ancora della risposta.
- 63/63 test mirati, lint e diffcheck puliti; build Web nativa riuscita in una
  directory temporanea di sistema, con i soli warning già noti.
- Browser: tap dalla Home fino all'ancora, lead su riga propria, singola fonte,
  IT/FUR, tema chiaro/scuro e larghezza 390 px verificati senza overflow.
  Nessun errore console; lingua, tema e viewport iniziali ripristinati.
- Nessuna APK, deploy o modifica a beta, Firebase, cloud o frequenze.

### Home: ultimo ritocco a spazio e CTA

- Solo la tessera “I perché”: distanza rubrica–domanda da 10 a 15 px;
  CTA sempre oro e 12 px, peso ridotto da 750 a 600. Nessun altro cambiamento.
- 34/34 test mirati superati e diffcheck pulito; browser a 541 e 390 px senza
  overflow, altezza standard conservata a 184 px. Viewport ripristinato.

### Home: Memoria del giorno come mini-articolo

- Solo nella pilota, intestazione piccola in blu senza icona o freccetta;
  data · categoria discreta, titolo completo da 17 px, estratto limitato via
  CSS a due righe e una sola CTA “Leggi →” / “Lei →” in basso.
- I campi già presenti `type`, `typeLabel`, `seasonLabel` arrivano al renderer:
  `musica` è mostrato come Musica/Musiche, coerentemente con Scopri. Il vecchio
  `metaLabel` resta invariato per la beta; nessuna categoria dedotta dal testo.
- Titolo, testo integrale, record selezionato, ancora e azione non cambiano.
  Il nome accessibile della CTA include “Leggi” / “Lei” come l'invito visibile,
  per riconoscerla anche con lettore di schermo e controllo vocale.
  Niente nuove linee decorative; stessi padding e superficie della griglia.
  Nessuna modifica alla tessera “I perché”, salvo il naturale allineamento
  in altezza della coppia al mini-articolo (circa 212 px nel caso verificato).
- 98/98 test mirati su cinque file, lint senza errori e build Web nativa riuscita
  in directory temporanea; soli warning di bundle/import già noti.
- Browser IT/FUR a 541/390 px, chiaro/scuro: nessun overflow, estratto di due
  righe, CTA leggibile. Tap reale IT verificato fino all'ancora di Glauco Venier
  in Scopri. Nessun errore console; lingua, tema e viewport ripristinati.
- Nessuna APK, deploy o modifica a Firebase, servizi cloud o beta pubblicata.
