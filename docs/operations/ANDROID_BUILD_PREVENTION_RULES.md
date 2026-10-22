# Regole obbligatorie prima di una build Android ufficiale

Leggere questo file **prima di preparare dipendenze, modificare la versione o
avviare il builder**, anche se il lavoro riprende dopo una pausa. Integra il
[runbook Play](PLAY_AAB_RUNBOOK.md); non sostituisce i suoi gate. Le regole
seguenti derivano dagli errori della preparazione 0.1.15 del 21 ottobre 2026.

> Aggiornamento 22 ottobre: preflight, retry e correzione della configurazione
> nativa sono conservati nel ramo `codex/release-0.1.15`, ancora da promuovere.
> Il [nuovo controllo automatico](ANDROID_NATIVE_CONFIG_FIX_20261022.md) supera
> le regressioni locali; una nuova AAB minificata e la prova sul dispositivo
> restano da autorizzare/eseguire. Consultare lo
> [stato corrente](RELEASE_0.1.15_STATUS_20261021.md).

## 1. Fissare il perimetro prima dei comandi

- Usare il ramo release dedicato e allinearlo al main verificato. Annotare
  checkout, branch e commit: non compilare dal checkout canonico se è su un
  altro ramo. Conservare modifiche estranee e file ignorati.
- Rileggere le autorizzazioni della sessione. Generare, caricare su Play,
  installare, distribuire servizi e inviare notifiche sono azioni distinte.
  Non richiedere di nuovo un'autorizzazione già esplicita; non estenderla.
- Per la 0.1.15: sponsor spenti; nessuna attivazione del pannello o allineamento
  dei dati sponsor. Verificare il catalogo live in lettura e registrare l'esito.
- Non avviare emulatori o installazioni quando il proprietario li ha esclusi.
  Contrassegnare le verifiche runtime mancanti, senza inventare un PASS.

## 2. Dipendenze complete e appartenenti al checkout

**Vietato escludere ricorsivamente le directory chiamate `build`, `dist` o
`lib` durante una copia di `node_modules`.** Sono spesso il codice eseguibile
distribuito dai pacchetti. In questa release escludere `build` aveva rimosso
`idb/build`, richiesto da Firebase Messaging.

- Preferire dipendenze riproducibili dal lockfile con la procedura del progetto.
  Se si riusa una copia locale, confrontare prima i lockfile e copiare l'intero
  albero dei pacchetti. Non aggiornare pacchetti o toolchain incidentalmente.
- Nel checkout release, `frontend/node_modules` deve essere una directory
  fisica. Controllare `LinkType` e `Target`: una junction verso un altro
  worktree può far generare a Capacitor percorsi esterni.
- Se occorre sostituire una junction, verificare prima il percorso assoluto e
  rimuovere **solo il collegamento**, mai il suo albero di destinazione.
  Non usare comandi di cancellazione costruiti passando tra shell diverse.
- Controllare che i file Gradle generati da Capacitor contengano i percorsi
  relativi attesi. Percorsi a un altro checkout bloccano la preparazione.
- Prima di consumare un codice versione, completare una build Web in modalità
  Android in una directory unica sotto la cartella temporanea del sistema,
  con le stesse basi API e Community della candidata. Verificare binding API,
  Carto e import dei pacchetti coinvolti. Il solo test unitario o un controllo
  `Test-Path node_modules` non dimostra che la copia sia completa.
- Conservare log ed esito di questa build preliminare. Se fallisce, correggere
  la causa e ripetere quel controllo; non usare il builder AAB come diagnosi.

## 3. Provenienza e prerequisiti prima della riserva

- Controllare firma, Firebase ufficiale, mappe, JDK/SDK e hash del bundletool.
  Non stampare credenziali o copiare segreti nei file versionati.
- Controllare API/tag, revisione, digest e sorgente realmente attestati.
  Le evidenze TTL storiche possono riferirsi alla cronologia Git originale,
  mentre i commit correnti appartengono a una cronologia ripulita.
- Se un controllo di ancestry fallisce, fermarsi e confrontare le identità.
  Un messaggio di commit simile non dimostra equivalenza. Servono confronto
  dei file effettivamente inclusi nell'immagine, percorsi, modi Git, Dockerfile,
  requirements e contratto dei writer; conservare la prova di equivalenza.
  Non riscrivere attestazioni immutabili, non disabilitare il gate e non
  importare la cronologia privata nel ramo pubblico per farlo passare.
- Eseguire i test pertinenti e l'audit del registro. Ispezionare tutto il diff
  da pubblicare, inclusi i commit antenati ancora non pubblicati: il controllo
  privacy del push può bloccare anche un antenato, pur con un albero finale
  pulito. Non usare `--no-verify`, non allentare la baseline del controllo.
- Salvare le sorgenti e soddisfare il controllo di allineamento remoto del
  builder prima della compilazione. Se il push non è autorizzato, preparare
  localmente e dichiarare quel requisito; non bypassarlo.

## 4. Versioni: distinguere nome, codice e tentativo

- Leggere il massimo effettivo in Play Console e il registro locale completo.
  Non dedurlo dal nome dell'app, dalla TEST o dal solo package.json.
- `versionName` è il nome concordato con il proprietario; `versionCode`
  deve superare tutti i codici Play e locali, comprese le riserve abbandonate.
