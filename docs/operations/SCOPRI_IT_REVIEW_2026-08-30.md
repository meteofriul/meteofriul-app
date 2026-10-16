# Scopri — revisione italiana delle dieci bozze rimanenti

30 agosto 2026 · Revisione assistita su fonti primarie.

Passaggi successivi: le dieci bozze FUR sono raccolte in [SCOPRI_FUR_REVIEW_2026-08-30_BATCH_04.md](SCOPRI_FUR_REVIEW_2026-08-30_BATCH_04.md); calendario e integrazione sono documentati in [SCOPRI_ARCHIVE_INTEGRATION_2026-08-30.md](SCOPRI_ARCHIVE_INTEGRATION_2026-08-30.md). Questo documento e `itCopyReview.remainingWork` conservano lo stato storico al termine della revisione italiana. Il lavoro residuo attuale è in `promotionReview.remainingBlockers`: revisione FUR, senza pubblicazione automatica.

## Stato e perimetro

Il lavoro precedente, sulle quattro bozze FUR del terzo gruppo, è salvato nel commit `d373fdb` (`docs: review remaining prepared Scopri archive drafts`). Nessun push o deploy.

Questa passata completa titolo, corpo e anteprima italiani delle dieci schede che erano ancora in bozza. È una revisione editoriale assistita per preparare la stesura FUR, **non un'approvazione umana, una traduzione friulana o una pubblicazione**.

Il nuovo stato interno `it_ready_for_fur_draft` separa l'italiano revisionato dalle schede già bilingui: `reviewStatus: it_copy_approved`, `languageStatus.it: approved`, tre campi FUR ancora nulli, `languageStatus.fur: pending_human_review`, `readyForUi: false`. Non viene creato un `promotionReview`, né viene estesa l'eccezione editoriale concessa alla prima terna.

La ricerca originaria conserva `source.checkedAt: 2026-08-28`; la nuova verifica è registrata in `itCopyReview.sourceRecheckedAt: 2026-08-30`. Identità, ambiti geografici e regole temporali non cambiano.

## Testi rivisti

### 1. Il Bacio delle Croci a Zuglio

Identità: `archive-research-bacio-croci-zuglio`.

Per l'Ascensione del 1973, a Zuglio le croci delle comunità della valle, decorate con fiori e nastri, si disponevano in cerchio sotto la pieve di San Pietro. Alla chiamata in friulano, ogni portatore inclinava la propria croce verso quella della pieve madre, per il bacio simbolico.

Anteprima IT: Nel rito documentato nel 1973, le croci delle comunità si inchinavano davanti a quella della pieve madre.

