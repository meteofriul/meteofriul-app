# Audit Android: posizione e segnalazioni meteo

Data audit: 2026-10-02
Ramo: `codex/android-location-reporting-audit`
Baseline: `main` / `f89af76b928335bcf129e69ebc3b6b4e9918e8e4`
Esito: audit concluso; contratto raccomandato approvato, correzione frontend
applicata e percorso negativo verificato sul dispositivo reale; nessun push o
deploy.

## Sintesi esecutiva

Il flusso corrente separa correttamente la localita selezionata nell'app dalla
posizione usata per inviare una segnalazione. La localita manuale o persistita
serve per meteo e lettura del feed, ma non sostituisce un campione GPS recente.
Il backend rifiuta campioni oltre 120 secondi o con accuratezza peggiore di 500
metri e persiste/pubblica il centro canonico del Comune, non le coordinate GPS
grezze ricevute.

E stato pero riprodotto un difetto di controllo nello stesso ciclo in primo
piano: dopo che il modulo ha acquisito una posizione valida, spegnere i servizi
di localizzazione Android non invalida lo stato `ready`. Il pulsante
`Conferma e invia` resta abilitato e l'invio ordinario riutilizzerebbe il
campione gia acquisito finche la sua eta resta entro 120 secondi. Il backend non
puo conoscere lo stato corrente dell'interruttore Android e accetterebbe quel
campione se tutti gli altri vincoli fossero rispettati.

Il problema e classificato **medio**: non e una fuga di dati, non consente di
usare indefinitamente una posizione vecchia e non rende pubbliche coordinate
precise; viola pero l'aspettativa di una verifica GPS al momento della conferma
e rende ambiguo il consenso quando i servizi vengono spenti dopo l'acquisizione.

La correzione raccomandata e una verifica/acquisizione finale della posizione
al momento dell'invio, con invalidazione immediata del modulo in caso di
servizi spenti, permesso revocato, posizione approssimativa, timeout o campione
non conforme. Il contratto e stato approvato dall'utente il 2026-10-02 e la
correzione minima e stata applicata sul ramo dell'audit.

## Vincoli e metodo

- Audit eseguito sul ramo dedicato, riallineato al nuovo `main` senza riportare
  modifiche locali del filone webcam.
- Revisione del flusso React, adapter Capacitor/browser, client API, controller
  della segnalazione, backend e documentazione privacy/operativa.
- Verifica dinamica su Samsung SM-A525F con app `com.meteofriul.app` versione
  `0.1.8` (`versionCode 300025`).
- Nessuna segnalazione pubblica e stata inviata. E stato selezionato un tipo di
  fenomeno solo per verificare lo stato del pulsante.
- Al termine, servizi di localizzazione e permessi fine/coarse/background sono
  stati ripristinati allo stato iniziale; l'app e stata lasciata chiusa sul
  launcher.
- Le schermate ADB sono evidenze locali ignorate da Git sotto
  `.dev-logs/android-location-audit/`; non fanno parte della consegna.

## Comportamento osservato sul dispositivo prima della correzione

La tabella descrive il comportamento della versione Android installata prima
della correzione. La verifica post-fix su un package pilot isolato e documentata
piu avanti.

| Scenario | Risultato osservato | Valutazione |
| --- | --- | --- |
| Avvio a freddo con servizi di localizzazione spenti | Android mostra il prompt per attivare la posizione; chiudendolo, il modulo non ottiene una posizione e l'invio resta disabilitato | Sicuro; testo del modulo troppo generico |
| Servizi attivi e permessi precisi | Dopo l'acquisizione compare Pordenone, origine GPS e avviso di approssimazione pubblica; selezionando il fenomeno l'invio si abilita | Conforme al contratto attuale |
| Servizi spenti dopo acquisizione, modulo ancora in primo piano | Testo e pulsante restano invariati e `Conferma e invia` resta abilitato | Difetto riprodotto |
| App portata in background e poi ripresa con servizi spenti | Il modulo viene rivalidato, mostra errore e disabilita l'invio | Sicuro al resume |
| Solo posizione approssimativa Android | L'invio resta bloccato | Sicuro; messaggio errato: indica GPS spento/non disponibile |
| Permessi fine e coarse negati | L'invio resta bloccato e il testo segnala il permesso negato | Sicuro; testo migliorabile per il contesto Android |
| Riavvio con servizi spenti | Nuova acquisizione fallisce e l'invio resta bloccato | Sicuro |

