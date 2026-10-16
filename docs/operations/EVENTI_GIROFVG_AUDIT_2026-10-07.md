# GiroFVG — audit del 7 ottobre 2026

## Decisione

[GiroFVG](https://www.girofvg.com/eventi) e' un **indice di scoperta**, non
una fonte da pubblicare automaticamente nel catalogo. Le sue schede hanno
campi separati `Data inizio`, `Data fine` e `Luogo`, ma il confronto tra
campi, testo e organizzatori ha trovato errori nell'edizione corrente.
Un campo strutturato da solo non prova una data. I candidati unici vanno
ricondotti alla pagina dell'organizzatore e confrontati con le schede gia'
presenti; una copia da GiroFVG produrrebbe doppioni o date errate.

## Copertura della prova

- La [sitemap XML](https://www.girofvg.com/index.php?option=com_jmap&view=sitemap&format=xml)
  contiene 12.297 URL distinti. L'audit ha letto i dettagli dei 207 URL con
  `lastmod` nel 2026 e di altri sei URL che contengono `2026` nel percorso:
  213 richieste, zero errori HTTP. In 188 dettagli erano presenti i campi
  data; 17 avevano una data di fine non passata al 7 ottobre.
- Le sette categorie di [Eventi](https://www.girofvg.com/eventi) sommano
  90 pagine di archivio. La scansione indipendente ne ha lette 89, con
  1.793 tessere e 16 URL distinti con fine non passata. La pagina
  [`fiere-e-mostre?start=168`](https://www.girofvg.com/fiere-e-mostre?start=168)
  restituisce stabilmente HTTP 500, anche al nuovo tentativo. Le pagine
  adiacenti sono di eventi del 2021-2020 e del 2008: l'errore e' isolato
  in una zona storica dell'archivio, ma impedisce di chiamare completo il
  controllo di tutte le pagine. Il dettaglio del Premio Rilke compare
  nella sitemap e non nei 16 URL attivi degli archivi letti.
- L'home Eventi mostra solo una selezione. Leggere la sola home o la prima
  pagina di ogni categoria avrebbe perso almeno due schede con intervallo
  ancora aperto (Treni storici e Digital Art Gallery) e il Premio Rilke.

Il file locale ignorato `.dev-logs/events-girofvg-2026-10-07/audit.json`
contiene i dettagli dei 213 candidati; `category-scan.json` conserva URL,
conteggi e l'errore della scansione indipendente.

## Riconciliazione delle 17 schede con fine non passata

| Gruppo | Esito |
| --- | --- |
| DuinoBook/Aquileia, Festa della Zucca, Sapori del Carso, Barcolana, Il Dialogo/Illegio, Una Sfinge l'attrae, Il Vangelo di Marco | Manifestazioni gia' coperte da TurismoFVG con titolo talvolta diverso; non creare una seconda scheda. [Il Dialogo](https://www.turismofvg.it/eventi/dialogo) e' nel catalogo regionale con le [date ufficiali](https://illegio.it/archivio-mostre/). |
| Giornate del Cinema Muto | L'adattatore del sito ufficiale ha il programma, con un intervallo piu' ampio di quello indicato da GiroFVG. |
| Laguna in Tecja | Articolo che raccoglie sedici partenze; TurismoFVG pubblica gia' singole partenze datate. Confrontare eventuali partenze mancanti, senza aggiungere un evento padre duplicato. |
| Feste delle castagne, Giornate FAI d'Autunno, Giornata delle Ville Venete, Treni storici | Articoli che aggregano piu' luoghi, visite o corse. Occorrono le schede dei singoli programmi; l'intervallo dell'articolo non equivale ad apertura quotidiana. |
| Domenica al Museo, Digital Art Gallery Gorizia | Ricorrenza nazionale generica e installazione permanente senza programma distinto: fuori dal criterio concordato «solo eventi con programma». |
| Premio Rilke | Il periodo nei campi include le candidature, con scadenza 30 settembre; non e' un evento continuativo fino alla premiazione. La cerimonia va verificata presso l'organizzatore prima di creare una scheda. |
| Nave Amerigo Vespucci, Trieste | **Candidato realmente scoperto:** assente dai 1.418 record del controllo TurismoFVG del 7 ottobre. L'[organizzatore Barcolana](https://www.barcolana.it/it/news/2026/nave-amerigo-vespucci-e-il-villaggio-in-italia-in-arrivo-a-trieste-per-la-conclusione-del-tour-mondiale-vespucci-campagna-in-nord-america-2026) conferma sosta, visite e programma dall'8 al 12 ottobre. L'[audit iniziale Barcolana](EVENTI_BARCOLANA_AUDIT_INIZIALE_2026-10-07.md) ne conserva la prova per la scheda unica del festival. |

## Incoerenze che vietano la copia automatica

- [Il Vangelo di Marco](https://www.girofvg.com/vangelo-marco-aquileia-mostra-2026-2027)
  ha `Data fine = 25-04-2028`, mentre il testo dell'articolo e la
  [Fondazione Aquileia](https://www.fondazioneaquileia.it/it/eventi/il-vangelo-di-marco-sette-secoli-tre-frammenti-un-racconto-europeo)
  confermano **25 aprile 2027**.
- [Sapori del Carso 2026](https://www.girofvg.com/sapori-del-carso-okusi-krasa-2026)
  ha date e corpo dell'edizione 2026, ma il primo paragrafo di anteprima
  parla ancora dell'edizione **2025**. Prenderlo come descrizione preview
  mostrerebbe testo sbagliato.
- Immagini in articoli correnti puntano a file di anni precedenti (per
  esempio Laguna in Tecja 2025 e Nave Vespucci 2022). Ne' l'immagine ne'
  la prima frase vanno usate senza controllo dell'edizione.

## Controllo automatico da preparare

Per rendere GiroFVG un indice diagnostico nel job occorre sorvegliare
sitemap e sette categorie con confronto incrementale degli URL e dei campi
data/luogo, segnalare schede nuove o mutate e conservare la lista di
eccezioni note. Una scheda segnalata non va pubblicata finche' data, luogo,
programma, anteprima e immagine non sono confermati dall'organizzatore e
non si e' verificata la deduplica. Il controllo deve registrare anche i
fallimenti di paginazione (compreso l'HTTP 500 noto), senza fingere che una
lista parziale sia completa. Non servono PDF, locandine o download delle
immagini nel ciclo periodico.

Questo audit e' sul ramo `codex/events-discovery-audit`; non modifica il
job online e non chiude ancora il monitor automatico di GiroFVG.

Il [monitor diagnostico dell'8 ottobre](EVENTI_GIROFVG_MONITOR_2026-10-08.md)
e' ora integrato nel codice del job sul ramo. La prova live riproduce
12.297 URL, 89/90 pagine e 1.793 tessere, con zero novita' da revisionare.
La pagina storica in HTTP 500 resta esplicitamente non letta; il ramo non
e' stato distribuito.
