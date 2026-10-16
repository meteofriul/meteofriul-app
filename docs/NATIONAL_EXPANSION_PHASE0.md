# Espansione nazionale — contratto di fase 0

Stato: baseline tecnica di fase 0 implementata; adapter DPC, ICON-2I nazionale
e rollout Community oltre il FVG restano nelle fasi successive.

## Posizionamento

> Meteo Friûl — nato in Friuli, aperto all’Italia. In FVG, anche con il dettaglio dei dati OSMER.

Il nome e la voce editoriale restano friulani. L’estensione nazionale riguarda meteo, radar e,
progressivamente, community e allerte. Non implica affiliazione a OSMER, DPC o altri enti.

## Bounded context

La località selezionata non è più un contesto globale implicito. L’app distingue cinque ambiti:

| Contesto | Identità | Segue la località meteo | Ambito iniziale |
| --- | --- | --- | --- |
| Meteo | `weatherLocation` | sì | Italia |
| Disponibilità fonti | `sourceAvailability` | sì, tramite policy | per fonte |
| Community | `communityPolicy` | sì per la scrittura | lettura Italia, scrittura pilota FVG |
| Editoriale | `editorialContext` | no | Friuli Venezia Giulia |
| Identità anonima | `communityIdentity` | no | indipendente dal luogo |

Regola fail-closed: una località senza identità territoriale sufficiente non abilita fonti o
mutazioni regionali. Il nome della città, da solo, non prova l’appartenenza a una regione.

## Fonti: pertinenza e stato runtime

La pertinenza territoriale di una fonte è distinta dal suo stato tecnico (`fresh`, `cache`,
`unavailable`). Una fonte fuori ambito è `unsupported`, non “temporaneamente non disponibile”.

| Fonte | Copertura di prodotto | Stato fase 0 |
| --- | --- | --- |
| Previsioni ICON-2I autonome | FVG | attive nella pilota |
| Previsioni ICON-2I nazionali | Italia fuori FVG | pianificate; UI indisponibile esplicita |
| Radar precipitazioni DPC | Italia | attivo |
| OSMER ARPA FVG | solo FVG | attivo in FVG, non mostrato altrove |
| Webcam editoriali | solo FVG | attive in FVG, non caricate né attribuite ad altre località |
| Criticità DPC per zona | Italia | pianificata; richiede resolver di zona e adapter verificato |
| ICON-2I puntuale | Italia | pianificato; porta coordinate → cella prima dei manifest |

I dati DPC e OSMER restano layer separati con fonte, area, validità e aggiornamento propri. Non
si fondono livelli diversi fingendo equivalenza.

### Routing meteo nella pilota autonoma

La pilota meteo resta autonoma per una località FVG: le richieste usano esclusivamente il
data-plane ICON/CAMS della pilota e non fanno fallback automatico. Il vincolo operativo
`METEOFRIUL_OPEN_METEO_ENABLED=false` resta autoritativo.

Il catalogo autonomo corrente contiene solo Comuni FVG. Perciò una località italiana
esplicitamente fuori FVG non seleziona un provider alternativo: Home mostra
“Previsioni nazionali in preparazione” e la sezione Previsioni spiega che ICON-2I nazionale
non è ancora disponibile. Il client non costruisce né invia richieste Open-Meteo, non riusa
cache Open-Meteo precedenti e non espone un proxy Vite verso l'API meteo ordinaria.

Il codice del provider ordinario preesistente rimane temporaneamente nel repository per
compatibilità con rilasci precedenti, ma nessuna rotta introdotta dall'espansione nazionale di
fase 0 può selezionarlo. La futura copertura nazionale si abiliterà soltanto quando il percorso
autonomo coordinate → cella ICON-2I avrà contratto, copertura e controlli di qualità approvati.

## Località nazionale

La ricerca può proporre località italiane oltre al catalogo FVG. Ogni record nazionale conserva,
quando disponibili, `countryCode`, regione, coordinate pubbliche, provincia e codice ISTAT.
Il catalogo locale FVG resta una scorciatoia offline e ad alta qualità, non un filtro sui risultati.
La ricerca nazionale usa Nominatim/OpenStreetMap con filtro Italia fail-closed,
cache bounded, `User-Agent` identificabile e la stessa corsia serializzata del
reverse geocoding. Non usa Open-Meteo e non aggira il relativo kill switch.

Chiavi cache e recenti devono includere identità nazionale sufficiente per evitare collisioni tra
omonimi. Una regione mancante non viene mai sostituita automaticamente con il FVG.

## Identità anonima

L’alias descrive l’autore, non il luogo della segnalazione. Usa soggetto ed epiteto friulani
curati, per esempio `Acuile di Aur`, `Lôf dal Bosc`, `Clâf dal Fogolâr`.

Invarianti:

- cambiare località meteo non modifica alias o avatar;
- rigenerare l’identità influenza soltanto le segnalazioni future;
- ogni report conserva lo snapshot pubblico usato al momento dell’invio;
- gli snapshot legacy con alias geografico restano leggibili;
- nessun codice artificiale (`R7`, `M4`) viene mostrato all’utente.

## Community

La lettura è progettata per diventare nazionale. La scrittura resta inizialmente abilitata nelle
regioni pilota, a partire dal FVG. Il backend è autoritativo: l’interfaccia anticipa la decisione,
ma non la sostituisce.

Fuori da una regione abilitata la risposta e la UI usano il motivo stabile
`community_region_not_enabled` e la copy:

> Le segnalazioni partecipative non sono ancora attive in questa regione.

Prima dell’apertura nazionale occorrono location ID canonici, grouping non basato sul solo nome,
moderazione, deduplica, paginazione e filtri regionali/bbox.

## Editoriale ed Eventi

Scopri, Almanacco e contenuti municipali mantengono un `editorialContext` FVG autonomo.
La prima migrazione acquisisce una località FVG già selezionata, se presente; altrimenti usa Udine.
In seguito il contesto non segue automaticamente la località meteo: selezionare Roma o Torino
non trasferisce i contenuti editoriali a quelle città.

Gli Eventi hanno invece una disponibilità territoriale legata alla località meteo attiva:
sono visibili e richiesti soltanto quando questa è riconosciuta come FVG. Quando abilitati,
seguono la località meteo attiva per ricerca, ranking, cache, teaser Home e badge. Il contesto
editoriale autonomo resta riservato a Scopri e Almanacco.

Fuori FVG, o senza identità territoriale sufficiente, non si avviano query Eventi, compresi
refresh e retry, e non si mostrano risultati in cache, badge o schede di singoli eventi.
Nella Home il richiamo Eventi diventa un avviso; la sezione Eventi mostra lo stesso limite
territoriale in modo esplicito:

> Gli eventi sono disponibili solo in Friuli Venezia Giulia.

Le risposte già in volo non devono ripristinare risultati, badge o card dopo il passaggio fuori
FVG. La cache FVG può essere conservata per il ritorno in regione, ma non è un fallback da
mostrare per la località esterna. Questa regola non modifica il contesto di Scopri e Almanacco.

## Sequenza di rollout

1. Separazione dei contesti, policy centrali e test di non contaminazione.
2. Ricerca nazionale e stato di disponibilità esplicito; poi previsioni ICON-2I puntuali sulle coordinate selezionate.
3. Criticità DPC per zona; dettaglio OSMER aggiuntivo solo in FVG.
4. Porta ICON-2I coordinate → cella, QA su regioni pilota; manifest solo se volume/cache lo richiedono.
5. Community nazionale in lettura e apertura graduale della scrittura per regione.
6. Mappa previsionale ICON e notifiche nazionali location-aware.

## Ordine di rilascio

Il backend va distribuito prima del frontend web e dell'app Android. Il nuovo
backend accetta sia gli snapshot alias legacy sia i nuovi alias non geografici;
una vecchia versione del backend, invece, può rifiutare alias nuovi come
`Acuile di Aur` o `Lôf dal Bosc`. Solo dopo aver verificato il contratto backend
si pubblicano i client, quindi si riavvia la pilota locale per applicare ricerca
nazionale e capability territoriali senza introdurre proxy meteo alternativi.

## Criteri di accettazione della fase 0

- Pordenone, Roma e località sconosciuta producono capability diverse e sicure.
- Roma non genera alcuna richiesta Open-Meteo e non riusa una precedente cache Open-Meteo.
- `METEOFRIUL_OPEN_METEO_ENABLED=false` resta il blocco autoritativo della pilota.
- OSMER e allerte FVG non compaiono per una località nazionale fuori FVG.
- Il cambio della località meteo non modifica alias o avatar.
- Scopri e Almanacco restano editoriali FVG e non associano una città nazionale ai contenuti FVG.
- Eventi visibili e richiesti solo con località meteo attiva riconosciuta come FVG.
- Passando da FVG a Roma o a una località sconosciuta, nessuna nuova query, refresh o retry Eventi;
  nessun risultato in cache, badge o scheda di un singolo evento; la Home e la sezione Eventi
  mostrano il messaggio esplicito di disponibilità limitata al FVG.
- Le risposte Eventi tardive non ripristinano contenuti fuori FVG; tornando in FVG si riabilita
  il normale flusso Eventi, senza modificare il contesto editoriale di Scopri e Almanacco.
- La scrittura Community fuori pilota è negata con motivo esplicito anche dal backend.
- Ricerca, recenti e cache distinguono località omonime in regioni differenti.
- Le segnalazioni già pubblicate conservano lo snapshot storico dell’identità.