La riproduzione critica non prova un invio reale: il pulsante non e stato
premuto. L'accettazione lato server entro 120 secondi deriva dal flusso del
client e dai vincoli backend verificati nei test automatici.

## Correzione implementata dopo l'approvazione

Per create, correct e replacement, `CommunityReportForm` ora esegue una seconda
verifica prima del POST e usa esclusivamente il risultato di tale verifica.
Durante il controllo il pulsante viene bloccato. Se servizi, permessi,
precisione o acquisizione non sono conformi, lo stato GPS precedente viene
invalidato, il fenomeno selezionato resta compilato e la mutazione non parte.

La richiesta finale passa `requireCurrent: true` al controller. Il servizio di
posizione applica:

- `maximumAge: 0` e alta accuratezza per Capacitor e Web/PWA;
- percorso Android bilanciato/corrente, senza il fast path da cache, per il
  bridge nativo legacy;
- limite locale di 30 secondi sul campione restituito, lasciando invariato il
  limite backend di 120 secondi come difesa in profondita.

La localita manuale legacy viene mantenuta solo se compare ancora fra i luoghi
compatibili con il nuovo fix. Il pilot corrente continua a usare il Comune
risolto dal nuovo campione. Rinnovi di una propria osservazione e conferme di un
gruppo esistente non sono stati modificati: non inviano coordinate e non fanno
parte del POST create/correct/replace interessato dal difetto.

Sono stati aggiunti messaggi distinti per servizi di posizione disattivati e
autorizzazione soltanto approssimativa, in italiano e friulano.

## Flusso completo

### 1. Posizione attiva dell'app

`frontend/src/app/appLocation.js` gestisce la localita usata per meteo, mappe e
lettura del feed. Una localita manuale puo usare le coordinate del catalogo
comunale; una localita automatica conserva dati canonici e metadati di
accuratezza/tempo senza trasformarsi automaticamente in autorizzazione per una
segnalazione.

`frontend/src/services/localCommunityPilot.js` conferma il contratto: la
localita selezionata determina lo scope di lettura, mentre l'invio richiede una
posizione GPS recente. Nel pilot corrente l'editor manuale del luogo nel modulo
non e esposto.

### 2. Acquisizione Capacitor e Web/PWA

`frontend/src/services/capacitorLocationAdapter.js` usa tre tentativi:

1. rapido, bassa accuratezza, cache massima 30 secondi;
2. bilanciato, campione nuovo e timeout 5 secondi;
3. preciso, alta accuratezza e timeout 18,5 secondi.

Per la segnalazione, `frontend/src/services/deviceLocation.js` rifiuta una
posizione classificata `approximate`. Su Android viene preferito Capacitor; il
browser e un fallback solo quando Capacitor non e disponibile, non dopo un
errore reale del plugin. Sul Web/PWA viene usata una richiesta one-shot con
`maximumAge: 0` e timeout 25 secondi.

Il problema successivo all'acquisizione e condiviso concettualmente anche dal
Web/PWA: il componente conserva lo stato `ready` e l'invio non richiede una
nuova verifica. Il caso browser non e stato riprodotto dinamicamente in questo
audit e resta una conclusione derivata dal codice.

### 3. Risoluzione del Comune

`locateLiveCommunityReport` in
`frontend/src/features/live/liveReportController.js` richiede una posizione
con accuratezza massima 500 metri ed eta massima 120 secondi. Nel flusso v2
chiama poi `/api/community/resolve`, che riceve:

