# TurismoFVG: audit della scoperta eventi — 4 ottobre 2026

Ramo locale `codex/events-discovery-audit`. Nessuna pubblicazione o modifica al
catalogo cloud. Questo documento registra solo TurismoFVG; le altre fonti
richiedono contratti separati.

**Stato più recente (5 ottobre):** la data strutturata della scheda è il
riferimento primario. La correzione nell'ultima sezione sostituisce la
precedente conclusione sulle cinque schede future messe in quarantena.

## Risultato della raccolta generale

| Misura | Valore |
| --- | ---: |
| Pagine del catalogo percorse | 89 |
| Risultati dichiarati dal sito | 707 |
| Schede lette | 707 |
| URL distinti con dettaglio ispezionato | 652 |
| Record correlati automaticamente a un dettaglio | 588 |
| URL con dati non risolti | 64 |

Il valore 588 misura la corrispondenza fra scheda e dettaglio secondo le regole
attuali. Non dimostra che ogni intervallo rappresenti giorni consecutivi o che
ogni evento abbia una sola sede.

## Scoperta decisiva: ricerca ufficiale con date

Il modulo pubblico del sito espone `start` e `end`. Una raccolta diagnostica
separata ha percorso tutte le pagine delle finestre annuali. Il sito ha
restituito i seguenti valori durante la prova:

| Finestra | Schede dichiarate e lette | Pagine |
| --- | ---: | ---: |
| 4 ottobre–31 dicembre 2026 | 1816 | 228 |
| 2027 | 402 | 51 |
| 2028 | 0 | 1 |
| 2029 | 0 | 1 |
| **Totale** | **2218** | **281** |

Una ricerca aggiuntiva 2030–2099 ha restituito esplicitamente «Nessun evento
trovato». Il nuovo estrattore ripete questa verifica oltre le finestre annuali:
due anni vuoti da soli non provano l'assenza di eventi più lontani.

Le finestre filtrate contengono **1665 URL distinti** e 1793 schede con giorno
e mese nel badge. Il confronto con la lista generale di 707 schede/652 URL
mostra una **differenza netta di 1013 URL distinti** nelle finestre annuali, oltre a più
occorrenze di URL già presenti. La ricerca filtrata per
anno consente di assegnare un anno non ambiguo al badge. Per esempio, il
mercatino di Gemona ha badge 4 ottobre, 1 novembre e 6 dicembre 2026; la
scheda di Piero Poletto ha cinque date separate fra ottobre e novembre.

La prova filtrata ha impiegato circa **334 secondi**, prima di ispezionare i
1665 dettagli. Non entra nel budget attuale di 360 secondi per TurismoFVG.
Il nuovo modulo `pilot_regional_filtered.py` è per ora diagnostico; il job
pubblicato non lo usa. Il gate ora richiede esplicitamente prova delle finestre
annuali e della finestra successiva fino al 2099, così la lista generale non potrà essere dichiarata completa dopo
avere risolto soltanto i 64 casi precedenti. La fonte resta **non verificata**.
I conteggi sono snapshot del sito e possono cambiare.

Il vecchio lettore `fetch_turismofvg_events` interrogava filtri locali e di
categoria, apriva solo alcuni dettagli e si fermava raggiunto il limite di
risultati. Riutilizziamo la lettura dei campi delle schede, non quella soglia:
non era una prova di copertura dell'intera fonte.

## La sitemap e le schede dettaglio

`robots.txt` indica `https://www.turismofvg.it/sitemapcms`, con due file figli.
La lettura richiede circa 12 secondi e nella prova più recente elenca circa
2290 URL italiani sotto `/eventi/`. È un indice veloce da cui partire, ma
include anche pagine di categoria e schede non attuali. Inoltre, su 74 schede
campionate in vari punti del calendario filtrato, **due pagine valide erano
assenti dalla sitemap**: `vajont-un-puzzle-incompleto` e
`femart-2026-opposte-traiettorie-gli-archi-tra-venezia-e-la-mitteleuropa-500891`.

Ogni evento campionato ha una pagina dettaglio con campi visibili e descrizione.
Le pagine campionate non espongono però un oggetto `schema.org/Event` con
`startDate`: il campo data può essere una regola ricorrente o gli estremi di
una serie di appuntamenti. Le schede sono la fonte primaria per identità,
luogo e testo; il calendario filtrato fornisce le singole occorrenze quando
il dettaglio non le espone in una riga strutturata. `lastmod` nella sitemap
indica la modifica della pagina, non la data dell'evento.

Il piccolo indice sperimentale `pilot_regional_index.py` raggruppa le schede
filtrate per URL, conserva **tutti** i badge datati e segnala gli URL del
calendario assenti dalla sitemap. Al momento crea candidati solo dagli URL del
calendario: gli URL presenti solo nella sitemap non sono ancora classificati
tramite dettaglio. Per questo l'indice, pur utile alla prova, **non certifica
la completezza degli eventi futuri**.
Il conteggio degli URL della sitemap ancora non classificati è ora una
condizione esplicita del gate: finché è maggiore di zero, TurismoFVG non può
essere marcata come fonte completa.

