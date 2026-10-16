# Verifica dipendenze del 16 ottobre 2026

Base pubblica: `a70d3c68c8ee21f8d7938e931d5443af15574248`. Intervento dedicato sul branch `codex/dependency-security-2026-10-16`.

Sono stati verificati tutti i 23 avvisi Dependabot aperti: 1 critico, 13 alti, 8 moderati e 1 basso. Le versioni erano effettivamente presenti nei manifest o nel lockfile; questo conferma la presenza del componente vulnerabile, non uno sfruttamento dell’app. Nessun avviso è stato ignorato o chiuso manualmente.

## Correzioni e perimetro

- **Capacitor Android:** 8.5.0 → 8.5.1, con Core e CLI allineati. La patch blocca la navigazione al proxy interno e ne impedisce l’uso come documento. `CapacitorHttp` disabilitato non proteggeva la versione precedente. L’aggiornamento del repository non corregge le app già installate: occorre una nuova build nativa, collaudata e distribuita con autorizzazioni separate.
- **gRPC:** introdotto transitivamente da `firebase` → `@firebase/firestore`. L’app importa solo Firebase App, Messaging e App Check; non espone un server gRPC né usa `getAuthContext`. Le precondizioni dei due avvisi server non risultano presenti. Il componente è comunque corretto con un override limitato a Firestore, a 1.13.6. Anche Firestore 4.18.0 continua a richiedere `~1.9.0`; non è necessario aggiornare Firebase a una nuova major per questa correzione.
- **UUID:** `@capacitor/cli` → `xcode` 3.0.1 richiede ancora UUID 7. Xcode usa `v4()` senza buffer esterno; i percorsi vulnerabili v3/v5/v6 non sono usati da quel consumer. Override limitato a `xcode` con UUID 11.1.1, che mantiene CommonJS. La generazione degli identificatori Xcode e il rifiuto dei buffer insufficienti sono verificati da test.
- **lxml:** dipendenza di sviluppo del tool di audit HTML Pro Loco; nessuna chiamata applicativa a `iterparse()` o `ETCompatXMLParser()`. Aggiornamento 5.4.0 → 6.1.0 e verifica con file canary che i parser predefiniti non leggano entità esterne locali, più controllo della compatibilità HTML/XPath.
- **xmldom:** dipendenza di sviluppo di `plist`/CLI. Corrette tutte le nove segnalazioni. I controlli del serializer indicati dagli advisory richiedono ancora `requireWellFormed: true`: non si presume che l’upgrade renda sicura la serializzazione arbitraria di DOM non fidati. Non ci sono call site applicativi xmldom; i file di progetto/plist restano input fidati degli strumenti di build.
- **Vitest/mocker:** usato per test locali/CI; nessun uso applicativo degli export `mockerPlugin`/`interceptorPlugin` né server mock esposto. Aggiornamento alla serie corretta 4.1.
- **PostCSS, source-map-js, brace-expansion, browserslist, baseline-browser-mapping:** strumenti di build/lint/test. Gli avvisi richiedono input malevoli come CSS, sourcemap, pattern o statistiche; aggiornati nel lockfile entro i vincoli compatibili dei consumer.

Gli override possono essere rimossi quando i rispettivi pacchetti a monte richiederanno versioni corrette; prima della rimozione ripetere audit e `npm run test:dependency-security`.

## Corrispondenza completa degli avvisi