- `lat` e `lon` precise;
- `accuracy_m`;
- `age_ms`.

Il server valida il campione e risolve il Comune attraverso la geografia
canonica/offline del progetto. Il luogo salvato nell'app non viene usato come
prova alternativa.

### 4. Stato del modulo

`CommunityReportForm` in `frontend/src/features/live/LiveView.jsx` acquisisce la
posizione all'apertura e la conserva nello stato del componente. Il pulsante e
abilitato in base a tipo selezionato, termini accettati e
`locationState.status === "ready"`.

Mancano:

- una scadenza a timer dello stato `ready`;
- una verifica dei permessi/servizi mentre il modulo resta in primo piano;
- una nuova acquisizione o verifica al click su `Conferma e invia`.

Il resume dell'app ha provocato una rivalidazione nel test reale, ma non copre
lo spegnimento effettuato mentre il modulo resta visibile.

### 5. Payload di invio

Nel flusso v2 corrente, `frontend/src/services/liveApi.js` invia a
`/api/community/reports`:

- consenso e versione della policy;
- `client_id` pseudonimo e identificazione pubblica opzionale;
- tipo della segnalazione;
- Comune/ISTAT risolto;
- `lat` e `lon` precise;
- `accuracy_m`;
- `age_ms`, ricalcolata da `locatedAt` al momento dell'invio;
- `operation_id` e, quando necessario, token di sostituzione.

Il journal locale in
`frontend/src/features/live/pilotReportOperations.js` conserva l'intento e gli
identificatori necessari all'idempotenza, non le coordinate GPS precise.

### 6. Validazione e persistenza server

`backend/app/services/pilot_community.py` applica i vincoli principali:

- `0 < accuracy_m <= 500`;
- `0 <= age_ms <= 120000`;
- Comune/ISTAT e nome selezionato coerenti con la posizione risolta;
- distanza e regole di vicinato;
- termini e versione della policy;
- tipo ammesso, quote, univocita, moderazione e proprieta/revisione per le
  modifiche.

I campioni non conformi vengono rifiutati con
`community_fresh_gps_required`. Il server non puo pero verificare se, dopo il
campionamento, l'utente abbia spento i servizi Android o revocato il permesso:
riceve soltanto coordinate, accuratezza ed eta dichiarate dal client ufficiale.

La registrazione storica e la risposta pubblica contengono il punto canonico
del Comune e `locationPrecision: "zone"`, non il fix preciso. Le coordinate
grezze transitano comunque nella richiesta per la validazione.

## Messaggi, consenso e privacy

Aspetti conformi:

- il modulo informa che la segnalazione e anonima/non verificata e visibile per
  circa un'ora;
- la posizione pubblica e presentata come approssimata;
- la documentazione privacy descrive l'uso transitorio del fix preciso e la
  persistenza del centro comunale;
- non viene costruita una cronologia degli spostamenti.

Ambiguita da correggere:

- `location_services_disabled` non ha una mappatura dedicata in
  `frontend/src/features/live/liveReportFeedback.js`, quindi puo produrre il
  generico “Non e stato possibile inviare la segnalazione”;
- `approximate_location` ricade nel testo “GPS spento o non disponibile”, che
  non descrive il caso reale;
- “Posizione rilevata dal GPS” non mostra quando e avvenuta la verifica ne
  chiarisce che un campione recente puo restare valido fino a due minuti;
- il consenso nel modulo non esplicita che le coordinate precise transitano al
  server prima di essere ridotte al punto comunale pubblico. La privacy page lo
  documenta, ma una frase contestuale renderebbe la scelta piu trasparente.

## Causa del difetto

La causa non e un fallback sulla localita manuale e non e un errore di
persistenza server. E una discrepanza temporale fra tre livelli:

1. il client acquisisce un fix e mantiene `locationState` pronto;
2. il submit ordinario riusa quel fix e ne aggiorna solo `age_ms`;
3. il server considera valido ogni fix entro 120 secondi e non conosce lo stato
   corrente dei servizi del dispositivo.

Il flusso di sostituzione ha controlli locali di freschezza aggiuntivi, ma il
flusso ordinario create/correct non effettua la stessa verifica finale.

## Comportamento corretto proposto

### Raccomandazione

Al click su `Conferma e invia`, prima di qualsiasi POST di creazione o
correzione:

1. passare il modulo allo stato di verifica e disabilitare il pulsante;
2. verificare permessi e servizi e richiedere un nuovo campione con
   `maximumAge: 0`;
3. applicare gli stessi limiti di precisione e area e risolvere nuovamente il
   Comune se il fix e cambiato;
4. inviare solo la posizione appena verificata;
5. in caso di errore, invalidare il precedente stato `ready`, conservando tipo
   selezionato e testo inserito per consentire un nuovo tentativo.

Il backend deve mantenere i limiti 120 secondi/500 metri come difesa in
profondita. Portare l'eta server a zero non e praticabile per latenza di rete e
durata della richiesta.

In aggiunta:

- invalidare/rivalidare la posizione su resume, cambio di visibilita e scadenza
  locale;
- aggiungere messaggi distinti per servizi spenti, permesso negato,
  autorizzazione solo approssimativa, timeout e fix impreciso;
- mostrare “verificata ora” o un tempo relativo, senza visualizzare coordinate
  grezze;
- spiegare nel consenso contestuale che il fix preciso e usato transitoriamente
  per verificare il Comune e che il punto pubblico e approssimato.

### Alternativa non raccomandata

Mantenere valido il fix per 120 secondi anche con servizi successivamente
spenti e tecnicamente coerente con l'attuale policy server. Richiederebbe pero
una dichiarazione esplicita nel modulo (“posizione verificata N secondi fa”) e
un'accettazione consapevole di questo comportamento. Non risolve l'aspettativa
espressa dall'utente di una verifica attuale al momento dell'invio.

## Piano minimo di correzione eseguito

1. Il controller supporta una richiesta finale corrente e senza cache per
   create, correct e replacement.
2. Il submit usa il risultato della verifica, non la posizione conservata
   all'apertura.
3. Stato del modulo e copy degli errori sono aggiornati senza cancellare il
   fenomeno selezionato.
4. Payload, validazione server e regola di non persistenza delle coordinate
   precise restano invariati.
5. Non sono state incluse modifiche webcam, ai flussi di build, deploy o
   configurazioni Cloud/Firebase.

## Test richiesti per la correzione

### Frontend unit/integration

- servizi attivi all'apertura, spenti prima del submit: nessuna chiamata create;
- permesso revocato dopo il fix: nessuna chiamata create;
- solo posizione approssimativa: blocco e messaggio dedicato;
- nuovo fix preciso al submit: payload usa il nuovo campione;
- fallimento della verifica finale: fenomeno e testo restano compilati;
- scadenza a 120001 ms: stato invalidato;
- localita manuale/persistita: mai usata come coordinate di submit;
- resume e `visibilitychange`: rivalidazione coerente su Android e Web/PWA;
- nessuna coordinata precisa nel journal locale.

### Backend

- 120000 ms accettato e 120001 ms rifiutato;
- 500 m accettato e valore superiore rifiutato;
- Comune/ISTAT incongruente rifiutato;
- record persistito e risposta pubblica contengono soltanto il punto canonico;
- idempotenza e replacement non reintroducono coordinate grezze persistenti.

### Matrice dispositivo reale

- servizi spenti prima dell'apertura;
- servizi spenti dopo il fix e prima del submit, restando in primo piano;
- permesso preciso revocato e modalita approssimativa;
- background/resume e force-stop/restart;
- passaggio manuale ad altro Comune;
- Web/PWA con revoca del permesso e cambio visibilita;
- cattura del payload verso ambiente locale/test, senza pubblicare una
  segnalazione reale non necessaria.

