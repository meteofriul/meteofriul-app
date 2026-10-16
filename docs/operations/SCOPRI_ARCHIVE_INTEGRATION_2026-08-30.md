# Scopri — preparazione del calendario e dell'integrazione

30 agosto 2026 · Quarto gruppo · Simulazione sul selettore reale, senza pubblicazione.

Stato successivo: [promozione del 31 agosto](SCOPRI_ARCHIVE_PROMOTION_2026-08-31.md), dopo l'approvazione editoriale esplicita dell'utente, con le [copie attuali dei 17 testi](SCOPRI_FUR_REVIEW_2026-08-31.md). Le regole temporali documentate qui restano invariate. Il resto di questo documento conserva lo snapshot della preparazione del 30 agosto, quando i candidati erano ancora in attesa.

## Esito

Le dieci schede della [revisione italiana](SCOPRI_IT_REVIEW_2026-08-30.md) e del [quarto gruppo FUR](SCOPRI_FUR_REVIEW_2026-08-30_BATCH_04.md) hanno ora identità di destinazione, tipologia e regola temporale compatibili con Scopri. Sono `promotion_ready_except_fur`, non contenuti visibili.

Il totale dei due lotti è di **20 schede: 3 già promosse e 17 preparate ma ancora in attesa della revisione FUR**. Le copie di ricerca restano tutte `readyForUi: false`. Non viene estesa l'approvazione editoriale condizionata concessa alla prima terna; non viene registrata alcuna nuova approvazione umana o certificazione linguistica.

Il catalogo runtime resta di 71 record culturali, inclusi i tre già presenti in `institutionalArchive.json`. Nessuna modifica a componenti, selettore, import runtime, media o contenuti pubblicati. Nessun commit, push o deploy effettuato in questo passaggio.

## Mappa delle dieci schede

Tutte appartengono alla sezione `archivio_tradizioni`. L'identità di destinazione sostituisce il prefisso `archive-research-` con `institutional-archive-`, conservando il suffisso seguente.

| Suffisso | Tipo | Finestra di lettura |
| --- | --- | --- |
| bacio-croci-zuglio | rito | Dal giovedì dell'Ascensione alla domenica seguente: Pasqua +39…+42 |
| maj-lucinico | rito | 30 aprile–7 maggio |
| cramars-carnia | storia_locale | Autunno, inverno e primavera |
| osmiza-frasco | vita_quotidiana | Rotazione annuale d'archivio |
| toco-marano | vita_quotidiana | Rotazione annuale d'archivio |
| mulini-risorgive | vita_quotidiana | Rotazione annuale d'archivio |
| animali-nomi-campanacci | vita_quotidiana | Rotazione annuale d'archivio |
| pettini-osso-andreis | vita_quotidiana | Rotazione annuale d'archivio |
| bucato-ranno | vita_quotidiana | Rotazione annuale d'archivio |
| ago-osso-prosciutto | vita_quotidiana | Rotazione annuale d'archivio |

Il tipo `rito` non sposta le prime due nella rubrica “Riti e credenze popolari”: il routing dipende dalla sezione. Gli strumenti per gli animali restano cultura materiale, non “Segni naturali”. Tutte le tipologie hanno già etichette IT/FUR.

## Finestre editoriali, non programmi di eventi

