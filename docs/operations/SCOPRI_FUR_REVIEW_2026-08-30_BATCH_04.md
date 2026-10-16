# Scopri — dieci nuove bozze FUR

30 agosto 2026 · Quarto gruppo · Stesura e confronto assistito con riferimenti dello standard.

Stato successivo: [promozione del 31 agosto](SCOPRI_ARCHIVE_PROMOTION_2026-08-31.md), dopo l'approvazione editoriale esplicita dell'utente. Una correzione di accordo nel bucato e una modifica stilistica nel Maj sono raccolte in [SCOPRI_FUR_REVIEW_2026-08-31.md](SCOPRI_FUR_REVIEW_2026-08-31.md), insieme alle copie attuali dei 17 testi. Il resto di questo documento conserva lo snapshot della prima stesura e della preparazione del 30 agosto; la revisione assistita, da sola, non aveva assegnato approvazioni FUR.

Passaggio successivo: [calendario e integrazione](SCOPRI_ARCHIVE_INTEGRATION_2026-08-30.md) completati in simulazione. Questo documento e `furDraftReview.remainingWork` conservano lo stato storico della stesura FUR; ora le dieci schede hanno `promotion_ready_except_fur` e `promotionReview.remainingBlockers: [fur_human_review]`. Non sono pubblicate né approvate linguisticamente.

## Esito e limiti

Titolo, corpo e anteprima FUR sono ora presenti per tutte le dieci schede trattate nella [revisione italiana](SCOPRI_IT_REVIEW_2026-08-30.md). Gli italiani, le fonti culturali, gli ambiti geografici e le regole temporali di quella passata sono conservati.

Si tratta di **bozze linguistiche, non di testi certificati dall'ARLeF o approvati da un revisore umano**. I riferimenti verificano lemmi, usi e toponimi; non attestano automaticamente ogni frase composta. L'eccezione editoriale concessa alla prima terna non viene estesa agli altri record.

Alla conclusione di questa passata, lo stato `bilingual_draft_pending_review` distingueva queste dieci dalle sette già predisposte per la promozione, senza `promotionReview` né `languageReview`. Tutte mantengono `languageStatus.fur: pending_human_review` e `readyForUi: false`; il blocco rimane effettivo anche dopo la successiva preparazione tecnica.

Il lavoro residuo registrato alla conclusione della stesura è in `furDraftReview.remainingWork`: revisione competente del friulano, audit calendario/duplicati e, per le quattro schede con ricorrenze non ancora definite, regola temporale compatibile. Le liste in `itCopyReview` e `furDraftReview` sono snapshot storici; lo stato corrente è nel successivo `promotionReview`.

## Testi affiancati

### 1. Il Bacio delle Croci a Zuglio

Identità: `archive-research-bacio-croci-zuglio`.

**IT · Il Bacio delle Croci a Zuglio**

Per l'Ascensione del 1973, a Zuglio le croci delle comunità della valle, decorate con fiori e nastri, si disponevano in cerchio sotto la pieve di San Pietro. Alla chiamata in friulano, ogni portatore inclinava la propria croce verso quella della pieve madre, per il bacio simbolico.

Anteprima IT: Nel rito documentato nel 1973, le croci delle comunità si inchinavano davanti a quella della pieve madre.

**FUR · La Bussade des Crôs a Zui**

Pe Sense dal 1973, a Zui lis crôs des comunitâts de val, ornadis cun flôrs e curdelis, si metevin in cercli sot de plêf di San Pieri. Ae clamade par furlan, ogni puartadôr al inclinave la sô crôs viers chê de plêf mari, pe bussade simboliche.

Anteprima FUR: Tal rît documentât tal 1973, lis crôs des comunitâts si inchinavin denant di chê de plêf mari.

