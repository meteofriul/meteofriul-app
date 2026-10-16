# Meteo Friûl — distribuzione Android Play

> **Percorso corrente:** la distribuzione prosegue tramite Google Play Console
> e AAB protetto. Firebase App Distribution e il percorso `private_test` sono
> congelati come storico/rollback: non creare nuove release o nuovi tester su
> quel canale. La relativa procedura eseguibile e' disponibile soltanto nella
> cronologia Git e non fa parte di questo runbook.

Il gate autorevole, esclusivamente di lettura, per il cutover notifiche
`play_beta` è [PLAY_NOTIFICATION_CUTOVER_AUDIT.md](PLAY_NOTIFICATION_CUTOVER_AUDIT.md).
Deve risultare `PASS` prima della prima registrazione Play (`staged`) e prima
di abilitare gli invii (`active`).

Questo documento nasce dal collaudo del pilot precedente, ma descrive soltanto
il percorso Google Play corrente. La candidata usa versione pubblica `1.0.0` e
`versionCode 300011`; non e' ancora una distribuzione pubblica e non abilita
pubblicita', acquisti o abbonamenti. Il cutover notifiche parte con il solo
telefono owner e cap `1`; soltanto dopo i gate e la prima installazione
riconosciuta/licenziata da Play puo' estendersi ai partecipanti del closed test.

## Baseline funzionale della candidata Play

- meteo, bollettino, radar, eventi, territorio e scopri tramite il backend HTTPS
  di Meteo Friûl;
- tema di sistema come valore iniziale e Italiano come lingua iniziale;
- posizione automatica foreground solo dopo il consenso Android; per gli
  Avvisi con app chiusa, consenso separato `Consenti sempre`, geofence e
  WorkManager, senza servizio GPS continuo o notifica permanente;
- onboarding Web in due azioni esplicite, richiesta GPS e poi richiesta
  notifiche, perché ciascun prompt del browser richiede un gesto dell'utente;
- scelta manuale del Comune sempre disponibile e capace di disattivare la
  posizione automatica;
- `Segnala` protetto da Firebase App Check Debug su Android e reCAPTCHA
  Enterprise sul Web; senza provider configurato la mutazione resta chiusa;
- sostegno volontario tramite `https://ko-fi.com/meteofriul`, aperto nel
  browser esterno e senza SDK o credenziali di pagamento nell'app;
- preferenze `Allerte` e `Avvisi` entrambe attive per impostazione predefinita;
- allerte ufficiali regionali predisposte per invio FCM ai dispositivi Android
  del gruppo privato, senza targeting per Comune;
- avvisi meteo locali sperimentali soltanto sul telefono owner, con detector
  Open-Meteo conservativo, deduplica e audit sanitizzato per 14 giorni.

## Identita' Firebase e cutover Play

Le route `play_beta` devono accettare soltanto verdict `PLAY_RECOGNIZED` e
`LICENSED`, oppure usare un Firebase Android App ID distinto. Il gate precede la
primissima registrazione Play, anche con cap `1`, e naturalmente precede
qualsiasi invio. Token FCM, ID installazione e relativi hash non vanno trascritti
nei registri condivisi.

Le app Firebase registrate per il pilot sono:

- Android: `1:49007668366:android:725bf6f8b339177a852ddf`, package
  `com.meteofriul.app`;
- Web: `1:49007668366:web:a848e70da40a12eb852ddf`.

Il file `frontend/android/app/google-services.json` è locale e ignorato da Git.
Su una nuova postazione si recupera dalla configurazione già esistente, senza
creare una seconda app:

```powershell
npx firebase-tools apps:sdkconfig ANDROID 1:49007668366:android:725bf6f8b339177a852ddf `
  -o frontend\android\app\google-services.json --project meteo-friul
