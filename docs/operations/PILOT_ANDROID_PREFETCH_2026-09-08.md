# Prefetch Android della pilota

Intervento successivo al checkpoint `fbfa7aa`, identificato dal tag locale
`pilota-stabile-pre-prefetch-20260908`. Stessa sequenza di sviluppo, nessun branch
nuovo o copia del progetto. Questo intervento ha un commit separato.

## Perimetro

- Solo package `com.meteofriul.app.localpilot`, senza modifiche a MainActivity,
  Gradle, manifest, CSS, JSX, testi, permessi, Firebase o servizi della beta.
- Nessun deploy cloud, Play, web o sito. Scheduler ICON/CAMS invariati.
- Il telefono legge solo file gia pubblicati dal reader HTTPS pilota: non
  avvia acquisizioni dei modelli, non chiama API legacy e non invia la posizione.
- Una sola localita: l'ultimo comune richiesto dal runtime della pilota. Nessun
  GPS in background o pre-caricamento di localita ipotetiche.

## Responsabilita dei file

| Parte | Dove | Compito |
| --- | --- | --- |
| Collegamento Android | `frontend/src/services/pilotWeatherPrefetch.js` | Abilitazione solo pilota Android/cloud, configurazione comune, letture con attesa limitata, deduplica e reset |
| Client dati esistente | `weatherV1Client.js`, `localWeatherV1Adapter.js`, `localWeatherV1Runtime.js` | Unica validazione di schema, hash, provenienza, revoche e finestra ICON 12–48 |
| Lavoro nativo | `frontend/android/app/src/localPilot/java/com/meteofriul/app/pilot/` | Plugin, WorkManager, trasporto HTTPS e staging privato |
| Registrazione | `frontend/android/app/src/localPilot/assets/capacitor.plugins.json` | Conserva i quattro plugin precedenti e aggiunge soltanto quello della pilota |

Lo staging nativo contiene byte non fidati, non un secondo modello dati
applicativo. Non scrive nelle chiavi localStorage weather-v1. Il client promuove
i file nella propria cache solo dopo tutte le verifiche gia previste.

## Comportamento

1. La cache applicativa valida continua a soddisfare subito l'apertura.
   Anche su un cache hit viene configurato il lavoro nativo, senza attendere I/O.
2. Un unico lavoro periodico WorkManager: intervallo nominale 60 minuti,
   primo controllo dopo 30 minuti, rete disponibile e batteria non bassa.
   `KEEP` evita duplicazioni e rinvii continui a ogni riapertura. Android puo
   rinviare il lavoro: non e un timer esatto o una garanzia a schermo spento.
3. Il worker controlla i puntatori ICON e CAMS con ETag. Se non cambiano e gli
   oggetti sono presenti, non riscarica manifest e dati dei comuni.
4. ICON attivo/precedente e famiglia CAMS sono indipendenti. CAMS core/pollini
   vengono salvati insieme. Un fallimento non sostituisce lo staging completo
   precedente. La pubblicazione locale usa AtomicFile e controllo generazionale.
5. Riapertura/refresh: i puntatori mutabili restano verificati realmente in rete.
   Il port nativo fornisce solo oggetti immutabili con l'hash atteso dal parent
   verificato. Nessun puntatore nativo vecchio viene spacciato per dato fresco.
6. Refresh forzato e discendenti di metadata recuperati offline non usano il
   prefetch. Restano operativi il percorso rete/cache e il fallback ICON esistenti.
7. Lettura del bridge limitata a 500 ms complessivi; configurazione facoltativa
   a 1000 ms. Errori, dati incoerenti o bridge indisponibile diventano cache miss,
   non errori visibili aggiuntivi. Abort, cambio comune e reset scartano risposte
   in ritardo. Il reset esistente richiede anche la pulizia dello staging nativo.

