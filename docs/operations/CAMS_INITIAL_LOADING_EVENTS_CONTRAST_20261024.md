# Aria/pollini all'avvio della richiesta e contatore Eventi — 24 ottobre 2026

## Identità e stato

Ramo dedicato `codex/cams-initial-loading-events-contrast`, dalla base main
`8fb11af83d94bb779049350cb913541534d85d1c` (PR 19 già promossa).
Due correzioni locali verificate, ancora da committare e promuovere.
Gli hash dei tre file frontend identificano il candidato nella
[ricevuta strutturata](evidence/cams-initial-events-contrast-20261024/verification.json).
Main e ramo release non modificati da questa attività.

La richiesta riguarda i due rilievi residui della
[precedente prova sul Galaxy](WEB_POST_300036_GALAXY_20261024.md), senza AAB,
installazioni, push, deploy o invii. Sponsor disattivati; configurazione,
pannello e dati sponsor non toccati. Nessuna interrogazione o modifica dei job.

## Correzioni

- **Aria e pollini:** il nuovo token di aggiornamento determina lo stato di
  caricamento già nel render iniziale, prima della prima risposta ICON o CAMS.
  Il precedente esito indisponibile non viene mostrato durante questo tratto
  della richiesta. Lo stato è di presentazione, non viene salvato come dato
  meteo nella cache. Il completamento o un errore dell'intera richiesta
  chiudono il caricamento anche quando non arriva un callback CAMS separato.
  Restano i dati numerici validi e i controlli di validità già esistenti;
  nessuna modifica a provider, soglie, timeout o numero di richieste.
- **Eventi in scuro:** il contatore nel pulsante «Mostra altri» usa `#06463f`
  sul suo fondo chiaro esistente. Tema chiaro e testo del comando invariati.
  In friulano il comando rimane «Mostre altris».

## Controlli locali

**76 test in 8 suite PASS**, incluse quattro nuove regressioni IT/FUR:
attesa della prima risposta e fallimento dell'intera richiesta senza callback
CAMS. Le nuove regressioni riproducevano il difetto prima della correzione.
Coperti anche ciclo differito CAMS, candidato attivo, revoche all'avvio,
viewmodel meteo, card ambientali, Eventi e testi. ESLint dei due file JSX PASS.
Comandi e suite completi nella ricevuta.

Compilazione Vite 8.1.6 con configurazione nativa e modalità `cloudflare` PASS,
2122 moduli, output temporaneo del sistema. Endpoint pubblico ricavato dal
manifest della 300036. Restano i consueti avvisi sull'import Almanac e sui
chunk oltre 500 kB. È una verifica di compilazione: non un nuovo archivio Web
di consegna, né un'attestazione di pubblicazione o compatibilità CORS.

## Prova reale sul Galaxy

Samsung Galaxy A52 SM-A525F, Android 14 / API 34, Brave 1.97.59 (429705904),
1080×2400, viewport CSS 411×728. Anteprima del nuovo ramo avviata esclusivamente
con `scripts/start-local-weather-pilot.ps1 -WeatherCloud`, porta 5174.
ADB/CDP usati per osservazioni, tocchi, misure e screenshot sul telefono reale.

| Caso | Italiano | Friulano |
| --- | --- | --- |
| Retry da indisponibile, ICON e CAMS sospesi, poi dati reali | PASS | PASS |
| Retry, ICON disponibile, CAMS termina con errore | PASS | PASS |
| Retry, fallisce l'intera richiesta senza callback CAMS utile | PASS | PASS |
| Contatore Eventi in chiaro, tocco da 16 a 20 schede | PASS | PASS |
| Contatore Eventi in scuro, tocco da 16 a 20 schede | PASS | PASS |

Per ciascuno dei sei casi CAMS, il primo campione dopo due animation frame e
12 ulteriori campioni con le risposte sospese mostrano entrambe le card in
«Caricamento…» / «In cjariament…», senza indisponibilità e senza callback di
completamento dei provider. Alla fine compaiono i valori reali oppure
«Dati non disponibili» / «Dâts no disponibii», senza caricamento bloccato.
Gli errori e i ritardi sono indotti soltanto nella pagina locale di prova;
componenti, provider e stili provengono dal candidato. La prova non simula
un nuovo disservizio cloud e non modifica i dati pubblicati.

Eventi usa 20 schede locali dichiaratamente fittizie perché il catalogo
vicino alla località osservata non raggiungeva la soglia del pulsante.
Componente e CSS sono quelli effettivi. In scuro il contrasto calcolato è
**almeno 5,23:1**, componendo il fondo semitrasparente sul nero, caso più
sfavorevole. Nessun overflow orizzontale (411/411 px). Dopo il tocco reale
appaiono tutte le 20 schede e il pulsante scompare.

La sessione termina nelle Previsioni complete in italiano chiaro, con dati
reali: PM2.5 3,7 e PM10 5,7 µg/m³, graminacee 0,21 grani/m³. Le preferenze
iniziali di lingua, tema, Posizione e località sono conservate. Il controllo
di rete della scheda consente soltanto GET/HEAD/OPTIONS: zero tentativi di
scrittura e zero eccezioni JavaScript non gestite. Guardia rimossa e forwarding
di debug chiuso al termine; anteprima lasciata accessibile al proprietario.

## Evidenze e limiti

JSON, screenshot e strumenti locali sono in
`.tmp/cams-initial-events-galaxy-20261024/` della radice canonica, ignorati da Git.
La ricevuta versionabile contiene esiti e hash, senza token, identificativi
del telefono o preferenze private. Le pagine di prova in `frontend/tmp/`
rimangono ignorate e fuori dagli ingressi di build.

Queste prove chiudono i due rilievi nel candidato Web locale. Non attestano
il comportamento di una nuova AAB minificata, Safari/iPhone, altre versioni
Android, aggiornamento della cache pubblica o servizi del bundle Web da
un'origine pubblicata. AAB 300036 e relativo archivio Web restano immutabili
e non contengono queste correzioni. La verifica non autorizza ulteriori azioni
di distribuzione; commit e promozione restano da effettuare separatamente.