- **Bacio delle Croci:** la scheda delle [Teche Friulane](https://www.techefriulane.it/patrimonio-culturale/ricerche-etnografiche-ciceri-pellis/il-bacio-delle-croci) documenta il 31 maggio 1973. La finestra di quattro giorni consente di riproporre quel racconto nel periodo dell'Ascensione, senza sostenere che il rito attuale si svolga in una data precisa. La distinzione tra giovedì dell'Ascensione e domenica successiva è attestata anche dal [Vaticano](https://www.vatican.va/content/benedict-xvi/it/angelus/2012/documents/hf_ben-xvi_reg_20120520.html). La [pagina diocesana 2026](https://www.diocesiudine.it/wd-appuntamenti/a-zuglio-il-bacio-delle-croci-tra-le-chiese-della-carnia/) indica domenica 17 maggio nel corpo, ma 18 maggio nell'intestazione/metadati: nessuna data evento è importata da quella pagina. La regola usa `movableDateRanges`, non il token `easter_relative`, che nel selettore indica la Domenica delle Palme.
- **Maj:** le [Teche Friulane](https://www.techefriulane.it/bdi-iccd/lalbero-di-maggio-il-maj) descrivono la prima domenica di maggio e il rito del 5–6 maggio 1973. Il 30 aprile–7 maggio è una scelta editoriale: comprende ogni possibile prima domenica e la vigilia. Non è la durata della festa né un programma contemporaneo. Il riferimento al 1973 resta esplicito in entrambi i testi.
- **Cramârs:** si conserva il contesto delle partenze autunnali e dei rientri primaverili documentato dal [Museo Carnico](https://museocarnico.it/it/esplora/cramars/), senza attribuire giorni precisi.
- **Osmiza e tòco:** `always` significa che il racconto storico-culturale può ruotare durante l'anno. Non significa osmize sempre aperte, pesca sempre consentita o sorteggi programmati.

Nessun mese è aggiunto alle regole degli intervalli: il selettore lo tratterebbe come un criterio più ampio, rendendo eleggibili giorni esterni alla finestra. Bacio delle Croci ammette primavera ed estate, perché l'intervallo può cadere a giugno; Maj soltanto primavera.

Le vecchie `temporalRule`, `itCopyReview.remainingWork` e `furDraftReview.remainingWork` sono conservate come snapshot di ricerca. Non sono lo stato operativo corrente: le regole proposte sono in `promotionReview.runtimeTemporal`, i blocchi correnti in `promotionReview.remainingBlockers`, i riscontri tecnici in `integrationReview`.

## Duplicati e rotazione

Il controllo indipendente non ha trovato collisioni di identità o testi identici normalizzati IT/FUR rispetto a 71 record culturali attivi, 215 profili comunali e 10 candidati dei gruppi precedenti. Le dieci nuove identità e chiavi canoniche sono uniche anche rispetto alle destinazioni già prenotate.

Le vicinanze tematiche sono intenzionali, non copie: mulini delle risorgive rispetto al profilo di Camino/Glaunicco; sorteggio del tòco rispetto alla presentazione generale di Marano; pettini d'osso rispetto a Tavan e maschere di Andreis; bucato con ranno rispetto al trasporto nei cesti e alle credenze lunari di Ostermann; campanacci identificativi rispetto ai presagi animali.

Simulazioni sul selettore reale:

- Catalogo attivo più tutti i **17 candidati**, per ogni giorno del **2026–2031**, sia IT sia FUR: nessuna collisione visibile, nessuna violazione della precedenza delle ricorrenze esatte, tutti i candidati usati almeno una volta in ciascun anno/lingua, ripetizione consecutiva massima non superiore a due giorni.
- Catalogo attivo più soltanto i **10 nuovi candidati**, nel 2028 IT/FUR: stesso esito. La loro integrazione non dipende dall'approvazione delle altre sette bozze.
- Confini inclusivi/esclusivi del Bacio verificati anche per il 1973 e per Pasque molto precoci/tardive; Maj verificato anche con prima domenica il 1° o il 7 maggio. Cramârs esclusi dall'estate; sette racconti annuali privi di date inventate.

Le proiezioni con flag di approvazione sono create soltanto nei test. Non modificano gli oggetti di ricerca e non costituiscono pubblicazione o approvazione FUR.

## Verifiche e prossimo passo

**73 test superati in 10 file**, inclusi i 14 nuovi controlli di integrazione; lint frontend superato. Confronto strutturale rispetto all'inizio del passaggio: nei dieci record sono cambiati soltanto stato editoriale e metadati di preparazione; testi IT/FUR, fonti, ambiti, snapshot precedenti e gli altri dieci record sono invariati.

Non è stata eseguita una build: nessun codice runtime o asset è cambiato. Il prossimo passaggio editoriale è la revisione competente del FUR dei 17 candidati, mantenendo le cautele documentate. Solo dopo un'approvazione esplicita e tracciata si potrà promuovere un gruppo nel catalogo pubblico e ripetere i controlli. Il semplice salvataggio o commit non abilita le schede.
