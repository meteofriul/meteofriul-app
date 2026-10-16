# Meteo Friul UI 3.0.0 - Audit visualizzazione dati Bollettino

Data: 2026-06-27

## Scopo

Questo audit chiude una regola di prodotto per il Bollettino:

la UI non deve mostrare previsioni, mappe, allerta o dati utili alternativi quando manca il dato ufficiale previsto.

La schermata puo' degradare, ma non deve sostituire OSMER/ARPA FVG con fixture, proiezioni o fonti di supporto senza dichiararlo.

## Verifica locale read-only

Preview locale:

- frontend: `http://127.0.0.1:5173/?tab=bulletin`
- backend locale: `http://127.0.0.1:8001`

Endpoint letti in sola lettura:

- `GET /api/health/data-sources`
- `GET /api/weather/bootstrap?city=Udine`

Esito osservato il 2026-06-27 alle 18:18 circa:

- `osmer_bulletin`: ok;
- `protezione_civile_alerts`: ok nel controllo locale;
- `forecast.osmer_structured`: presente;
- `forecast.osmer_structured.source_status`: `merged_xml_window`;
- giorni OSMER strutturati: 5;
- giorni con `source_kind=structured_xml`: 5;
- ogni giorno ha A1-A9 complete e F1-F4 complete;
- `official_alerts.source_mode`: `github_actions_dpc_national_criticity_no_active_fvg_unverified`;
- `official_alerts.active`: `false`.

Conclusione:

- la mappa nativa del Bollettino e' mostrabile per questo payload, perche' arriva da XML strutturato OSMER completo;
- il payload allerta DPC/no-active non e' una conferma verde FVG e non deve generare avviso visibile;
- il testo giornaliero arriva dal blocco ufficiale OSMER italiano;
- il testo FUR resta una passata dedicata, non fonte primaria del bollettino.

## Regola di visualizzazione

### Mappa

Mostrare overlay meteo sulla mappa solo se:

- esiste un giorno OSMER strutturato per la data selezionata;
- `source_kind=structured_xml`;
- A1-A9 sono complete;
- il dato non e' marcato stale/unavailable;
- il contratto `canRenderNativeMap` e' vero.

Se manca una di queste condizioni:

- mostrare la base mappa Meteo Friul;
- mostrare stato dati non disponibili;
- non inventare marker;
- non usare `official_projected` come mappa nativa.

### Testo previsionale

Mostrare testo del giorno solo se arriva da:

- `forecast.official.it.forecasts[*].text`;
- oppure campo ufficiale equivalente gia normalizzato dal backend.

Non mostrare testo fixture come previsione reale.

### Proiezioni `official_projected`

`official_projected` puo' restare utile per audit, confronto e laboratorio.

Nella UI utente non e' equivalente a XML OSMER:

- non abilita la mappa nativa;
- non produce marker ufficiali;
- non deve sembrare una previsione ufficiale strutturata;
- se un giorno verra' mostrato, dovra' avere etichetta distinta e decisione esplicita.

### Fixture

Le fixture sono ammesse solo per:

- sviluppo visuale;
- test;
- lab espliciti.

Non sono ammesse come fallback silenzioso nella route Bollettino reale.

Correzione applicata:

- `buildBulletinViewModel()` non usa piu' fixture come contenuto reale di default;
- le fixture sono disponibili solo con `allowFixtureFallback: true`;
- senza dato ufficiale la UI produce `status=unavailable`, testo di indisponibilita', niente marker, niente focus/data utili finti.

### Allerte

Mostrare un avviso allerta solo se il dominio `officialAlerts` classifica lo stato come realmente azionabile.

Non mostrare:

- DPC diagnostico;
- fonte non disponibile;
- payload stale;
- verde non confermato dalla fonte regionale FVG;
- allerta scaduta senza conferma regionale fresca.

## Stato dei dati utili

I dati utili del Bollettino non devono essere riempiti da fixture.

Finche' non hanno fonte reale dichiarata, la sezione resta nascosta.

In futuro possono entrare solo se il modello dati indica chiaramente:

- fonte;
- data/ora;
- localita o area;
- affidabilita del dato;
- differenza tra dato ufficiale regionale e dato locale automatico.

## Audit campo per campo

Strumento laboratorio:

```text
python -B backend_dryrun_staging/bulletin_display_payload_audit.py --city Pordenone
```

Il comando legge payload salvati, URL read-only o bootstrap locale per citta e produce una tabella:

```text
Campo UI -> path payload -> fonte -> stato -> show/no-show -> motivo
```

Non scrive storage, non invia FCM, non chiama workflow e non collega la UI live.

Regole protette:

- `source.title` e' copy UI, non dato meteo;
- `source.updatedLabel` e' mostrabile solo se esistono testo ufficiale OSMER o `osmer_structured`;
- `alert.banner` e' mostrabile solo per allerta regionale non verde e non diagnostica;
- `days[*].officialText` richiede testo ufficiale/normalizzato;
- `days[*].nativeMap` richiede `structured_xml`, A1-A9 complete e dato non stale;
- `days[*].reliability` si mostra solo se anche la mappa nativa e' usabile.

Verifica read-only su Pordenone:

```text
righe=24
show=23
no-show=1
testi=5
mappe=5
```

L'unico no-show osservato e' corretto: `alert.banner` resta nascosto perche' il payload letto e' diagnostico DPC/no-active non verificato come verde regionale FVG.

## Confronto audit dati / UI Bollettino

Tranche 98 verifica che il view model usato dalla UI rispetti lo stesso criterio dell'audit payload.

Regola corretta:

- se `days[*].nativeMap` non e' mostrabile, anche `days[*].reliability` deve restare nascosta;
- `official_projected` puo mantenere contratto diagnostico, ma non produce overlay mappa e non produce attendibilita visibile;
- fonte stale/unavailable puo mantenere testo ufficiale se presente, ma non mappa nativa, badge mappa o attendibilita;
- A1-A9 parziale blocca mappa, marker e attendibilita;
- DPC/no-active diagnostico non produce banner allerta.

Correzione applicata:

- `bulletinViewModel` ora calcola `displayStructuredDay` solo quando `canRenderNativeMap=true`;
- `reliability`, `mapBadges`, `mapPoints` e summary derivata non leggono piu un giorno strutturato non renderizzabile come dato UI mostrabile.

Limite QA:

- il browser integrato non ha prodotto screenshot per errore runtime interno: `failed to write kernel assets: Impossibile trovare il percorso specificato`;
- la verifica e' stata quindi eseguita con test frontend, build, lint e audit payload read-only.

## Test eseguiti

```text
npx vitest run --configLoader native src/features/bulletin/bulletinViewModel.test.js src/features/bulletin/bulletinDataController.test.js src/domain/weather/osmerStructuredContract.test.js
3 file, 17 test OK

npx vitest run --configLoader native src/domain/alerts/officialAlerts.test.js src/features/bulletin/bulletinViewModel.test.js
2 file, 19 test OK

npm run build
build OK

python -B -m unittest backend_dryrun_staging.test_bulletin_display_payload_audit
7 test OK

python -B backend_dryrun_staging\bulletin_display_payload_audit.py --city Pordenone
righe=24, show=23, no-show=1, testi=5, mappe=5

npm run test
47 file, 311 test OK

npm run lint
OK

npm run build
OK

python -B -m unittest discover backend_dryrun_staging
84 test OK
```

Nota tecnica:

`npm test` senza `--configLoader native` e' stato bloccato da Windows su `node_modules/.vite-temp`. Il test e' stato rieseguito con loader nativo, coerente con gli script Vite del progetto.

## Tranche 99 - Audit visivo tab giorni

Il browser integrato e' stato riavviato e la verifica visuale del Bollettino e' tornata disponibile.

Problema rilevato:

- le tab visibili del Bollettino potevano usare ancora i `weekdayLabels` della fixture;
- con payload reale aggiornato al 27/06, le tab mostravano Martedi/Mercoledi/Giovedi/Venerdi mentre i giorni reali erano domenica 28, lunedi 29, martedi 30 e mercoledi 01.

Regola corretta:

- la tab "Oggi" resta una label funzionale;
- le tab successive derivano dal `forecastDate` reale del giorno;
- la UI legge `day.tabLabel` dal view model e non decide piu' il weekday usando la fixture.

Verifica browser:

```text
URL: http://127.0.0.1:5173/?tab=bulletin
titolo: Meteo Friul UI 3.0.0
tab: Oggi, Domenica, Lunedi, Martedi, Mercoledi
console error/warn: 0

Oggi -> sabato 27 giugno -> Poco nuvoloso
Domenica -> domenica 28 giugno -> Poco nuvoloso
Lunedi -> lunedi 29 giugno -> Poco nuvoloso
Martedi -> tendenza per martedi 30 giugno -> Temporale
Mercoledi -> tendenza per mercoledi 01 luglio -> Coperto
```

Verifiche:

```text
npx vitest run --configLoader native src/features/bulletin/bulletinViewModel.test.js
1 file, 11 test OK

npm run test
47 file, 313 test OK

npm run lint
OK

npm run build
OK

python -B -m unittest discover backend_dryrun_staging
Ran 84 tests
OK
```

## Tranche 100 - Coerenza contenuto previsionale giorno per giorno

Audit browser sul Bollettino pronto:

- tab/data: coerenti sui cinque giorni;
- source/update: `OSMER ARPA FVG`, aggiornato `27/06 - 13:38`;
- console browser: nessun errore/warning;
- mappa e attendibilita: presenti solo su giorni con mappa nativa OSMER.

Problema rilevato:

- il payload contiene anche un array modellistico locale (`forecast.forecast`) che puo essere slittato di un giorno rispetto ai giorni ufficiali OSMER;
- il view model usava `modelDay.condition` per indice prima della lettura OSMER;
- questo produceva titoli incoerenti, ad esempio `Coperto` su un giorno il cui testo OSMER parlava di peggioramento con rovesci e temporali.

Regola corretta:

- nel Bollettino, un `modelDay` puo integrare un giorno ufficiale solo se ha la stessa `date`;
- la sintesi visibile preferisce `official.title/headline`, poi OSMER strutturato/testo ufficiale, e solo come ultima risorsa il modello locale;
- la mappa strutturata si aggancia alla `forecastDate`, non all'indice dell'array.

Verifica browser dopo correzione:

```text
Oggi -> sabato 27 giugno -> Tempo stabile -> Attendibilita 73%
Domenica -> domenica 28 giugno -> Sole e nubi -> Attendibilita 73%
Lunedi -> lunedi 29 giugno -> Sole e nubi -> Attendibilita 73%
Martedi -> tendenza per martedi 30 giugno -> Sole e nubi -> Attendibilita 69%
Mercoledi -> tendenza per mercoledi 01 luglio -> Temporali possibili -> Attendibilita 60%
console error/warn: 0
```

Verifiche:

```text
npx vitest run --configLoader native src/features/bulletin/bulletinViewModel.test.js
1 file, 13 test OK

npm run test
47 file, 315 test OK

npm run lint
OK

npm run build
OK

python -B -m unittest discover backend_dryrun_staging
Ran 84 tests
OK
```

## Tranche 101 - Label Oggi legata alla data reale

Rischio individuato:

- la prima tab non deve chiamarsi `Oggi` solo perche' e' in posizione 0;
- dopo la mezzanotte, un payload vecchio del giorno precedente non deve essere presentato come `Oggi`;
- quando il giorno avanza, la nuova data corrente deve poter diventare `Oggi` correttamente.

Regola corretta:

- `Oggi` viene mostrato solo se `forecastDate` coincide con la data locale corrente;
- se la prima previsione ha una data diversa dalla data corrente, la tab mostra il weekday reale;
- il comportamento e' testabile passando `now` al view model.

Verifiche mirate:

```text
now=2026-06-28, forecastDate=2026-06-28 -> tabLabel=Oggi
now=2026-06-28, forecastDate=2026-06-27 -> tabLabel=Sabato

npx vitest run --configLoader native src/features/bulletin/bulletinViewModel.test.js
1 file, 15 test OK

npm run test
47 file, 317 test OK

npm run lint
OK

npm run build
OK

python -B -m unittest discover backend_dryrun_staging
Ran 84 tests
OK
```

Verifica browser corrente:

```text
URL: http://127.0.0.1:5173/?tab=bulletin
tab attiva: Oggi
data riepilogo: sabato 27 giugno
console error/warn: 0
```

## Tranche 102 - Audit giorno per giorno e allineamento strumento display

Obiettivo:

- verificare il Bollettino reale giorno per giorno, non solo il primo giorno;
- confrontare cio' che vede l'utente con il payload letto dal dry-run display;
- correggere solo lo strumento di audit se non rappresenta la stessa regola della UI.

Esito browser:

```text
URL: http://127.0.0.1:5173/?tab=bulletin
console error/warn: 0

Oggi -> Tempo stabile -> Attendibilita 73% -> mappa 9/9
Domenica -> Sole e nubi -> Attendibilita 73% -> mappa 9/9
Lunedi -> Sole e nubi -> Attendibilita 73% -> mappa 9/9
Martedi -> Sole e nubi -> Attendibilita 69% -> mappa 9/9
Mercoledi -> Temporali possibili -> Attendibilita 60% -> mappa 9/9
```

Esito dry-run display:

```text
city=Udine
official_text_days=5
native_map_days=5
source.updatedLabel=2026-06-27T11:38:00Z
alert.banner=not safe to show
side_effects: Firestore=no, FCM=no, workflow=no, writes=no
```

Incoerenza trovata:

- lo strumento `bulletin_display_payload_audit.py` leggeva `forecast.official.it.forecasts[0].emission`;
- la UI invece usa la priorita' effettiva `official.updated_at/updatedAt`, poi `osmer_structured.data_emissione`, poi `osmer_structured.source_date`;
- nel payload reale questo produceva un falso disallineamento: audit `26-06-2026 14:27 CEST`, UI `27/06 - 13:38`.