```

Il backend pilota deve separare gli App ID con
`PUSH_APP_CHECK_ANDROID_APP_IDS` e `PUSH_APP_CHECK_WEB_APP_IDS`; per `Segnala`,
`COMMUNITY_APP_CHECK_ALLOWED_APP_IDS` deve includere soltanto gli App ID
autorizzati. Usare `PUSH_APP_CHECK_MODE=enforce` e
`COMMUNITY_APP_CHECK_MODE=enforce`: non inserire package name, token o FID in
queste variabili. La site key reCAPTCHA Enterprise e la chiave VAPID sono
configurazioni pubbliche della build Web, non credenziali server. La coppia
VAPID è stata generata e la chiave pubblica è versionata; il push Web resta da
collaudare nella preview HTTPS controllata.

Non annotare coordinate GPS precise nel registro di test. Sono sufficienti il
Comune rilevato, il tipo di rete, il risultato e l'eventuale errore.

## Matrice minima comune

1. Primo avvio: Italiano, tema Sistema, Udine solo come placeholder; `Allerte`
   e `Avvisi` entrambe ON.
2. Posizione precisa consentita: Comune corretto e aggiornamento dell'app.
3. Posizione approssimativa o negata: nessun blocco, scelta manuale disponibile.
4. Ritorno in primo piano, oppure app lasciata visibile per almeno 3 minuti: un
   solo nuovo controllo della posizione, prima rapido/bilanciato e poi preciso
   soltanto se necessario.
5. Cambio Comune manuale: posizione automatica disattivata e nessuna risposta
   GPS tardiva capace di sovrascrivere la scelta.
6. Modalità offline e ritorno online: dati precedenti conservati e recupero
   senza schermate vuote ingannevoli.
7. `Segnala`: consenso obbligatorio, posizione recente e sufficientemente
   precisa, invio singolo, conferma e annullamento entro la finestra prevista.
8. Lingua IT/FUR, tema e preferenze persistenti dopo riavvio.
9. Allerte push: contenuto regionale e apertura del Bollettino; il Comune
   selezionato non restringe la consegna.
10. Avvisi locali: verificare prima sul telefono owner Comune/localita, testo
    probabilistico, orario, deduplica e audit; estendere ai partecipanti del
    closed test soltanto dopo il cutover Play approvato.

### Android

1. Permesso notifiche richiesto subito dopo il tentativo GPS.
2. App Check Debug e' ammesso soltanto per il preflight owner locale; la build
   Play deve usare Play Integrity e risultare `PLAY_RECOGNIZED` e `LICENSED`.
3. Registrazione token FCM prima sul solo owner con cap `1`, poi sul closed test
   esclusivamente dopo il cutover approvato.
4. Link esterni aperti nel browser predefinito, non dentro la WebView.
5. Da Impostazioni, `Posizione per gli Avvisi` apre la schermata Android e
   richiede esplicitamente `Consenti sempre`; al rientro lo stato deve risultare
   attivo, senza notifica permanente di localizzazione.
6. Con app chiusa, uscire di oltre 200–500 m dalla zona del fix e verificare il
   trigger `geofence_exit`; verificare anche `periodic` entro i limiti imposti
   da Android. Annotare solo localita, orario, trigger ed esito, mai coordinate.
7. Dopo riavvio del telefono, verificare che il controllo venga ripristinato.

### Web

1. Preview HTTPS: onboarding GPS e notifiche usa due pulsanti distinti; ogni
   rifiuto o rinvio lascia disponibile la scelta manuale e non blocca l'app.
2. Build senza VAPID: stato esplicito «non configurato», nessuna registrazione
   browser e nessuna falsa conferma di ricezione.
3. Build con VAPID: service worker `/firebase-messaging-sw.js` disponibile,
   permesso concesso, FID registrato e revoca verificabile.
4. App Check reCAPTCHA Enterprise valido abilita `Segnala` e le mutazioni push;
   configurazione mancante o App ID Web non autorizzato resta fail-closed.
5. Il push Web resta un circuito separato e non e' prova del cutover Android.

## Attivazione push in due fasi

Nessuno scheduler o invio va dichiarato attivo prima del completamento di
questa procedura. La presenza del workflow nel repository non basta: vanno
verificati endpoint, IAM, variabili e risultato E2E.

### Gate obbligatorio della versione distribuita

Una build Web o APK destinata a terzi non puo' ricevere soltanto un URL tagged:
deve dichiarare anche l'URL Community ufficiale separato, la revisione Cloud Run
attesa e il commit backend da cui proviene. Il nome della revisione deve
contenere i primi sette caratteri del commit backend. Prima di costruire
occorre avere un worktree pulito con `HEAD` uguale al branch remoto.

Usare esclusivamente gli script protetti. La procedura Play e' distinta dalla
build privata e non effettua automaticamente alcun upload:

```powershell
.\scripts\deploy-cloudflare-app.ps1 `
  -ApiBase "https://<TAG>---meteofriul-api-<HASH>.a.run.app/api" `
  -ExpectedRevision "meteofriul-api-<SCOPO>-<COMMIT7>" `
  -ExpectedBackendCommit "<COMMIT_BACKEND_40>"

pwsh -NoProfile -File .\scripts\build-play-aab.ps1 `
  -ApiBase "https://<TAG>---meteofriul-api-<HASH>.a.run.app/api" `
  -CommunityApiBase "https://meteofriul-community-49007668366.europe-west1.run.app/api" `
  -ExpectedRevision "meteofriul-api-<SCOPO>-<COMMIT7>" `
  -ExpectedBackendCommit "<COMMIT_BACKEND_40>" `
  -ExpectedLatestPlayVersionCode <ULTIMO_VERSION_CODE_PLAY_O_0> `
  -BundletoolPath "C:\secure\bundletool-all.jar" `
  -ExpectedBundletoolSha256 "<SHA256_BUNDLETOOL_ATTESO>" `
  -ExpectedUploadCertificateSha256 "<SHA256_UPLOAD_KEY_PRIMA_BUILD>"
```

La build Play richiede PowerShell 7 e
`ConvertFrom-Json -DateKind`: avviarla sempre con `pwsh -NoProfile -File`.
Windows PowerShell 5.1 viene rifiutato prima di qualsiasi preflight.

