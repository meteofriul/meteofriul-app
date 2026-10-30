# Mercati: gestione dal pannello — proposta del 30 ottobre 2026

La ricerca territoriale deve produrre contenuti che il proprietario possa
aggiungere, correggere, sospendere e archiviare dal **pannello di gestione
esistente**. Questo documento definisce il collegamento da realizzare; non
attesta una funzione già disponibile e non modifica il pannello esterno.

## Stato verificato

Audit in sola lettura del progetto correlato `../PANNELLO INSERZIONI`, ramo
`codex/control-center`, HEAD `4fb0b33daa70526c48649dd3afe5d266c171be96`.
La copia locale contiene modifiche e file non tracciati già presenti: il
riscontro descrive quella copia di lavoro, non un artefatto pubblicato.

| Componente | Capacità osservata | Conseguenza per Mercati |
|---|---|---|
| Centro di gestione | Eventi e Scopri segnati `planned` in `src/panelSections.js` e `src/components/ControlCenter.jsx` | Sono punti di ingresso predisposti, senza gestione Mercati collegata |
| Consiglio del giorno | `EditorialPreview.jsx` / `editorialDraftStorage.js`: bozze nel browser | Non è un archivio condiviso, una pubblicazione o una sincronizzazione con l'app |
| Sponsor e Webcam | Moduli/API amministrativi propri | Permessi e procedure non autorizzano automaticamente la gestione Mercati |
| App Meteo Friûl | `frontend/src/features/markets/marketsCatalog.js` importa il JSON statico `catalogue2026.json` | Per ora una modifica nel pannello non cambia l'app |
| Eventi | Riconciliazione per ID mercato, URL/alias e città; ID sintetico `market:<id>:<data>` | Spostare una data cambia oggi l'ID derivato; serve identità stabile dell'edizione |
| Calendario | Date puntuali per gli occasionali; giorni della settimana per gli abituali | Mancano eccezioni generali, sedi con decorrenza e archiviazione amministrativa remota |

Il catalogo attuale contiene 60 schede, di cui 53 pubbliche e 7 escluse, e
176 date con orizzonte 2026. La scadenza del calendario non certifica la
cessazione del mercato. Il registro di ricerca è distinto dal catalogo pubblico.

## Un archivio, due viste

Nel pannello esistente, **Scopri → Mercati** è il punto di gestione della
scheda e del calendario. Eventi usa le edizioni dello stesso archivio e può
rinviare al medesimo editor: non deve nascere una seconda scheda indipendente.
La collocazione è proposta; va coordinata con il lavoro già in corso nel
progetto del pannello, preservandone le modifiche locali.

| Oggetto | Dati da conservare |
|---|---|
| Mercato | `market_id` stabile; nome e alias; comune con codice ISTAT; frazione; tipo; organizzatore; descrizioni IT/FUR e loro stato di revisione |
| Sede | `venue_id`; nome pubblico, indirizzo e coordinate pubbliche verificate; indicazioni; validità da/a; fonte. Un indirizzo dell'organizzatore non è automaticamente il luogo del mercato |
| Regola ricorrente | Giorni ISO 1–7, fascia di vendita, mesi/stagione, decorrenza, fine della validità verificata, regola dei festivi se documentata; fonte per ciascuna informazione |
| Edizione | `edition_id` stabile indipendente da data e sede; `market_id`; date e orari locali, fuso `Europe/Rome`; eventuale sede specifica; stato; fonte e data di verifica |
| Eccezione | Giorno/intervallo interessato, sospensione o spostamento; vecchi e nuovi valori; motivo pubblico; fonte; decorrenza e scadenza, anche non ancora nota |
| Fonte | URL, editore, titolo, pubblicazione quando comprovata, consultazione, passaggio/pagina, accesso completo/indice/bloccato, campi supportati, limiti e prossima verifica |
| Revisione | Numero progressivo, autore interno, data, motivazione, differenze rispetto alla versione pubblicata e riferimento alla fonte |

Non incorporare recapiti personali nel catalogo pubblico. Conservare soltanto
i recapiti istituzionali necessari, se già pubblici e pertinenti.

Separare tre dimensioni:

- **Evidenza:** da verificare, documentata, in conflitto, soltanto storica.
- **Pubblicazione:** bozza, da revisionare, pubblicata, ritirata.
- **Attività:** prevista, attiva, sospesa, cessata. Una singola edizione può
  essere provvisoria, confermata, rinviata o annullata.

Un risultato di ricerca mancante non diventa «mercato assente». Un documento
storico resta utile come pista, senza rendere attiva una scheda. La soppressione
di alcuni posteggi non equivale alla chiusura del mercato.

## Operazioni che deve poter fare il proprietario

| Operazione | Comportamento richiesto |
|---|---|
| Aggiungere un mercato | Bozza con ID nuovo; ricerca preventiva di omonimi, frazioni, alias e URL; validazione delle fonti prima della pubblicazione |
| Correggere una data | Modifica della stessa edizione; conserva il giorno precedente e la motivazione; rimuove il vecchio appuntamento dalle liste e impedisce la ricomparsa da feed/cache |
| Cambiare sede | Scelta esplicita fra singola edizione, intervallo e sede abituale da una decorrenza; anteprima delle date coinvolte e aggiornamento delle indicazioni stradali |
| Aggiungere un'edizione | Data documentata collegata al mercato, anche fuori ricorrenza; nessuna duplicazione in Eventi |
| Annullare o sospendere | Stato visibile, motivo e fonte; esclusione dalle proposte «da visitare»; un dettaglio già condiviso deve spiegare il cambiamento |
| Togliere un mercato | Ritiro/archiviazione dalla pubblicazione; mantiene ID e storico. La cancellazione definitiva non è l'operazione ordinaria |
| Riaprire o ripristinare | Nuova revisione e conferma della validità corrente; nessun ripristino implicito perché ricompare una vecchia fonte |
| Correggere un errore pubblicato | Anteprima del confronto, pubblicazione atomica e possibilità di ripristinare una revisione precedente senza perdere l'audit |

