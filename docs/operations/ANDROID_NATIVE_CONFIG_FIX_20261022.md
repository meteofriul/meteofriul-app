# Correzione locale della configurazione nativa Android — 22 ottobre 2026

## Perimetro e stato

Lavoro sul ramo esistente `codex/release-0.1.15`. Il main locale verificato
`3da1db2d4d2f1de4bd14745ef7fd078ec8d399dd` è stato incorporato con merge
`8693345c`, preservando registri e artefatti release. I due conflitti
documentali (README e stato release) sono stati risolti conservando gli
aggiornamenti di main sui job verificati.

**Correzione locale preparata; NATIVE-CONFIG-01 non ancora chiuso sul runtime.**
Nessuna nuova AAB, build Gradle, installazione, emulatore, push, deploy o
invio manuale. Sponsor, pannello e allineamento dati sponsor restano disattivati.
I rami GPS e navigazione fissa di Bollettino/Eventi non sono stati incorporati.

## Evidenza e causa

Artefatto esaminato in sola lettura: `meteofriul-300033-0.1.15.aab`,
SHA256 `cb461c8e5e6fddd05407214a507e151e02e8041f403d9346c364bbe0174ba019`.
Resta la AAB già installata dal proprietario tramite test interno Play.

- Il bundle non contiene `base/assets/capacitor.config.json`. Il builder usava
  `cap update android` e copiava soltanto il contenuto Web: mancava il passaggio
  di copia della configurazione che il normale comando Capacitor copy esegue.
- Il bundle non contiene la risorsa `com.meteofriul.app:xml/config`.
  La lettura mirata con bundletool 1.18.3 termina con codice 0 e output vuoto;
  la lettura completa della tabella risorse conferma l'assenza. Il jar è stato
  verificato con l'hash registrato nel manifesto storico.
- Il file sorgente `res/xml/config.xml` esiste nel checkout. Cordova 14.0.1 lo
  cerca per nome tramite `getIdentifier` all'avvio del bridge: conservare il
  solo file sorgente non dimostra che la risorsa sopravviva alla build.
  Il log del telefono riportava `config.xml is missing!`. La nuova regola
  mirata dovrà ancora essere verificata nell'output minificato reale.

Riferimenti: [copia della configurazione Capacitor 8.5.1](https://github.com/ionic-team/capacitor/blob/8.5.1/cli/src/tasks/copy.ts),
[lettura Cordova 14.0.1](https://github.com/apache/cordova-android/blob/rel/14.0.1/framework/src/org/apache/cordova/ConfigXmlParser.java),
[regole Android per conservare risorse](https://developer.android.com/topic/performance/app-optimization/customize-which-resources-to-keep).

## Correzione

1. Il builder valida il JSON approvato prima della riserva versione: identità
   ufficiale, asset locali, HTTPS, niente URL di sviluppo, debug WebView o mixed
   content, configurazione SystemBars attesa. Rifiuta buildOptions, che possono
   contenere opzioni di firma e non devono finire nell'APK.
2. Dopo `cap update android` copia esplicitamente quel JSON negli asset nativi
   e registra gli hash di configurazione e registro plugin. La copia non
   sostituisce né tocca gli asset Web.
3. Un file `res/raw/com_meteofriul_native_config_keep.xml` conserva soltanto
   `@xml/config`. R8 e lo shrinking delle altre risorse restano abilitati.
4. Dopo la validazione bundletool, prima di archiviare e accettare il bundle,
   il nuovo modulo controlla JSON, registro plugin, hash e risorsa Cordova.
   Verifica l'identità nella tabella risorse e l'esistenza del file effettivo,
   anche se il nome fisico del file viene ottimizzato.
5. Il manifesto registra l'esito in `NativeConfiguration`. I registri e il
   bundle storico non vengono riscritti.

Implementazione: [modulo](../../scripts/play-native-configuration.psm1),
[builder](../../scripts/build-play-aab.ps1),
[regressioni](../../scripts/play-native-configuration.contract.tests.ps1).

## Controlli locali

Ambiente Windows, PowerShell 7, strumenti Java già presenti. Fixture ZIP locali
temporanee: non sono nuove build Android. Nessun accesso operativo al cloud.

| Controllo | Esito |
| --- | --- |
| Contratti nativi con regressione in lettura sulla AAB 300033 | PASS, 42 asserzioni; il vecchio artefatto è rifiutato per configurazione assente e il suo hash resta invariato |
| Contratti del builder con `-SkipGradleExecution` | PASS; comprende ora anche i contratti nativi. Prove Gradle esplicitamente saltate |
| Audit immutabilità ledger | PASS, 49 record storici e 49 correnti, nessuna nuova riserva |
| Versione configurata e artefatto 300033 | Invariati |
| Nuova AAB minificata e prova sul telefono | NON ESEGUITE |

Le regressioni coprono copia da configurazione obsoleta, sorgenti mancanti o
non approvate, hash diversi, file mancanti/duplicati, registro plugin invalido,
identità e file della risorsa Cordova, più l'ordine dei controlli nel builder.
La suite esistente richiama la nuova suite: non occorrono nuovi trigger CI.

## Numerazione e prossimi passi

Android distingue `versionName` (nome mostrato, per esempio 0.1.15) e
`versionCode` (codice crescente dell'aggiornamento). Il nome può restare
0.1.15 con un nuovo codice, secondo la
[documentazione Android](https://developer.android.com/studio/publish/versioning).
Il prossimo codice va scelto dopo aver letto Console e ledger: 300034 è
soltanto un esempio, non una riserva.

Al 22 ottobre la guardia locale sul riuso del nome è più restrittiva: ammette
solo un retry dopo una riserva abbandonata senza bundle, quindi blocca ancora
una seconda 0.1.15 dopo 300033. Questo lavoro non cambia tale regola.
Prima di una build con lo stesso nome occorre adeguare e verificare quella
guardia mantenendo immutabili le identità e i record esistenti.

Dopo autorizzazione alla nuova build: controllare il contenuto minificato reale
con le nuove guardie, poi verificare avvio, log Capacitor/Cordova, barre/inset
e plugin sul telefono. Per le altre aree obbligatorie seguire il
[runbook Play](PLAY_AAB_RUNBOOK.md); nessun PASS è dedotto dai test su fixture.
Promozione su main, build, upload e installazione restano passaggi distinti.