Gli script correnti risolvono il tag mediante l'account Google Cloud Meteo Friûl e
bloccano la procedura se tag, URL risolto, servizio, revisione, commit, stato
`Ready`, digest o `/api/healthz` non coincidono. Il controllo viene ripetuto
dopo la build; il deploy Web lo ripete anche dopo la pubblicazione. Un errore
non va aggirato cambiando i valori attesi: occorre identificare quale elemento
e' realmente vecchio o incoerente, correggere tag/revisione oppure produrre una
nuova revisione isolata e ricominciare il gate.

Conservare nel risultato della prova: commit frontend, commit backend,
revisione, tag, digest container e hash APK/AAB/deployment. Non dichiarare mai una
versione distribuita basandosi soltanto sul nome del tag o sul successo della
compilazione.

La cronologia APK `release-history/android-private-test` e lo script
`build-private-test-apk.ps1` appartengono al percorso congelato. Non usarli per
un nuovo tester o come preparazione dell'AAB.

Per Google Play, `frontend/android/play-keystore.properties` e la upload key
sono segreti locali ignorati da Git e separati dalla chiave private-test. Lo
script `build-play-aab.ps1` richiede bundletool esplicito e il suo SHA-256
atteso, che viene confrontato prima di eseguire il jar. Verifica inoltre che
`google-services.json` appartenga esattamente al progetto `meteo-friul`, al
project number `49007668366`, all'app Firebase
`1:49007668366:android:725bf6f8b339177a852ddf` e al package
`com.meteofriul.app`. Quindi convalida il bundle, legge application ID e
versioni dal manifesto realmente impacchettato, verifica ogni entry firmata e
un singolo fingerprint del certificato upload, controlla la stessa API nel
bundle WebView e nel worker nativo e ripete il preflight Cloud Run. Il valore
`ExpectedLatestPlayVersionCode` deve provenire dalla Play Console; `0` e'
ammesso soltanto se il package non contiene ancora artefatti caricati.

Prima di creare il candidato AAB, verificare manualmente anche il gate privacy:

- `https://meteofriul.it/privacy/` deve essere pubblica, raggiungibile via
  HTTPS e contenere esattamente
  `Titolare del trattamento: Riccardo Rosset — progetto Meteo Friûl`;
- il contatto pubblicato deve essere `info@meteofriul.it`;
- profilo sviluppatore, URL privacy e dati inseriti dal titolare in Play
  Console devono usare informazioni coerenti;
- la dicitura Crediti è già presente nell'app e va soltanto ricontrollata; lo
  splash non va modificato come parte di questo gate.

Questi campi vengono compilati dal titolare nella Console: lo script AAB non
li deduce e non modifica la pagina privacy o il profilo Play.

Il manifest richiede `ACCESS_BACKGROUND_LOCATION`; prima del caricamento Play
è quindi obbligatorio completare il Permissions Declaration Form. Preparare un
breve video Android accessibile alla revisione che mostri nell'ordine la
funzione Avvisi locali, la disclosure prominente in-app, il consenso
dell'utente e il prompt/pannello Android per `Consenti sempre`. La descrizione
della funzione nella scheda Store e nel modulo deve coincidere con l'uso reale:
avvisi meteo locali legati alla posizione, senza pubblicità o tracciamento. Se
modulo, video, disclosure o descrizione Store non sono pronti, l'AAB non va
caricato in Play Console.

Prima della build deve passare anche il gate Firestore TTL, documentato in
`docs/operations/FIRESTORE_PUSH_TTL_GATE.md`:

```powershell
.\scripts\audit-firestore-push-ttl.ps1
```

Il gate richiede le policy `ACTIVE` su
`push_official_alert_outbox.expires_at` e
`push_local_notice_outbox.expires_at`, gli orizzonti applicativi rispettivamente
di 30 e 14 giorni e l'evidenza della verifica/backfill una tantum dei record
storici. Una policy TTL non elimina i documenti privi del campo `expires_at`.
Non creare l'AAB finche' l'exit code non e' `0`.

La sezione Territorio contiene UGC anonimo, strutturato e a scelta chiusa. Prima
dell'AAB deve risultare verde anche il gate separato
`docs/operations/COMMUNITY_MODERATION_GATE.md`: linee guida v2, otto fenomeni
predefiniti, Comune canonico, feed di 60 minuti, segnalazione e blocco fonte in
app, contratti runtime, privacy/Data Safety e policy TTL `ACTIVE` per tutte le
collection community. Il gate push precedente non attesta queste collection e
non lo sostituisce.

La decisione autorevole del 25 agosto 2026 non richiede per la prima beta un job,
uno scheduler, service account dedicati, policy Monitoring o email di
moderazione. `build-play-aab.ps1` verifica invece due volte il contratto effimero
dell'API pubblica: tipi chiusi, catalogo comunale canonico, durata di 60 minuti,
posizione zonale e assenza di identificatori interni o contenuti liberi nelle risposte. Il
codice digest resta una contingenza dormiente e la sua assenza dal runtime non e'
un errore di rilascio.

