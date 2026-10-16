# Meteo Friul UI 3.0.0 - Audit permessi posizione e notifiche

Data: 2026-06-29

## Scopo

Auditare la vecchia app per recuperare il flusso corretto dei permessi Android:

```text
apertura app -> richiesta posizione nativa -> localita risolta/scelta -> richiesta notifiche nativa
```

Questa tranche non collega push reali, non modifica APK, non invia token e non cambia backend.

## Decisione UX

- In Android la prima richiesta all'apertura deve essere il permesso posizione nativo.
- Dopo accettazione/rifiuto della posizione, l'app procede.
- La richiesta notifiche nativa arriva dopo che esiste una localita risolta o scelta.
- Non devono esistere finestre, card o pannelli custom per chiedere questi permessi prima del prompt nativo.
- La UI nostra puo mostrare stato, fallback e impostazioni dopo la risposta del sistema, non sostituire il prompt Android.

## Terminologia aggiornata

- Nella UI utente si usa `Usa posizione`, non `Usa GPS`.
- `GPS` resta ammesso solo nei documenti tecnici quando si parla del comportamento legacy o delle API Android.
- Per l'utente, `posizione dispositivo` significa posizione stimata da Android: GPS satellitare, rete mobile, Wi-Fi, celle o ultima posizione nota.
- Se il GPS satellitare e' spento o non aggancia, Android puo comunque restituire una posizione approssimativa tramite provider di rete.
- Se i servizi posizione del telefono sono disattivati o il permesso e' negato, l'app deve restare sulla localita manuale.

## Fonti audit vecchia app

| Area | File sorgente vecchia app | Cosa recuperare |
| --- | --- | --- |
| Gate iniziale | `frontend/src/App.jsx` | ordine GPS -> localita -> notifiche |
| Policy posizione | `frontend/src/utils/autoLocationPolicy.js` | fallimenti temporanei vs disattivazione automatica |
| Bridge Android | `frontend/android/app/src/main/java/com/meteofriul/app/MainActivity.java` | Fused Location Provider, payload e stato servizi |
| Manifest Android | `frontend/android/app/src/main/AndroidManifest.xml` | permessi e portrait lock |
| Push native | `frontend/src/utils/pushNotifications.js` | check/request/register/unregister |
| Backend device | `backend/main.py` | payload `devices/register` e `devices/unregister` |
| Note operative | `docs/codex-startup-note.md`, `docs/manuale-operativo-tab.md` | decisioni gia approvate e regressioni note |

## Posizione dispositivo: comportamento vecchia app

### Stato iniziale

La vecchia app inizializza `autoLocationEnabled` cosi:

```text
localStorage.getItem("autoLocationEnabled") !== "false"
```

Quindi al primo avvio pulito la posizione automatica e' attiva.

### Sequenza di apertura

1. Se `autoLocationEnabled` e' attivo, l'app prova `handleAutoDetect({ silent: true })`.
2. In APK Android prova prima il bridge nativo.
3. Se il bridge nativo risponde con posizione valida, fa reverse geocoding e salva localita GPS.
4. Se il bridge e' lento/in transizione, non salva un fallback manuale finto e non spegne subito la posizione automatica.
5. Se la posizione e' negata o non supportata, passa a fallback/localita manuale.
6. Bollettino regionale resta consultabile anche senza localita meteo.

### Bridge Android

Il bridge espone `window.MeteoAndroid` con:

- `getLocationStatus()`;
- `requestFastLocation(requestId)`;
- `requestBalancedLocation(requestId, timeoutMs)`.

Il payload nativo contiene:

```text
ok
source
reason
lat
lon
accuracy_m
age_ms
provider
permission
services_enabled
requestId
```

Il risultato torna al WebView con evento:

```text
meteo-fast-location
```

### Soglie qualita posizione

| Caso | Eta massima | Accuratezza massima | Uso |
| --- | ---: | ---: | --- |
| fast | 15 minuti | 5000 m | usare subito |
| confirm | 60 minuti | 10000 m | accettabile come conferma |
| altro | oltre soglia | oltre soglia | non usare |