Fonte: [Teche Friulane · Il Bacio delle Croci](https://www.techefriulane.it/patrimonio-culturale/ricerche-etnografiche-ciceri-pellis/il-bacio-delle-croci).

Riscontro: Rilevamento del 31 maggio 1973: comunità della valle, ornamenti, disposizione, chiamata e gesto rituale.

Ulteriore riscontro: [Il programma 2026 indica domenica 17 maggio: non ricavare automaticamente una data runtime dal giovedì dell'Ascensione documentato nel 1973.](https://www.diocesiudine.it/wd-appuntamenti/a-zuglio-il-bacio-delle-croci-tra-le-chiese-della-carnia/)

Modifiche e cautele:

- La copy è esplicitamente riferita al 1973, non annuncia un evento attuale.
- Sostituito il riferimento indiscriminato alle antiche pievi con le comunità della valle.
- La regola mobile resta da definire prima della promozione: il documento storico e il calendario attuale non giustificano da soli un offset fisso.

### 2. Il Maj di Lucinico, l'albero dei coscritti

Identità: `archive-research-maj-lucinico`.

Nel rito documentato a Lucinico il 5 e 6 maggio 1973, i coscritti innalzavano un albero con la bandiera della propria classe. La notte proseguiva nella capannina alla base del tronco, tra scritte scherzose sulle strade e fiori ed erbe lasciati sugli usci secondo un codice simbolico.

Anteprima IT: Un albero e una bandiera di classe erano al centro della festa dei coscritti documentata a Lucinico nel 1973.

Fonte: [Teche Friulane · L'albero di maggio](https://www.techefriulane.it/bdi-iccd/lalbero-di-maggio-il-maj).

Riscontro: Scheda BDI 17454: rilevamento del 5 maggio e svolgimento il 5–6 maggio 1973; scjarnete come deposizione simbolica sugli usci.

Modifiche e cautele:

- Corretta la raccolta rituale: la fonte descrive fiori ed erbe lasciati sugli usci.
- Mantenuto il contesto documentato del 1973, senza trasformarlo in programma attuale.
- La futura regola della prima domenica di maggio deve considerare anche la vigilia; nessuna data runtime aggiunta.

### 3. I cramârs partivano in autunno

Identità: `archive-research-cramars-carnia`.

I cramârs erano commercianti ambulanti carnici: raggiungevano i mercati dell'Europa centrale a piedi e con carri, vendendo spezie, medicamenti, stoffe e mercerie. Le partenze autunnali e i rientri primaverili seguivano il ritmo dei lavori nei campi, con gli animali e nei boschi.

Anteprima IT: Dalla Carnia ai mercati dell'Europa centrale, i cramârs alternavano il commercio invernale ai lavori della terra.

Fonte: [Museo Carnico · La stanza dei cramârs](https://museocarnico.it/it/esplora/cramars/).

Riscontro: La stanza dei cramârs: merci, viaggi a piedi e con carri, partenze autunnali e rientri primaverili legati ai lavori agro-silvo-pastorali.

Modifiche e cautele:

- Eliminati i nuovi contatti culturali e gli oggetti riportati a casa, non documentati nella pagina scelta.
- Non si riduce il trasporto alle cassette: cràme e cràssigne sono strumenti distinti.
- La datazione degli oggetti esposti non viene estesa all'intero fenomeno storico.

### 4. Il frasco dell'osmiza

Identità: `archive-research-osmiza-frasco`.

Nella tradizione del Carso, il frasco è un ramo d'edera che annuncia un'osmiza aperta. Qui i produttori offrono vino e altri prodotti propri: una vendita temporanea che è anche un'occasione d'incontro.

Anteprima IT: Nel Carso, un ramo d'edera segnala l'osmiza: prodotti propri e un'occasione per incontrarsi.

Fonte: [Regione FVG · Il Geoparco del Carso Classico](https://www.regione.fvg.it/rafvg/export/sites/default/RAFVG/ambiente-territorio/geologia/FOGLIA34/allegati/Il_geoparco_del_Carso_Classico_ITA.pdf).

Riscontro: Il Geoparco del Carso Classico, p. 123 stampata (pagina 125 PDF), paragrafo osmiza e figura 5.3.4(c): edera, frasco, prodotti propri e funzione sociale; colophon a pagina 4 PDF.

Modifiche e cautele:

- Ambito limitato al Carso, non generalizzato a tutto il Friuli.
- Nessuna apertura attuale, data fissa o durata universale di otto giorni.
- Il colophon riserva i diritti dell'intera pubblicazione: ampliata la nota, prima limitata alle fotografie.

### 5. Il tòco dei pescatori maranesi

Identità: `archive-research-toco-marano`.

Nella tradizione dei pescatori di Marano, il tòco era un sorteggio per assegnare le zone della laguna in cui pescare durante una stagione. Un modo comunitario di organizzare il lavoro sull'acqua.

Anteprima IT: Il tòco assegnava per sorteggio le zone di pesca ai maranesi, stagione dopo stagione.

Fonte: [Regione FVG · I mestieri della pesca in laguna](https://www.regione.fvg.it/rafvg/export/sites/default/RAFVG/economia-imprese/pesca-acquacoltura/FOGLIA12/allegati/Allegato_A.pdf).

Riscontro: I mestieri della pesca nella laguna di Marano e Grado, pagina 1, ultimo paragrafo della Premessa: assegnazione stagionale tramite sorteggio tradizionale.

Modifiche e cautele:

- Eliminati l'incipit non semplicemente occupate e il confronto con il libero accesso a Grado.
- Si descrive un uso storico-culturale, non la disciplina vigente né un trasferimento di proprietà.
- Nessuna data del sorteggio o regola normativa ricavata dal documento.

### 6. I mulini lungo le risorgive

Identità: `archive-research-mulini-risorgive`.

Tra Codroipo e Aiello, la portata regolare delle acque di risorgiva favorì la costruzione di molti mulini. Alcuni sorgevano nei borghi, altri restavano isolati nelle campagne, vicino ai corsi d'acqua più adatti a muovere le attrezzature.

Anteprima IT: Le acque di risorgiva alimentavano mulini nei borghi e nelle campagne della Bassa friulana.

Fonte: [ERPAC FVG · Andar per mulini da Codroipo ad Aiello](https://patrimonioculturale.regione.fvg.it/percorso-tematico/?s_id=819778).

Riscontro: Andar per mulini da Codroipo ad Aiello: portata costante delle risorgive e collocazione degli opifici nei borghi o isolati presso i corsi d'acqua.

Modifiche e cautele:

- Corpo italiano confermato; tolto nascosti dal titolo perché non necessario alla descrizione documentata.
- Non si promettono aperture, visite o un itinerario attualmente percorribile.
- Tema più ampio del profilo di Camino al Tagliamento; resta il controllo di coesistenza prima della promozione.

### 7. Un nome nella stalla, un suono al pascolo

Identità: `archive-research-animali-nomi-campanacci`.

Nella stalla, tavolette con i nomi segnavano il posto di cavalli e bovini. Al pascolo si mettevano campanacci agli animali da controllare, soprattutto irrequieti o dominanti: i suoni diversi aiutavano a seguirne gli spostamenti.

Anteprima IT: Tavolette nella stalla e campanacci al pascolo aiutavano a riconoscere gli animali.

Fonte: [ERPAC FVG · Animali e vita contadina nel Museo Diogene Penzi](https://patrimonioculturale.regione.fvg.it/percorso-tematico/?s_id=597659).

Riscontro: Animali e vita contadina: tavolette per cavalli e bovini e uso selettivo dei campanacci, soprattutto per animali irrequieti o dominanti.

Modifiche e cautele:

- Rimosso ogni animale: le tavolette documentate riguardano in particolare cavalli e bovini.
- Esplicitato l'uso selettivo dei campanacci; non se ne attribuisce uno a tutti gli animali.
- Nessuna località o pratica aggiunta oltre il contesto del Museo Diogene Penzi.

### 8. Pettini d'osso fra i sedonêrs di Andreis

Identità: `archive-research-pettini-osso-andreis`.

Il Museo etnografico di Andreis conserva testimonianze dei sedonêrs, artigiani che lavoravano il legno e l'osso. Tra gli oggetti ricordati ci sono anche pettini d'osso, accanto a utensili per la vita domestica.

Anteprima IT: Ad Andreis, anche i pettini d'osso raccontano l'artigianato dei sedonêrs.

Fonte: [Parco Naturale Dolomiti Friulane · Andreis](https://www.parcodolomitifriulane.it/i-paesi-del-parco/andreis/).

Riscontro: Portale del Parco, Andreis: Museo etnografico, sedonêrs, lavorazione del legno e dell'osso, pettini d'osso.

Modifiche e cautele:

- Eliminata la valutazione generica sulla precisione dell'artigianato.
- Il termine ambiguo tabaccherie resta escluso; nessuna reinterpretazione come tabacchiere.
- Oggetti distinti dai temi già trattati per Andreis; controllo di coesistenza ancora richiesto prima della promozione.

### 9. Il bucato che poteva durare giorni

Identità: `archive-research-bucato-ranno`.

Fare il bucato poteva richiedere più giorni. Prima si strofinavano i panni con il sapone, poi si trattavano con il ranno, acqua e cenere, lasciandoli in ammollo per una notte. Seguiva il risciacquo in acqua corrente, strofinando e battendo la biancheria sui lavatoi.

Anteprima IT: Il bucato comprendeva una notte in ammollo nel ranno, prima del risciacquo al lavatoio.

Fonte: [ERPAC FVG · I lavori femminili nel Museo Diogene Penzi](https://patrimonioculturale.regione.fvg.it/percorso-tematico/?s_id=597655).

Riscontro: I lavori femminili: lavaggio con sapone, trattamento con ranno, ammollo notturno e risciacquo in acqua corrente strofinando e battendo la biancheria.

Modifiche e cautele:

- Titolo reso non categorico: il lavoro poteva durare più giorni.
- Resa esplicita la sequenza storica documentata, senza aggiungere ricette o istruzioni domestiche.
- Diverso dalla scheda sui cesti: qui il tema è il lavaggio, non il trasporto del bucato.

### 10. Un ago d'osso per leggere il prosciutto

Identità: `archive-research-ago-osso-prosciutto`.

Al Museo del Territorio di San Daniele si conservano anche aghi ricavati da osso di cavallo. Servivano nei salumifici per valutare la stagionatura e le caratteristiche organolettiche dei prosciutti.

Anteprima IT: A San Daniele, gli aghi d'osso raccontano il lavoro di chi valutava i prosciutti.

Fonte: [ERPAC FVG · Museo del Territorio di San Daniele del Friuli](https://patrimonioculturale.regione.fvg.it/museo/?s_id=440505&s_tab=f).

Riscontro: Scheda del Museo del Territorio: aghi in osso di cavallo impiegati nei salumifici per valutare stagionatura e caratteristiche organolettiche.

Modifiche e cautele:

- Confermati materiale, contesto professionale e funzione degli oggetti.
- Leggere è una metafora editoriale; nessuna istruzione alimentare o tecnica aggiunta.
- Tema distinto dal profilo di San Daniele dedicato alla Biblioteca Guarneriana.

## Calendario, duplicati e riuso

Bacio delle Croci e Maj sono racconti di rilevamenti del 1973, non un programma di appuntamenti attuali. Restano da definire le rispettive regole mobili, tenendo conto della domenica di celebrazione e della vigilia. Per osmiza e tòco non esiste una data fissa documentata da trasformare automaticamente in calendario: va scelta una regola editoriale compatibile senza inventare aperture o appuntamenti.

Le sovrapposizioni tematiche già segnalate restano esplicite: mulini/Profilo di Camino, tòco/Profilo di Marano, artigianato/Andreis, bucato/cesti. La verifica preliminare non ha individuato testi duplicati; il controllo di coesistenza nel calendario resta da eseguire sulla futura versione bilingue prima di qualsiasi promozione.

Nessuna foto, filmato, mappa o riproduzione d'archivio aggiunta. Per la pubblicazione sul Carso la nota sui diritti ora riguarda l'intera opera, non soltanto le fotografie. Le card sono brevi sintesi originali dei fatti documentati.

## Quadro dei venti candidati

- Tre schede già integrate nel catalogo separato: cesti, latteria e cartoline di Lignano; invariate.
- Sette schede già bilingui con revisione assistita FUR, ancora in attesa della decisione prevista; invariate.
- Dieci schede ora complete in italiano, ancora da redigere e revisionare in FUR.
- Nessuna nuova scheda attivata nell'app da questa passata.

Prossimo lavoro: stesura FUR delle dieci, confronto linguistico con riferimenti affidabili, revisione prevista e audit finale di calendario/duplicati. La sola revisione italiana non rimuove nessuno di questi passaggi.

## Verifiche

- 42 test superati in sette file: nuova revisione italiana, ricerca delle due wave, promozione, registro editoriale, archivio istituzionale e guardie di visibilità. Compreso l'audit di calendario 2026–2031 IT/FUR sulle schede già preparate.
- Lint frontend e `git diff --check` superati.
- Confronto strutturale con `d373fdb`: cambiano esattamente i dieci record prima IT draft. Le tre promozioni e le sette bozze FUR precedenti sono identiche; catalogo attivo e codice runtime invariati.
- Controllo indipendente completato: metadati e conteggi coerenti; nessuna delle dieci schede è visibile o pubblicabile. Il nuovo stato rimane escluso anche se il solo flag `readyForUi` venisse impostato per errore.
- Nessuna build Android o produzione necessaria per questa passata limitata a ricerca, documentazione e test; non è stata creata una release.

Queste modifiche sono successive al commit iniziale del turno e restano da committare. Nessun push, deploy, nuova release o variazione del catalogo pubblico.