Il gate TTL community ha due prove indipendenti. La build esegue sempre un
read-back LIVE fresco e in sola lettura dell'identita', delle otto policy e di
ogni documento presente; una collection vuota e' valida in questa fotografia.
L'ottava policy puo' restare quella di `community_moderation_digest_state` come
contingenza dormiente: la policy `ACTIVE` non equivale all'attivazione del digest.
Richiede inoltre il record LIVE aggregato piu' recente in
`release-history/firestore-community-ttl`: deve coprire almeno un campione
valido per tutte le otto collection, avere non piu' di 30 giorni ed essere
stato aggiunto una sola volta in Git. Il record e' legato tramite SHA-256 ai
sorgenti writer correnti. Fixture, account/progetto/database errati, hash non
coerente, file non tracciati/sporchi o record modificati bloccano la build.

La registrazione non va eseguita insieme alla build e non assume documenti
reali. Da `backend`, avviare in due terminali lo smoke TTL privato e il seed
marker-owned; entrambi fanno cleanup in `finally`, non creano job, scheduler o
email e il hold massimo e' 120 s:

```powershell
.\venv\Scripts\python.exe tools\smoke_community_moderation_live.py `
  --apply --hold-seconds 120
.\venv\Scripts\python.exe tools\seed_community_ttl_evidence_live.py `
  --api-base "https://<TAG>---meteofriul-api-<HASH>.a.run.app/api" `
  --apply --hold-seconds 120
```

Il secondo tool crea il report gia' scaduto e nascosto, verifica l'assenza
pubblica prima/durante/dopo e cancella in transazione soltanto documenti che
conservano il proprio marker. Quando entrambi hanno emesso `evidence_ready`,
registrare in un terzo terminale prima della pulizia e poi sottoporre il record
a review e commit append-only:

```powershell
pwsh -NoProfile -File .\scripts\record-firestore-community-ttl-evidence.ps1 `
  -RecordLiveEvidence `
  -SourceCommit "<COMMIT_BACKEND_40_DELLA_REVISIONE_LIVE>" `
  -OutputPath .\release-history\firestore-community-ttl\<YYYYMMDDTHHMMSSfffZ>-community-ttl.evidence.json
```

Attendere sempre la pulizia verde di entrambi i tool; un record catturato
durante una run poi fallita non va committato.

Non modificare, rinominare o cancellare un record precedente. Il file conserva
solo identita' cloud, policy, conteggi ed estremi aggregati; non include ID,
chiavi pseudonime, coordinate o contenuti community. Una modifica a uno dei
writer elencati nel ledger richiede una nuova registrazione LIVE.
`SourceCommit` identifica la revisione backend LIVE che ha prodotto i campioni.
Durante la build il digest viene ricalcolato direttamente dai blob writer e
producer del `releaseApiState.BackendCommit` risolto dal tag, senza checkout:
uguaglianza del
solo campo JSON non e' sufficiente. `SourceCommit` deve esserne un antenato;
un discendente con writer invariati passa, uno che modifica gli writer blocca.

La privacy Territorio richiede inoltre il passaggio separato
`docs/operations/COMMUNITY_PRIVACY_DATA_SAFETY_HANDOFF.md`. Non creare l'AAB se
le pagine HTTPS IT/FUR dichiarano ancora la vecchia combinazione IP + ID, se
omettono dati pubblici, `client_id` pseudonimo, hash server-side scoped,
flag/blocco locale, intervento globale manuale eventuale o gli orizzonti
45 min/60 min/2 h/24 h, oppure se il testo FUR non ha una revisione linguistica
esplicita. Le pagine non devono descrivere digest, log ready o email automatiche
come trattamento attivo della prima beta. La stessa mappatura deve coincidere
con Data Safety.

La cronologia permanente Play e' `release-history/android-play`. Prima della
compilazione viene creato un record `*.reservation.json`: da quel momento
`versionCode` e `versionName` restano riservati anche se la build fallisce o
viene abbandonata. Il candidato deve superare sia il massimo di tutta la
cronologia locale, compresa quella private-test, sia l'ultimo versionCode
osservato in Play Console. Il manifesto `*.release.json` dichiara soltanto
`built-not-uploaded` e non simula visibilita' o accettazione in Console.

La continuita' della upload key usa un trust anchor esplicito per il primo AAB
e, in seguito, esclusivamente l'ultima evidenza append-only `play-accepted`.
Una build non caricata non diventa mai una fonte di fiducia; una rotazione
richiede un'evidenza `upload-key-rotation` con riferimento verificabile. Gli
stati successivi si aggiungono con `scripts/record-play-release-evidence.ps1`
come `play-accepted` oppure `abandoned`, senza sovrascrivere record. Il
certificato di app signing applicato da Google e' distinto e si registra in
Firebase App Check soltanto dopo averlo letto da Play Console.

Prima di ogni build e in CI, `scripts/audit-play-release-ledger.ps1` verifica
anche la storia Git completa: ciascun JSON deve avere un solo commit di
aggiunta e nessuna modifica, rinomina, copia o cancellazione successiva. Un
registro alterato blocca la procedura; non si corregge riscrivendo il passato.

