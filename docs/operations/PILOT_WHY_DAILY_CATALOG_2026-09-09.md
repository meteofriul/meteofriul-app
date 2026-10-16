# Rubrica giornaliera “I perché del Friûl” — integrazione pilota 2026-09-09

## Ambito

La rubrica della sola app Android pilota usa ora il catalogo editoriale locale
convertito dai Markdown in:

- `frontend/src/data/discover/pilotWhyCatalog.json`;
- `frontend/src/features/discover/pilotWhyContent.js`.

Beta, servizi cloud, Firebase, frequenze, sito pubblico e web app pubblicata non
sono stati modificati. Non è stata compilata né installata una nuova APK.

## Origine e riproducibilità

Il catalogo è generato con `scripts/import-pilot-why-catalog.mjs` a partire da
`01_ARCHIVIO_I_PERCHE_DEL_FRIUL.md` e `02_CALENDARIO_ANNUALE.md`. Lo script
verifica prima di scrivere:

- 366 schede ordinate e senza ID mancanti;
- 365 date ordinarie distinte più `02-29` associato alla scheda #366;
- validità di tutte le date e di tutti gli ID referenziati;
- assenza di caratteri CJK residui nei contenuti;
- permanenza esplicita delle anomalie di calendario già documentate.

Hash SHA-256 dei Markdown normalizzati LF importati:

- archivio: `0a79fd339a7de3b278659059b17b6926da87b01b699942a5e59fd03747619899`;
- calendario: `026543ea05894109679c13200246bdf6f7ae40d4b14740a0e4511d87376678d2`.

## Comportamento

- La data civile seleziona in modo deterministico la mappatura `MM-DD`.
- Home mostra la domanda; Scopri mostra la stessa scheda e la risposta completa.
- L'ID cliccato in Home viene conservato durante la navigazione, anche se cambia
  la giornata prima dell'apertura di Scopri.
- Il cambio lingua conserva l'identità della scheda.
- Il 29 febbraio usa #366; negli anni non bisestili la scheda non viene scelta.
- La scheda #01 continua a usare il record Palmanova già verificato, con le due
  fonti HTTPS esistenti, invece di regredire alla variante grezza dell'archivio.
- Le altre fonti, fornite dai documenti solo come denominazione, sono mostrate
  come testo e non trasformate in link inventati o dichiarate verificate.
- Il riferimento storico del prompt a una Bottom Sheet non è stato applicato:
  resta il percorso già approvato Home → Scopri.

## Rettifiche testuali tracciate

I cinque caratteri CJK già presenti nei Word sono stati ricostruiti con
sostituzioni minime, registrate anche nei metadati del JSON:

- #48: `r<U+64B9>e` → `rave`;
- #77: `l<U+8BC6>e` → `lasse`;
- #102 e #363, tre occorrenze: `v<U+9855>is` → `vignis`.

Sono ricostruzioni tecniche assistite, non una certificazione linguistica umana.

## Anomalie del calendario preservate senza supposizioni

Il calendario sorgente copre ogni data, ma usa 359 ID ordinari distinti. Restano
ripetuti #80, #110, #186, #290, #303 e #340; restano non assegnati #167, #250,
#266, #272, #286 e #298. Il catalogo contiene comunque tutte le 366 schede.
L'importatore fallisce se questo insieme cambia, così una futura rettifica non
può passare inosservata. Non sono state inventate associazioni sostitutive.

## Verifiche eseguite

- 51/51 test mirati superati su catalogo, Home, Scopri e card della rubrica.
- Lint senza errori e `git diff --check` pulito.
- Build Vite di produzione riuscita in directory temporanea del sistema; il
  warning di dimensione chunk è quello non bloccante già noto.
- Suite completa: 3378 test superati, 11 saltati e un solo fallimento fuori dal
  diff in `EventsView.test.jsx` (“shows available descriptions…”). Nessun file
  Eventi è stato modificato da questo intervento.