Timeout:

- fast native: 1200 ms;
- balanced native: 2800 ms;
- browser geolocation in APK: 3000 ms;
- browser geolocation web: 10000 ms.

### Fallimenti posizione

La policy vecchia mantiene la posizione automatica attiva dopo fallimenti temporanei:

- `permission_pending`;
- `native_location_timeout`;
- `null_location`;
- `native_unavailable`;
- errori di qualita temporanei.

La spegne solo per:

- `denied`;
- `permission_denied`;
- `unsupported`.

Questa distinzione e' importante: dopo il consenso Android, il sistema puo metterci qualche istante a restituire una posizione. Non va trattato come rifiuto.

### Provider Android

La vecchia app considera attivi i servizi posizione se e' disponibile almeno uno fra:

```text
LocationManager.GPS_PROVIDER
LocationManager.NETWORK_PROVIDER
```

La richiesta bilanciata usa il Fused Location Provider con priorita:

```text
Priority.PRIORITY_BALANCED_POWER_ACCURACY
```

Quindi il recupero posizione non dipende solo dal GPS satellitare: puo usare anche rete mobile, Wi-Fi, celle o posizione recente, se Android li considera validi.

## Notifiche: comportamento vecchia app

### Sequenza di apertura

La vecchia app chiama la richiesta notifiche solo quando:

- esiste una localita risolta/scelta;
- l'app e' nativa Android;
- `startupNotificationsAsked:v1` non e' gia stato salvato;
- `weatherAlertsEnabled` non e' gia attivo.

Poi salva:

```text
startupNotificationsAsked:v1 = true
```

e chiama `handleWeatherAlertsChange(true)`.

### Push native

`registerNativePushNotifications()`:

1. carica Capacitor e `@capacitor/push-notifications`;
2. esce con `unsupported` se non e' piattaforma nativa;
3. registra listener `registration` e `registrationError`;
4. controlla `PushNotifications.checkPermissions()`;
5. se `receive === "prompt"`, chiama `PushNotifications.requestPermissions()`;
6. se non concesso, cancella token/backend;
7. se concesso, crea canale Android e chiama `PushNotifications.register()`.

Canale Android:

```text
id: weather_alerts
name: Avvisi Meteo
importance: 4
visibility: 1
lights: true
vibration: true
```

### Payload backend device

`POST /api/devices/register` riceve:

```text
installation_id
token
platform
city
language
device_name
alerts_enabled
notification_preferences
```

Il backend normalizza:

- lingua solo `it` o `fur`, altrimenti `it`;
- nome dispositivo;
- preferenze notifiche.

`POST /api/devices/unregister` riceve:

```text
installation_id
```

## Manifest Android

La vecchia app dichiara:

```text
ACCESS_COARSE_LOCATION
ACCESS_FINE_LOCATION
POST_NOTIFICATIONS
```

e blocca la rotazione:

```text
android:screenOrientation="portrait"
```

Questo va mantenuto nella nuova app Android.

## Contratto UI3 da implementare dopo audit

### Startup gate

Stati minimi:

| Stato | Significato |
| --- | --- |
| `gps_prompt_pending` | il prompt Android posizione deve ancora essere risolto |
| `gps_granted_resolving` | permesso concesso, ricerca posizione/reverse in corso |
| `gps_denied` | utente ha negato posizione |
| `gps_unavailable` | servizi spenti/non disponibili |
| `gps_temporary_failure` | errore temporaneo, non spegnere posizione automatica |
| `location_resolved` | comune risolto da GPS |
| `manual_location_required` | serve scelta localita manuale |
| `notifications_prompt_pending` | localita ok, si puo chiedere notifica nativa |
| `ready` | app pronta |

### Regole

