# Audit delle 18 schede Eventi in quarantena

15 ottobre 2026. Ramo `codex/events-quarantine-recovery`.

**Audit completato su tutte le 18 schede. Nessun recupero pubblicato.**
Nove recuperi sono riusciti in una prova diagnostica con normalizzazioni
applicate soltanto in memoria; quattro schede hanno dati sufficienti ma
richiedono l'estrazione di programmi/aperture; due vanno riconciliate per
evitare duplicati; tre non vanno ripristinate con le prove disponibili.

Il numero 18 indica URL/schede in revisione, non necessariamente 18 eventi
mancanti: un programma può contenere più incontri e un vecchio URL può
riferirsi a un evento già pubblicato.

Aggiornamento successivo: [regole implementate per i nove recuperi](EVENTI_RECUPERO_QUARANTENE_REGOLE_2026-10-15.md).
Questo documento conserva gli esiti della diagnosi precedente alla correzione.

## Perimetro e metodo

- Baseline: ciclo Cloud Run `meteofriul-events-refresh-qklc5`, snapshot
  `2026-10-15T14:26:55.958729+00:00`, 14 TurismoFVG, 2 SagreFVG,
  1 CSS Udine, 1 Pordenone Pensa.
- Codice distribuito `223422e1`; base locale con verbale `a0c33be2`.
- Ramo dedicato creato dal main locale `5a68de5d`, poi allineato con
  fast-forward al backend distribuito. Main non è stato modificato.
- Tutti i 18 URL sono stati riletti via HTTPS: 15 rispondono 200,
  3 rispondono ancora 404. Letture circa 17:25–17:29 italiane.
- Confrontati motivi di quarantena, dati conservati nel checkpoint, HTML
  corrente, API SagreFVG/WordPress e sitemap TurismoFVG corrente (2.419 URL).
- Verificati anche gli organizzatori Biblioteca Austriaca e SBHU e la
  locandina della mostra di Flagogna.
- Nessuna modifica al codice runtime, API, job, catalogo cloud, scheduler,
  main, APK, AAB o Play. Nessuna installazione o push GitHub.
- Le normalizzazioni in memoria dimostrano la fattibilità sui casi esaminati:
  **non equivalgono a correzioni implementate, testate in generale e distribuite**.

## Elenco completo