Fonte culturale della scheda: [Teche Friulane · Il Bacio delle Croci](https://www.techefriulane.it/patrimonio-culturale/ricerche-etnografiche-ciceri-pellis/il-bacio-delle-croci). I fatti sono quelli della revisione italiana; i riscontri linguistici non li sostituiscono.

Scelte e punti da rileggere:

- Resta esplicito il 1973: nessuna trasformazione del rilevamento in programma attuale.
- I testi giornalistici attestano il lessico del rito, non certificano questa traduzione; le forme locali estranee allo standard non sono riprodotte automaticamente.
- Nessun dubbio lessicale specifico individuato; restano la revisione competente del testo e il distinto controllo del calendario.

Riscontri linguistici:

- [Toponimo ufficiale Zuglio → Zui.](https://arlef.it/app/uploads/documenti/DPReg_Toponimi_ALLEGATO.pdf)
- [La Patrie, maggio 2014, p. 2: Sense, Plêf Mari, S. Pieri di Zui, in cercli, clamade e bussade nel racconto del rito.](https://arlef.it/app/uploads/stampa-friulana/patrie.mai_.2014.pdf)
- [La Patrie, aprile 2024: denominazione Bussade des Crôs de Plêf di Zui.](https://arlef.it/app/uploads/stampa-friulana/patrie_avricc82l_2024_cerce.pdf)
- [Ornare → ornâ.](https://superdizionari.arlef.it/lemma/ornare/4998?language=it&oneshot=1&gui=fur)
- [Nastro → curdele.](https://superdizionari.arlef.it/lemma/nastro/7861?language=it&oneshot=1&gui=fur)
- [Portatore → puartadôr.](https://superdizionari.arlef.it/lemma/portatore/36523?language=it&oneshot=1&gui=fur)
- [Inclinare → inclinâ.](https://superdizionari.arlef.it/lemma/inclinare/9587?language=it&oneshot=1&gui=fur)
- [Inchinarsi → inchinâsi.](https://superdizionari.arlef.it/lemma/inchinarsi/25165?language=it&oneshot=1&gui=fur)

### 2. Il Maj di Lucinico, l'albero dei coscritti

Identità: `archive-research-maj-lucinico`.

**IT · Il Maj di Lucinico, l'albero dei coscritti**

Nel rito documentato a Lucinico il 5 e 6 maggio 1973, i coscritti innalzavano un albero con la bandiera della propria classe. La notte proseguiva nella capannina alla base del tronco, tra scritte scherzose sulle strade e fiori ed erbe lasciati sugli usci secondo un codice simbolico.

Anteprima IT: Un albero e una bandiera di classe erano al centro della festa dei coscritti documentata a Lucinico nel 1973.

**FUR · Il Maj di Lucinîs, l'arbul dai coscrits**

Tal rît documentât a Lucinîs ai 5 e ai 6 di Mai dal 1973, i coscrits a dreçavin sù un arbul cu la bandiere de lôr classe. La gnot e lave indenant te piçule barache ae base dal tronc, tra scritis scherçosis su lis stradis e flôrs e jerbis lassâts sui soiârs daûr di un codiç simbolic.

Anteprima FUR: Un arbul e une bandiere di classe a jerin tal centri de fieste dai coscrits documentade a Lucinîs tal 1973.

Fonte culturale della scheda: [Teche Friulane · L'albero di maggio](https://www.techefriulane.it/bdi-iccd/lalbero-di-maggio-il-maj). I fatti sono quelli della revisione italiana; i riscontri linguistici non li sostituiscono.

Scelte e punti da rileggere:

- Conservate entrambe le date del rilevamento, senza suggerire che valgano per il programma attuale.
- Piçule barache rende capannina; sui soiârs conserva la deposizione di fiori ed erbe sulle soglie, non la loro raccolta.
- La revisione competente dovrà valutare in particolare la naturalezza di la gnot e lave indenant e la resa contestuale di usci, senza aggiungere significati ai singoli fiori.

Riscontri linguistici:

- [Lucinîs è la forma comune ufficiale; Luzinîs è la variante locale.](https://arlef.it/app/uploads/documenti/DPReg_Toponimi_ALLEGATO.pdf)
- [Pagina friulana, 7 maggio 2022: attestato Maj di Lucinîs; usato per il nome, non per ridatare la scheda storica.](https://arlef.it/app/uploads/stampa-friulana/fdj-07-05-2022.pdf)
- [Notiziario comunale 2015/3, p. 15: coscrits.](https://comune.trasaghis.ud.it/media/files/md/030124/Notiziario_2015_3.pdf)
- [Dreçâ sù per innalzare.](https://superdizionari.arlef.it/lemma/innalzare/7378?language=it&oneshot=1&gui=fur)
- [Barache; piçule barache rende capannina senza inventare un diminutivo.](https://superdizionari.arlef.it/lemma/capanna/10117?language=it&oneshot=1&gui=fur)
- [Tronco → tronc.](https://superdizionari.arlef.it/lemma/tronco/19291?language=it&oneshot=1&gui=fur)
- [Scherzoso → scherçôs.](https://superdizionari.arlef.it/lemma/scherzoso/19213?language=it&oneshot=1&gui=fur)
- [Soglia → soiâr: adottato sui soiârs per la deposizione sugli usci.](https://superdizionari.arlef.it/lemma/soglia/46288?language=it&oneshot=1&gui=fur)
- [Lâ indenant per proseguire.](https://superdizionari.arlef.it/lemma/proseguire/4191?language=it&oneshot=1&gui=fur)
- [Attestata la costruzione codiç simbolic.](https://arlef.it/app/uploads/comunicati-stampa/arlef_ires_cs_ricerca-sociolinguistica_infografica_fur.pdf)

### 3. I cramârs partivano in autunno

Identità: `archive-research-cramars-carnia`.

**IT · I cramârs partivano in autunno**

I cramârs erano commercianti ambulanti carnici: raggiungevano i mercati dell'Europa centrale a piedi e con carri, vendendo spezie, medicamenti, stoffe e mercerie. Le partenze autunnali e i rientri primaverili seguivano il ritmo dei lavori nei campi, con gli animali e nei boschi.

Anteprima IT: Dalla Carnia ai mercati dell'Europa centrale, i cramârs alternavano il commercio invernale ai lavori della terra.

**FUR · I cramârs a partivin in timp di Sierade**

I cramârs a jerin comerciants ambulants cjargnei: a rivavin ai marcjâts de Europe centrâl a pît e cui cjars, vendint droghis, medisinis, stofis e robe di cramarie. Lis partencis di Sierade e lis tornadis di Primevere a seguivin il ritmi des voris tai cjamps, cui animâi e tai boscs.

Anteprima FUR: De Cjargne ai marcjâts de Europe centrâl, i cramârs a alternavin il cumierç invernâl aes voris de tiere.

Fonte culturale della scheda: [Museo Carnico · La stanza dei cramârs](https://museocarnico.it/it/esplora/cramars/). I fatti sono quelli della revisione italiana; i riscontri linguistici non li sostituiscono.

Scelte e punti da rileggere:

- Droghis significa qui spezie secondo l'accezione lessicografica pertinente, non sostanze stupefacenti.
- Robe di cramarie indica le merci e non le botteghe.
- Merci, cammino e carri, partenze e ritorni restano quelli documentati dalla fonte culturale; nessuna epoca o merce aggiunta. Il testo completo rimane soggetto alla revisione competente.

Riscontri linguistici:

- [Strolic furlan pal 1995, Società Filologica: grafia cramârs nel titolo di un contributo.](https://www.techefriulane.it/biblioteca-digitale/strolic/fascicolo/strolic-furlan-pal-1995)
- [Commerciante → comerciant.](https://superdizionari.arlef.it/lemma/commerciante/18272?language=it&oneshot=1&gui=fur)
- [Ambulant.](https://superdizionari.arlef.it/lemma/ambulante/14073?language=it&oneshot=1&gui=fur)
- [Cjargnel; plurale cjargnei.](https://superdizionari.arlef.it/lemma/carnico/27093?language=it&oneshot=1&gui=fur)
- [Marcjât.](https://superdizionari.arlef.it/lemma/mercato/47959?language=it&oneshot=1&gui=fur)
- [Droghe, nell'accezione di spezia.](https://superdizionari.arlef.it/lemma/spezia/33974?language=it&oneshot=1&gui=fur)
- [Medicamento → medisine.](https://superdizionari.arlef.it/lemma/medicamento/37168?language=it&oneshot=1&gui=fur)
- [Stoffa → stofe.](https://superdizionari.arlef.it/lemma/stoffa/7512?language=it&oneshot=1&gui=fur)
- [Robe di cramarie, insieme degli articoli di merceria, non il negozio.](https://superdizionari.arlef.it/lemma/merceria/47978?language=it&oneshot=1&gui=fur)
- [Sierade; attestata l'espressione in timp di Sierade.](https://superdizionari.arlef.it/lemma/autunno/8415?language=it&oneshot=1&gui=fur)
- [Rientro → tornade.](https://superdizionari.arlef.it/lemma/rientro/55350?language=it&oneshot=1&gui=fur)
- [Cumierç.](https://superdizionari.arlef.it/lemma/commercio/20494?language=it&oneshot=1&gui=fur)
- [Invernâl.](https://superdizionari.arlef.it/lemma/invernale/43486?language=it&oneshot=1&gui=fur)
- [Alternâ.](https://superdizionari.arlef.it/lemma/alternare/13605?language=it&oneshot=1&gui=fur)

### 4. Il frasco dell'osmiza

Identità: `archive-research-osmiza-frasco`.

**IT · Il frasco dell'osmiza**

Nella tradizione del Carso, il frasco è un ramo d'edera che annuncia un'osmiza aperta. Qui i produttori offrono vino e altri prodotti propri: una vendita temporanea che è anche un'occasione d'incontro.

Anteprima IT: Nel Carso, un ramo d'edera segnala l'osmiza: prodotti propri e un'occasione per incontrarsi.

**FUR · Il «frasco» de osmiza**

Te tradizion dal Cjars, il «frasco» al è un ramaç di elare che al segnale une osmiza vierte. Achì i produtôrs a ufrissin vin e altris prodots de lôr produzion: une vendite temporanie che e je ancje une ocasion di incuintri.

Anteprima FUR: Tal Cjars, un ramaç di elare al segnale la osmiza: prodots propris e une ocasion par cjatâsi.

Fonte culturale della scheda: [Regione FVG · Il Geoparco del Carso Classico](https://www.regione.fvg.it/rafvg/export/sites/default/RAFVG/ambiente-territorio/geologia/FOGLIA34/allegati/Il_geoparco_del_Carso_Classico_ITA.pdf). I fatti sono quelli della revisione italiana; i riscontri linguistici non li sostituiscono.

Scelte e punti da rileggere:

- Frasco e osmiza restano denominazioni locali della fonte culturale, non lemmi presentati come standard FUR; frasco è evidenziato fra caporali.
- Mantenuti ambito carsico, produzione propria e apertura temporanea; nessun giorno di apertura o evento attuale aggiunto.
- Le voci del dizionario documentano le scelte lessicali, non certificano l'intera frase. Resta la revisione competente della scorrevolezza.

Riscontri linguistici:

- [Edera → elare, accezione botanica comune; non edare.](https://superdizionari.arlef.it/lemma/edera/34338?language=it&oneshot=1&gui=fur)
- [Ramo vegetale → ramaç; scelta l'accezione comune, non la sola forma tecnica ram.](https://superdizionari.arlef.it/lemma/ramo/18455?language=it&oneshot=1&gui=fur)
- [Ufrî è documentato anche nell'accezione mettere in vendita, non soltanto offrire gratuitamente.](https://superdizionari.arlef.it/lemma/offrire/3244?language=it&oneshot=1&gui=fur)
- [Produtôr, plurale produtôrs attestato anche per produttori agricoli.](https://superdizionari.arlef.it/lemma/produttore/36496?language=it&oneshot=1&gui=fur)
- [Temporani: adottato temporanie in accordo con vendite.](https://superdizionari.arlef.it/lemma/temporaneo/8998?language=it&oneshot=1&gui=fur)
- [Incuintri: incontro fra persone, anche come occasione di riunione.](https://superdizionari.arlef.it/lemma/incontro/20788)
- [Attestato Cjars nel quadro delle diverse comunità linguistiche della regione.](https://arlef.it/lenghe-e-culture/lenghe/)
- [Attestato il plurale propris: adottato nell'anteprima.](https://superdizionari.arlef.it/lemma/proprio/3167)
- [Attestata la forma verbale a ufrissin.](https://arlef.it/arlef-e-regjon-f-vj-insiemi-pe-sanitat-e-pal-social/)

### 5. Il tòco dei pescatori maranesi

Identità: `archive-research-toco-marano`.

**IT · Il tòco dei pescatori maranesi**

Nella tradizione dei pescatori di Marano, il tòco era un sorteggio per assegnare le zone della laguna in cui pescare durante una stagione. Un modo comunitario di organizzare il lavoro sull'acqua.

Anteprima IT: Il tòco assegnava per sorteggio le zone di pesca ai maranesi, stagione dopo stagione.

**FUR · Il «tòco» dai pescjadôrs di Maran**

Te tradizion dai pescjadôrs di Maran, il «tòco» al jere une gjavade a sorte par assegnâ lis zonis de lagune dulà pescjâ par une stagjon. Un mût comunitari di organizâ il lavôr su la aghe.

Anteprima FUR: Il «tòco» al assegnave a sorte lis zonis di pescje ai maranês, stagjon dopo stagjon.

Fonte culturale della scheda: [Regione FVG · I mestieri della pesca in laguna](https://www.regione.fvg.it/rafvg/export/sites/default/RAFVG/economia-imprese/pesca-acquacoltura/FOGLIA12/allegati/Allegato_A.pdf). I fatti sono quelli della revisione italiana; i riscontri linguistici non li sostituiscono.

Scelte e punti da rileggere:

- Tòco resta il nome locale maranese, fra caporali, spiegato con gjavade a sorte.
- Traduzione in friulano della narrazione; non attribuisce il friulano come lingua del rito o dei pescatori maranesi.
- Conservati passato storico e assegnazione stagionale delle zone, senza confronto normativo con Grado o indicazioni di pesca attuali.

Riscontri linguistici:

- [Sorteggio → gjavade a sorte; non viene inventato un equivalente del nome locale tòco.](https://superdizionari.arlef.it/lemma/sorteggio/56829?language=it&oneshot=1&gui=fur)
- [Assegnâ: attribuire o mettere a disposizione, senza implicare un trasferimento di proprietà.](https://superdizionari.arlef.it/lemma/assegnare/5702?language=it&oneshot=1&gui=fur)
- [Comunitari, nel senso relativo alla comunità, non soltanto all'Unione europea.](https://superdizionari.arlef.it/lemma/comunitario/21174?language=it&oneshot=1&gui=fur)
- [La pagina ARLeF attesta Maran e maranês e distingue la varietà veneta locale dalla lingua friulana della narrazione.](https://arlef.it/lenghe-e-culture/lenghe/)
- [Testo ARLeF in FUR: uso della costruzione gjavâ a sorte.](https://arlef.it/l-arlef-a-friuli-doc-2019/)
- [Dopo è ammesso anche per la successione temporale ripetuta.](https://superdizionari.arlef.it/lemma/dopo/1410)

### 6. I mulini lungo le risorgive

Identità: `archive-research-mulini-risorgive`.

**IT · I mulini lungo le risorgive**

Tra Codroipo e Aiello, la portata regolare delle acque di risorgiva favorì la costruzione di molti mulini. Alcuni sorgevano nei borghi, altri restavano isolati nelle campagne, vicino ai corsi d'acqua più adatti a muovere le attrezzature.

Anteprima IT: Le acque di risorgiva alimentavano mulini nei borghi e nelle campagne della Bassa friulana.

**FUR · I mulins dilunc lis risultivis**

Tra Codroip e Dael, la puartade regolâr des aghis di risultive e favorì la costruzion di tancj mulins. Cierts a jerin tai borcs, altris a restavin isolâts tes campagnis, dongje dai cors di aghe plui adats a movi i imprescj.

Anteprima FUR: Lis aghis di risultive a alimentavin i mulins tai borcs e tes campagnis de Basse furlane.

Fonte culturale della scheda: [ERPAC FVG · Andar per mulini da Codroipo ad Aiello](https://patrimonioculturale.regione.fvg.it/percorso-tematico/?s_id=819778). I fatti sono quelli della revisione italiana; i riscontri linguistici non li sostituiscono.

Scelte e punti da rileggere:

- Usati puartade e Codroip, non portade o Cudroip; alimentavin riguarda l'energia fornita dall'acqua.
- Conservati i due contesti dei mulini, nei borghi e isolati in campagna, senza aperture o visite attuali.
- Resta la verifica editoriale della naturalezza sintattica e della coesistenza con il profilo di Camino.

Riscontri linguistici:

- [Attestato lis risultivis in una presentazione istituzionale ARLeF.](https://arlef.it/libris/aghe/)
- [Risultive: significato idrogeologico della risorgenza d'acqua, anche in pianura.](https://dizionarifurlan.eu/headword/risultive)
- [Senso 8, idraulica: puartade.](https://superdizionari.arlef.it/lemma/portata/14493)
- [Mulino → mulin.](https://superdizionari.arlef.it/lemma/mulino/49175)
- [Uso preposizionale di dilunc.](https://superdizionari.arlef.it/lemma/lungo/13662)
- [Imprescj per l'insieme degli strumenti.](https://superdizionari.arlef.it/lemma/attrezzatura/2623)
- [Movi, anche per l'acqua che aziona macchinari.](https://superdizionari.arlef.it/lemma/muovere/9134)
- [Alimentâ nel senso tecnico di fornire energia al funzionamento.](https://superdizionari.arlef.it/lemma/alimentare/10914)
- [Toponimi ufficiali Codroip e Dael.](https://arlef.it/app/uploads/page/comuni_friulanofoni.pdf#page=1)

### 7. Un nome nella stalla, un suono al pascolo

Identità: `archive-research-animali-nomi-campanacci`.

**IT · Un nome nella stalla, un suono al pascolo**

Nella stalla, tavolette con i nomi segnavano il posto di cavalli e bovini. Al pascolo si mettevano campanacci agli animali da controllare, soprattutto irrequieti o dominanti: i suoni diversi aiutavano a seguirne gli spostamenti.

Anteprima IT: Tavolette nella stalla e campanacci al pascolo aiutavano a riconoscere gli animali.

**FUR · Un non te stale, un sun a passon**

Te stale, breutis cui nons a segnavin il puest dai cjavai e dai bovins. A passon si metevin sampogns ai nemâi di controlâ, soredut a chei incuiets o dominants: i suns diferents a judavin a stâ daûr ai lôr moviments.

Anteprima FUR: Breutis te stale e sampogns a passon a judavin a cognossi i nemâi.

Fonte culturale della scheda: [ERPAC FVG · Animali e vita contadina nel Museo Diogene Penzi](https://patrimonioculturale.regione.fvg.it/percorso-tematico/?s_id=597659). I fatti sono quelli della revisione italiana; i riscontri linguistici non li sostituiscono.

Scelte e punti da rileggere:

- Conservato l'uso selettivo dei sampogns: animali da controllare, soprattutto irrequieti o dominanti, non tutti.
- Cognossi è usato nel senso identificativo e moviments per gli spostamenti.
- Nessun luogo o fatto aggiunto rispetto all'italiano. La sintassi resta soggetta alla revisione competente.

Riscontri linguistici:

- [Breute, sensi 2 e 5; plurale breutis.](https://superdizionari.arlef.it/lemma/tavoletta/59790)
- [Sampogn per gli animali al pascolo; la diversa accezione cjampane riguarda il richiamo delle api.](https://superdizionari.arlef.it/lemma/campanaccio/25905)
- [Locuzione a passon.](https://superdizionari.arlef.it/lemma/pascolo/53428)
- [Bovin, plurale bovins.](https://superdizionari.arlef.it/lemma/bovino/18330)
- [Cjaval; esempi espliciti con cjavai.](https://superdizionari.arlef.it/lemma/cavallo/27989)
- [Incuiet, plurale incuiets.](https://superdizionari.arlef.it/lemma/irrequieto/1371)
- [Dominant, plurale dominants.](https://superdizionari.arlef.it/lemma/dominante/33642)
- [Stâ daûr, anche per seguire i movimenti senza accompagnarli.](https://superdizionari.arlef.it/lemma/seguire/1417)
- [Moviment, plurale moviments.](https://superdizionari.arlef.it/lemma/spostamento/29531)
- [Cognossi nel senso di identificare.](https://superdizionari.arlef.it/lemma/riconoscere/6061)

### 8. Pettini d'osso fra i sedonêrs di Andreis

Identità: `archive-research-pettini-osso-andreis`.

**IT · Pettini d'osso fra i sedonêrs di Andreis**

Il Museo etnografico di Andreis conserva testimonianze dei sedonêrs, artigiani che lavoravano il legno e l'osso. Tra gli oggetti ricordati ci sono anche pettini d'osso, accanto a utensili per la vita domestica.

Anteprima IT: Ad Andreis, anche i pettini d'osso raccontano l'artigianato dei sedonêrs.

**FUR · Pietins di vues fra i «sedonêrs» di Andreis**

Il Museu etnografic di Andreis al conserve testemoneancis dai «sedonêrs», artesans che a lavoravin il len e il vues. Jenfri i ogjets ricuardâts a son ancje pietins di vues, dongje di imprescj pe vite di cjase.

Anteprima FUR: A Andreis, ancje i pietins di vues a contin l'artesanât dai «sedonêrs».

Fonte culturale della scheda: [Parco Naturale Dolomiti Friulane · Andreis](https://www.parcodolomitifriulane.it/i-paesi-del-parco/andreis/). I fatti sono quelli della revisione italiana; i riscontri linguistici non li sostituiscono.

Scelte e punti da rileggere:

- Sedonêrs resta un nome locale citato fra caporali, non viene presentato come lemma normativo per tutti gli artigiani.
- Conservato Andreis, toponimo ufficiale in friulano comune.
- Nessuna aggiunta sugli oggetti esclusi dalla scheda italiana; resta la revisione della fluidità del testo.

Riscontri linguistici:

- [Pettine → pietin.](https://superdizionari.arlef.it/lemma/pettine/54047?language=it&gui=fur)
- [Vues, anche come materiale.](https://superdizionari.arlef.it/lemma/osso/50946?language=it&gui=fur)
- [Artigiano → artesan.](https://superdizionari.arlef.it/lemma/artigiano/5437?language=it&gui=fur)
- [Artigianato → artesanât.](https://superdizionari.arlef.it/lemma/artigianato/5440?language=it&gui=fur)
- [Testimonianza → testemoneance.](https://superdizionari.arlef.it/lemma/testimonianza/7437?language=it&gui=fur)
- [Attestato l'aggettivo etnografic.](https://arlef.it/lenghe-e-culture/leterature/)
- [Pagina 18 stampata: Andreis in friulano comune, Andrees nella forma locale.](https://arlef.it/app/uploads/documenti/DPReg_Toponimi_ALLEGATO.pdf)
- [Sedonâr significa mestolaio: distinto dalla denominazione locale sedonêrs della fonte culturale, senza sostituzione automatica.](https://superdizionari.arlef.it/lemma/mestolaio/48070?language=it&gui=fur)

### 9. Il bucato che poteva durare giorni

Identità: `archive-research-bucato-ranno`.

**IT · Il bucato che poteva durare giorni**

Fare il bucato poteva richiedere più giorni. Prima si strofinavano i panni con il sapone, poi si trattavano con il ranno, acqua e cenere, lasciandoli in ammollo per una notte. Seguiva il risciacquo in acqua corrente, strofinando e battendo la biancheria sui lavatoi.

Anteprima IT: Il bucato comprendeva una notte in ammollo nel ranno, prima del risciacquo al lavatoio.

**FUR · La bugade che e podeve durâ dîs**

Fâ la bugade al podeve domandâ plui dîs. Prime si freave la blancjarie cul savon, po si le tratave cu la lissie, aghe e cinise, lassantle in muel par une gnot. Dopo si le resentave in aghe corint, freantle e batintle sui lavadôrs.

Anteprima FUR: La blancjarie e restave une gnot in muel te lissie, prime di jessi resentade tal lavadôr.

Fonte culturale della scheda: [ERPAC FVG · I lavori femminili nel Museo Diogene Penzi](https://patrimonioculturale.regione.fvg.it/percorso-tematico/?s_id=597655). I fatti sono quelli della revisione italiana; i riscontri linguistici non li sostituiscono.

Scelte e punti da rileggere:

- Distinte bugade, il bucato, e lissie, la sostanza detergente; non adottata la forma lessee non riscontrata.
- Conservati ordine del lavaggio, ammollo notturno e risciacquo, senza dettagli nuovi sulla preparazione.
- Forme impersonali e scorrevolezza restano da validare nella revisione competente.

Riscontri linguistici:

- [Bucato → bugade.](https://superdizionari.arlef.it/lemma/bucato/18928?language=it&gui=fur)
- [Cenere → cinise; esempio con lissie.](https://superdizionari.arlef.it/lemma/cenere/28320?language=it&gui=fur)
- [La Vôs, 6 marzo 2026: attestazioni contestuali di lissie, in muel, lavadôr e resentâle.](https://arlef.it/app/uploads/stampa-friulana/vos06c11-7.pdf)
- [Ammollo → muel.](https://superdizionari.arlef.it/lemma/ammollo/14375?language=it&gui=fur)
- [Risciacquare → resentâ.](https://superdizionari.arlef.it/lemma/risciacquare/56007?language=it&gui=fur)
- [Strofinare → freâ.](https://superdizionari.arlef.it/lemma/strofinare/5186?language=it&gui=fur)
- [Lavatoio → lavadôr.](https://superdizionari.arlef.it/lemma/lavatoio/45806?language=it&gui=fur)
- [Plurale dîs negli esempi.](https://superdizionari.arlef.it/lemma/giorno/19031?language=it&gui=fur)

### 10. Un ago d'osso per leggere il prosciutto

Identità: `archive-research-ago-osso-prosciutto`.

**IT · Un ago d'osso per leggere il prosciutto**

Al Museo del Territorio di San Daniele si conservano anche aghi ricavati da osso di cavallo. Servivano nei salumifici per valutare la stagionatura e le caratteristiche organolettiche dei prosciutti.

Anteprima IT: A San Daniele, gli aghi d'osso raccontano il lavoro di chi valutava i prosciutti.

**FUR · Une gusiele di vues par lei il persut**

Tal Museu dal Teritori di San Denêl si conservin ancje gusielis fatis di vues di cjaval. A vignivin dopradis tes fabrichis di salams par valutâ la stagjonadure e lis carateristichis organoletichis dai persuts.

Anteprima FUR: A San Denêl, lis gusielis di vues a contin il lavôr di cui che al valutave i persuts.

Fonte culturale della scheda: [ERPAC FVG · Museo del Territorio di San Daniele del Friuli](https://patrimonioculturale.regione.fvg.it/museo/?s_id=440505&s_tab=f). I fatti sono quelli della revisione italiana; i riscontri linguistici non li sostituiscono.

Scelte e punti da rileggere:

- Adottato gusiele dal GDB attuale, distinguendolo dalla forma gusele nella pubblicazione più vecchia.
- Fabriche di salams è l'equivalente lessicografico di salumificio, non un cambiamento del prodotto della scheda.
- Conservata la metafora del titolo senza aggiungere istruzioni tecniche o alimentari; resta la revisione linguistica prevista.

Riscontri linguistici:

- [Ago → gusiele; plurale gusielis.](https://superdizionari.arlef.it/lemma/ago/12607?language=it&gui=fur)
- [Osso → vues.](https://superdizionari.arlef.it/lemma/osso/50946?language=it&gui=fur)
- [Cavallo → cjaval.](https://superdizionari.arlef.it/lemma/cavallo/27989?language=it&gui=fur)
- [Stagionatura → stagjonadure.](https://superdizionari.arlef.it/lemma/stagionatura/57401?language=it&gui=fur)
- [Organoletic; esempio esplicito carateristichis organoletichis.](https://superdizionari.arlef.it/lemma/organolettico/50755?language=it&gui=fur)
- [Salumificio → fabriche di salams.](https://superdizionari.arlef.it/lemma/salumificio/58171?language=it&gui=fur)
- [Pagina 11: persut/persuts, stagjonadure e valutâts; per ago si segue il lemma GDB attuale gusiele, non la forma gusele del vecchio testo.](https://arlef.it/app/uploads/giochi/alcce-n-58.pdf)
- [Pagina 149 stampata: toponimo ufficiale San Denêl.](https://arlef.it/app/uploads/documenti/DPReg_Toponimi_ALLEGATO.pdf)

## Integrità editoriale

- Restano tre schede integrate: cesti, latteria, cartoline di Lignano.
- Restano sette bozze precedenti con stato `promotion_ready_except_fur`, in attesa della revisione prevista; nessun testo o metadato cambiato.
- Dieci nuove schede hanno adesso una bozza FUR documentata, ma non una predisposizione completa alla pubblicazione.
- Totale ricerca: venti record con titolo, corpo e anteprima IT/FUR; diciassette ancora non approvati in FUR.
- Il catalogo runtime, l'interfaccia, i calendari attivi e la selezione giornaliera sono invariati.

Maj, frasco, osmiza, tòco e sedonêrs conservano il loro carattere di denominazioni locali documentate. Non vengono attribuiti arbitrariamente alla grafia normativa né usati per suggerire che una tradizione maranese o carsica abbia origine friulanofona.

Bacio delle Croci e Maj continuano a indicare il 1973. Non si aggiungono appuntamenti attuali, orari di visita, date di apertura delle osmize o indicazioni normative per la pesca. Nessun contenuto multimediale di terzi è stato aggiunto.

## Verifiche

- 48 test superati in otto file: nuove bozze FUR, revisione IT, ricerca delle due wave, promozione, registro editoriale, archivio istituzionale e guardie di visibilità. Inclusa la regressione di calendario 2026–2031 IT/FUR per le schede già predisposte.
- Lint frontend e `git diff --check` superati.
- Confronto con lo snapshot all'inizio della passata: invariati tutti i testi IT, le fonti culturali, gli ambiti geografici, le regole temporali, gli stati di approvazione e `itCopyReview`. Aggiunti soltanto FUR, metadati di revisione e nuovo stato editoriale nei dieci record.
- Controllo strutturale indipendente con `d373fdb`: identiche le tre promozioni e le sette bozze FUR precedenti. Catalogo attivo, getter e codice runtime invariati; conteggi del registro coerenti.
- Documento confrontato con i dati: titolo, corpo e anteprima corrispondono per tutte le dieci schede in entrambe le lingue.
- Nessuna build Android o distribuzione: questa passata riguarda bozze editoriali escluse dalla UI, documentazione e test.

Nessun commit, push, deploy o nuova release in questa passata. Il precedente lavoro IT non committato è preservato e queste aggiunte FUR si sommano ad esso.