- Posizione automatica attiva di default su primo avvio Android.
- Prima apertura Android: tentare posizione nativa.
- Se posizione accettata e reverse FVG ok: salvare localita risolta e proseguire.
- Se posizione negata: lasciare possibile scelta manuale; Bollettino regionale resta disponibile.
- Se posizione temporaneamente lenta: non salvare un fallback manuale e non spegnere auto-location.
- Solo dopo localita risolta/scelta: chiedere notifiche native una volta.
- Nessuna notifica reale collegata finche non viene importato il modulo push e verificato su APK.

## Cosa non importare ora

- Invio push reale.
- Scheduler o backend check.
- Token FCM in UI3.
- WorkManager/background location.
- WatchPosition continuo.
- Pannelli custom di consenso.

## Debiti aperti

- UI3 oggi ha un flusso browser `Usa posizione` in Opzioni: va considerato laboratorio/web, non flusso finale Android.
- Serve modulo startup dedicato, non logica sparsa in `App.jsx`.
- Serve separare ancora:
  - posizione meteo/localita;
  - posizione segnalazioni Vedi/Cjale;
  - posizione dispositivo per Eventi vicino a me.
- Serve test Android reale o emulatore prima di dichiarare completo il gate.

## Ripresa audit 2026-06-30

Questa ripresa conferma lo stato dopo il riavvio del workspace e prima di qualsiasi collegamento nativo.

### Stato UI3 verificato

| Area | Esito |
| --- | --- |
| Capacitor/Android | `frontend/package.json` non contiene ancora Capacitor, Push Notifications o Android project. |
| Bridge Android | Non esiste ancora `frontend/android/` in UI3. |
| GPS web | `frontend/src/services/deviceLocation.js` usa solo `navigator.geolocation.getCurrentPosition()`. |
| Reverse geocoding | `frontend/src/services/reverseLocation.js` chiama `/location/reverse` e usa cache locale 7 giorni. |
| Opzioni | `App.jsx` collega solo il tap esplicito `Usa posizione` in Settings. |
| Startup Android | `frontend/src/domain/startup/androidPermissionGate.js` e' gia modulo puro, senza Capacitor e senza richieste reali. |
| Notifiche | Nessun modulo push reale e nessuna registrazione token sono presenti in UI3. |

Conclusione: UI3 ha il contratto decisionale, ma non ha ancora il livello nativo Android. Quindi non e' stato collegato nulla che possa chiedere permessi reali o inviare token.

### Vecchia app verificata

| File vecchia app | Cosa e' stato confermato |
| --- | --- |
| `frontend/android/app/src/main/AndroidManifest.xml` | Permessi `ACCESS_COARSE_LOCATION`, `ACCESS_FINE_LOCATION`, `POST_NOTIFICATIONS`, blocco `portrait`, canale FCM. |
| `frontend/android/app/src/main/java/com/meteofriul/app/MainActivity.java` | Bridge `window.MeteoAndroid`, Fused Location Provider, `requestFastLocation`, `requestBalancedLocation`, evento `meteo-fast-location`. |
| `frontend/src/App.jsx` | Orchestrazione startup: auto-location attiva di default, tentativo GPS, fallback controllato, richiesta notifiche dopo localita. |
| `frontend/src/utils/autoLocationPolicy.js` | Distinzione tra fallimenti temporanei e rifiuto/unsupported. |
| `frontend/src/utils/pushNotifications.js` | Capacitor Push: check/request permission, canale Android, register/unregister token. |
| `frontend/capacitor.config.json` | `appId=com.meteofriul.app`, `webDir=dist`, presentation options push. |
| `frontend/package.json` | Capacitor Android e `@capacitor/push-notifications` presenti; non risulta `@capacitor/geolocation`. |

Nota tecnica importante: nella vecchia app il bridge Android non mostra da solo il prompt permesso posizione. Il bridge legge/usa i permessi e restituisce `permission_denied` o payload posizione. La richiesta effettiva della posizione passa poi anche da `navigator.geolocation.getCurrentPosition()`, che nel WebView/Capacitor attiva il prompt posizione del sistema. Se in UI3 vogliamo un gate piu pulito, va deciso se mantenere questo schema o introdurre un adapter nativo dedicato, ma senza copiare `App.jsx`.