L'AAB viene copiato in modo immutabile fuori dagli output Gradle, in
`release-artifacts/android-play`; la directory e' ignorata da Git ma deve
risiedere su storage durevole e protetto. Il guard Gradle blocca ogni task che
puo' assemblare, produrre, firmare, impacchettare, finalizzare o pubblicare una
release, compreso `signReleaseBundle`, se non riceve il marker monouso dello
script e tutte le proprieta' API, signing e Firebase previste.

Diagnosi dei blocchi principali:

| Codice | Significato | Correzione ammessa |
| --- | --- | --- |
| `release_android_play_powershell_7_required` / `release_android_play_convertfromjson_datekind_required` | la build e' stata avviata con Windows PowerShell 5.1 o con un runtime senza parsing date esplicito | usare `pwsh -NoProfile -File`; non rimuovere il guard o reinterpretare l'evidenza con 5.1 |
| `release_git_worktree_not_clean` | esistono modifiche non committate | verificare i file, eseguire test e creare il commit previsto |
| `release_git_head_not_pushed` | il commit locale non coincide col remoto | controllare branch e push; non costruire dal solo locale |
| `release_gcloud_account_mismatch` | e' attivo un account Google Cloud diverso | fermarsi e selezionare esclusivamente l'account Meteo Friûl |
| `release_api_tag_resolution_invalid` | il tag manca o non e' univoco | correggere la route Cloud Run e ripetere il controllo |
| `release_api_tag_revision_mismatch` | il tag serve una revisione diversa da quella dichiarata | verificare quale revisione e' stata collaudata; spostare il tag solo dopo il test isolato oppure correggere il valore atteso se era documentato male |
| `release_revision_does_not_identify_backend_commit` | revisione e commit backend non corrispondono | distribuire una revisione nominata col commit corretto |
| `release_revision_not_ready` | Cloud Run non dichiara la revisione pronta | leggere condizioni e log; non distribuire |
| `release_revision_image_digest_missing` | l'immagine servita non e' identificabile in modo immutabile | correggere il deploy Cloud Run e ripetere il gate |
| `release_api_health_request_failed` / `release_api_health_not_ok` | l'endpoint tagged non e' sano | controllare health e log della revisione; non costruire o pubblicare |
| `release_android_version_already_exists` | `versionCode` o `versionName` e' gia' presente in un APK versionato | incrementare entrambi nel progetto; non cancellare o sovrascrivere il rilascio precedente per aggirare il gate |
| `release_android_version_not_incremented` | il nuovo `versionCode` non supera quello piu' recente | correggere la versione Android e ricominciare dalla build pulita |
| `release_android_existing_artifact_invalid` | un APK storico non e' leggibile o non ha metadati/firma verificabili | isolare e identificare l'artefatto; non procedere finche' la cronologia non e' verificata |
| `release_android_history_directory_missing` / `release_android_history_record_invalid` | il registro permanente manca o contiene JSON non valido/incompleto | ripristinare il registro dal repository e correggere il record; non ricostruire valori ignoti per deduzione |
| `release_android_signing_certificate_changed` | la chiave di firma non coincide con un APK precedente | recuperare la chiave corretta; non distribuire un aggiornamento non installabile |
| `release_android_artifact_path_exists` / `release_android_manifest_path_exists` | esiste gia' l'output previsto | trattarlo come rilascio gia' prodotto e incrementare la versione |
| `release_android_artifact_copy_verification_failed` | la copia versionata non coincide byte per byte col file firmato | non distribuire; conservare entrambi i file per diagnosi e controllare filesystem/antivirus |
| `release_android_manifest_verification_failed` | il manifesto scritto non coincide con APK o identita' Cloud | conservare gli artefatti per diagnosi, non distribuire e correggere la procedura |
| `release_android_play_signing_not_configured` | manca il file segreto della upload key Play | creare e verificare il file ignorato soltanto dopo la decisione sulla chiave; non riusare automaticamente la chiave tester |
| `release_android_play_bundletool_*` / `release_android_play_bundle_invalid` | bundletool manca, il suo hash non coincide o rifiuta l'AAB | usare il jar ufficiale e il digest ottenuto dalla fonte fidata; non eseguirlo o caricare il bundle in caso di discordanza |
| `release_android_play_google_services_*` / `release_android_play_firebase_*` | la configurazione Firebase locale non coincide con progetto, app ID e package approvati | ripristinare il `google-services.json` corretto; non modificare i valori attesi per aggirare il gate |
| `release_android_play_application_id_mismatch` | l'AAB contiene un package diverso | fermarsi: il package Play non puo' essere corretto dopo la creazione dell'app |
| `release_android_play_api_missing_from_webview` / `release_android_play_api_missing_from_native_worker` | WebView e worker non condividono l'endpoint approvato | correggere binding/sync Android e ricostruire da un nuovo commit |
| `release_android_play_candidate_version_reserved` / `release_android_play_version_not_incremented` | versione gia' riservata oppure non superiore a cronologia e Console | incrementare il progetto; non cancellare prenotazioni o dichiarare un valore Console falso |
| `release_android_play_upload_trust_anchor_required` / `release_android_play_upload_certificate_untrusted` | manca una fonte autorevole per il certificato upload oppure il fingerprint e' cambiato | per la prima build fornire il fingerprint atteso; in seguito registrare accettazione o rotazione con evidenza append-only |
| `release_android_play_signature_verification_failed` | almeno una entry non e' firmata, ha piu' signer o usa un fingerprint diverso | correggere signing e produrre una nuova versione; non caricare l'AAB |
| `release_android_play_firestore_ttl_gate_failed` | policy TTL, read-back corrente o evidenza storica non soddisfano il contratto 30/14 giorni | non creare l'AAB; seguire `docs/operations/FIRESTORE_PUSH_TTL_GATE.md` e ripetere il gate solo dopo la correzione separata |
| `release_android_play_firestore_community_ttl_gate_failed` | identita', otto policy o almeno un documento corrente non sono conformi; l'assenza di documenti da sola non produce questo errore | correggere lo stato LIVE; non creare campioni durante la build |
| `release_android_play_firestore_community_ttl_historical_evidence_*` | manca un record aggregato LIVE recente e immutabile, oppure fixture, identita', copertura, SHA-256 writer o storia Git non sono conformi | registrare esplicitamente un nuovo record LIVE append-only con tutti gli otto campioni; non modificare quello precedente |
| `release_android_play_community_ephemeral_gate_failed` | l'API Territorio non prova piu' tipi chiusi, Comune canonico, TTL di 60 minuti, posizione zonale o assenza di identificatori interni/contenuto libero nelle risposte pubbliche | correggere il contratto API; non creare un runtime digest per aggirare il finding |

