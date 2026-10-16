# Geografia nazionale della Community pilota

Il modulo `backend/app/services/pilot_community_geography.py` è indipendente
dal resolver FVG della versione pubblicata. Usa il catalogo nazionale canonico
dei 7.894 Comuni per identità, provincia e regione. Per attribuire un GPS a un
Comune usa i confini ISTAT **non generalizzati** del 1 gennaio 2026, senza
semplificazione e senza fallback al Comune più vicino.

I punti su confini condivisi e i punti fuori dai poligoni italiani non producono
un'attribuzione. Questo include i territori esteri interni al perimetro italiano,
come San Marino e Città del Vaticano. L'eventuale accuratezza e freschezza del GPS
sono controlli del servizio di invio, non deduzioni del resolver geografico.

## Artefatto locale verificato

- Percorso predefinito: `.dev-logs/local-weather-pilot/community-geography.sqlite3`.
- Override esplicito: variabile `PILOT_COMMUNITY_GEOGRAPHY_PATH`.
- Dimensione: 93.220.864 byte, solo sul backend locale; non viene inviato al telefono.
- Vertici: 6.968.899; Comuni correnti: 7.894.
- SHA-256: `1eb9e8dd66759b36a8d1dc59da824493e43c500428ce875127ed863691ce006e`.
- Sorgente: <https://www.istat.it/storage/cartografia/confini_amministrativi/non_generalizzati/2026/Limiti01012026.zip>.
- SHA-256 sorgente: `a9075f8d839dcb2b409099703da7bdd37cc214f8967fa7372b32305875ad046f`.
- Licenza della sorgente: CC BY 4.0, attribuzione ISTAT.

SQLite viene aperto in sola lettura. Ogni richiesta seleziona i pochi rettangoli
che contengono il punto, poi decomprime soltanto i relativi poligoni. Una cache
limitata conserva le ultime geometrie. All'avvio vengono verificati hash
dell'artefatto, provenienza, versione e completezza delle identità. Le geometrie
decompresse hanno un limite di dimensione e un controllo di integrità proprio.
L'artefatto mancante o alterato causa un errore esplicito; nessun download o
collegamento a un servizio cloud viene attivato automaticamente.

## Coordinate pubbliche

Il punto GPS serve a determinare il Comune. Il punto esposto per una segnalazione
è invece un punto fisso rappresentativo del Comune, uguale per tutti gli utenti
di quel Comune. Il resolver non sostituisce quel punto con il GPS dell'utente.

Il builder verifica che ogni punto del catalogo ricada nel confine originale.
Per cinque Comuni (`001024`, `001318`, `012038`, `080049`, `084018`) il punto
derivato dai confini generalizzati non superava questo controllo: è stato
ricalcolato un punto interno dal confine originale ISTAT. Questa trasformazione
è registrata nei metadati locali; il catalogo canonico condiviso rimane invariato.
Questi punti non vengono presentati come sedi comunali o indirizzi.

Le fusioni amministrative successive al 1 gennaio riusano le associazioni
esplicite già revisionate nel catalogo nazionale (`018094` e `024129`).

## Ricostruzione

Il builder usa `pyproj` solo per la trasformazione offline EPSG:32632 →
EPSG:4326, con `always_xy=True`. Il runtime non ha nuove dipendenze. L'artefatto
verificato è stato prodotto con pyproj 3.8.0. L'archivio sorgente già disponibile
si trova nella cartella temporanea come `meteofriul-Limiti01012026.zip`.

Da un interprete che disponga di pyproj, dalla radice del repository:

```powershell
python backend/tools/build_pilot_community_geography.py `
  --boundaries-zip "$env:TEMP/meteofriul-Limiti01012026.zip" `
  --output ".dev-logs/local-weather-pilot/community-geography.sqlite3"
```

Il builder verifica hash e proiezione della sorgente, non scarica dati e non
sovrascrive file esistenti. Per un confronto riproducibile usare un nome di output
nuovo e confrontare l'hash stampato con quello sopra. Un hash diverso richiede
analisi delle differenze prima di modificare il pin del runtime.

Verifica mirata, dalla cartella `backend`:

```powershell
python -m unittest tests.test_pilot_community_geography -v
```

I test unitari usano piccoli poligoni sintetici chiaramente separati dai dati
reali; i test integrativi usano l'artefatto ISTAT locale, quando disponibile.
Non vengono pubblicati dati di test né alterati servizi della versione pubblicata.