### Decisione aggiornata

- Il modulo `androidPermissionGate` resta la fonte della sequenza.
- Il gate Android finale deve stare in un orchestratore dedicato, non dentro componenti UI.
- Il primo avvio APK deve chiedere posizione nativa come primo permesso.
- Dopo esito posizione e localita risolta/scelta, si puo chiedere il permesso notifiche nativo.
- La UI puo mostrare stati successivi, ma non deve sostituire i prompt Android con finestre custom.
- Le notifiche restano scollegate: niente token FCM, niente register/unregister, niente invio reale in questa fase.

### Prossima tranche consigliata

1. Preparare `nativeLocationAdapter` UI3 con interfaccia pura:
   - `getNativeLocationStatus()`;
   - `requestFastLocation()`;
   - `requestBalancedLocation()`;
   - fallback web controllato.
2. Preparare `nativePushAdapter` UI3 con interfaccia pura:
   - `checkPermissions()`;
   - `requestPermissions()`;
   - `register()`;
   - `unregister()`;
   - nessuna chiamata backend finche non approvata.
3. Solo dopo, collegare l'orchestratore startup Android al gate.
4. Verifica obbligatoria su APK/emulatore: ordine prompt GPS -> notifiche, rifiuto GPS, GPS lento, notifiche negate, rotazione bloccata.

## Adapter posizione esplicito UI3 2026-06-30

Creato:

```text
frontend/src/services/nativeLocationAdapter.js
frontend/src/services/nativeLocationAdapter.test.js
```

Scopo:

- smettere di ragionare sul prompt posizione come effetto collaterale della WebView;
- definire un contratto esplicito fra UI3 e Android;
- mantenere l'adapter fuori dalla UI e fuori dallo startup finche non esiste Android project in UI3;
- rendere testabili timeout, request id, payload e stato del bridge.

Interfaccia prevista:

| Funzione | Ruolo |
| --- | --- |
| `getNativeLocationStatus()` | legge stato permesso/servizi dal bridge Android. |
| `requestNativeLocationPermission()` | richiede il permesso posizione tramite metodo esplicito nativo futuro. |
| `requestNativeFastLocation()` | chiede una posizione rapida al bridge. |
| `requestNativeBalancedLocation()` | chiede una posizione bilanciata con timeout controllato. |
| `normalizeNativeLocationPayload()` | normalizza coordinate, accuratezza, eta e stato per la policy posizione. |

Contratto bridge futuro:

```text
window.MeteoAndroid.getLocationStatus()
window.MeteoAndroid.requestLocationPermission(requestId)
window.MeteoAndroid.requestFastLocation(requestId)
window.MeteoAndroid.requestBalancedLocation(requestId, timeoutMs)
```

Risultato verso WebView:

```text
window.dispatchEvent(new CustomEvent("meteo-native-location", { detail: payload }))
```

Nota: la vecchia app usa `meteo-fast-location` e non espone `requestLocationPermission`. UI3 non deve dipendere da quella ambiguita: quando arrivera Android project, il bridge andra aggiornato al contratto esplicito sopra.

Non collegato:

- nessun prompt GPS reale;
- nessun Android project;
- nessuna modifica ad `App.jsx`;
- nessuna notifica;
- nessun token;
- nessun backend.

## Adapter notifiche native esplicito UI3 2026-06-30

Creato:

```text
frontend/src/services/nativePushAdapter.js
frontend/src/services/nativePushAdapter.test.js
```

Scopo:

- separare il prompt notifiche nativo dalla registrazione backend;
- evitare che l'app UI3 salvi token o chiami `/devices/register` prima della tranche dedicata;
- preparare un contratto testabile per Capacitor Push Notifications;
- mantenere le notifiche dopo il gate GPS/localita, come deciso in `androidPermissionGate`.