I valori `ExpectedRevision` ed `ExpectedBackendCommit` non devono essere
modificati soltanto per far passare lo script: devono provenire dal collaudo
della revisione isolata e dal commit backend realmente pubblicato.

Dopo una build Android riuscita la procedura non e' ancora distribuibile:

1. controllare APK, hash e manifesto mostrati dallo script;
2. aggiungere soltanto il nuovo `.release.json` al commit del registro;
3. eseguire commit e push; i branch `codex/**` avviano la stessa CI di `main`;
4. verificare dalla run GitHub Actions che il commit esatto sia verde;
5. distribuire esattamente l'APK il cui SHA-256 coincide col manifesto;
6. conservare APK e manifesto nell'archivio tecnico.

Per un AAB Play, sostituire i passi di distribuzione con questi gate:

1. confrontare AAB archiviato, SHA-256, `versionCode`, upload certificate,
   prenotazione e manifesto;
2. committare e pushare i nuovi record `*.reservation.json` e
   `*.release.json` in `release-history/android-play`, poi attendere la CI
   verde;
3. caricare in Play Console esattamente l'AAB conservato in
   `release-artifacts/android-play` con lo SHA-256 registrato;
4. non promuovere il track finche Play non ha accettato il bundle e mostrato
   la versione attesa. Registrare quindi `play-accepted` con
   `scripts/record-play-release-evidence.ps1`; se il candidato viene scartato,
   registrare `abandoned`. Committare e pushare la nuova evidenza senza
   riscrivere prenotazione o manifesto;
5. leggere dalla sezione App signing lo SHA-256 del certificato applicato da
   Google, collegare Play Integrity allo stesso progetto `meteo-friul` e
   registrare quel certificato in Firebase App Check;
6. prima di impostare il backend su `play_beta`, configurare App Check per
   richiedere `PLAY_RECOGNIZED` e `LICENSED`; se i verdict non sono separabili
   dal sideload privato, usare un Firebase Android App ID distinto;
7. revocare **tutti** i token App Check Debug associati all'app Android,
   conservare un'evidenza verificabile che la lista sia vuota, chiudere la
   policy sideload e attendere almeno la TTL massima configurata dei token gia'
   emessi. Qualsiasi nuovo token Debug fa ripartire l'attesa;
8. soltanto dopo questi gate, installare dal track e verificare App Check, API,
   registrazione con cap `1`, notifiche e aggiornamento
   prima di ampliare il gruppo beta.

### Gate obbligatorio dell'account Play personale

Poiche' l'account sviluppatore personale e' stato creato dopo il 13 novembre
2023, l'accesso alla produzione richiede un **closed test** con almeno 12 tester
opted-in continuativamente per 14 giorni. L'internal testing e i suoi tester
non sostituiscono questo requisito. Il conteggio va avviato solo dopo che il
track chiuso, il link di adesione e la build installabile sono stati verificati;
prima della richiesta di produzione controllare in Console che numero e durata
risultino soddisfatti.

E' prudente invitare qualche tester in piu' di 12 per assorbire rinunce o
problemi di adesione, ma il margine aggiuntivo e' una raccomandazione operativa,
non un requisito dichiarato. L'espansione delle notifiche resta comunque
separata: prima si collauda il solo owner con cap `1`, poi si aumenta il cap in
modo esplicito e controllato per i partecipanti del closed test.

La versione `versionName+versionCode` dichiarata dal client è un controllo
aggiuntivo, non una prova crittografica del canale. Non mantenere la policy
unrecognized/unlicensed del vecchio APK durante il cutover Play e non accettare
nemmeno la prima registrazione beta finché i gate precedenti non sono
verificati. `PLAY_RECOGNIZED` e `LICENSED` non revocano un token Debug gia'
valido: il backend vede l'App ID attestato, non quale provider lo ha emesso.

