# Anteprima Sagre — audit del 7 ottobre 2026

## Decisione

[Anteprima Sagre](https://www.anteprimasagre.it/) resta una **fonte
diagnostica**, senza schede pubblicate nel nuovo job. Gli articoli sono
editoriali e la data di pubblicazione o modifica WordPress non e' la data
della festa. Le categorie indicano provincia e mese, ma non provano l'anno
o il programma di un'edizione. La homepage mostra solo pochi articoli.

Al 7 ottobre l'inventario pubblico recente non contiene una festa FVG
futura con giorno, mese e anno 2026 esplicitamente confermati. La pagina
della [Sagra del Pan-Zal a Rosa](https://www.anteprimasagre.it/sagra-del-pan-zal-rosa-san-vito-al-tagliamento/)
parla del terzo e quarto fine settimana di ottobre e del patrono il 18,
ma dichiara: «Le date dell'edizione 2026 non sono ancora state comunicate».
Non si puo' trasformare quella consuetudine in date dell'edizione corrente.

## Inventario completo dell'orizzonte utile

- L'API WordPress pubblica espone **1.397 articoli**; i due file della
  [sitemap degli articoli](https://www.anteprimasagre.it/sitemap_index.xml)
  sommano **1.397 URL distinti**.
- La sitemap e l'API concordano su **347 articoli aggiornati nel 2026**.
  L'audit ha letto il testo HTML di tutti e 347, inclusi articoli FVG fuori
  dalle categorie provinciali.
- Aggiungendo gli articoli aggiornati nel 2025, l'orizzonte e' **423 post**.
  Quattro ricadono nella categoria `Area Riservata` e non entrano nel
  monitor periodico pubblico: **419 post** su cinque pagine API.
- Le ricerche dell'API per ottobre, novembre, dicembre 2026 e 2027 sono
  state incrociate con l'inventario: le poche pagine escluse dal filtro di
  modifica non contengono programmi futuri. La sola data 2026 trovata in
  una pagina modificata nel 2025 riguarda aprile, gia' passato.

Tra i post del 2026 con giorno e mese espliciti per ottobre, i programmi
provati finiscono il 3 o il 4 ottobre: la
[Mostra Regionale della Mela](https://www.anteprimasagre.it/mostra-regionale-della-mela-pantianicco/),
la [Festa dell'Agricoltura a Resiutta](https://www.anteprimasagre.it/festa-dellagricoltura-di-resiutta/),
la [Festa della Zucca a Bagnaria Arsa](https://www.anteprimasagre.it/festa-della-zucca-bagnaria-arsa/),
la Festa dei Cavoli Nostri e la Sagra di San Michele a Sacile. Pan-Zal e'
l'unico articolo recente che suggerisce una data futura senza provarne
l'edizione. Gli articoli di dicembre aggiornati a gennaio descrivono il
Natale **2025-2026**, non dicembre 2026.

## Controllo automatico nel ramo

`backend/app/events/pilot_anteprima_watch.py` usa l'API pubblica con
`modified_after` dall'inizio dell'anno precedente ed esclude la categoria
riservata. Riconcilia totale e pagine, rifiuta ID duplicati e risposte
parziali, quindi cerca nel solo HTML degli articoli date esplicite
giorno-mese-anno non passate. Date future esplicite fanno fallire il job
per revisione prima che possano diventare schede. Verifica anche le date
giorno-mese senza anno negli articoli recenti, senza trasformarle in date
pubblicabili. Il Pan-Zal e' una quarantena nota: una modifica del suo post
fa riaprire automaticamente la revisione.

La prova live del 7 ottobre ha letto **419 post in cinque pagine**, con
**zero date future provate** e **una quarantena nota** (Pan-Zal). Il monitor
non legge PDF o locandine e non scarica immagini. Quando una scheda futura
sarà confermata, serviranno prima il confronto con le altre fonti per
evitare doppioni e la scelta di un'anteprima tratta dal testo dell'edizione
corrente, escludendo appelli o contenuto promozionale.

Il monitor e' solo nel ramo, non nel job online. La verifica del primo ciclo
distribuito resta parte del rilascio complessivo. I test mirati del monitor,
del job e del registro fonti passano.