Il worker usa solo GET sull'origine fissa
`https://pilot-weather-335641913741.europe-west1.run.app`; redirect disabilitati,
dimensioni e percorsi limitati, timeout rete 12 s. I fallimenti transitori hanno
al massimo quattro tentativi con backoff esponenziale da 5 minuti, senza tenere
il processo occupato nell'attesa. Nessuna notifica o servizio foreground.

## Verifica

- Test funzionali JVM del core/HTTPS con trasporto e repository iniettati:
  16 passati. Coprono ETag/304, hash, limiti, grafo ICON, famiglia CAMS,
  indipendenza dei provider e veto generazionale su cambio comune/reset.
- Guard strutturali nativi: 8 passati. Sono controlli di isolamento e codice,
  non una simulazione dell'esecuzione WorkManager sul telefono.
- Test JavaScript dedicati a port e bridge, integrazione runtime/cache,
  annullamento, fallback e compatibilita legacy: 322/322 nel gruppo finale di
  11 file, inclusi i due test aggiuntivi di disabilitazione durante una lettura.
- Lint dei file JS modificati e `git diff --check` puliti.
- Suite frontend estesa con due worker: 3302 passati, 11 skip gia previsti,
  un solo fallimento preesistente (excerpt Eventi). Nessun timeout Scopri in
  questa esecuzione. Due test di hardening del bridge aggiunti successivamente
  sono verificati nel gruppo mirato finale.
- Build protetta Web + Android `assembleLocalPilot`: completata. Registro
  realmente contenuto nell'APK controllato: quattro plugin precedenti piu
  `com.meteofriul.app.pilot.PilotWeatherPrefetchPlugin`.
- APK generato: `frontend/android/app/build/outputs/apk/localPilot/app-localPilot.apk`.
  Package `com.meteofriul.app.localpilot`, meteo cloud, nessun orologio simulato.
  SHA-256: `b0128295d93aab7e6bb04ecc8efe13542db67ac727aaee072be744ffec8a68ac`.
  Alla chiusura della build non installato e non pubblicato; l'installazione
  successiva e descritta sotto. Le build successive riutilizzano quel percorso:
  confrontare l'hash, non soltanto il nome del file.

Comandi frontend: `npx vitest run --configLoader native --maxWorkers=2` e
`node --test scripts/android-pilot-prefetch.node-tests.mjs`.
Il test `PilotWeatherPrefetchCoreTest` e eseguibile con JDK 21 insieme a Core e
Http, senza Android o librerie aggiunte; il wrapper JUnit e nel source set
`src/testLocalPilot` per `testLocalPilotUnitTest`.

## Limiti di collaudo

La compilazione non equivale a installazione o collaudo fisico. Restano da
verificare sulla sola pilota: riapertura dopo ore, risparmio energetico/Doze,
esecuzione WorkManager effettiva, perdita e ritorno della rete, cambio comune,
reset con lavoro attivo e assenza di nuove notifiche. Non si dichiara questo
collaudo eseguito tramite i test JVM o la sola generazione dell'APK.

Il test Eventi preesistente sull'excerpt e i rilievi lint globali sono descritti
nel rapporto del checkpoint; non sono stati nascosti o corretti cambiando la UI.
Il gate cloud esteso terminato successivamente ha 104 successi e tre errori:
due per ecCodes assente su Windows e un timeout del test concorrente publisher
(`resume.wait(20)`). I 62 test diagnostici mirati restano verdi; questo intervento
non modifica quei file e non certifica completate le recovery cloud.

## Primo collaudo sul telefono, 8 settembre 2026

APK del commit `8dc74f5`, con lo SHA-256 sopra riportato, installato tramite
aggiornamento conservativo (`adb install -r`) sul Samsung A52 / Android 14.
Package pilota `com.meteofriul.app.localpilot`, versione `1.0.1-local-pilot`,
codice `300012`, ultimo aggiornamento dispositivo `2026-09-08 18:08:14` CEST.
Non sono stati cancellati dati o preferenze dell'app.