## Verifiche automatiche eseguite

Frontend:

```text
Set mirato della correzione: 7 file, 98 test superati
Suite completa: 530 file superati, 5 saltati
Suite completa: 4708 test superati, 13 saltati
```

Comando eseguito tramite lo script repository, che usa il loader Vite nativo:

```text
npm test -- src/services/capacitorLocationAdapter.test.js \
  src/services/deviceLocation.test.js \
  src/features/live/liveReportController.test.js \
  src/features/live/CommunityReportForm.directEdit.test.jsx \
  src/features/live/CommunityReportForm.submitLocation.test.jsx \
  src/features/live/CommunityReportForm.locationCopy.test.jsx \
  src/copy/liveViewCopy.test.js
npm test
npm run lint
```

Backend:

```text
48 test superati, 8 subtest superati
python -m pytest tests/test_pilot_community.py -q
```

I test attuali coprono permessi, posizione approssimativa, eta, accuratezza,
geografia e validazione server. I nuovi test coprono anche lo spegnimento dei
servizi fra acquisizione iniziale e submit, il blocco del POST, l'uso del nuovo
fix, la posizione approssimativa e i percorsi correnti Capacitor/bridge nativo.

## Verifica reale post-fix

La correzione e stata compilata e installata sul Samsung SM-A525F nel package
isolato `com.meteofriul.app.localpilot`, lasciando intatta l'app Play
`com.meteofriul.app`. La build `localPilot` versione `0.1.8-local-pilot`
(`versionCode 300025`) ha superato le guardie del repository. APK verificato:

```text
frontend/android/app/build/outputs/apk/localPilot/app-localPilot.apk
SHA-256 04ceab284d7aaa7cd085a62121a0f748e787d8afad8169751af4341478ace301
```

Il profilo usava il backend meteo cloud e il servizio Community ufficiale. Per
questo la prova e stata deliberatamente limitata al percorso negativo, senza
inviare una segnalazione pubblica.

Sequenza verificata sul telefono:

1. con posizione attiva, il modulo ha acquisito Pordenone ed e arrivato allo
   stato pronto;
2. e stato selezionato `Situazione tranquilla` e accettato il consenso;
3. i servizi di posizione sono stati spenti lasciando il modulo in primo piano;
4. al click su `Conferma e invia`, la verifica finale ha invalidato il fix
   precedente e mostrato `Servizi di posizione disattivati: attivali nelle
   impostazioni del dispositivo.`;
5. il pulsante e diventato disabilitato, mentre il fenomeno selezionato e
   rimasto compilato;
6. `Riprova GPS`, dopo la riattivazione dei servizi, ha riportato il modulo allo
   stato pronto senza perdere la selezione.

Una cattura diretta degli eventi di rete del WebView durante una seconda prova
ha registrato zero richieste Community e, in particolare, zero `POST` a
`/community/reports`. Non e stato eseguito il submit positivo con posizione
attiva, per evitare una mutazione pubblica non necessaria.

Al termine i servizi di posizione del telefono sono stati ripristinati su
attivi, i permessi dell'app Play principale sono rimasti invariati, l'app pilot
e stata arrestata e i quattro servizi locali usati per il test sono stati
chiusi tramite il launcher protetto. Le evidenze ADB/XML locali restano ignorate
da Git in `.dev-logs/android-location-audit/`.

## Decisione approvata

Contratto scelto:

- nuova verifica GPS obbligatoria per ogni submit create/correct/replace;
- nessun invio quando la verifica fallisce;
- backend invariato come difesa in profondita.

La correzione e verificata automaticamente e sul dispositivo reale per il caso
critico servizi attivi all'acquisizione e spenti prima del submit. Il controllo
di rete conferma che la mutazione non parte. Push e deploy non sono stati
eseguiti.
