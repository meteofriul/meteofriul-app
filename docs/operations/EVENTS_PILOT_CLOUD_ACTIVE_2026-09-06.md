# Eventi pilota — pubblicazione 6 settembre 2026

Solo progetto `meteofriul-pilot-20260906`, regione `europe-west1`.
Beta `meteo-friul` non modificata.

## Risorse

- Job `pilot-events`: 1 CPU, 512 MiB, timeout 900 s, un task, zero retry.
- Servizio HTTPS: https://pilot-events-335641913741.europe-west1.run.app
- Lettura `/api/local/events?lat=45.9569&lon=12.6605&radius=20&limit=100`.
- Scheduler `pilot-events-refresh`, abilitato ogni giorno alle 04:00 UTC
  (06:00 italiane in estate, 05:00 in inverno).
- Catalogo privato `gs://meteofriul-pilot-20260906-data/pilot/events/v1/catalog.json`.
- Identità separate `pilot-events-writer` e `pilot-events-reader`, permessi
  condizionati al solo oggetto del catalogo. Scheduler usa `pilot-scheduler`.
- Nessuna raccolta in background dentro le richieste HTTP; cache lettura 60 s.
- Scrittura con precondizione sulla generazione per evitare sovrascritture concorrenti.

## Verifiche e copertura

Prima raccolta remota riuscita: `pilot-events-l8qh7`.
Il secondo avvio tramite scheduler, `pilot-events-rrhnv`, è terminato con successo
alle 20:32:35 UTC. Verificata anche la risposta Udine/20 km: 31 appuntamenti.
Primo catalogo: Pordenonelegge 445, Azalea 6, CSS 29,
Pordenone Pensa 5, Verdi Pordenone 52, Verdi Trieste 10 appuntamenti.
Non sono tutti eventi distinti: sono incluse le repliche con date diverse.
Risposta HTTPS verificata dopo correzione della lettura di `updated_at: null`.
76 test locali mirati superati; immagine Linux costruita con test Eventi selezionati.
16 test frontend Eventi/cache superati, incluse date pilota e identità delle repliche.

## Limiti espliciti

- TurismoFVG inizialmente indisponibile per budget pagine superato, recuperato
  con il collaudo descritto sotto. Non equivale alla copertura di ogni evento regionale.
- Date/sedi non interpretabili restano in `review_required`, non nella lista pubblica.
- Pordenone Pensa copre la pagina verificata dell'edizione settembre 2026;
  CSS i programmi collegati dalla homepage; Trieste solo date singole esplicite.
- Le coordinate comunali sono approssimative, non rappresentano la sede esatta.
- Il filtro tra fonti è conservativo: non unisce date, orari o sedi discordanti.
- Il servizio risponde a pagine da 100; il client pilota legge tutte le pagine
  dello stesso snapshot prima di mostrare il catalogo. Un cambio snapshot
  restituisce un errore e richiede di riprovare: non combina cataloghi diversi.
- APK pilota aggiornato e collaudato sul telefono nella sessione descritta sotto.

## Costi

Massimo teorico del solo nuovo job con 31 esecuzioni da 900 s: circa 0,53 USD/mese
prima delle franchigie; scheduler circa 0,10 USD/mese prima della franchigia.
Vanno aggiunti servizio HTTP, storage, registry, build e risorse meteo preesistenti.
Min istanze zero e max una per il lettore; ciò non costituisce un tetto di spesa.
Il limite complessivo richiesto di 5 EUR/mese richiede verifica della fatturazione
effettiva; gli avvisi di budget non bloccano gli addebiti.

Prezzi di riferimento: https://cloud.google.com/run/pricing e
https://cloud.google.com/scheduler/pricing.

## Ampliamento TurismoFVG

Limite portato da 20 a 128 pagine; restano obbligatori fine paginazione,
assenza di loop e riconoscimento del markup. Un superamento non pubblica
il lotto parziale. Budget finale TurismoFVG 360 s, altre sei fonti 80 s ciascuna:
840 s complessivi, lasciando margine nel job da 900 s. CPU, memoria,
frequenza e timeout totale invariati.

80 test locali superati. Build Linux `e204aea9-9582-420b-9153-1e1b547c49c6`
riuscita. Job aggiornato al digest
`sha256:fa14603c3d80b772efe6d3193e6f5e1b84d70c0c1ef903840d7a4c86c73c6be3`.
Collaudo remoto `pilot-events-292h4` riuscito alle 20:45:15 UTC. API verificata:
tutte sette fonti `fresh`, Udine/20 km 171 appuntamenti prima del limite risposta.
Prova locale completa: 85 pagine, 672 schede, 618 localizzate al comune,
una data esclusa, 328,8 s. Cloud più rapido, completato entro il primo budget
di 300 s. Margine finale 360 s preparato nella build Linux riuscita
`4169c909-2fba-4ce9-9034-c8387361d62a`, digest finale job
`sha256:ce1c215c83244f050c0e93df734be9904d205f810079d0119be58d5a30f26b0c`.
Non è stata ripetuta la raccolta dopo il solo ampliamento finale del timeout.

## Raggio, paginazione e telefono — collaudo serale

Servizio lettore aggiornato alla revisione `pilot-events-00003-k6t` con immagine
`sha256:15b0b937a1a245848f436d32f2508e3606fb595c7dfeafd29023dd77f2f984c5`.
Job di raccolta e scheduler invariati. Nuovi parametri `offset` e `snapshot`;
risposta include `total` e `next_offset`. Cache client separata per raggio.
Selettore a destra della località, opzioni 5/10/20/30/50 km, iniziale 20 km.
Il cambio comune rimonta la vista e riporta il raggio a 20 km.
Lista visualizzata a gruppi di 16 con Mostra altri; nessun taglio silenzioso a 100.

83 test backend e 65 frontend mirati superati prima della build.
APK localPilot installato, SHA256
`362326a938323c0eb926e9cc804f065be8dd769b89cba9a8970b537cd5f1c868`.
Verifiche reali sul telefono, senza modificare GPS o spostamenti:

- Pordenone 20 km: 612; 5 km: 561.
- Cambio a Udine: 174 a 20 km.
- Drenchia: 15 a 20 km; zero a 5 km, messaggio vuoto correttamente visibile.
- Ripristinata Pordenone a 20 km.
- Schede Oggi con date 6 settembre e intervalli comprendenti il giorno corrente.
- Mostra altri verificato: avanzamento da 16/45 a 32/45 nelle schede Oggi.

Questo collaudo verifica selettore e lista, non certifica l'esattezza di ogni
scheda delle fonti. Le coordinate comunali restano approssimative.
Pacchetto beta non aggiornato.