Correzione:

- `source.updatedLabel` nello strumento di audit usa la stessa priorita' della UI;
- aggiunto test anti-regressione: se manca `updated_at`, l'audit deve usare `osmer_structured.data_emissione`, non l'emissione del primo giorno.

Verifiche:

```text
python -B -m unittest backend_dryrun_staging.test_bulletin_display_payload_audit
Ran 8 tests
OK

python -B -m unittest discover backend_dryrun_staging
Ran 85 tests
OK

git diff --check
OK
```

## Tranche 103 - Quinto giorno non ancora emesso

Problema:

- il quinto giorno del bollettino puo' non essere ancora emesso da OSMER durante la giornata;
- lo slot deve restare visibile per calendario, ma non deve essere riempito dal modello locale;
- nel caso reale del 28/06/2026, dopo Oggi/Lunedi/Martedi/Mercoledi il quinto slot corretto e' Giovedi 02/07/2026, non un giorno modellistico successivo.

Decisione:

- quando esiste una finestra OSMER ma il quinto giorno non e' ancora pubblicato, la UI mostra la tab del giorno di calendario previsto;
- il contenuto visibile e' solo `Non ancora emesso` / `Bollettino non ancora emesso.`;
- mappa, icone meteo e attendibilita non vengono mostrate per lo slot pending;
- il modello locale non puo' spostare o sostituire il quinto giorno ufficiale.

Verifica browser:

```text
URL: http://127.0.0.1:5173/?tab=bulletin
tab visibili: Oggi, Lunedi, Martedi, Mercoledi, Giovedi
tab Giovedi selezionata:
  titolo: Non ancora emesso
  testo: Bollettino non ancora emesso.
  mappa: 0 icone meteo
  warning mappa: Non ancora emesso
  vecchio warning "Dati previsionali non disponibili": assente
console error/warn: 0
```

Esito dry-run display reale:

```text
Udine | righe=24 | show=21 | no-show=3 | testi=4 | mappe=4
days[plus4].officialText = pending / UI copy / Bollettino non ancora emesso.
days[plus4].nativeMap = pending / no-show / valid_date=2026-07-02
days[plus4].reliability = pending / no-show
```

Verifiche:

```text
npx vitest run --configLoader native src/features/bulletin/bulletinViewModel.test.js
1 file, 16 test OK

npx vitest run --configLoader native
47 file, 318 test OK

npm run lint
OK

npm run build
OK

python -B -m unittest backend_dryrun_staging.test_bulletin_display_payload_audit
Ran 9 tests
OK

python -B -m unittest discover backend_dryrun_staging
Ran 86 tests
OK
```

## Tranche 104 - Calendario FUR allineato al Bollettino OSMER

Problema:

- nel payload reale del 28/06/2026 la finestra IT/OSMER e' `2026-06-28` -> `2026-07-01`;
- la lista FUR contiene 4 testi paralleli, ma il campo `date` e' spostato indietro di un giorno;
- usando il FUR come calendario, la UI perdeva il quinto slot pending corretto (`Joibe 2 Lui`) e poteva mostrare testi/data sfalsati.

Decisione:

- il calendario del Bollettino viene sempre dalla finestra IT/OSMER strutturata;
- i testi FUR sono trattati come lista localizzata parallela, quindi usati per posizione quando esistono;
- il quinto slot resta `Joibe` e mostra `No ancjemò publicât` finche' OSMER non emette il quinto giorno.

Verifica browser:

```text
URL: http://127.0.0.1:5173/?tab=bulletin
lingua: FUR
tab visibili: Vuê, Lunis, Martars, Miercus, Joibe
tab Vuê:
  data: domenie 28 Jugn
  testo FUR del 28/06 visibile
tab Joibe:
  data: Joibe 2 Lui
  titolo: No ancjemò publicât
  testo: Boletin no ancjemò publicât.
  icone mappa: 0
console error/warn: 0
```

Esito dry-run display reale:

```text
Lingua: fur
Udine | righe=24 | show=21 | no-show=3 | testi=4 | mappe=4
days[plus4].officialText = pending / UI copy
days[plus4].nativeMap = pending / valid_date=2026-07-02
```

Verifiche:

```text
npx vitest run --configLoader native src/features/bulletin/bulletinViewModel.test.js
1 file, 17 test OK

npx vitest run --configLoader native
47 file, 319 test OK

npm run lint
OK

npm run build
OK

python -B -m unittest backend_dryrun_staging.test_bulletin_display_payload_audit
Ran 10 tests
OK

python -B -m unittest discover backend_dryrun_staging
Ran 87 tests
OK
```
