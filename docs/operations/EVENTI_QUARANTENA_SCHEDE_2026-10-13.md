# Eventi: schede in quarantena e stato del ramo

Data: 13 ottobre 2026. Ramo: `codex/events-card-quarantine`.

Aggiornamento del ramo: la separazione degli allarmi per Palazzo Attems e
GiroFVG è stata collaudata in un'esecuzione cloud isolata. Il funzionamento
completo e i passaggi ancora necessari sono nel
[resoconto dei job Eventi](EVENTI_ARCHITETTURA_JOB_E_ALLARMI_2026-10-13.md).
La policy dedicata è stata creata e riletta online il 13 ottobre; il job
schedulato resta sull'immagine precedente. Il gate generico mette inoltre in
quarantena una sola scheda inattesa riconoscibile se restano altre schede
valide.

## Regola implementata

Un inventario verificato può essere pubblicato come `partial`: le schede
con URL e motivo di revisione sono escluse, mentre quelle verificate restano
visibili. Errori di paginazione, sitemap, API, identità o inventario continuano
a rendere la fonte `stale` e a far fallire il job. Il catalogo conserva la
diagnostica delle schede escluse. Il controllo generico di pubblicazione
continua a fermare anomalie che l'estrattore non ha classificato per scheda.

| Fonte | Gestione attuale delle schede dubbie |
| --- | --- |
| TurismoFVG | Quarantena delle singole pagine dopo inventario calendario e sitemap verificato |
| Pordenone Pensa | Quarantena dei singoli articoli o pagine dopo confronto API e sitemap |
| Pordenonelegge | Quarantena dei singoli appuntamenti; edizione passata chiusa solo con prova precedente e reindirizzamento ufficiale |
| Teatro Verdi Pordenone | Quarantena dei singoli spettacoli dopo confronto stagione e sitemap |
| Teatro Verdi Trieste | Quarantena dei singoli spettacoli dopo confronto stagione e calendario |
| CSS Udine | Quarantena dei singoli spettacoli dopo lettura degli indici di stagione |
| Azalea | Quarantena delle singole pagine dopo lettura dell'archivio e controllo sitemap |
| SagreFVG | Quarantena delle singole righe API con date non valide; finestre annuali complete obbligatorie |
| Villa Manin | Quarantena delle singole schede; inventario API, calendario e archivio annuale obbligatorio |
| Magazzino delle Idee | Quarantena delle singole schede; inventario API, sitemap e liste pubbliche obbligatorio |
| Le Giornate del Cinema Muto | Quarantena delle singole voci del calendario; giorni e widget completi obbligatori |
| Paesi in Festa | Quarantena per scheda già presente prima di questo ramo |
| MESS | Quarantena per singola voce del programma 2026 o singola mostra; totale delle 36 posizioni, mappa dei 18 musei e inventario notizie obbligatori |
| Galleria Spazzapan | Quarantena per dettaglio o data discordante sulle quattro schede note; inventari API incrociati obbligatori |
| Barcolana | Una sola scheda aggregata: un programma non verificabile invalida l'intera fonte |

La proposta iniziale di rendere silenziose le variazioni degli inventari
monitorati di Palazzo Attems e GiroFVG è stata respinta: avrebbe nascosto le
novità. Il ramo ora prepara un **allarme separato** per i due monitor e li
toglie dal risultato del job soltanto dopo avere installato la policy email;
questa è ora installata, ma la notifica con un log reale resta da collaudare.
Resta bloccante
il caso in cui Villa Manin o Magazzino non producano alcuna scheda verificata
pur mostrando eventi attivi.

## Controlli eseguiti