Nell'editor usare termini semplici («Solo questa data», «Da questa data»,
«Tutto il mercato») e un riepilogo concreto prima di pubblicare. Gli ID e i
dettagli delle API restano fuori dalle normali schermate di lavoro.

## Collegamento tecnico proposto

1. Persistenza comune lato server con API amministrativa Mercati e controllo
   dei permessi sul server. Le bozze locali del browser non sono la fonte unica.
2. Pubblicazione di una revisione immutabile del catalogo tramite API pubblica
   di lettura; bozze e note interne restano escluse. Le operazioni amministrative
   richiedono autenticazione e autorizzazione. Validazioni identiche lato
   editor e server.
3. Concorrenza tramite revisione attesa/ETag: una modifica più vecchia non
   sovrascrive silenziosamente quella di un altro dispositivo. Pubblicazione
   e ritentativi idempotenti; errori di rete non producono doppie edizioni.
4. App Web e Android leggono lo stesso contratto. L'import statico diventa
   eventualmente un pacchetto iniziale con validità limitata, mai una fonte
   capace di far riapparire un ritiro già acquisito. Cache e offline devono
   conservare revisioni e soppressioni e segnalare dati non aggiornati.
5. Scopri, Home quando pertinente, Eventi e dettaglio usano la stessa revisione.
   Il lettore Eventi deve rispettare annullamenti/spostamenti anche quando un
   feed esterno ripropone la vecchia data. Servono mapping degli alias e
   soppressioni persistenti, senza confronti approssimativi sul solo titolo.
6. Una ricorrenza può proporre date al redattore; non certifica che il mercato
   si svolga nei festivi. Per gli occasionali resta il vincolo delle date
   documentate. Intervalli di festival e metadati di pagina non diventano
   automaticamente giornate di mercato.

La scelta di database, endpoint definitivi e modello dei permessi resta da
concordare con l'architettura del pannello. Non viene riutilizzata implicitamente
l'API Sponsor. La migrazione deve mantenere gli ID M001…M060 e gli alias utili,
deduplicare le candidature di ricerca e convertire esplicitamente i giorni:
il selettore attuale usa la convenzione JavaScript **0=domenica**, mentre il
registro di ricerca usa ISO **7=domenica**.

Per le edizioni generate localmente dal catalogo serve un mapping dal vecchio
ID basato sulla data al nuovo ID stabile; gli eventi provenienti dai feed
conservano oggi il proprio ID. La sede dell'edizione deve prevalere sulla sede
generale anche nel collegamento «Indicazioni». Il limite globale di validità
del calendario `validThrough` non basta per governare tutte le fonti e tutte
le stagioni.

## Casi concreti per la futura verifica

- **Muggia:** trasferimento dal 07/05/2026 fino a fine lavori e sospensione del
  02/07/2026, distinti nella [sezione comunale Mercato](https://www.comune.muggia.ts.it/it/categories/mercato-9905)
  (consultata nell'indice; lettore diretto restituisce applicazione JavaScript).
- **Riuso Udine M024:** 05/12 anticipato al 28/11; vecchia fonte ancora in
  conflitto. Una revisione conserva entrambi i riscontri senza pubblicare due
  edizioni equivalenti: [dossier fonti](MERCATI_FONTI_CATALOGAZIONE_20261030.md).
- **Sacellum M037:** 27/12 dichiarato modificabile: la provvisorietà è della
  data, non dell'intero mercato.
- **San Floriano del Collio:** l'[iniziativa MIMIT del 15/04/2026](https://www.mimit.gov.it/en/eventi-2026/mercato-all-aperto)
  annuncia l'intenzione di istituire un mercato. Non certifica una prima
  giornata di vendita né la sede operativa indicata nell'anagrafica dell'ente.
- **San Pietro al Natisone:** l'[organizzatore](https://www.nediskedoline.it/wpnediske/event/gesti-antichi-per-un-nuovo-natale-2026/)
  annuncia apertura 5, 6 e 8 dicembre 2026 e chiusura il 7: l'intervallo della
  manifestazione non deve generare una falsa apertura intermedia.
- **Archiviazione e rete assente:** dopo aver acquisito un ritiro, riaprire
  l'app offline o ricevere un vecchio feed non deve ripubblicare il mercato.
- **Modifica concorrente:** due browser cambiano la stessa scheda; il secondo
  riceve un confronto con la revisione corrente, senza perdita di dati.

## Passaggio alla realizzazione

Prima implementare e verificare archivio/API, permessi e migrazione su dati
di prova, poi l'editor nel pannello esistente, infine il lettore condiviso
nell'app. Verificare creazione, cambio data/sede, sospensione, archiviazione,
duplicati, ripristino e cache su Web e Android. La prova del solo editor non
dimostra l'aggiornamento dell'app; la sola compilazione non prova il flusso.

Questo lotto consegna **ricerca e contratto proposto**. Integrazione, test di
scrittura, distribuzione del pannello e pubblicazione del catalogo sono passi
successivi, da svolgere nel rispettivo progetto e con le autorizzazioni di
pubblicazione previste dai runbook. Nessun nuovo servizio o job è stato avviato.