## Preflight Android owner corrente su Windows/Codex

Il preflight owner serve a controllare sul telefono UI, onboarding, disclosure,
permessi e comportamento nativo prima di autorizzare l'AAB. E' un APK debug
locale: non e' distribuibile, non prenota un `versionCode` Play e non dimostra
Play Integrity o gli stati `PLAY_RECOGNIZED` e `LICENSED`.

Quando la build e' eseguita da Codex Desktop, `android:sync` e Gradle devono
partire **direttamente fuori dal sandbox**, con autorizzazione limitata ai soli
comandi di build. Non effettuare prima un tentativo nel sandbox: su questa
postazione Windows le scritture Node in `frontend/dist` e quelle Gradle negli
output Android possono restituire un `EPERM` ambientale anche senza un vero file
bloccato.

Al primo `EPERM` non cancellare ripetutamente `frontend/dist`, non copiare gli
asset uno alla volta e non creare un altro output dentro `frontend`. Ripetere
una sola volta lo stesso comando fuori dal sandbox. Se fallisce anche li':

1. fermare la build senza produrre o installare artefatti;
2. controllare in sola lettura processi, porta di Vite, attributi e ACL del
   percorso esatto;
3. risolvere e confrontare il percorso assoluto prima di rimuovere soltanto una
   directory generata;
4. usare una directory univoca sotto `%TEMP%` soltanto come fallback
   diagnostico, mai come procedura ordinaria del preflight owner.

Il warning Vite sui chunk superiori a 500 kB resta non bloccante.

```powershell
$env:JAVA_HOME = "C:\Program Files\Android\Android Studio\jbr"
$env:ANDROID_HOME = Join-Path $env:LOCALAPPDATA "Android\Sdk"
$env:ANDROID_SDK_ROOT = $env:ANDROID_HOME
$env:VITE_ANDROID_API_BASE = "https://<TAG-CANDIDATO>---<SERVIZIO>.a.run.app/api"
Remove-Item Env:VITE_API_BASE -ErrorAction SilentlyContinue

Push-Location frontend
# Da Codex Desktop: fuori dal sandbox fin dal primo tentativo.
npm run android:sync
Pop-Location

# Da Codex Desktop: fuori dal sandbox e con lo stesso endpoint tagged.
frontend\android\gradlew.bat -p frontend\android assembleDebug `
  "-PMETEO_API_BASE=$env:VITE_ANDROID_API_BASE"