| Avviso | Pacchetto | Prima → dopo | Advisory |
| --- | --- | --- | --- |
| [#31](https://github.com/meteofriul/meteofriul-app/security/dependabot/31) | `@capacitor/android` | 8.5.0 → 8.5.1 | [GHSA-rvm3-566m-v7fv](https://github.com/advisories/GHSA-rvm3-566m-v7fv) |
| [#32](https://github.com/meteofriul/meteofriul-app/security/dependabot/32) | `source-map-js` | 1.2.1 → 1.2.2 | [GHSA-68fv-2mgg-jv7q](https://github.com/advisories/GHSA-68fv-2mgg-jv7q) |
| [#30](https://github.com/meteofriul/meteofriul-app/security/dependabot/30) | `@grpc/grpc-js` | 1.9.16 → 1.13.6 | [GHSA-m9gg-hp2v-232j](https://github.com/advisories/GHSA-m9gg-hp2v-232j) |
| [#29](https://github.com/meteofriul/meteofriul-app/security/dependabot/29) | `@grpc/grpc-js` | 1.9.16 → 1.13.6 | [GHSA-f596-whhp-79r4](https://github.com/advisories/GHSA-f596-whhp-79r4) |
| [#28](https://github.com/meteofriul/meteofriul-app/security/dependabot/28) | `brace-expansion` | 5.0.6 → 5.0.12 | [GHSA-q2hr-2g5m-vwhr](https://github.com/advisories/GHSA-q2hr-2g5m-vwhr) |
| [#25](https://github.com/meteofriul/meteofriul-app/security/dependabot/25) | `@xmldom/xmldom` | 0.9.11 → 0.9.12 | [GHSA-c7q8-3ch8-vqpv](https://github.com/advisories/GHSA-c7q8-3ch8-vqpv) |
| [#24](https://github.com/meteofriul/meteofriul-app/security/dependabot/24) | `@xmldom/xmldom` | 0.9.11 → 0.9.12 | [GHSA-jxjr-3g7g-3944](https://github.com/advisories/GHSA-jxjr-3g7g-3944) |
| [#23](https://github.com/meteofriul/meteofriul-app/security/dependabot/23) | `@xmldom/xmldom` | 0.9.11 → 0.9.12 | [GHSA-27p8-2357-5qqv](https://github.com/advisories/GHSA-27p8-2357-5qqv) |
| [#22](https://github.com/meteofriul/meteofriul-app/security/dependabot/22) | `@xmldom/xmldom` | 0.9.11 → 0.9.12 | [GHSA-3px3-54cx-rmw9](https://github.com/advisories/GHSA-3px3-54cx-rmw9) |
| [#21](https://github.com/meteofriul/meteofriul-app/security/dependabot/21) | `@xmldom/xmldom` | 0.9.11 → 0.9.12 | [GHSA-vr34-hp96-76pp](https://github.com/advisories/GHSA-vr34-hp96-76pp) |
| [#20](https://github.com/meteofriul/meteofriul-app/security/dependabot/20) | `@xmldom/xmldom` | 0.9.11 → 0.9.12 | [GHSA-6h8r-xr42-gp59](https://github.com/advisories/GHSA-6h8r-xr42-gp59) |
| [#19](https://github.com/meteofriul/meteofriul-app/security/dependabot/19) | `@xmldom/xmldom` | 0.9.11 → 0.9.12 | [GHSA-8344-3jmq-59r6](https://github.com/advisories/GHSA-8344-3jmq-59r6) |
| [#17](https://github.com/meteofriul/meteofriul-app/security/dependabot/17) | `@xmldom/xmldom` | 0.9.11 → 0.9.12 | [GHSA-93r5-fhx6-vmg9](https://github.com/advisories/GHSA-93r5-fhx6-vmg9) |
| [#15](https://github.com/meteofriul/meteofriul-app/security/dependabot/15) | `vitest` | 4.1.9 → 4.1.12 | [GHSA-82fw-gwwq-j7x9](https://github.com/advisories/GHSA-82fw-gwwq-j7x9) |
| [#14](https://github.com/meteofriul/meteofriul-app/security/dependabot/14) | `@vitest/mocker` | 4.1.9 → 4.1.12 | [GHSA-82fw-gwwq-j7x9](https://github.com/advisories/GHSA-82fw-gwwq-j7x9) |
| [#13](https://github.com/meteofriul/meteofriul-app/security/dependabot/13) | `baseline-browser-mapping` | 2.10.38 → 2.11.29 | [GHSA-w5vr-8v7q-w6rv](https://github.com/advisories/GHSA-w5vr-8v7q-w6rv) |
| [#12](https://github.com/meteofriul/meteofriul-app/security/dependabot/12) | `@xmldom/xmldom` | 0.9.11 → 0.9.12 | [GHSA-6gmq-8vp8-gcm6](https://github.com/advisories/GHSA-6gmq-8vp8-gcm6) |
| [#10](https://github.com/meteofriul/meteofriul-app/security/dependabot/10) | `browserslist` | 4.28.2 → 4.29.3 | [GHSA-73wf-gq98-2v4g](https://github.com/advisories/GHSA-73wf-gq98-2v4g) |
| [#7](https://github.com/meteofriul/meteofriul-app/security/dependabot/7) | `postcss` | 8.5.15 → 8.5.30 | [GHSA-fxqj-rqcc-2cmp](https://github.com/advisories/GHSA-fxqj-rqcc-2cmp) |
| [#4](https://github.com/meteofriul/meteofriul-app/security/dependabot/4) | `postcss` | 8.5.15 → 8.5.30 | [GHSA-r28c-9q8g-f849](https://github.com/advisories/GHSA-r28c-9q8g-f849) |
| [#3](https://github.com/meteofriul/meteofriul-app/security/dependabot/3) | `brace-expansion` | 5.0.6 → 5.0.12 | [GHSA-3jxr-9vmj-r5cp](https://github.com/advisories/GHSA-3jxr-9vmj-r5cp) |
| [#2](https://github.com/meteofriul/meteofriul-app/security/dependabot/2) | `uuid` | 7.0.3 → 11.1.1 | [GHSA-w5hq-g745-h8pq](https://github.com/advisories/GHSA-w5hq-g745-h8pq) |
| [#1](https://github.com/meteofriul/meteofriul-app/security/dependabot/1) | `lxml` | 5.4.0 → 6.1.0 | [GHSA-vfmq-68hx-4jfw](https://github.com/advisories/GHSA-vfmq-68hx-4jfw) |

## Verifiche

- Node 22.17.1, npm 10.9.2, Python 3.13 su Windows; ambiente Python isolato.
- Installazione standard `npm ci`: PASS; nessuna opzione peer speciale richiesta per l’installazione o la CI. Durante la sola rigenerazione iniziale del lockfile il risolutore npm 10.9.2/10.9.4 andava in crash sui peer opzionali di Vitest; dopo il bootstrap senza peer automatici sono stati eseguiti aggiornamento standard e `npm ci` standard.
- Confronto di tutte le versioni del lockfile con i 23 intervalli degli advisory: zero corrispondenze vulnerabili.
- `npm audit`: zero vulnerabilità note. `pip-audit -r requirements-dev.txt`: zero vulnerabilità note alla data della verifica.
- Vitest: 4.790 test superati, 13 saltati come previsto dalla suite (535 file passati, 5 saltati).
- Backend: suite esistente, 1.769 test eseguiti, un caso saltato; due nuovi test lxml superati separatamente. `compileall` e `pip check`: PASS.
- Cinque test Node di regressione e compatibilità: PASS (UUID/Xcode, gRPC locale, PostCSS, xmldom, brace-expansion). Inseriti nella CI frontend esistente; trigger e pianificazioni invariati.
- Guardie Node release/local pilot/Android local pilot: 9 + 10 + 6 test superati.
- ESLint e build web (incluso service worker): PASS.
- `cap sync android` e `:app:compileDebugJavaWithJavac`: PASS, JDK 21 / SDK 36. Il task unitario app passa un solo test esemplificativo; Capacitor non include test unitari nel pacchetto npm (`NO-SOURCE`). Questi esiti non certificano il comportamento della WebView su dispositivo.
- Contratti release API, R8 e protezioni AAB: PASS. Per il worktree nuovo è stato necessario completare `cap sync android` e impostare JDK/SDK prima del contratto Gradle. Nessun artefatto AAB prodotto.
- Verifica pulizia workspace canonico: PASS.

## Gate Android e promozione

Compilazione, lint e CI sono registrati nella pull request. Il collaudo su dispositivo reale non è stato eseguito e la promozione a `main` resta subordinata al workflow del repository. Nessuna AAB, installazione sul telefono, pubblicazione Play o modifica dei servizi cloud è inclusa in questo intervento.

La patch Capacitor scelta è 8.5.1 per limitare il cambio alla correzione di sicurezza e alle piccole correzioni Core/CLI correlate, senza importare le modifiche SystemBars di 8.5.2. Target/compile SDK 36, AGP/Gradle, gestione insets, orientamento e R8 non cambiano. I contratti Android automatici non sostituiscono la verifica runtime: edge-to-edge/insets, API delle barre, orientamento/grandi schermi e build minificata restano da ricontrollare sulla candidata da distribuire secondo il [runbook Play](PLAY_AAB_RUNBOOK.md#controlli-android-obbligatori-per-ogni-release).

Gli avvisi GitHub del branch predefinito possono restare aperti finché la correzione non viene promossa a `main`. Non confondere l’assenza di vulnerabilità nel branch della correzione con la chiusura degli avvisi sulla base pubblicata.