- Verificare entrambi i controlli di versione sul ledger **prima** del builder.
  Non consumare un altro numero se il fallimento precedente era prima della
  creazione della riserva.
- Dopo una riserva, il codice è consumato anche se non esiste una AAB. Conservare
  e versionare la riserva; registrare `abandoned` con lo script dedicato e il
  motivo. Non cancellare o modificare record per liberare il numero.
- Per le AAB ufficiali, lo stesso `versionName` può essere usato con un codice
  maggiore quando il tentativo precedente ha un manifesto di build validato
  oppure un evento `abandoned` validato. Vale anche dopo accettazione Play e
  dopo abbandono di un bundle già costruito. Un nome mostrato non identifica
  un artefatto: per ogni build conservare codice, commit e SHA-256.
- Una riserva senza manifesto di build né abbandono resta aperta e blocca un
  nuovo tentativo con quel nome. Due riserve aperte dello stesso nome rendono
  il ledger incoerente. Non aggiungere un abbandono fittizio per liberare il nome.
- La regola deriva dal ledger validato, senza parametro di bypass. Codici
  crescenti, immutabilità, firma, provenienza e altri gate restano obbligatori.
  L'adeguamento del 22 ottobre è locale al ramo release: nessun numero è stato
  cambiato o riservato. Il percorso APK privato conserva la propria protezione
  sui nomi, perché i suoi archivi non includono il codice nel nome del file.
- Se la AAB è già valida, conservarla e usare quel file in seguito. Non
  rigenerarla per ottenere un file diverso con lo stesso numero.

## 5. Una sola procedura di build, poi prove sull'artefatto

- Usare `scripts/build-play-aab.ps1` con PowerShell 7, fuori sandbox, sin dal
  primo tentativo. **Non precederlo con android:sync e non sostituirlo con una
  chiamata manuale a bundleRelease.** Il builder prepara e controlla gli asset.
- Usare Vite/Vitest con `--configLoader native`. Per build Web preliminari
  usare output nel temporaneo del sistema, non nuove cartelle in frontend.
- Non modificare checkout, dipendenze o evidenze mentre il builder è attivo.
  Non lanciare una seconda build per aggirare un'attesa senza averne capito
  la causa. Non terminare indiscriminatamente processi Java condivisi.
- A ogni errore registrare fase, causa e codice consumato o non consumato.
  Correggere la causa precisa; riprovare solo dopo il controllo che la copre.
  Nessun loop di cancellazioni, copie parziali o bypass dei controlli.
- Una modifica a una guardia richiede regressioni positive e negative prima
  del nuovo tentativo; i vincoli estranei al difetto devono restare intatti.
- Dopo successo confrontare AAB, hash, firma, manifesto, package, versione,
  binding e mapping R8. Archiviare senza sovrascrivere; registrare
  `built-not-uploaded` finché Play non ha accettato il file.
- La copia dei soli asset Web e `cap update android` **non sostituiscono** la
  preparazione della configurazione nativa. Prima di dichiarare valido il
  bundle, verificare dentro l'AAB `base/assets/capacitor.config.json`, JSON valido
  e corrispondenza con la configurazione approvata del checkout, oltre al registro
  plugin. Controllare anche le risorse native caricate per nome a runtime e
  chiudere eventuali errori `config.xml is missing` sulla release minificata.
  Non accettare il fallback silenzioso ai default e non correggere l'artefatto
  già firmato a mano. Il ramo release implementa copia esplicita del JSON,
  confronto degli hash e verifica della risorsa Cordova `xml/config` tramite
  bundletool. Il keep mirato `@xml/config` protegge la risorsa caricata per nome:
  non disabilitare R8 o lo shrinking globale per conservarla. Eseguire anche
  `scripts/play-native-configuration.contract.tests.ps1`, incluso nella suite
  del builder. Il PASS locale non chiude la verifica della prossima AAB e del
  runtime; seguire il [verbale](ANDROID_NATIVE_CONFIG_FIX_20261022.md).
- Per attestare la conservazione delle preferenze attraverso un aggiornamento,
  acquisire lo stato prima e subito dopo l'aggiornamento autorizzato, prima di
  azioni che lo possano cambiare. Distinguere permessi Android, servizio Posizione
  del sistema e interruttori dell'app. Due letture entrambe successive al Play
  update verificano soltanto la sessione; non certificano la migrazione.
- CI verde e compilazione non dimostrano il funzionamento sul telefono. Indicare
  separatamente test automatici, verifiche statiche e prove runtime mancanti.
  Non dichiarare risolte le quattro aree Android del runbook senza evidenze.

## Evidenze di applicazione

Il [verbale 0.1.15](https://github.com/meteofriul/meteofriul-app/blob/codex/release-0.1.15/docs/operations/ANDROID_0.1.15_BUILD_20261021.md) conserva errori,
correzioni e limiti. I contratti del ramo release in `scripts/build-play-aab.contract.tests.ps1`
coprono il riuso del solo nome dopo build, accettazione o abbandono, il blocco
dei codici già riservati e delle riserve aperte, più bundle distinti con lo stesso
nome e selezione dell'ultima accettazione per codice. Le guide devono restare collegate da README,
AGENTS.md e runbook; aggiornarle quando emerge una nuova causa verificata.