| N. | Scheda e fonte ufficiale | Fonte | Perché è esclusa e cosa abbiamo trovato | Esito e intervento |
| ---: | --- | --- | --- | --- |
| 1 | [1976–2026: 50 anni dal terremoto](https://www.turismofvg.it/eventi/1976-2026-50-anni-dal-terremoto) | TurismoFVG | La descrizione ufficiale annuncia cancellazione e rinvio senza nuova data dell’incontro con Toni Capuozzo del 18 ottobre. | **Non ripristinare ora**. Esclusione corretta. Attendere una nuova data ufficiale. |
| 2 | [Campagna Amica Tour FVG](https://www.turismofvg.it/eventi/campagna-amica-tour-fvg) | TurismoFVG | Il testo dice in casodi maltempo: lo spazio mancante fa scambiare una condizione ipotetica per annullamento. Data 18 ottobre 2026, Trieste. | **Recupero diagnostico riuscito**. Normalizzare la condizione meteo; conservare il blocco per cancellazioni effettive. |
| 3 | [Ciclo autunnale Biblioteca Austriaca](https://www.turismofvg.it/eventi/ciclo-autunnale-dell-associazione-biblioteca-austriaca) | TurismoFVG | La località Udine, Sistiana contiene un Comune e una frazione. Il programma assegna date e sedi differenti. | **Recuperabile con estrazione dedicata**. Estrarre le sessioni del 20 e 27 ottobre, 11 e 18 novembre a Udine; 12 novembre Sistiana–Duino, senza associare tutte le date a entrambi i luoghi. |
| 4 | [Autunno musicale 2026](https://www.turismofvg.it/eventi/autunno-musicale-2026) | TurismoFVG | Il calendario narrativo con ore, sedi e titoli non viene riconosciuto; la pagina risponde 200. | **Recuperabile con estrazione dedicata**. Estrarre le quattro date future: 16 e 25 ottobre, 8 e 22 novembre. Le prime tre a Palazzo Tadea, l’ultima nella chiesa dei SS. Giuseppe e Pantaleone, Spilimbergo. |
| 5 | [Il segno della memoria — vecchio URL](https://www.turismofvg.it/eventi/il-segno-della-memoria) | TurismoFVG | Il dettaglio restituisce 404. Il vecchio record era associato a Tavagnacco; una scheda omonima già pubblicata è a Udine. | **Non ripristinare ora**. Non sostituire automaticamente Comuni diversi. Serve prova del ritiro o della corrispondenza; mantenere la quarantena del vecchio URL. |
| 6 | [Una Terra, una Storia — Flagogna](https://www.turismofvg.it/eventi/inaugurazione-mostra-una-terra-una-storia-504353) | TurismoFVG | Testo con ricorrenza senza anno nel campo data; la locandina ufficiale conferma inaugurazione 4 ottobre 2026. Il testo indica sabato e domenica 16:00–18:30 fino al 1 novembre. | **Recuperabile con estrazione dedicata**. Pubblicare le aperture della mostra, non l’inaugurazione già passata. Corroborare in codice periodo, anno e titolo con la prova della stessa edizione. |
| 7 | [Smarrimenti e rinvenimenti](https://www.turismofvg.it/eventi/samrrimenti-e-rinvenimenti) | TurismoFVG | Il calendario scrive Samrrimenti, il dettaglio Smarrimenti. Stessi URL, Udine e 21 ottobre; l’organizzatore SBHU conferma ore 18, Sala Tito Maniacco. | **Recupero diagnostico riuscito**. Riconciliazione circoscritta del refuso con identità, Comune e data; evitare corrispondenze approssimative indiscriminate. |
| 8 | [Friuli 1976: Voci dalla Terra — vecchio URL](https://www.turismofvg.it/eventi/stagione-teatrale-2026-2027-friuli-1976-voci-dalla-terra) | TurismoFVG | 404 anche con parametro lingua. La rappresentazione a Lignano Sabbiadoro del 29 ottobre è già pubblicata sotto friuli-1976-voci-dalla-terra, Cinecity. | **Riconciliare senza duplicare**. Riconciliare il vecchio URL come scheda sostituita con prova di identità e data; non aggiungere un secondo evento. |
| 9 | [Elena Lipizer: Latino Mediterraneo — vecchio URL](https://www.turismofvg.it/eventi/stagione-concertistica-elena-lipizer-2026-2027-latino-mediterraneo-da-bach-a-morricone) | TurismoFVG | Il vecchio URL del 6 novembre è 404. Il suffisso 506076 non è un sostituto equivalente: data 13 novembre e descrizione di Tradizione, confine, identità. | **Non ripristinare ora**. Non recuperare usando la scheda simile. Verificare il programma dell’organizzatore; annotata anche l’incoerenza titolo/descrizione della scheda 506076 già pubblicata. |
| 10 | [Digger — Teatro Pasolini](https://www.turismofvg.it/eventi/teatro-pasolini-digger) | TurismoFVG | Il calendario titola Teatro Pasolini: Digger, il dettaglio Digger. Coincidono Cervignano, sede e 25–26 ottobre. | **Recupero diagnostico riuscito**. Riconciliare il prefisso della sede solo con controlli su identità, date e Comune. Il link esterno del dettaglio punta a naza e non va usato come prova di identità. |
| 11 | [Giangiacomo Feltrinelli — Rivoluzione permanente](https://www.turismofvg.it/eventi/giangiacomo-feltrinelli-rivoluzione-permanente) | TurismoFVG | Il dettaglio mostra ottobre 2026; il calendario ufficiale contiene una sola data, 18 ottobre. Il primo controllo accetta la data, la proiezione della scheda la perde. | **Recupero diagnostico riuscito**. Conservare il giorno esatto corroborato da calendario, identità, mese e anno. Moggio Udinese, ore 18. |
| 12 | [Giro del Mondo in 80 libri — Nero come il mare](https://www.turismofvg.it/eventi/giro-del-mondo-in-80-libri-nero-come-il-mare-di-charlotta-meconaghy) | TurismoFVG | Dettaglio con solo ottobre 2026; calendario ufficiale con una sola data, 16 ottobre. | **Recupero diagnostico riuscito**. Stessa correzione della proiezione delle date: Moggio Udinese, Biblioteca Civica, ore 17:30. |
| 13 | [Il volto della Passione: la S. Sindone](https://www.turismofvg.it/eventi/il-volto-della-passione-la-s-sindone-come-specchio-del-vangelo) | TurismoFVG | Dettaglio con solo ottobre 2026; calendario ufficiale con una sola data, 17 ottobre. | **Recupero diagnostico riuscito**. Stessa correzione: Moggio Udinese, Abbazia di San Gallo, ore 20:30. |
| 14 | [Libri a merenda](https://www.turismofvg.it/eventi/libri-a-merenda) | TurismoFVG | Dettaglio con solo ottobre 2026; calendario ufficiale con una sola data, 16 ottobre. | **Recupero diagnostico riuscito**. Stessa correzione: Moggio Udinese, Biblioteca Civica presso le scuole, ore 16:15. |
| 15 | [Itinerari nel teatro contemporaneo — terza edizione](https://www.cssudine.it/stagione-contatto/2026/2940/itinerari-nel-teatro-contemporaneoterza-edizione) | CSS Udine | La testata riporta l’intero arco 9 ottobre 2026–13 aprile 2027; il corpo è un programma di cinque spettacoli e più teatri. Due spettacoli futuri sono già nel catalogo CSS. | **Riconciliare senza duplicare**. Gestire il programma e deduplicare i singoli spettacoli. Non inventare un evento continuo di sei mesi né eliminare la revisione prima della riconciliazione. |
| 16 | [ABC dell’educazione finanziaria — assicurazioni](https://www.pnpensa.it/torna-labc-delleducazione-finanziaria-cinque-appuntamenti-sulle-assicurazioni-dal-27-ottobre/) | Pordenone Pensa | Il parser ammette un appuntamento, la pagina contiene cinque incontri del 2026 con sedi diverse a Pordenone. | **Recuperabile con estrazione dedicata**. Estrarre 27 ottobre; 3, 10, 17 e 24 novembre, tutti alle 19, conservando titolo e sede di ogni incontro. |
| 17 | [51ª Sagra della Madonna della Salute](https://sagrefvg.it/sagre/san-quirino-pn-50a-sagra-della-madonna-della-salute-duplicate-1/) | SagreFVG | Il titolo API San Quirino (PN)- ... non ha lo spazio prima del trattino; il separatore non viene riconosciuto. | **Recupero diagnostico riuscito**. Accettare il separatore dopo la provincia anche senza spazio, conservando i controlli su Comune, coordinate e data 14–18 ottobre 2026. |
| 18 | [Burnjak 2026 — Festa delle Castagne](https://sagrefvg.it/sagre/tribil-superiore-ud-burnjak-2025-festa-delle-castagne-duplicate-1/) | SagreFVG | Tribil Superiore è una frazione; l’indirizzo della fonte indica Stregna UD e le coordinate della sede. L’URL conserva 2025, ma titolo, API e testo confermano 2026. | **Recupero diagnostico riuscito**. Associare la frazione al Comune verificato di Stregna, mantenendo coordinate e controlli di provincia. Data 18 ottobre 2026. |

## Prove di recupero eseguite

Lo script [verify_recovery_candidates.py](evidence/events-quarantine-audit-2026-10-15/verify_recovery_candidates.py)
usa esclusivamente le risposte salvate in `.tmp/quarantine-audit-2026-10-15/`.
Si riferisce al codice di audit `0928e7d6` e va eseguito con quella versione,
dalla radice del worktree, senza rete o scritture cloud. I test della correzione
implementata sono descritti nel verbale successivo collegato sopra.

- Campagna Amica passa dopo aver riconosciuto anche il refuso `casodi`.
  La cancellazione del caso 1 continua a produrre quarantena.
- Le quattro schede di Moggio passano usando il singolo giorno del calendario
  ufficiale, dopo verifica di mese/anno, identità e corrispondenza dei dati già
  accettati. Non si pubblica l'intero mese e non si inventano repliche.
- Smarrimenti e Digger passano dopo riconciliazione esplicita dei titoli,
  mantenendo le verifiche di Comune e calendario. È una prova sui due URL,
  non l'autorizzazione ad adottare un confronto approssimativo generale.
- Le due sagre passano normalizzando separatore e Comune della frazione,
  conservando i controlli esistenti su provincia e coordinate.
- Risultato TurismoFVG: da **1.316 a 1.323** schede nella proiezione locale;
  le 1.316 schede precedenti restano presenti. A queste si aggiungono due
  candidati SagreFVG validi: **9 recuperi diagnostici**, tutti accettati dal
  controllo individuale di pubblicazione.

Non è stato rieseguito un ciclo cloud né un intero ciclo locale delle 15
fonti; la prova usa il checkpoint del ciclo precedente e i soli 18 dettagli.
Le regressioni necessarie prima di distribuire restano da implementare.

## Programmi da estrarre

**Biblioteca Austriaca**: quattro giornate a Palazzo Antonini, Udine,
20/10 (17:45), 27/10 (17:00), 11/11 (mattina e pomeriggio in aule diverse),
18/11 (16:00–18:00). Il 12/11 è una camminata a Sistiana–Duino, 8:00–17:30.
Il [programma dell'organizzatore](https://abaudine.uniud.it/news-e-iniziative-varie/iniziative/ciclo-autunno-2026)
conferma la distinzione. Non collocare la camminata a Udine.

**Autunno musicale**: il concerto dell'11/10 è passato. Restano 16/10 20:30,
25/10 18:00 e 8/11 18:00 a Palazzo Tadea; 22/11 17:00 nella chiesa dei
SS. Giuseppe e Pantaleone. Tutti a Spilimbergo. Non attribuire la stessa sede
indiscriminatamente a tutta la rassegna.

**Una Terra, una Storia**: la locandina dichiara 4 ottobre 2026, ore 18,
per l'inaugurazione. Il dettaglio attuale dichiara le aperture sabato e
domenica, 16:00–18:30, fino al 1 novembre. Recuperare la mostra e le sue
aperture, senza riutilizzare l'orario dell'inaugurazione per le visite.

**ABC assicurazioni**: cinque incontri a Pordenone, tutti alle 19.
27/10 Spazio Zero; 3/11 e 10/11 Biblioteca Civica, sala Degan;
17/11 ex convento di San Francesco; 24/11 Biblioteca Civica, sala Degan.
Ogni sessione deve mantenere il proprio argomento e la propria sede.

## Casi in cui il recupero automatico sarebbe sbagliato

- **Capuozzo**: la fonte attuale annuncia la cancellazione e il rinvio a data
  da destinarsi. Una copia indicizzata più vecchia non riporta l'avviso:
  prevale la lettura diretta attuale, conservata nelle evidenze.
- **Il segno della memoria**: vecchio URL 404, Comune precedente Tavagnacco;
  la scheda omonima `506020` già pubblicata è a Udine. La somiglianza del
  titolo non autorizza a spostare un evento da un Comune all'altro.
- **Latino Mediterraneo**: vecchio URL 404 e giorno 6/11. La pagina `506076`
  oggi riporta 13/11 e descrive un altro concerto. Nessuna sostituzione automatica.
- **Friuli 1976**: il 29/10 a Lignano è già presente sotto
  [l'altro URL ufficiale](https://www.turismofvg.it/eventi/friuli-1976-voci-dalla-terra).
  Va risolta la revisione del vecchio indirizzo, senza aumentare il numero degli eventi.
- **Itinerari CSS**: non è uno spettacolo quotidiano dal 9/10 al 13/4.
  Il primo titolo è già passato; le tre repliche di *Mi sa che fuori è primavera*
  e *La Lettre* sono già nel catalogo CSS. Gli altri due spettacoli hanno
  dettagli propri: [Prima Facie, 12/1/2027](https://www.teatroudine.it/evento/prima-facie/)
  e [L'ultima domenica di agosto, 13/4/2027](https://www.teatroudine.it/evento/lultima-domenica-di-agosto/).
  Occorre riconciliare programma e singole rappresentazioni senza duplicare
  quelle già acquisite. Non è un recupero immediato del riepilogo come unico evento.

## Anomalia collegata emersa nell'audit

La scheda TurismoFVG `506076`, già pubblicata e quindi esterna alle 18,
ha titolo **Latino Mediterraneo – Da Bach a Morricone**, mentre la descrizione
parla di **Tradizione, confine, identità**, Quartetto K, il 13 novembre.
Anche l'API riflette questi dati della fonte. È un problema da verificare
sul programma Lipizer: non è stato corretto o dichiarato risolto qui.

## Ordine consigliato per l'implementazione

1. Le nove normalizzazioni dimostrate, con regressioni negative:
   annullamenti reali, Comuni/date discordanti, titoli non riconducibili,
   calendario privo di giorno o con giorno fuori dal mese e coordinate errate.
2. Estrattori dei quattro programmi/aperture, con controlli di completezza
   e assegnazione data–sede–orario. Usare fixture delle risposte reali.
3. Riconciliazione dei due riepiloghi/vecchi URL con eventi già presenti;
   conservare la quarantena dove la corrispondenza non è dimostrata.
4. Collaudo locale della candidata e successiva distribuzione separata.
   Non svuotare il contatore delle quarantene come obiettivo a sé stante.

## Evidenze

Nell’inventario, `sha256` identifica i byte della risposta HTTP. Nel manifest
locale identifica il file salvato in UTF-8, che può differire per codifica o
fine riga. I file grezzi restano nella directory locale ignorata indicata sopra.

- [Inventario e valutazione delle 18 schede](evidence/events-quarantine-audit-2026-10-15/inventory-assessment.json)
- [Risultato esperimenti di recupero](evidence/events-quarantine-audit-2026-10-15/recovery-experiments.json)
- [Prova della locandina](evidence/events-quarantine-audit-2026-10-15/poster-evidence.json)
- [Manifest degli HTML e dei dati locali](evidence/events-quarantine-audit-2026-10-15/local-evidence-manifest.json)
- [SHA-256 delle evidenze versionate](evidence/events-quarantine-audit-2026-10-15/SHA256SUMS.txt)