- Test locali Eventi: 753 passati, 2 saltati, 185 subtest passati.
- L'esecuzione programmata del 13 ottobre (`meteofriul-events-refresh-lhmv4`)
  ha fallito con quattro fonti; l'esecuzione del 12 ottobre era riuscita.
  La diagnostica persistita nel catalogo attribuisce i fallimenti a:
  TurismoFVG (`incomplete_source`, tre pagine da rivedere), Pordenone Pensa
  (`source_verification_failed`, una pagina con una data futura aggiuntiva),
  Pordenonelegge (`unexpected programme response`, il programma ora rinvia
  alla home) e Teatro Verdi Pordenone (`timeout`). Questi sono dati del job
  online ancora in produzione, non della PR.
- TurismoFVG, scansione reale in sola lettura: 1.151 schede, 3 URL in
  quarantena, gate `partial`, 322,4 secondi su 360 consentiti.
- Pordenone Pensa, lettura reale: un articolo con date ulteriori in
  quarantena, gate `partial`, zero altre schede future verificate.
- Pordenonelegge: risposta ufficiale HTTP 302 verso la home; usando la prova
  dell'edizione terminata il gate accetta un catalogo vuoto.
- CSS Udine: 157 schede, zero revisioni, gate `ok`.
- Teatro Verdi Pordenone: 88 schede, zero revisioni, gate `ok`, 31,8 secondi
  sul limite proposto di 60.
- Galleria Spazzapan, lettura reale in sola lettura del 13 ottobre: due
  schede ancora attive, zero revisioni, gate `ok`. I test coprono la quarantena
  di un singolo dettaglio, l'identità URL e il rifiuto del catalogo attivo
  completamente vuoto.
- MESS, lettura reale in sola lettura del 13 ottobre: 36 laboratori letti,
  nessuna voce da rivedere, tre mostre corroborate; 17 schede attive, gate
  `ok`. I test coprono una riga del programma illeggibile, una mostra
  discordante, la riconciliazione delle posizioni e il blocco di un programma
  strutturalmente incompleto.
- Ciclo completo in sola lettura del 13 ottobre con il catalogo ufficiale come
  input: 15 fonti superate, 1.532 schede nel JSON locale, TurismoFVG `partial`
  con tre URL isolati, Pordenone Pensa `partial` con un URL isolato, 13 fonti
  `fresh`. Palazzo Attems e GiroFVG hanno generato un log diagnostico separato
  senza fermare il ciclo. La query locale mostra una sola Sagra del Rosario a
  Caneva e una sola Barcolana a Trieste. Nessun dato di questa prova è stato
  pubblicato all'app.

Il ciclo in sola lettura non ha scritto nel catalogo cloud. Una successiva
esecuzione cloud separata ha usato una copia del JSON sotto `preflight/`; il job
schedulato è stato subito ripristinato all'immagine e alla chiave ufficiali.
La prova cloud `meteofriul-events-refresh-gzkth` è riuscita: 15 fonti
`fresh`/`partial`, 1.533 schede, quattro URL TurismoFVG e uno Pordenone Pensa
in revisione. Palazzo Attems e GiroFVG hanno emesso il log separato
`event_candidate_watch_alert`; il catalogo ufficiale è rimasto alla stessa
generazione. Il quarto URL TurismoFVG è Triestespresso Expo 2026. Una lettura
successiva della pagina ufficiale con la stessa funzione del job ha verificato
titolo, città e periodo 21–23 ottobre 2026; la causa della diversa
classificazione nel ciclo cloud non è ancora provata. Il caso resta da
osservare, senza forzare un'inclusione.

## Prima della promozione

Il log reale dell'allarme separato e il collaudo cloud controllato sono
verificati; la consegna dell'email resta da confermare. Mancano la verifica
con l'app sul telefono, il passaggio del ramo secondo `AGENTS.md` e la
distribuzione ordinaria coordinata di job e API: l'API online usa un digest
precedente e il codice del baseline `main` mostra `partial`
soltanto per Paesi in Festa. Non è verificato che il digest online supporti
già i nuovi lotti `partial`; il solo aggiornamento del job rischierebbe di
nascondere TurismoFVG. GitHub è sospeso su richiesta dell'utente.