Interfaccia prevista:

| Funzione | Ruolo |
| --- | --- |
| `checkNativePushPermission()` | legge lo stato permesso dal plugin nativo. |
| `requestNativePushPermission()` | chiede il permesso solo se lo stato e' `prompt`. |
| `ensureNativePushAndroidChannel()` | crea il canale Android `weather_alerts` solo su Android. |
| `registerNativePush()` | chiama solo `PushNotifications.register()`, senza backend. |
| `unregisterNativePush()` | chiama solo `PushNotifications.unregister()`, senza backend. |
| `addNativePushListeners()` | inoltra token/errori a callback esplicite, senza localStorage. |

Canale Android previsto:

```text
id: weather_alerts
name: Avvisi Meteo
importance: 4
visibility: 1
lights: true
vibration: true
```

Guardrail:

- nessun `installation_id`;
- nessun `pushRegistrationToken`;
- nessun `pushDeviceName`;
- nessuna chiamata `POST /devices/register`;
- nessuna chiamata `POST /devices/unregister`;
- nessun invio reale;
- nessun collegamento allo startup.

Prossimo collegamento consentito solo dopo:

1. Android/Capacitor project presente in UI3;
2. adapter posizione collegato e verificato;
3. decisione esplicita sul payload device/backend;
4. test APK/emulatore sul prompt notifiche nativo.

## Orchestratore startup GPS -> notifiche UI3 2026-07-02

Creato:

```text
frontend/src/domain/startup/androidStartupPromptFlow.js
frontend/src/domain/startup/androidStartupPromptFlow.test.js
```

Scopo:

- formalizzare l'ordine dei prompt Android prima del collegamento reale;
- chiamare sempre la posizione dispositivo prima delle notifiche quando `autoLocationEnabled` e' attivo;
- chiedere le notifiche solo dopo una localita risolta da posizione o una localita manuale gia selezionata;
- fermarsi su richiesta manuale localita se il permesso posizione viene negato e non esiste una localita utile;
- non ripetere il prompt notifiche se `startupNotificationsAsked:v1` e' gia vero o se `weatherAlertsEnabled` e' gia vero.

Guardrail:

- nessun prompt reale aperto;
- nessun import diretto di Capacitor Push Notifications;
- nessuna registrazione FCM;
- nessun salvataggio token;
- nessuna chiamata backend device;
- nessun Android project aggiunto.

Verifica:

- test mirati startup/push/location: 4 file, 35 test passati.

Restano fuori:

- collegare `androidStartupPromptFlow` ad `App.jsx`;
- persistere i patch storage prodotti dal flow;
- collegare il plugin nativo push reale;
- test APK/emulatore dell'ordine visibile GPS -> notifiche.

## Collegamento App runtime Android UI3 2026-07-02

Creato:

```text
frontend/src/app/androidStartupRuntime.js
frontend/src/app/androidStartupRuntime.test.js
```

Aggiornato:

```text
frontend/src/app/App.jsx
```

Comportamento:

- il flow startup viene eseguito solo se il runtime e' Android nativo;
- nel browser non parte nessun prompt posizione automatico;
- la posizione startup usa lo stesso percorso tecnico del pulsante `Usa posizione`;
- il primo avvio Android interpreta assenza di storage come `autoLocationEnabled=true`;
- le notifiche restano dry-run `unsupported` finche' non colleghiamo il plugin push reale;
- una patch notifiche dry-run non viene salvata, cosi non blocca il prompt futuro.

Guardrail:

- nessun token FCM;
- nessun backend device;
- nessuna registrazione push;
- nessun Android project;
- nessuna modifica alle fonti meteo.

Verifica:

- test mirati startup/runtime/location: 34 test passati;
- suite completa frontend: 475 test passati;
- lint e build passati.

Restano fuori:

- collegare il plugin nativo push reale;
- test APK/emulatore dell'ordine prompt posizione -> notifiche;
- decidere e testare registrazione device/backend.