```

Dopo la compilazione verificare endpoint in WebView e worker nativo, package,
`versionCode`, `versionName`, firma, permessi, SHA-256 e worktree Git. Installare
via cavo soltanto l'APK appena verificato. Se il test successivo deve registrare
il vero primo avvio, lasciare l'app installata ma chiusa.

Per un candidato Play non eseguire questa sequenza e non lanciare prima
`android:sync`. Eseguire direttamente, fuori dal sandbox, lo script protetto
`scripts/build-play-aab.ps1`: usa gia' `%TEMP%`, verifica il runtime, sincronizza
gli asset, applica i gate Gradle e archivia AAB e manifesto. Un workaround
manuale rende il candidato non distribuibile.

## Regole operative condivise per notifiche e cache

Per gli avvisi meteo locali la revisione candidata deve rispettare questi gate:

1. leggere fino a sei ore soltanto per validare le finestre multi-orarie, ma
   scartare dall'invio ogni fenomeno il cui inizio disti piu di 60 minuti;
2. temporali solo con codice WMO `95/96/99`, probabilita almeno `70%` e
   precipitazione liquida concorde; la grandine e' una variante dei codici
   `96/99`, non un avviso autonomo;
3. pioggia intensa solo con `15 mm/3 h`, almeno `5 mm` in una singola ora e
   probabilita almeno `70%` sulla stessa fascia;
4. raffiche da `70 km/h`, neve moderata/forte esplicita o `2 cm/3 h` con alta
   probabilita, precipitazioni gelate soltanto da codice esplicito;
5. caldo da `35 °C` reali o `38 °C` percepiti per due ore consecutive, una sola
   volta al giorno;
6. testi sempre probabilistici; nessun uso di `allerta`, `pericolo` o
   `criticita` negli avvisi Open-Meteo;
7. simulazioni sotto soglia, oltre la finestra di un'ora, grandine, collisioni
   tra fenomeni, cambio localita e deduplica devono passare prima di qualsiasi
   passaggio da `dry_run` a `send`.

Il workflow GitHub resta un percorso separato e la sua presenza non dimostra
lo stato Cloud. Nel pilot operativo è Cloud Scheduler a invocare direttamente
il Cloud Run Job verificato. I due scheduler legacy verso route HTTP obsolete
sono stati eliminati.

Il percorso operativo in Cloud Run è: metadati del post del canale ufficiale
`@ProtCivileFVG` → riconciliazione stretta con il pannello PCR ARPA/OSMER.
Devono coincidere numero/anno, livello, zone e finestra di validità; una
discordanza critica blocca l'invio. `23:59` e `24:00` sono considerate la
stessa fine giornata. Il PDF resta una verifica più forte quando è
raggiungibile, ma il dominio documentale della Protezione Civile non è
raggiungibile da Cloud Run e non può bloccare il percorso corroborato. Telegram
è soltanto positivo: l'assenza di un post non cancella un'allerta.

Cloud Monitoring invia un avviso a `info@meteofriul.it` dopo almeno due
esecuzioni fallite del job ufficiale nella finestra di 5 ore. Un singolo errore
transitorio non apre l'incidente. La policy mantiene un solo canale email e
invia una notifica di apertura e una di ripristino per incidente, non una mail
per ogni ciclo. Il push resta owner-only e l'outbox deve deduplicare le
esecuzioni successive della stessa allerta.

L'ultima allerta regionale FVG autorevole viene conservata sul dispositivo in
una cache dedicata, indipendente dal Comune meteo. Un avvio a freddo deve
mostrarla subito finche `valid_to` non e' trascorso; errori di rete, prefetch
incompleti e cambi di localita non possono cancellarla. La rimozione e' ammessa
soltanto alla scadenza o dopo una risposta regionale autorevole che conferma
l'assenza di allerte. Cold start, offline, cambio Comune, aumento di livello,
scadenza e revoca fanno parte dei test obbligatori prima della distribuzione.

## Build Web di preview

La preview deve essere compilata come Web, mai riutilizzando `dist` Android:

```powershell
Push-Location frontend
Remove-Item Env:VITE_ANDROID_API_BASE -ErrorAction SilentlyContinue
$env:VITE_API_BASE = "/api"
# Impostare le variabili pubbliche VITE_FIREBASE_* elencate in .env.example.
npm run build
Pop-Location
```

La configurazione deve includere Firebase Web, la site key reCAPTCHA Enterprise
e la chiave VAPID pubblica, già versionata nella configurazione di produzione e
sovrascrivibile localmente con `VITE_FIREBASE_VAPID_KEY`. Non usare token App
Check Debug in una build di preview/produzione e non inizializzare Analytics. Prima
del test verificare che manifest e `/firebase-messaging-sw.js` siano serviti via
HTTPS e senza cache persistente del service worker.

## Build Android locale per il preflight owner

La vecchia procedura private-test e' sostituita dal preflight owner corrente e
dallo script Play protetto. Non eseguire comandi storici per preparare un tester
o un candidato AAB.

Il precedente fallback Firebase Hosting è stato rimosso. Ogni APK push deve
incorporare esplicitamente l'endpoint Cloud Run tagged approvato e il bundle va
controllato prima dell'installazione. La sequenza manuale seguente e' ammessa
soltanto per la build debug owner; un APK tester distribuibile deve passare lo
script protetto e il gate della versione distribuita descritto sopra.

Per aggiornare il telefono senza perdere l'ID installazione usare:

```powershell
& "$env:ANDROID_HOME\platform-tools\adb.exe" install -r `
  frontend\android\app\build\outputs\apk\debug\app-debug.apk
```

L'APK debug è riservato al telefono owner e non dimostra Play Integrity,
`PLAY_RECOGNIZED`, `LICENSED`, firma upload o installazione dal track. Non
trascrivere token App Check, FCM o ID installazione nel registro condiviso.

## Scheda risultato

Per ogni prova registrare:

- etichetta del target, browser/versione oppure versione Android;
- versione APK e `versionCode`;
- data e ora;
- rete Wi-Fi o mobile;
- Comune atteso e Comune rilevato, senza coordinate;
- risultato `OK`, `KO` o `NON PROVATO`;
- passaggi essenziali per riprodurre l'errore;
- screenshot privo di token, credenziali o dati personali.

## Criteri di avvio del closed test Play

Il closed test puo' partire soltanto quando non ci sono errori bloccanti in
avvio, posizione, aggiornamento dati, App Check, `Segnala`, sicurezza effimera
Territorio e push;
non compaiono token o ID installazione nei log condivisi; non esiste
localizzazione continua; registrazione e revoca sono verificate; gli invii sono
deduplicati; la prima installazione Play owner ha superato il cutover con cap
`1`. Play Billing, AdMob e accesso alla produzione restano decisioni e gate
separati.

## Backlog grafico non bloccante

Rinviare a una revisione dedicata, senza mescolarla al pilot notifiche:

- dichiarare un'immagine social esplicita e coerente tramite metadati Open
  Graph su `meteofriul.app` e `meteofriul.it`; favicon e anteprima social sono
  risorse distinte e le cache dei servizi di messaggistica vanno considerate;
- uniformare le icone PWA 192 e 512 px, oggi rispettivamente trasparente e
  opaca, e aggiungere una risorsa separata `maskable` con safe area verificata;
- calibrare la dimensione ottica dell'icona PWA rispetto al foreground adattivo
  dell'APK. Il badge Brave/Chrome sui collegamenti Web è applicato dal browser
  o dal launcher e non va confuso con una parte del logo.

Queste differenze sono solo visive e non bloccano GPS, dati, App Check o push.
