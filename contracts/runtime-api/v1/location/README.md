# Contratto location v1

La UI3 usa due endpoint con base relativa `/api`:

- `GET /api/location/search?q=<testo>` restituisce localita italiane: il
  catalogo FVG viene interrogato per primo e la ricerca nazionale usa
  Nominatim/OpenStreetMap con filtro Paese `IT`;
- `POST /api/location/reverse` con body
  `{ "lat": ..., "lon": ..., "accuracyM": ... }` risolve Comune e, quando
  l'accuratezza e' presente, la localita senza mettere le coordinate nella
  URL; il vecchio `GET` resta temporaneamente disponibile ma e' deprecato.

In FVG, il reverse usa lo snapshot versionato dei 215 Comuni e dei toponimi
regionali. Il Comune viene determinato esclusivamente mediante point-in-polygon
sui confini ISTAT 2026. Fuori FVG il backend usa il geocoder pubblico configurato
per ottenere una localita nazionale o estera esplicita, conservando sempre
`country` e `countryCode`; un payload senza identita Paese valida viene respinto.
Se la ricerca nazionale non e raggiungibile e il catalogo FVG non contiene
risultati, l'endpoint risponde con `503 location_search_source_unavailable`.
Ricerca e reverse condividono cache bounded, `User-Agent` identificabile e una
corsia serializzata che mantiene almeno un secondo tra chiamate al servizio
pubblico. I record nazionali espongono `provider: nominatim_search`; il provider
non viene dedotto dal nome della localita.

Con `accuracyM`, la localita e' il toponimo IRDAT piu vicino nello stesso
Comune soltanto se tutte le condizioni fail-closed sono vere:

- distanza del primo candidato + `accuracyM` + 10 m <= 350 m;
- deve esistere un secondo candidato con nome diverso e deve distare dal primo piu di
  `2 * (accuracyM + 10 m)`.

Senza `accuracyM` non viene eseguito alcun nearest sui toponimi IRDAT: la
risposta FVG resta `municipality_only`. Anche il `GET` deprecato segue questa
regola. Fuori dai confini FVG la risposta e `external_place` e usa come
`dataPoint` il punto pubblico canonico restituito dal geocoder.

Per compatibilita, `city` e `istatCode` continuano a identificare il Comune.
I client nuovi mostrano `displayName`/`locality` e usano `municipality` per le
operazioni amministrative; `resolution` distingue `resolved`,
`municipality_only`, `external_place` e `outside_fvg` per compatibilita. Per una localita scelta,
`resolution.matchMethod` vale `nearest`, mentre `distanceM` e
`runnerUpDistanceM` rendono verificabile la decisione. I tre campi sono `null`
quando non viene promossa alcuna localita. Il resolver geografico conserva
anche il metodo strutturato `name` per usi su nomi gia disponibili da fonti
controllate, ma il reverse runtime non interroga servizi di geocoding esterni.

Il top-level `lat`/`lon` conserva il fix ricevuto per compatibilita. I client
devono invece usare `dataPoint` per le successive richieste meteo e per la
persistenza: contiene le coordinate pubbliche canoniche IRDAT quando la
localita e' risolta, oppure il punto del catalogo comunale in
`municipality_only`; fuori FVG contiene il punto pubblico del geocoder. In
questo modo le coordinate GPS esatte non vengono ripetute nelle successive
query meteo.

Per i risultati FVG, `resolution.boundaryDistanceM` indica la distanza minima
del fix dal confine comunale. Il client confronta questo valore con il raggio
di accuratezza del GPS e non sostituisce la localita quando il cerchio di
incertezza puo attraversare un altro Comune.

Le fixture in questa cartella sono condivise dai test frontend e backend.
