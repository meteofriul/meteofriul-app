# Procedura operativa per la AAB Google Play

Prima di qualsiasi tentativo, applicare le [regole obbligatorie di preparazione e recupero](ANDROID_BUILD_PREVENTION_RULES.md). Coprono dipendenze, provenienza storica, riserve e retry; valgono anche quando si riprende una release già avviata.

[Stato della release corrente e rilievi aperti](RELEASE_0.1.15_STATUS_20261021.md).

Questa procedura prepara la variante ufficiale `com.meteofriul.app`, non la
variante TEST installabile in parallelo. **Build, caricamento nel test interno e
promozione in produzione sono tre autorizzazioni distinte.** Una fase conclusa
non autorizza automaticamente la successiva.

## Allineamento con la Web App

Ogni aggiornamento Android include il candidato Web dalla stessa base frontend
approvata, secondo il [runbook Web/Android](WEB_ANDROID_RELEASE_PARITY.md).
La Web App è anche il canale iPhone: verificare testi IT/FUR, temi, meteo FVG e
nazionale, Eventi e Community, oltre a Safari e alla modalità Aggiungi a Home.
Registrare i due commit/artefatti e la versione effettivamente pubblicata per
ciascun canale. Non dichiarare il rilascio coordinato concluso lasciando il
sito sulla vecchia UI. Eventuali differenze di piattaforma o pubblicazioni
scaglionate devono essere esplicite e approvate; non attivare automaticamente
invii o servizi nativi per ottenere una parità soltanto nominale.

## Controlli Android obbligatori per ogni release

Questi controlli sono parte della procedura standard, anche quando Play non
mostra nuovi avvisi. Eseguirli sulla candidata di ogni release e riesaminare le
guide Google correnti quando cambiano target SDK, AndroidX, Capacitor, AGP o
Gradle. Distinguere sempre un requisito Google applicabile da una raccomandazione:
la verifica di entrambi è obbligatoria per il progetto, ma non ogni consiglio
della Console è un blocco imposto da Google.

| Area | Verifica richiesta | Evidenza per la candidata |
| --- | --- | --- |
| 1. Edge-to-edge | Contenuti e pulsanti accessibili rispetto a barre, cutout e tastiera; nessun inset doppio; icone leggibili con gesti e tre tasti, temi app e sistema chiaro/scuro. Verificare anche avvio, ripresa e ricaricamento WebView. | Prove di geometria e schermate Android 15/16, più una versione precedente supportata; dispositivo o immagine dell'emulatore identificati. |
| 2. API deprecate | Non reintrodurre i setter deprecati dei colori delle barre nel codice applicativo. Ricondurre ogni rilievo al codice proprio o alla dipendenza e alla sua versione; verificare una migrazione compatibile. Le chiamate interne di compatibilità AndroidX non si eliminano alla cieca. | Esito dei test sul plugin, compilazione nativa, analisi delle chiamate residue e, dopo un upload autorizzato, esito Play del bundle esatto. |
| 3. Orientamento e schermi grandi | Telefoni a schermo intero solo in verticale, senza impostazione di rotazione, come richiesto in AGENTS.md. Nessun blocco portrait globale nel manifest. Schermi con smallest width >= 600 dp e multi-window adattivi, senza overflow o perdita di stato. | Verificare il verticale fisso sul telefono ruotato; tablet nei due versi e finestre ridimensionabili. Dimensioni simulate e piega fisica non sono prove equivalenti. |
| 4. R8 e risorse | Verificare minificazione, resource shrinking, profilo ottimizzato, full mode e keep rule mirate. Controllare separatamente lo shrinking ottimizzato e la compatibilità della toolchain. Conservare mapping e inventario simboli. | Contratti R8 superati, esame degli artefatti e smoke test di un APK minificato con configurazione equivalente alla release; un APK debug non basta. |

Matrice minima da riportare per ciascuna candidata:

- Android 15/API 35 e Android 16/API 36, più una versione precedente supportata;
  ampliare la matrice quando cambiano target SDK o requisiti Google.