Una prova locale end-to-end su due schede reali ha correlato il
[mercatino di Gemona](https://www.turismofvg.it/eventi/mercatino-delle-pulci-e-del-libro-usato-290796)
con i badge del 4 ottobre, 1 novembre e 6 dicembre 2026 e la
[Sagra della Castagna](https://www.turismofvg.it/eventi/40%C2%AA-sagra-della-castagna)
con i giorni 10, 11, 17, 18, 24 e 25 ottobre 2026. Titolo, comune e
date sono stati confrontati con le rispettive schede dettaglio. È una prova
di estrazione su quei due eventi, non una misura di copertura della fonte.

## Problemi distinti emersi

1. **Programmi con giorni separati.** La [Sagra della Castagna](https://www.turismofvg.it/eventi/40%C2%AA-sagra-della-castagna)
   ha sei date, ora tutte conservate. [GEOinCANEVA](https://www.turismofvg.it/eventi/geoincaneva-escursioni)
   dichiara un intervallo maggio–ottobre, ma nel testo elenca soltanto quattro
   domeniche. L'intervallo non può essere interpretato come attività quotidiana.
2. **Ricorrenze senza anno esplicito.** Il [mercatino di Gemona](https://www.turismofvg.it/eventi/mercatino-delle-pulci-e-del-libro-usato-290796)
   usa la regola «prima domenica del mese, escluso agosto». La data concreta
   deve essere generata da una regola verificata contro il calendario filtrato
   del sito; non basta aggiungere l'anno corrente al testo.
3. **Più comuni nello stesso evento.** [Castelli aperti](https://www.turismofvg.it/eventi/castelli-aperti-in-autunno-2026)
   dichiara molti comuni. Il modello attuale conserva una sola coppia di
   coordinate per record: assegnare arbitrariamente un comune produrrebbe
   risultati locali errati. Anche alcuni eventi con due comuni ricadono qui.
4. **Testo data incompleto o irregolare.** Alcune schede riportano solo un mese,
   una stagione, una regola settimanale o un intervallo senza anno. Tre record
   con data esplicita nella lista hanno inoltre un conflitto con il dettaglio.
   Vanno mantenuti in revisione fino a una prova strutturata sufficiente.
5. **Ordinamento dell'API.** `query_catalog` ordina oggi principalmente per
   distanza. L'ordinamento cronologico richiesto dall'utente è un problema di
   presentazione distinto dal riconoscimento di questa fonte.

## Controllo automatico aggiunto in questo ramo

- Ogni pagina deve mantenere lo stesso totale dichiarato; la somma delle
  schede deve raggiungerlo. Una paginazione troncata fallisce.
- Gli URL dei dettagli sono correlati alle schede; titoli, comuni, date e badge
  devono essere coerenti. Liste di giorni e calendari etichettati vengono
  letti senza trasformarli in intervalli continui.
- Il gate richiede zero URL irrisolti e tutti i dettagli controllati prima di
  qualificare TurismoFVG come fonte riuscita. Salva lo stato diagnostico per
  proseguire la verifica successiva; il job segnala il fallimento della fonte.
- I record già verificati in un precedente catalogo restano conservati per
  diagnosi, ma una discrepanza di contenuto li nasconde dalle risposte live.

## Contratto da completare prima di distribuire

1. Partire dalla sitemap per gli URL, aprire una volta le schede dettaglio e
   riconoscere solo quelle evento. Confrontare gli URL con le finestre annuali
   del calendario: aggiungere le schede assenti dalla sitemap e conservare
   i badge delle singole occorrenze. Un singolo job da 360 secondi non basta
   al controllo completo; separare indice, riconciliazione e dettagli con
   progressi versionati, senza promuovere una scansione interrotta.
2. Modellare esplicitamente intervalli continui, date sparse, ricorrenze e
   programmi con sessioni. Per le date sparse, associare ogni giorno alla
   località quando il sito fornisce tale associazione.
3. Rappresentare più località senza duplicare una singola manifestazione come
   se si tenesse integralmente in ogni comune. Dove mancano gli abbinamenti
   giorno/luogo, mantenere un evento regionale non localizzato e un'anomalia
   verificabile, oppure richiedere una fonte organizzatrice più precisa.
4. Incrociare automaticamente le ricorrenze e i programmi ambigui con i filtri
   data del sito e con eventuali pagine ufficiali collegate. Conservare la
   prova dell'associazione, non solo la data calcolata.
5. Ripetere la prova live fino a zero casi irrisolti, controllare un campione
   delle date e delle località estratte e solo allora valutare pubblicazione e
   ordinamento cronologico nell'API.

## Classificazione sitemap-only — snapshot del 5 ottobre 2026

Una nuova ricerca ufficiale con data iniziale 5 ottobre, paginata fino alla
fine e verificata contro i totali dichiarati, ha prodotto **2039 schede in
258 pagine**, pari a **1504 URL distinti**. La sitemap dello stesso snapshot
aveva **2160 URL** sotto `/eventi/`. Le differenze erano **16 URL presenti solo
nel calendario** e **672 presenti solo nella sitemap**. I conteggi cambiano
con il sito e con la data iniziale del filtro.

Il modulo locale `pilot_regional_sitemap_audit.py` salva l'indice nella
cartella ignorata `tmp/` e ispeziona gli URL sitemap-only in blocchi
riprendibili. Ogni risposta deve provenire dallo stesso URL fidato; gli
errori di recupero restano ritentabili. Non conserva il testo integrale delle
pagine né pubblica eventi. Tutti i **672 URL** sono stati letti senza errori
di recupero:

| Esito basato sulla scheda | URL |
| --- | ---: |
| Data o anno esplicito già passato | 613 |
| Pagina di navigazione, non scheda evento | 18 |
| Estremi della scheda includono una data futura, programma da verificare | 4 |
| Esperienza di lunga durata solo su prenotazione, senza appuntamenti pubblicati | 1 |
| Identità, ricorrenza o programma ambiguo | 36 |

I quattro candidati futuri sono
[Escursioni del Zarnic](https://www.turismofvg.it/eventi/escursioni-del-zarnic-vita-morte-e-miracoli-al-zarnic-2026),
[Gradisca Memory Experience](https://www.turismofvg.it/eventi/itinerario-turistico-gradisca-memory-experience-486982),
[Vecchi Ricordi](https://www.turismofvg.it/eventi/vecchi-ricordi-474441) e
[Xilomonsters](https://www.turismofvg.it/eventi/xilomonsters). La pagina delle
escursioni, per esempio, elenca sei appuntamenti distinti: l'intervallo
maggio–ottobre **non** è un evento quotidiano. Nessuno dei quattro è stato
aggiunto al catalogo pilot.

La scelta di prodotto confermata il 5 ottobre è: **Eventi comprende le
manifestazioni con programma e le attività con periodo di apertura definito**.
[Cjarsons e Vino](https://www.turismofvg.it/eventi/cjarsons-e-vino) descrive
invece un'esperienza enogastronomica prenotabile dal 12 giugno 2026 al 31
dicembre 2027, senza un calendario di appuntamenti nella scheda dettaglio.
Il dettaglio dice «solo su prenotazione»; l'intervallo è una finestra di
disponibilità, non un programma giornaliero. La ricerca storica contiene
quattro badge (31 luglio, 1, 3 e 4 agosto 2026): il report li conserva come
prova, senza trasformarli in un calendario futuro. La regola locale esclude
questa scheda solo quando coincidono categoria,
prenotazione esclusiva, durata lunga, descrizione di esperienza e assenza di
un calendario esplicito. Se un'offerta simile compare con badge futuri
puntuali, passa in verifica per conflitto di classificazione. Le schede meno
chiare restano da verificare. Il
controllo live non ha trovato caratteri sostitutivi nei campi estratti: gli
accenti corrotti visti nella console erano un problema di visualizzazione.

Un controllo mirato del filtro pubblico ha restituito Xilomonsters cercando
dal **1° agosto** al 31 dicembre 2026 e lo ha escluso cercando dal **5 ottobre**
alla stessa data finale. La sua [scheda dettaglio](https://www.turismofvg.it/eventi/xilomonsters)
indica 1° agosto–31 dicembre. Questo dimostra che iniziare la ricerca da oggi
può perdere eventi già iniziati e ancora attivi. La sitemap recupera questi
casi quando li indicizza, ma il controllo di copertura definitivo richiederà
anche una finestra retrospettiva e la riconciliazione del programma delle
schede trovate.

Dei 36 ambigui, 17 non riportano un anno nel campo data, 15 contengono un
possibile avviso di modifica o annullamento, 3 hanno una data del 2026 senza
giorno verificabile e 1 è una ricorrenza non espandibile dalla sola scheda.
Restano fuori dalla pubblicazione finché la verifica automatica non trova una
prova sufficiente.

## Ricerca retrospettiva e riconciliazione — 5 ottobre 2026

La ricerca ufficiale con filtri data è stata percorsa anche all'indietro, dal
1° gennaio 2026 al 4 ottobre e poi anno per anno fino a due anni vuoti
consecutivi. La finestra residua 1900–2017 ha restituito zero risultati. I
totali dichiarati sono stati confrontati con tutte le schede lette. Il
risultato è **1409 schede / 923 URL distinti**: 690 schede nel 2026, 9 nel
2025, 2 nel 2024, 250 nel 2023, 448 nel 2022, 5 nel 2021 e 5 nel 2020.
Le finestre 2019 e 2018 sono vuote. Di questi URL, **660 non compaiono nella
ricerca futura**; 654 sono nella sitemap e 6 sono esterni sia alla sitemap
sia alla ricerca futura. I sei sono stati letti: cinque schede già passate e
una pagina HTTP 404. L'unione dei tre indici contiene **2182 URL**.

Questa prova ha trovato un difetto concreto del filtro futuro: una mostra
già iniziata come [Xilomonsters](https://www.turismofvg.it/eventi/xilomonsters)
compare cercando dal suo giorno iniziale ma sparisce quando la ricerca parte
da oggi, benché la scheda indichi un'apertura fino al 31 dicembre. La scheda
di [Gradisca Memory Experience](https://www.turismofvg.it/eventi/itinerario-turistico-gradisca-memory-experience-486982)
indica un programma venerdì–domenica fino a novembre, ma il filtro futuro non
la elenca; le schede retrospettive mostrano 47 badge passati. Per
[Escursioni del Zarnic](https://www.turismofvg.it/eventi/escursioni-del-zarnic-vita-morte-e-miracoli-al-zarnic-2026)
il badge retrospettivo del 24 agosto confligge con il calendario di sei date
nel dettaglio. Per [Vecchi Ricordi](https://www.turismofvg.it/eventi/vecchi-ricordi-474441)
la regola «seconda domenica» ha eccezioni storiche: non si possono generare
automaticamente tutte le date future senza confrontarle con il programma
ufficiale aggiornato.

Il modulo `pilot_regional_reconcile.py` registra i conflitti e non promuove
nessuna delle quattro schede future. I 36 ambigui sono in quarantena. Il
report mantiene `publication_ready: false`. Il controllo retrospettivo è ora
richiesto anche dal gate della fonte, ma non è ancora collegato a un job di
produzione entro il budget di 360 secondi.

## Tutte le schede del calendario futuro e descrizioni — 5 ottobre 2026

`pilot_regional_forward_audit.py` ha aperto tutte le **1504 schede distinte**
del calendario futuro, in blocchi riprendibili. Dopo la correzione del confronto
fra URL Unicode e URL HTTP codificati, sono rimasti **zero errori di lettura**.
La seconda passata ha riletto le schede allineate per ottenere una descrizione
da anteprima, senza conservare la pagina o il testo integrale. Due schede
prima allineate sono passate in revisione al ricontrollo.

| Risultato | URL |
| --- | ---: |
| Identità e limiti delle date coerenti fra badge e dettaglio | 1370 |
| Scarto, avviso di variazione o dati insufficienti | 133 |
| Esperienza lunga solo su prenotazione | 1 |

**Coerenza dei limiti non significa programma completo.** Delle 1370 schede
coerenti, 905 hanno una data singola e 3 un elenco di date esplicite. Le altre
si dividono in 302 intervalli che richiedono prova del programma o dell'apertura,
155 intervalli con badge che richiedono interpretazione dei giorni effettivi,
4 ricorrenze da espandere e 1 elenco in conflitto. Per esempio,
[Sapori nelle Valli](https://www.turismofvg.it/eventi/10-edizione-fiera-mercato-sapori-nelle-valli)
indica un arco di 23 giorni ma nella descrizione parla di quattro weekend;
non va pubblicato come 23 giorni consecutivi.

La preview dell'app conosce già i campi `description_excerpt` e fonte. Nel
nuovo controllo **1285 delle 1370 schede coerenti** hanno un estratto breve
attribuito, massimo 180 caratteri; **85** restano senza anteprima: 6 senza
descrizione utilizzabile e 79 con un estratto identico condiviso da schede
con titoli diversi. Le schede con lo stesso titolo possono mantenere la stessa
descrizione anche se hanno URL diversi. La mancanza di una
descrizione non diventa testo inventato. L'anteprima si collega all'URL della
scheda da cui è stata estratta. Gli estratti sono diagnostici locali: nessun
catalogo cloud è stato modificato.

## Programmi nelle descrizioni — seconda passata del 5 ottobre 2026

`pilot_regional_semantic_audit.py` ha riletto tutte le **462** schede con
intervallo, ricorrenza o badge da interpretare, senza errori di recupero. Legge
il testo integrale per controllare il programma, poi conserva solo fatti
diagnostici brevi. Il risultato conservativo è:

| Esito | Schede |
| --- | ---: |
| Elenco esplicito ed esaustivo di date | 5 |
| Apertura settimanale esplicita | 5 |
| Giorni interni non ricostruiti automaticamente | 452 |

Il primo riconoscitore aveva marcato 74 elenchi di date come completi. La
[Mostra Maruzzella](https://www.turismofvg.it/eventi/mostra-maruzzella) ha
mostrato il falso positivo: il dettaglio indica inaugurazione il 2 ottobre e
visite dal 3 all'11, mentre il riconoscitore ricavava solo il 2 e l'11. La
regola è stata ristretta ai calendari esplicitamente presentati come completi;
le 79 schede inizialmente considerate risolte sono state rilette. La nuova
classificazione non trasforma titoli di paragrafi datati in un calendario
esaustivo. Fra i casi davvero espliciti vi sono le sei date della
[41ª Festa delle Castagne](https://www.turismofvg.it/eventi/41-festa-delle-castagne)
e il [calendario aperture del Parco delle Ferrovie](https://www.turismofvg.it/eventi/apertura-parco-ferrovie-dello-stella-498119).
Per [14° Oktoberfest](https://www.turismofvg.it/eventi/14-oktoberfest) un
badge non compare nei giorni elencati nel dettaglio: resta in revisione.

I 452 casi comprendono 294 intervalli senza prova dell'apertura quotidiana,
153 intervalli con badge da interpretare, 4 ricorrenze e 1 elenco discordante.
Questa classificazione riguarda la ricostruzione delle singole giornate:
**non è necessaria per una scheda che mostra una volta sola il periodo
dichiarato e rimanda alla fonte**. Gli scarti veri fra badge e dettaglio
restano invece anomalie da controllare.

## Scarti calendario/dettaglio — terza passata del 5 ottobre 2026

`pilot_regional_discrepancy_audit.py` ha riletto tutte le **133** schede in
revisione, senza errori di recupero. Dopo il chiarimento sugli avvisi e due
varianti comunali verificate e i punti mappa della fonte, **85** hanno identità
e limiti delle date nuovamente coerenti, ma non sono state promosse: 56 hanno
una data singola e 29 un periodo. **48** restano in revisione. Le cause rilevate possono
sovrapporsi:

| Causa | Schede |
| --- | ---: |
| Più comuni senza associazione fra date e luoghi | 31 |
| Località senza punto mappa utilizzabile | 1 |
| Altra regola di correlazione o policy | 6 |
| Vero avviso di modifica del programma | 3 |
| Campo data non analizzabile | 3 |
| Anno assente dal campo data | 3 |
| Titolo della lista diverso dal titolo del dettaglio | 2 |

Il vecchio rilevatore di avvisi trattava anche «sospeso tra realtà e fantasia»
e «annullato in caso di maltempo» come modifiche già avvenute. La regola
condivisa ora distingue i contesti ipotetici e figurati. Le 58 schede prima
segnalate sono state rilette; tre contengono un vero avviso di modifica. Per
esempio, il [Mercatino di Ponterosso](https://www.turismofvg.it/eventi/mercatino-di-ponterosso-478819)
è previsto per una data definita e riporta una condizione meteo, non una
cancellazione già comunicata.

Le 29 località erano solo cinque forme: Duino-Aurisina (13), San Dorligo della
Valle - Dolina (10), Sistiana (4), Aprilia Marittima (1), Piancavallo (1).
Le prime due sono varianti del nome di un comune, confermate dal
[registro SUAP regionale](https://suap.regione.fvg.it/portale/cms/it/.content/config/templates/lista_comuni.jsp)
e dal [Comune di San Dorligo della Valle](https://www.comune.san-dorligo-della-valle.ts.it/).
L'adapter le risolve nel catalogo comunale: le 23 schede sono state rilette e
ora si allineano. Le altre sei richiedevano un punto geografico più preciso,
perché un centroide comunale può dare una distanza locale sbagliata. Cinque
schede espongono una coppia numerica nella mappa del dettaglio: sono state
rilette e ora si allineano con confidenza `source_map`. Una non espone un
punto valido e resta in revisione. [Sistiana](https://comune.duino-aurisina.ts.it/it/turismo-14716/come-arrivare-14719),
[Aprilia Marittima](https://www.comune.latisana.ud.it/media/files/030046/attachment/NET_All.B_Latisana.pdf)
e [Piancavallo](https://www.comune.aviano.pn.it/it/vivere-il-comune-212828/luoghi-233934/il-piancavallo-269880)
sono località da geocodificare senza perdere il nome di luogo fornito dalla
fonte. Un evento in più comuni è un terzo caso distinto.

## Finestra operativa per il pilota

Per il normale aggiornamento basta controllare l'**anno in corso** con il
filtro ufficiale, confrontarlo con la sitemap e rileggere i dettagli nuovi o
modificati. La ricerca retrospettiva pluriennale è stata una prova diagnostica
di copertura, non un'operazione da ripetere a ogni ciclo. Il filtro va
interrogato dall'inizio dell'anno: partire dal giorno corrente perde eventi
iniziati prima ma ancora aperti. La sitemap e i dettagli già verificati
servono anche a recuperare i rari eventi iniziati nell'anno precedente che
proseguono in quello corrente. Gli eventi del prossimo anno entreranno nella
raccolta ordinaria al cambio d'anno, salvo diversa scelta di prodotto.

## Scheda semplice confermata dall'utente

La sezione Eventi mostra **una scheda per URL di dettaglio**: titolo, periodo
o data riportati dalla fonte, luogo, breve descrizione attribuita quando
disponibile e collegamento alla pagina originale. Non presenta un intervallo
come un elenco di giornate di apertura. L'utente apre la pagina ufficiale per
orari e programma completo. Gli eventi già iniziati ma ancora compresi nel
periodo sono ordinati fra quelli in corso, poi seguono le nuove date.

`pilot_regional_display_audit.py` ha applicato questo criterio allo snapshot
locale: **1150 schede candidate per il resto del 2026**, di cui 715 a data
singola, 432 con periodo e 3 con date esplicite. **1070** hanno un'anteprima
breve attribuita; le altre mantengono il link alla fonte. **27** schede
allineate sul piano generale restano fuori per date non leggibili, modifiche
della pagina o contraddizioni specifiche. La prova incorpora anche le 85
schede riallineate alla terza passata e quattro dettagli recuperati dalla
sitemap, assenti dal filtro calendario. Lo snapshot contiene 1508 candidati
totali, inclusi quelli soltanto del 2027: non va letto come tasso di copertura
del solo 2026.

Le quattro schede recuperate sono [Escursioni del Zarnic](https://www.turismofvg.it/eventi/escursioni-del-zarnic-vita-morte-e-miracoli-al-zarnic-2026),
[Gradisca Memory Experience](https://www.turismofvg.it/eventi/itinerario-turistico-gradisca-memory-experience-486982),
[Vecchi Ricordi](https://www.turismofvg.it/eventi/vecchi-ricordi-474441) e
[Xilomonsters](https://www.turismofvg.it/eventi/xilomonsters). I rispettivi
dettagli ufficiali sono stati riletti: identità, date e anteprime risultano
coerenti. Le 1150 schede diagnostiche superano il controllo della policy
locale (`validate_candidate`) senza errori.

Per una prova nell'app mancano ancora il collegamento di queste schede al
catalogo locale, il trattamento dei **48** scarti persistenti (fra cui
località e più comuni), e il controllo incrementale di completezza. Il modulo diagnostico non pubblica
nulla. Nessuna prova su dispositivo né pubblicazione è stata eseguita.

## Aggiornamento conclusivo del 5 ottobre 2026: indice annuale e controllo ripetibile

I numeri precedenti descrivono passate diagnostiche. La base più recente usa
l'intero **anno in corso** dal filtro ufficiale, la sitemap e i dettagli. Il
filtro ha dichiarato **2260 schede in 283 pagine**: tutte le pagine e i
conteggi sono stati verificati. Le schede corrispondono a **1353 URL**; la
sitemap ne elenca **2160**; l'unione è di **2254 URL**, inclusi **94 presenti
solo nel calendario**. Il controllo rifiuta pagine mancanti, conteggi
discordanti, URL non affidabili e schede di calendario identiche ripetute.

`pilot_regional_year_control.py` conserva un'impronta per ogni URL basata su
identità, badge del calendario e `lastmod` della sitemap. Nelle esecuzioni
successive rilegge subito le schede nuove o cambiate e rinnova comunque le
verifiche: dopo un giorno per i dettagli allineati, trenta per quelli
passati o non pertinenti, un giorno per i casi ambigui o in revisione. I
batch sono riprendibili. Un URL futuro che sparisce sia dal calendario sia
dalla sitemap blocca il segnale di completezza finché non viene chiarito.
Una variazione della versione del parser invalida il riuso dei dettagli.
Questo è un controllo automatico eseguibile, ma **non è ancora collegato allo
scheduler o al catalogo pubblicato**.

La prima lettura annuale e la rilettura mirata hanno ispezionato **2254/2254
URL**, senza tentativi di rete pendenti. Gli esiti sono: 1548 dettagli
allineati, 613 eventi passati, 20 URL non evento, 2 esperienze prenotabili
escluse, 36 ambigui e 35 in revisione. Fra gli ultimi 71, **16** hanno un
badge dal 5 ottobre in poi; gli altri **55** non hanno tale prova nel
calendario corrente. Nessuno dei 71 è promosso automaticamente. La
disponibilità della fonte è quindi
`source_complete=false`.

`pilot_regional_display_audit.py --annual-control` produce direttamente dal
controllo annuale **1267 schede** per il resto del 2026: 780 a data singola,
479 con periodo, 4 con date esplicite e 4 ricorrenti. **1176** hanno
un'anteprima descrittiva attribuita al dettaglio ufficiale; per le altre 91
rimane il link. Ogni scheda usa un URL di dettaglio unico, passa la policy
locale ed è ordinata dalla data corrente o dalla prossima data disponibile.
La scheda indica il periodo senza inventare un'apertura quotidiana. Due
pagine con il prefisso «Calendario:» nella descrizione sono state rilette
e ammesse come periodo, perché identità, estremi strutturati e badge
coincidono. Il parser non pretende di ricostruire tutte le giornate del
programma per mostrare una sola scheda. L'indice
annuale ha inoltre rivelato due vecchi URL della sitemap che ora danno 404:
non compaiono nelle 1264 schede. Uno ha un'altra scheda valida all'URL
`festa-della-birra-e-delle-castagne-2026`.
Un altro falso scarto derivava da una data biografica del 1896 nel testo:
il parser ora distingue quel riferimento dalle date del programma 2026.

I **16** casi con badge futuri ancora in revisione si distribuiscono così:

| Motivo del blocco | Schede |
| --- | ---: |
| Giorni descritti fuori dagli estremi strutturati | 5 |
| Badge assente dal programma esplicito | 3 |
| Identità o calendario del dettaglio non coerenti | 3 |
| Badge incompatibile con i giorni di apertura dichiarati | 1 |
| Data strutturata non abbastanza esplicita | 1 |
| Dettaglio cambiato dopo l'indicizzazione | 1 |
| Possibile variazione del programma | 1 |
| Esperienza prenotabile con badge datato | 1 |

Fra i cinque scarti sugli estremi, il dettaglio di
[Autumn Leaves](https://www.turismofvg.it/eventi/autumn-leaves-504100)
include un concerto il 10 ottobre ma dichiara il periodo dal 16 ottobre;
[L'ora del racconto](https://www.turismofvg.it/eventi/l-ora-del-racconto-503683)
menziona il 17 dicembre oltre il termine strutturato dell'11 dicembre.
Altre pagine citano eventi collegati o mostre con un periodo diverso. La
regola non deve includere né scartare automaticamente quelle date senza
capire quale parte della pagina appartiene alla scheda corrente.

Per ripetere il controllo in locale, dal percorso `backend`:

```powershell
python -B -m app.events.pilot_regional_year_control --collect --previous ../tmp/turismofvg-year-control-2026-10-05.json --snapshot ../tmp/turismofvg-year-control-NEXT.json
python -B -m app.events.pilot_regional_year_control --batch 24 --snapshot ../tmp/turismofvg-year-control-NEXT.json
python -B -m app.events.pilot_regional_display_audit --annual-control ../tmp/turismofvg-year-control-NEXT.json --output ../tmp/turismofvg-annual-display-NEXT.json
```

Ripetere `--batch` finché `pending=0` e `attempts=0`. La proiezione delle
schede richiede l'ispezione di tutti gli URL dell'inventario. I file in `tmp`
sono prove locali ignorate da Git; il comando non modifica l'app né il cloud.
I 16 casi futuri sono stati riletti come descritto sotto. La prova in memoria
qui annotata ha preceduto la verifica nell'interfaccia; i conteggi aggiornati
del pilota locale sono nella sezione finale.

## Rilettura mirata dei 16 casi futuri — 5 ottobre 2026

Sono stati riscaricati e conservati localmente i dettagli ufficiali delle
16 pagine con badge futuri ancora in revisione. Le regole aggiunte sono
generali e richiedono prove incrociate: una data sostitutiva deve coincidere
con dettaglio e badge; un programma che corregge un estremo errato deve
elencare **esattamente** le stesse date del calendario; un intervallo di
apertura nel testo deve avere giorni della settimana coerenti. Le date di
altre escursioni o della mostra principale vengono separate solo quando la
pagina le presenta con un'etichetta esplicita e il programma dell'evento
coincide con tutti i badge.

**Correzione del criterio, 5 ottobre 2026.** Nella scheda TurismoFVG la riga
data è un campo strutturato e prevale sull'elenco delle singole attività nel
testo libero. Avevamo erroneamente messo in revisione cinque eventi perché il
testo non ripeteva tutte le date del calendario, anche se la riga data e i
badge erano coerenti. La descrizione resta utile per l'anteprima e per avvisi
espliciti di variazione; non serve a dedurre che l'evento sia aperto ogni
giorno dell'intervallo.

| Esito dei 16 dettagli riletti con il criterio corretto | Schede |
| --- | ---: |
| Ammesse con dettaglio e calendario verificati | 15 |
| Esperienza prenotabile senza programma, esclusa | 1 |
| Ancora in revisione per scarto tra testo libero e data strutturata | 0 |

La [32ª Festa delle Zucche](https://www.turismofvg.it/eventi/32-festa-delle-zucche)
e [Letture piccolissime](https://www.turismofvg.it/eventi/letture-piccolissime)
hanno un estremo strutturato errato, ma calendario e programma testuale
coincidono per tutte le rispettive date: la scheda mostra il periodo tratto
dal programma e il numero di date, con link al dettaglio. Per
[Sistiana](https://www.turismofvg.it/sistiana) si usa il punto numerico
pubblicato dalla stessa fonte per la ricerca geografica, con confidenza
`source_locality`; il punto non è presentato come sede esatta dell'evento.
[Udine Antiqua](https://www.turismofvg.it/eventi/udine-antiqua-494198)
riporta una data posticipata che coincide con campo data e badge.
[Vino e Frico in Equilibrio](https://www.turismofvg.it/eventi/vino-e-frico-in-equilibrio-491128)
è escluso come esperienza prenotabile senza programma di evento.

Le cinque schede prima escluse —
[14° Oktoberfest](https://www.turismofvg.it/eventi/14-oktoberfest),
[Amélie - Il Musical](https://www.turismofvg.it/eventi/amelie-il-musical),
[Autumn Leaves](https://www.turismofvg.it/eventi/autumn-leaves-504100),
[In viaggio nelle memorie ritrovate: eventi speciali](https://www.turismofvg.it/eventi/in-viaggio-nelle-memorie-ritrovate-eventi-speciali-in-galleria)
e [L'ora del racconto](https://www.turismofvg.it/eventi/l-ora-del-racconto-503683) —
sono state rielaborate dai dettagli ufficiali salvati il 5 ottobre. Tutte
hanno riga data, identità e badge compatibili e producono una scheda unica
con link al dettaglio. Per Amélie il periodo è **16–19 ottobre 2026**.

La proiezione locale corretta, ottenuta ripetendo la lettura di queste cinque
pagine sul controllo completo del 5 ottobre, comprende **1282 schede** per il
resto del 2026 e **1191 anteprime**. La classificazione diventa 1563 dettagli
allineati, 613 eventi passati, 20 URL non evento, 3 esperienze escluse, 36
ambigui e 19 in revisione su **2254/2254 URL** esaminati. I restanti 55 casi
incerti non sono stati risolti da questa correzione; `source_complete=false`.
Il controllo prevede di rileggere i dettagli allineati dopo 24 ore quando
viene eseguito, ma non è ancora schedulato né collegato alla pubblicazione.
Nessuna scheda è stata pubblicata.

## Prova nell'interfaccia locale — 5 ottobre 2026

`pilot_regional_local_preview.py` proietta il controllo annuale in una
risposta HTTP disponibile solo su `127.0.0.1`. Il servizio accetta soltanto
la fotografia del giorno, conserva una scheda per URL ufficiale, applica il
raggio e restituisce le pagine nello stesso ordine di data. Indica
`source_complete=false` e il numero di casi in quarantena; dopo il cambio
di giorno rifiuta la fotografia scaduta. Non modifica il catalogo cloud.

Per ripetere **il 5 ottobre** la stessa prova, dal percorso `backend`:

```powershell
python -m app.events.pilot_regional_local_preview --prepare --control ../tmp/turismofvg-year-control-2026-10-05.json --manifest ../tmp/turismofvg-review16-2026-10-05.json --html-dir ../tmp/turismofvg-review-html-2026-10-05 --display ../tmp/turismofvg-local-preview-2026-10-05.json
python -m app.events.pilot_regional_local_preview --serve --display ../tmp/turismofvg-local-preview-2026-10-05.json --port 8767
```

In un secondo terminale, dalla radice del progetto:

```powershell
$env:VITE_LOCAL_EVENTS_PROXY_TARGET = 'http://127.0.0.1:8767'
.\scripts\start-local-weather-pilot.ps1 -WeatherTestNow '2026-09-04T12:00:00Z'
```

L'orologio di prova riguarda solo i dati meteo offline, la cui fotografia
locale era scaduta. Gli eventi usano la data corrente del browser e del
servizio. Il 6 ottobre o successivamente occorre prima creare un nuovo
controllo annuale e una nuova proiezione: non riutilizzare questi file.

La UI canonica su porta 5174 è stata verificata con Udine, raggio 20 km,
filtro **Prossimi / Musica**. Amélie compare in ordine al 16 ottobre; la
scheda mostra **16–19 ottobre 2026**, l'anteprima tratta dalla descrizione
e il link alla [pagina ufficiale](https://www.turismofvg.it/eventi/amelie-il-musical).
Anche la Sagra del Rosario a Pordenone mostra il periodo e l'anteprima.
Il servizio locale restituisce 352 URL per Udine nel raggio di 20 km, ma i
55 URL ancora incerti restano fuori dalle schede. Questa prova non rende
la fonte completa e non sostituisce la verifica su dispositivo reale.

## Revisione delle 55 pagine escluse — 5 ottobre 2026

Tutte le 55 pagine sono state riscaricate e lette sulla fonte ufficiale.
Il [report per URL](EVENTI_TURISMOFVG_REVIEW_55_2026-10-05.md) registra
data dichiarata, giudizio e motivo. Otto pagine ora passano i controlli
automatici; la proiezione locale aggiornata contiene **1290 schede**, di cui
**1199 con anteprima**. Venticinque pagine non devono comparire nell'elenco
degli eventi futuri del 2026; 22 richiedono il recupero di una data o la
verifica dell'anno. Il motore conserva ancora **36 URL in quarantena** perché
14 esclusioni motivate dalla revisione non sono ancora codificate come regole
automatiche. `source_complete=false`; nessuna pubblicazione.

Per riprodurre la proiezione aggiornata **nello stesso giorno**, rileggendo
sia i 16 dettagli precedenti sia le 55 pagine ora verificate, da `backend`:

```powershell
python -m app.events.pilot_regional_local_preview --prepare --control ../tmp/turismofvg-year-control-2026-10-05.json --manifest ../tmp/turismofvg-review-all-manifest-2026-10-05.json --html-dir ../tmp/turismofvg-review-all-html-2026-10-05 --display ../tmp/turismofvg-local-preview-reviewed-2026-10-05.json
python -m app.events.pilot_regional_local_preview --serve --display ../tmp/turismofvg-local-preview-reviewed-2026-10-05.json --port 8767
```

## Controllo successivo delle 55 pagine — 5 ottobre 2026

Le cifre sopra descrivono la prima revisione. Il [rapporto per URL aggiornato](EVENTI_TURISMOFVG_REVIEW_55_2026-10-05.md#secondo-passaggio-regole-automatiche-e-recupero-verificato)
documenta le regole applicate in seguito: **1295 schede locali**, **1204
anteprime**, **17 URL in quarantena**, `source_complete=false`. Cinque pagine
con programma confermato sono state recuperate; le altre restano sospese
quando la fonte non prova l'anno o il formato corrente non rappresenta la
data senza inventarla. Il pilot locale usa
`tmp/turismofvg-local-preview-recovered-2026-10-05.json`. Nessuna
pubblicazione o promozione su `main` è stata eseguita.

### Priorità successiva: date nella scheda HTML

Il controllo locale non apre PDF. Recupera dall'HTML ufficiale il periodo
verificato di “C'era una volta…” e conserva per “Memorie riflesse” solo la
scadenza pubblicata, senza data iniziale. Il [rapporto per URL](EVENTI_TURISMOFVG_REVIEW_55_2026-10-05.md#priorita-alle-date-html-allegati-fuori-dal-job)
registra **1297 schede**, **1206 anteprime** e **15 URL sospesi**.
