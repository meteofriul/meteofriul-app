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
In questa prima fase i rami GPS e navigazione fissa di Bollettino/Eventi non
erano incorporati; l'integrazione successiva è registrata in fondo al verbale.

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

Al commit della correzione nativa `38e1910b` la guardia sul nome ammetteva
soltanto il retry dopo una riserva abbandonata senza bundle. Il successivo
adeguamento autorizzato il 22 ottobre permette il riuso del nome anche dopo
un manifesto di build validato, compresa una build accettata da Play.
Una riserva senza manifesto né abbandono continua a bloccare quel nome.

Verifiche dell'adeguamento, tutte locali:
- suite `build-play-aab.contract.tests.ps1 -SkipGradleExecution`: PASS;
  casi dopo build, abbandono e accettazione, più bundle dello stesso nome,
  riserve aperte, identità in conflitto e codici inferiori/riutilizzati;
- suite `release-api-preflight.tests.ps1`: PASS, protezioni APK privati incluse;
- audit ledger: PASS, 49 record storici e correnti invariati;
- lettura del ledger reale e della cronologia privata: entrambi i controlli
  accettano l'ipotesi `0.1.15 / 300034`, mentre `300033` resta rifiutato.
  La Console di riferimento è soltanto l'ultima attestazione salvata:
  non è una nuova lettura live, né una riserva del numero.

Nessuna modifica ai numeri configurati, ai JSON immutabili o all'AAB 300033.

Dopo autorizzazione alla nuova build: controllare il contenuto minificato reale
con le nuove guardie, poi verificare avvio, log Capacitor/Cordova, barre/inset
e plugin sul telefono. Per le altre aree obbligatorie seguire il
[runbook Play](PLAY_AAB_RUNBOOK.md); nessun PASS è dedotto dai test su fixture.
Promozione su main, build, upload e installazione restano passaggi distinti.

## Integrazione successiva del 22 ottobre

La release incorpora ora main `d62683b9` e la correzione della posizione,
con sorgente candidata `a3290715`. Ripetuti con successo i contratti del builder
senza Gradle, quelli API/R8 e le 42 asserzioni native sull'archivio 300033.
Ledger (49 record) e artefatto storico restano invariati. Sono compilati soltanto
Web e asset Web in modalità Android: nessuna nuova prova del contenuto minificato
nativo o del dispositivo. [Base comune, risultati e limiti](RELEASE_WEB_ALIGNMENT_20261022.md).

## Bundle reale 300035 — 23 ottobre

La [300035](ANDROID_0.1.15_300035_BUILD_20261023.md) supera il builder completo:
JSON Capacitor, registro plugin e risorsa Cordova presenti e verificati nel
bundle minificato. Nel tentativo 300034 è emerso anche un errore nel filtro
bundletool, corretto con regressioni basate sull'output reale. La correzione
di confezionamento è attestata; la verifica sul dispositivo resta aperta.

## Runtime reale 300035 — 23 ottobre

L'APK installato dal Play Store contiene i due JSON attesi e la risorsa Cordova.
L'avvio a freddo sul Galaxy A52 Android 14 non riproduce l'errore di
configurazione; i percorsi selezionati funzionano nel runtime minificato.
NATIVE-CONFIG-01 chiuso per confezionamento e avvio sul dispositivo.
[Verbale e limiti](ANDROID_0.1.15_300035_DEVICE_CHECK_20261023.md).