Il package beta `com.meteofriul.app` e rimasto alla versione `1.0.1`, codice
`300012`, ultimo aggiornamento `2026-08-30 00:41:28`, verificato prima e dopo.
Nessun deploy o modifica a rete, orologio, batteria o Doze del telefono.

### Evidenze positive

- Plugin nativo registrato e configurato realmente dalla WebView: Pordenone,
  ISTAT `093033`, generazione 1. Un solo job WorkManager, rete connessa,
  batteria non bassa, intervallo/backoff coerenti con il codice.
- Riapertura dopo terminazione del solo processo pilota: avvio Android COLD
  completato in 2457 ms secondo `am start -W`. Questo tempo misura l'avvio
  dell'Activity, non garantisce il completamento di tutti i dati della pagina.
- Ricaricamento della WebView con richieste di rete bloccate tramite DevTools
  della sola pilota: dati Home osservati dopo circa 888 ms, temperatura 32 C,
  cache Pordenone conservata e 44 ore future reali, dalle 19:00 dell'8 settembre
  alle 14:00 del 10 settembre CEST. Nessuna richiesta weather-v1 nel campione;
  altre richieste della WebView fallivano con `ERR_INTERNET_DISCONNECTED`.
  Simulazione rimossa in `finally`. Non equivale a modalita aereo reale e non
  blocca la rete del worker Java. `navigator.onLine` risultava true: non viene
  usato come prova dell'assenza fisica di rete.
- Ricaricamento successivo con rete ripristinata: dati Home osservati dopo
  circa 856 ms. Sono misure singole con debugging attivo, non benchmark.
- Cambio comune da Pordenone a Udine: configurazione nativa `030129`,
  generazione 2; ritorno a Pordenone: `093033`, generazione 3. Il job rimane
  unico e conserva la scadenza iniziale. La localita finale e Pordenone.
- Previsioni renderizzate con 44 card orarie, senza richiedere quota 48.
  Nessun crash Android rilevato nei log del processo durante le prove.

### Prefetch autonomo non ancora certificato

Prima finestra utile non anteriore alle 18:38:32 CEST circa, 30 minuti dopo
la configurazione iniziale. Un tentativo diagnostico limitato al job della
pilota con `cmd jobscheduler run -f` alle 18:09 e stato correttamente rinviato
da WorkManager (`executed before schedule`). Non prova l'esecuzione del worker.
Non sono stati alterati database, clock o intervalli per anticiparlo.

Il primo ID Android era 0; dopo il test di terminazione/riapertura Android lo
ha ripianificato come 1, sempre nella namespace `androidx.work.systemjobscheduler`.
Per qualsiasi prova successiva rilevare nuovamente l'ID dal dispositivo,
senza assumerlo costante. Work name: `meteofriul-pilot-weather-prefetch-v1`.

Restano da attestare: esecuzione autonoma con log `result=staged`, integrita
dei file nativi ICON/CAMS, uso effettivo dei byte pre-caricati da parte del
client, riapertura dopo ore e comportamento in risparmio energetico reale.
Una Home veloce dalla cache JS non certifica questi passaggi.

### Disponibilita dei dati distinta dal prefetch

Il confronto in sola lettura con il cloud, alle 18:14 circa, conferma ICON
latest `20260907T120000Z` (revisione 3) e CAMS `20260908T000000Z` (revisione 3).
Il telefono usa gli stessi modelli pubblicati: la scritta Home preesistente
`Dati non aggiornati` dipende dal `fresh_until` ICON oltrepassato, non da un
mancato download di una corsa piu recente gia pubblicata. La copertura futura
ICON rimane utilizzabile. Il prefetch non risolve la mancata pubblicazione
cloud; la recovery cloud non viene dichiarata completata da questo collaudo.
La scheda UV risultava senza dati verificati: anche questa disponibilita non
viene certificata come risolta. Nessun testo o componente UI e stato modificato.