- Gesti e tre tasti; temi chiaro/scuro dell'app e del sistema; cutout a sinistra
  e a destra, tastiera aperta/chiusa, ritorno dal background e ricaricamento.
- Telefono a schermo intero sempre verticale anche ruotando il dispositivo, larghezze compatte 320/360 dp, tablet
  verticale/orizzontale, ridimensionamento durante l'uso e finestre multiple.
  Verificare Home, Meteo, Eventi, Scopri e Impostazioni, scorrimento fino in
  fondo e conservazione di selezioni e tema.
- Per R8: avvio, bridge Capacitor, permessi, localizzazione, notifiche, mappe e
  ritorno in app sul pacchetto minificato autorizzato per il collaudo.

Una verifica mirata va presentata come tale anche nel messaggio finale;
non dichiarare verificata tutta l'app sulla base di pochi percorsi. Per una
qualifica completa registrare separatamente Home, **Previsioni, Bollettino,
Tempo reale**, Eventi, Scopri e Impostazioni. In Tempo reale verificare mappa
visibile con altezza utile, controlli del dock raggiungibili, lista segnalazioni
e webcam; rispettare il divieto di invii quando presente. Screenshot e
gerarchia devono essere concordi: elementi nel DOM/gerarchia, dati ricevuti o
log senza crash non provano che il contenuto sia visibile e utilizzabile.
Dopo modifiche a contenitori condivisi o barre fisse, riprovare anche le sezioni
adiacenti che non dovevano cambiare. Ogni percorso omesso resta NON VERIFICATO.

Usare emulatori dedicati. La sostituzione della prova sul telefono reale richiede
una decisione esplicita del proprietario per quello specifico intervento; una
precedente accettazione non diventa un'autorizzazione permanente. Se la prova
non è disponibile, registrarla come non verificata. Non installare sul telefono
per il solo fatto che sia collegato.

I controlli automatici già disponibili si eseguono dalla radice del worktree:

```powershell
npm --prefix frontend test -- src/services/nativeSystemBars.test.js src/ui/shellChromeCss.test.js src/ui/safeAreaCss.test.js src/ui/layout/layoutCss.test.js
npm --prefix frontend run test:release-guard
pwsh -NoProfile -File .\scripts\android-r8-hardening.contract.tests.ps1
```

Questi comandi non generano una AAB e non coprono da soli la matrice runtime.
Compilare i sorgenti e i test Android interessati fuori dalla sandbox; eseguire
i test runtime sull'emulatore/pacchetto autorizzato. Annotare separatamente
test compilati e test eseguiti. Per modifiche di codice attendere la CI della
PR e, dopo la promozione, quella di main. Per sole modifiche Markdown valgono
le verifiche locali previste da AGENTS.md.

Per ogni riga della matrice registrare in un resoconto versionato: commit,
package, versione, SHA-256 dell'artefatto usato, data, API/immagine o modello,
dimensioni/densità, navigazione, temi, scenario, risultato e riferimento alle
evidenze. Usare esiti **PASS**, **FAIL**, **NON VERIFICATO** o **NON APPLICABILE**
(motivato). Conservare log e schermate in una posizione durevole; un percorso
temporaneo scomparso non è un'evidenza disponibile. Non inserire segreti nei
resoconti o negli allegati.

Un FAIL o un requisito applicabile non verificato impedisce di dichiarare la
candidata pronta. Per una raccomandazione rinviata registrare motivo, rischio,
attività di seguito e decisione esplicita del proprietario. Non trasformare un
rinvio in PASS e non usare una deroga interna per ignorare un obbligo Google.
La checklist è procedurale: i test automatici esistenti coprono solo parte dei
controlli, non tutti gli avvisi della Console.

Riferimenti ufficiali da ricontrollare a ogni cambio di piattaforma:

- [Edge-to-edge e gestione degli inset](https://developer.android.com/develop/ui/views/layout/edge-to-edge).
- [API e comportamenti Android 15](https://developer.android.com/about/versions/15/behavior-changes-15).
- [Orientamento e ridimensionamento](https://developer.android.com/develop/adaptive-apps/guides/app-orientation-aspect-ratio-resizability).
- [Ottimizzazione R8](https://developer.android.com/topic/performance/app-optimization/enable-app-optimization).
  Con AGP 8.12/8.13 lo shrinking ottimizzato richiede
  `android.r8.optimizedResourceShrinking=true`; da AGP 9.0 si applica quando
  lo shrinking delle risorse è abilitato. Un aggiornamento AGP/Gradle richiede
  un intervento separato con verifica delle dipendenze e collaudo minificato.

### Stato di partenza verificato il 13 ottobre 2026

La base esaminata è `main` al commit `2fea747a9f4cd54b8fecd232db8ef91170908c82`.
Questo riepilogo storico non sostituisce i controlli sulla prossima candidata.

- Punti 1/2 integrati con [PR #45](https://github.com/meteofriul/old/pull/45):
  vedere [evidenze e limiti](ANDROID_EDGE_TO_EDGE_2026-10-12.md). Restano
  documentati il contrasto dei tre tasti nell'immagine Android 15 usata, le
  chiamate di compatibilità delle dipendenze e i rilievi di lint Android
  estranei all'intervento. La scomparsa degli avvisi Play non è certificata.
- Punto 3 integrato con [PR #47](https://github.com/meteofriul/old/pull/47):
  [21 verifiche di layout superate nella TEST](ANDROID_LARGE_SCREENS_TEST_2026-10-12.json).
  Finestre affiancate/libere e piega fisica restano non verificate. I percorsi
  locali delle schermate nel resoconto vanno verificati prima di riutilizzarli;
  la precedente cartella TEST non è più disponibile.
- Punto 4: R8, resource shrinking e protezioni del mapping sono già presenti.
  AGP è `8.13.0`, ma `android.r8.optimizedResourceShrinking` non è abilitato
  esplicitamente: questo avviso e la valutazione dell'aggiornamento AGP restano
  aperti. Il [precedente audit R8](ANDROID_0.1.8_R8_AUDIT.md) non certifica la
  risoluzione di questi due nuovi rilievi della Console.

## 1. Fissare il codice da distribuire

1. Partire dal `main` aggiornato e verificato. Le funzioni approvate devono
   essere unite tramite PR; prove locali e modifiche presenti solo nella TEST
   non entrano automaticamente nella AAB.
2. Confermare i test pertinenti e la prova sul telefono reale. Annotare commit,
   PR incluse e funzioni ancora escluse. Completare i quattro controlli Android
   sopra, riportando eventuali sostituzioni del dispositivo autorizzate e
   attività ancora aperte.
3. Usare un ramo `codex/` dedicato alla release, derivato dal `main` corrente.
   Il commit da compilare deve essere pulito e già pubblicato sul remoto.

Controlli iniziali dalla radice del worktree scelto:

```powershell
git status --short --branch
git log -1 --oneline
pwsh -NoProfile -File .\scripts\audit-play-release-ledger.ps1
```

Se lo stato mostra modifiche non previste, in particolare un record di release
non tracciato, fermarsi e chiarirne l'origine. Non cancellare file per ottenere
artificialmente un worktree pulito.

## 2. Controllare versione e ambiente prima della riserva

1. Leggere nella Play Console il `versionCode` più alto caricato e confrontarlo
   con il [registro immutabile](../../release-history/android-play/README.md)
   e la cronologia privata. Scegliere un nuovo `versionCode` superiore a
   tutti; concordare il `versionName` da mostrare nell'app.
2. Verificare nel worktree della release le configurazioni locali ignorate da
   Git: `frontend/android/play-keystore.properties`,
   `frontend/android/app/google-services.json` e la chiave Carto nel processo
   oppure in `frontend/.env.android.local`. Provare la chiave senza stamparla:

   ```powershell
   node .\frontend\scripts\carto-basemap-guard.mjs --mode android
   ```

3. Verificare Android SDK, JBR 21, Node, PowerShell 7 e un `bundletool` ufficiale
   locale con SHA-256 atteso. Confermare endpoint API tagged, revisione Cloud
   Run, commit backend e progetto Firebase. Lo script protetto ripete questi
   controlli e i gate LIVE in sola lettura; un esito negativo blocca la release.
4. Mostrare al proprietario commit, contenuto, versione nuova, test e
   prerequisiti. Richiedere conferma esplicita per **generare** quella AAB.

Ogni worktree ha file `.env` e materiali di firma separati. Non presumere che
la configurazione del progetto canonico esista anche in un worktree Codex. Non
copiare segreti nel repository e non mostrarli nei log.

## 3. Eseguire soltanto la build protetta

Avviare [lo script protetto](../../scripts/build-play-aab.ps1) dalla radice del
worktree, fuori dalla sandbox. Sostituire i valori fra parentesi angolari con
quelli verificati per questa release:

```powershell
pwsh -NoProfile -File .\scripts\build-play-aab.ps1 `
  -ApiBase "https://<api-tagged-host>/api" `
  -CommunityApiBase "https://meteofriul-community-49007668366.europe-west1.run.app/api" `
  -ExpectedRevision "<revisione-cloud-run>" `
  -ExpectedBackendCommit "<commit-backend-40-caratteri>" `
  -ExpectedLatestPlayVersionCode <codice-letto-in-play-console> `
  -BundletoolPath "<percorso-bundletool-jar>" `
  -ExpectedBundletoolSha256 "<sha256-del-jar>"
```

Per una revisione il cui nome non contiene il commit, lo script accetta anche
`-ExpectedImageDigest` e `-BackendEvidencePath`, sempre insieme. Non si tratta
di una deroga: entrambi i preflight verificano la stessa revisione, digest,
commit attestato e stato Ready. L'attestazione del tag `play-b6fbe4d` verificata
il 20 ottobre è
[`api-backend.json`](../../release-history/cloud-operations/20261020-services-attestation/api-backend.json):
revisione `meteofriul-api-00251-jow`, sorgenti runtime equivalenti al commit
`599aea2f8a3b1e7e65af2b43e77bb54e4637c96e`. Rileggere lo stato live prima della
build: questa prova non autorizza a usare il digest per una revisione diversa.

Solo per la prima build senza un'evidenza Play accettata, aggiungere
`-ExpectedUploadCertificateSha256 "<sha256-upload-key>"`. Il valore `0` per
`-ExpectedLatestPlayVersionCode` è valido solo se la Console conferma che non
esiste ancora alcuna versione caricata.

Non eseguire prima `npm run android:sync`, non lanciare Gradle manualmente e
non riutilizzare output precedenti. Lo script compila gli asset Web in una
directory temporanea, verifica gli endpoint WebView e nativi, firma e valida
la AAB. **Non carica nulla su Play.**

La correzione del 22 ottobre sul ramo release aggiunge il controllo della
[configurazione nativa](ANDROID_NATIVE_CONFIG_FIX_20261022.md): il JSON
approvato viene copiato separatamente dai contenuti Web; l'AAB deve contenere
JSON e registro plugin con gli hash attesi, più la risorsa Cordova
`com.meteofriul.app:xml/config` e il relativo file. I risultati vengono registrati
nel campo `NativeConfiguration` del manifesto. La mancanza di questi elementi
blocca l'archiviazione; non usare un bundle che ricade sui default.

## 4. Verificare e conservare il risultato

Una build riuscita produce riserva e manifesto nel registro, più AAB e mapping
versionati in `release-artifacts/android-play/`. L'AAB è ignorata da Git:
conservarla su storage durevole e protetto. Controllare che versione, package,
revisione API, certificato e SHA-256 dell'AAB corrispondano al manifesto; non
usare il file generico in `frontend/android/app/build` come consegna.

Committare e pubblicare **solo** riserva e manifesto, aprire la PR verso `main`
e attendere i controlli richiesti. Dopo il merge, verificare la CI del nuovo
`main` e l'assenza di run duplicati. L'upload rimane sospeso finché il
proprietario non conferma separatamente canale Play e AAB archiviata.

## 5. Caricare su Play solo dopo conferma

Per il test interno, caricare l'AAB archiviata il cui SHA-256 coincide con il
manifesto, completare nome e note della release e controllare l'esito nella
Console. Il test interno **non** è una promozione in produzione. Quando Play
accetta il bundle, registrare un'evidenza `play-accepted` con
[lo script dedicato](../../scripts/record-play-release-evidence.ps1), usando
il codice versione e un riferimento verificabile della Console; poi committare
e pubblicare la nuova evidenza senza modificare i record precedenti.

Dopo l'elaborazione del bundle riesaminare per quel `versionCode` i quattro
gruppi di avvisi, il report pre-lancio disponibile e gli eventuali nuovi
requisiti. Registrare cosa è risolto e cosa rimane aperto, distinguendo i rilievi
del vecchio bundle da quelli del nuovo. L'assenza di crash/ANR o di dati non
sostituisce questa verifica. La promozione in produzione richiede comunque
l'autorizzazione distinta del proprietario.

## 6. Gestire un arresto senza perdere la cronologia

| Momento dell'errore | Azione |
| --- | --- |
| Prima della riserva | Correggere il prerequisito e rieseguire i controlli. Nessun numero è stato consumato. |
| Dopo `*.reservation.json` | Non cancellare, riscrivere o riusare il numero. Conservare e versionare la riserva, registrare `abandoned` con il motivo, poi preparare una versione successiva. |
| AAB valida ma upload rinviato | Conservare AAB e manifesto `built-not-uploaded`. Un caricamento successivo usa **lo stesso file**, non una nuova build con lo stesso numero. |
| Play rifiuta l'AAB o serve cambiare il codice | Registrare l'esito e preparare un nuovo numero. Non correggere retroattivamente riserva o manifesto. |

L'evidenza di abbandono si crea con
`scripts/record-play-release-evidence.ps1 -Event abandoned -VersionCode <codice> -Reason "<motivo>"`
dopo che la riserva è stata acquisita nel registro. Ogni evidenza è append-only.

## 7. Consegnare uno stato verificabile

Alla fine di ogni fase riferire: commit sorgente e PR incluse; versione e
`versionCode`; test automatici e prova reale; percorso e SHA-256 dell'AAB se
esiste; stato esatto (`non costruita`, `built-not-uploaded`, `play-accepted` o
`abandoned`); blocco e **prossima azione che richiede conferma**. Non chiamare
«pronta per Play» una build finché questi dati non coincidono.


### Retry dopo fallimento prima del bundle

La regola seguente è implementata sul ramo release 0.1.15; la sola promozione
di queste istruzioni su main non distribuisce la modifica al builder.

Il versionCode riservato non si riutilizza mai. Il ramo release aggiornato il
22 ottobre permette lo stesso versionName per più AAB ufficiali, anche dopo
accettazione Play, purché ogni nuovo codice superi tutti i codici locali e
quello osservato in Console. Ogni tentativo precedente con quel nome deve avere
un manifesto di build validato oppure un evento `abandoned` validato.
Una riserva senza manifesto né abbandono resta aperta e blocca il nuovo tentativo.

Il ledger deriva questa condizione dalle prove validate; non esiste un
parametro di bypass. Bundle, mapping e manifesti sono distinti per codice e
nome; ogni hash resta legato al proprio codice. Non riscrivere 300033 per
preparare una nuova 0.1.15 e non registrare abbandoni fittizi di build accettate.
Firma, provenienza, TTL e immutabilità restano invariati. La distinzione tra
codice monotono e nome visualizzato è descritta nella
[documentazione Android](https://developer.android.com/studio/publish/versioning).
