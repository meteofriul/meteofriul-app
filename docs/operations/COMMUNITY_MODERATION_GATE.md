# Gate sicurezza community Territorio

Stato: **feed effimero approvato; gate distribuzione riaperto per il ledger reputazione pseudonimo**
Data decisione: 18 settembre 2026
Perimetro: segnalazioni anonime e strutturate della sezione Territorio. Questo
documento definisce il gate tecnico proporzionato; non autorizza da solo
modifiche a Play Console o la generazione dell'AAB.

## 1. Perche' la funzione rientra nell'UGC

Le segnalazioni di Territorio sono contenuti generati dagli utenti anche se:

- la scelta e' limitata a otto fenomeni predefiniti;
- non esistono testo libero, foto, nome pubblico o interazione diretta;
- la posizione pubblica e' soltanto comunale/zonale;
- il contenuto scade dopo circa 60 minuti.

Il criterio Google e' che un contenuto contribuito da un utente sia visibile o
accessibile ad almeno una parte degli altri utenti. Per l'UGC pubblico Google
richiede termini accettati prima della creazione, regole che vietino contenuti e
comportamenti impropri, segnalazione in-app di contenuto e fonte/utente, blocco
in-app e moderazione effettiva e continuativa.

Fonti ufficiali:

- [User-generated content](https://support.google.com/googleplay/android-developer/answer/9876937?hl=en-GB)
- [Understanding moderation requirements](https://support.google.com/googleplay/android-developer/answer/12923286?hl=en-GB)
- [User Data](https://support.google.com/googleplay/android-developer/answer/10144311?hl=en)
- [Data safety](https://support.google.com/googleplay/android-developer/answer/10787469?hl=en)

I comandi `Segnala contenuto` e `Nascondi questa fonte` devono restare distinti,
riconoscibili e accessibili sia dalla mappa sia dall'elenco. Il blocco fonte e'
offerto soltanto quando il contributo proviene da una singola fonte pubblica
identificabile; su un gruppo aggregato multi-fonte resta il flag del contenuto,
per non bloccare anche fonti estranee. Nella prima beta il flag deve nascondere
subito il contenuto al segnalante e restare temporaneo e azionabile; non deve
necessariamente attivare un job, una notifica email o una revisione umana di
ogni singolo evento.

## 2. Riduzione preventiva del rischio

Il contratto iniziale deve mantenere tutte queste limitazioni:

- nessun testo libero, immagine, audio, nome, profilo o messaggio tra utenti;
- tipi ammessi esclusivamente: pioggia, temporale, neve, grandine, nebbia,
  vento forte, ghiaccio e situazione tranquilla;
- creazione soltanto con posizione corrente in FVG e App Check valido;
- pubblicazione del centro canonico del Comune, mai delle coordinate GPS;
- cooldown anonimo, limiti globali e per installazione;
- visibilita' del contenuto per 60 minuti;
- disclaimer che le segnalazioni non sostituiscono allerte, bollettini o canali
  di emergenza.

Un ampliamento futuro con testo, foto, profili o interazioni richiede un nuovo
audit UGC e non puo' ereditare automaticamente questo gate.

## 3. Linee guida community v2

Versione tecnica obbligatoria: `community-guidelines-v2`.

Il testo deve essere mostrato integralmente prima dell'invio. L'utente deve
accettarlo con un'azione affermativa; una versione diversa o l'assenza
dell'accettazione deve essere rifiutata anche dal backend. Le stesse linee guida
devono inoltre restare riapribili dall'area informativa di Territorio; una pagina
pubblica IT/FUR puo' aiutare utenti e revisore, ma non sostituisce l'accettazione
in-app.

### Italiano proposto

Titolo: **Linee guida community**

> Invia solo ciò che osservi: niente segnalazioni false, duplicate o improprie.
> Le segnalazioni sono visibili agli altri utenti per circa 60 minuti e possono
> essere segnalate, rimosse o nascoste bloccando la fonte anonima fino al
> prossimo rinnovo giornaliero, per un massimo di 24 ore. Non sostituiscono i
> canali ufficiali.

Accettazione: **Accetto.**

### Furlan proposto, da approvare linguisticamente

Titolo: **Lineis guide community**

> Invie dome ce che tu osservis: no segnalazions falsis, doplis o impropriis.
> Lis segnalazions a son visibilis par chei altris utents par cirche 60 minûts
> e a puedin jessi segnaladis, gjavadis o platadis blocant la font anonime fin
> al prossim rinovament zornalîr, par un massim di 24 oris. No sostituissin i
> canâi uficiâi.

Accettazione proposta: **O aceti.**

Il testo FUR sopra e' una bozza funzionale: non deve essere dichiarato approvato
senza revisione editoriale/linguistica. Nel codice finale vanno mantenuti gli
accenti e la grafia ufficiale di `Friul`/`Friûl` decisa per l'interfaccia.

## 4. Contratto di segnalazione, blocco e sicurezza

### Segnalazione del contenuto

Motivi pubblici ammessi e chiusi:

- `inaccurate`: informazione inesatta;
- `duplicate`: contenuto duplicato;
- `misuse`: uso improprio.

Ogni flag deve identificare in modo azionabile:

- gruppo e report visualizzato oppure l'insieme esatto dei report aggregati;
- fonte anonima o fonti anonime che compongono il contenuto visualizzato;
- motivo;
- segnalante pseudonimo, per idempotenza e limite antiabuso;
- creazione e scadenza.

Il flag non deve esporre al client l'identificatore interno della fonte. Se un
gruppo contiene piu' fonti, l'eventuale strumento privato deve poter ricostruire
senza ambiguita' i report e le fonti compresi nel contenuto indicato. Conservare
soltanto il `group_id` non basta.

### Blocco da parte dell'utente

`Nascondi questa fonte` deve:

- nascondere immediatamente tutti i contenuti attivi della stessa fonte sul
  dispositivo dell'utente;
- restare efficace dopo ricarica/riavvio per la durata dichiarata;
- usare una chiave opaca e ruotata, mai `client_id`, `owner_key` o relativo hash
  interno grezzo;
- non inviare al server la lista locale dei blocchi.

La chiave pubblica della fonte ruota per finestre giornaliere. Il blocco locale
vale quindi fino al rinnovo della chiave e comunque non oltre **24 ore**. Il
copy non deve promettere 24 ore esatte: deve dire "fino al rinnovo giornaliero"
o una formula equivalente.

### Azione automatica e intervento manuale eventuale

- il primo flag nasconde subito il contenuto al segnalante;
- ogni flag crea un record privato temporaneo, con scadenza, senza notifiche;
- nessuna soglia numerica nasconde automaticamente un contenuto a tutti: il
  `client_id` e' pseudonimo e rigenerabile, quindi una soglia sarebbe esposta a
  falsi consensi o censure tramite reinstallazioni;
- retry dello stesso segnalante e' idempotente e non incrementa il conteggio;
- l'autore non puo' flaggare il proprio contenuto;
- il report pubblico viene escluso automaticamente dopo 60 minuti;
- in caso di abuso concreto, lo strumento privato consente a un operatore di
  elencare i flag ancora attivi, ispezionare report e fonte, nascondere o
  ripristinare il contenuto e applicare o rimuovere un blocco temporaneo;
- per la prima beta non esistono SLA di revisione, job pianificati o email di
  riepilogo: l'intervento globale e' una contingenza manuale, non il percorso
  ordinario di ogni flag.

Per la prima beta si raccomanda un blocco fonte unico di **24 ore**. Blocchi
manuali fino a sette giorni sono ammissibili soltanto dopo aver aggiunto durata,
motivazione, scadenza, procedura di riesame e disclosure privacy specifiche.
Nessun blocco deve essere indefinito.

## 5. Retention minima e TTL Firestore

Tutti i documenti devono avere `expires_at_timestamp` valido. La policy TTL deve
essere `ACTIVE` e verificata con read-back; la sola presenza del campo nel codice
non prova la cancellazione cloud.

| Dato/collection | Orizzonte applicativo | Nota |
| --- | ---: | --- |
| `community_reports` | 60 minuti | Contenuto pubblico e fonte interna |
| `community_report_cooldowns` | 45 minuti | Cooldown antiabuso per fonte pseudonima; limita la frequenza ma non e' da solo una garanzia anti-spam |
| `community_report_confirmations` | fino alla scadenza dell'ultimo report attivo del gruppo | Ogni report dura 60 minuti; un nuovo report nello stesso bucket orario estende la conferma, comunque non oltre due ore dall'inizio del bucket |
| `community_report_flags` | 24 ore dal flag | Deve conservare il target azionabile |
| `community_report_moderation` | 24 ore dall'ultimo flag | Stato aggregato e decisione |
| `community_source_blocks` | 24 ore | Nessun blocco indefinito nella prima beta |
| `community_report_rate_limits` | finestra + margine tecnico, massimo 2 ore | Solo contatori minimizzati |
| `community_moderation_digest_state` | 48 ore | Collection di contingenza dormiente: puo' conservare stato sanitizzato solo in una futura attivazione esplicita del digest; non e' prodotta dal flusso ordinario della prima beta |
| `community_reputation` | 365 giorni dall'ultimo invio, convalida o revoca | Riepilogo privato per chiave pseudonima, incluso il totale reale degli invii accettati; scadenza logica applicata anche prima della cancellazione TTL |
| `community_reputation_awards` | 365 giorni dalla convalida o revoca del relativo episodio | Idempotenza e revoca per episodio hashato; nessun `group_id` o `client_id` grezzo |
| blocchi locali sul dispositivo | fino alla rotazione giornaliera, massimo 24 ore | Non trasmessi; pulizia automatica |

Firestore elimina i documenti TTL in modo asincrono. L'informativa deve parlare
di cancellazione programmata alla scadenza e non promettere un istante fisico
esatto che il servizio non garantisce.

Il digest, il relativo evento `community_moderation_digest_ready` e il trasporto
email restano codice di contingenza dormiente. Nessun job, scheduler, evento di
riepilogo o email di moderazione e' richiesto o attivo nel modello della prima
beta. La policy TTL della collection tecnica puo' restare `ACTIVE` anche quando
la collection e' vuota: non dimostra un trattamento in corso. Una futura
attivazione richiedera' una decisione separata, un nuovo audit privacy/Data
Safety e la verifica di schema, retention dei log e retention del canale email.

Gate bloccante prima della distribuzione:

1. policy TTL `ACTIVE` per ogni collection group della tabella;
2. zero documenti correnti privi di `expires_at_timestamp` o con tipo errato;
3. evidenza storica LIVE aggregata con almeno un campione valido per ogni
   collection, distinta dal read-back corrente;
4. nessun ID privato grezzo, `client_id`, identificatore di installazione/fonte
   o GPS nelle risposte pubbliche, analytics o messaggi di errore pubblici; le
   chiavi/hash server-side restano pseudonime e scoped;
5. test di scadenza e nuova acquisizione della stessa fonte dopo il blocco.

Per il rango, `hide` e `remove` revocano in modo idempotente l'assegnazione del
gruppo. Un successivo `restore` rende il contenuto nuovamente non verificato ma
non ripristina automaticamente il punto: un recupero manuale richiederebbe una
procedura amministrativa separata e auditabile.

Il read-back dedicato e' `scripts/audit-firestore-community-ttl.ps1`; richiede
PowerShell 7, un `-OutputPath` esplicito e produce soltanto evidenza aggregata.
Valida sempre l'identita' LIVE, tutte le dieci policy e ogni documento presente.
Una collection vuota e' conforme nel read-back fresco: l'assenza non nasconde
documenti invalidi, ma non vale come prova che lo writer abbia mai prodotto una
scadenza corretta.

Per questo la build protetta richiede separatamente il record piu' recente in
`release-history/firestore-community-ttl`. Il record deve provenire da un audit
LIVE verde con copertura non zero per tutte le dieci collection, avere al massimo
30 giorni, usare l'identita' esatta e conservare il SHA-256 deterministico dei
sorgenti writer, dei due producer LIVE, dell'audit, del recorder e del
validator. La storia Git deve mostrare una sola aggiunta e nessuna modifica,
rinomina o cancellazione. Il build rifiuta anche file non tracciati o sporchi.

La registrazione e' un'operazione esplicita separata dalla build e non assume
la presenza di dati reali. E' una prova TTL controllata e non attiva job,
scheduler o email. Dal commit backend tagged, avviare prima
`tools/smoke_community_moderation_live.py --apply --hold-seconds 120`, che
produce quattro campioni privati. Dopo il suo `evidence_ready`, in un secondo
terminale avviare il seed delle sei collection normalmente vuote, incluse le
due del rango:

```powershell
# Primo terminale: preview, poi smoke applicato.
Set-Location .\backend
$env:COMMUNITY_STORAGE = "firestore"
$env:FIREBASE_PROJECT_ID = "meteo-friul"
.\venv\Scripts\python.exe tools\smoke_community_moderation_live.py
.\venv\Scripts\python.exe tools\smoke_community_moderation_live.py `
  --apply --hold-seconds 120
```

Nel secondo terminale:

```powershell
Set-Location .\backend
$env:COMMUNITY_STORAGE = "firestore"
$env:FIREBASE_PROJECT_ID = "meteo-friul"
.\venv\Scripts\python.exe tools\seed_community_ttl_evidence_live.py `
  --api-base "https://<TAG>---meteofriul-api-<HASH>.a.run.app/api"
.\venv\Scripts\python.exe tools\seed_community_ttl_evidence_live.py `
  --api-base "https://<TAG>---meteofriul-api-<HASH>.a.run.app/api" `
  --apply --hold-seconds 120
Set-Location ..
```

Il seed e' read-only senza `--apply`; il report e' gia' scaduto e anche
`moderation_hidden`. Crea atomicamente documenti con marker univoco, verifica
l'assenza dal servizio pubblico locale e dalla API tagged prima, durante il
hold e dopo, e pulisce in transazione soltanto documenti ancora marker-owned.
Collisione iniziale, race, collisione pubblica tardiva, perdita di ownership o
errore di cleanup falliscono chiusi. Il hold non puo' superare 120 secondi e
l'output contiene soltanto conteggi/booleani aggregati, mai ID o dati privati.

Solo dopo l'evento `evidence_ready` di entrambi i tool, mentre tutti i dieci
campioni esistono e prima della pulizia, eseguire in un terzo terminale:

```powershell
$GcloudPath = (
  Resolve-Path (
    "$env:LOCALAPPDATA\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.ps1"
  )
).Path
pwsh -NoProfile -File .\scripts\record-firestore-community-ttl-evidence.ps1 `
  -RecordLiveEvidence `
  -SourceCommit "<COMMIT_BACKEND_40_DELLA_REVISIONE_LIVE>" `
  -OutputPath .\release-history\firestore-community-ttl\<YYYYMMDDTHHMMSSfffZ>-community-ttl.evidence.json `
  -GcloudPath $GcloudPath
```

Su Windows usare il wrapper PowerShell ufficiale `gcloud.ps1`, non
`gcloud.cmd`: il passaggio del payload JSON attraverso `cmd.exe` rimuove le
virgolette interne e fa fallire chiuso la scrittura dell'attestazione. Il
percorso esplicito mantiene inoltre l'identita' del binario verificabile e
viene inoltrato anche all'audit e al read-back.

Attendere poi l'esito finale verde e la pulizia di entrambi i tool. Non
committare il record se uno dei due fallisce o se la pulizia non e' verificata.
Un hard stop lascia soltanto documenti con TTL limitato; non cancellare mai un
documento che non conserva il marker della stessa esecuzione.

Il record ammette solo aggregati: policy, conteggi, minimi/massimi osservati e
identita' cloud. Nomi documento, ID, chiavi pseudonime, coordinate e contenuti
UGC vengono scartati. Lo schema JSON e' esatto a ogni livello: proprieta' extra,
incluse varianti di ID o GPS, invalidano il record. Revisionare, testare e
committare il nuovo file; non
riscrivere mai un record precedente. Una modifica a uno dei sorgenti writer
invalida automaticamente il digest e impone una nuova registrazione LIVE. Gli
snapshot fixture restano utili soltanto ai contract test e vengono rifiutati sia
dal recorder sia dalla build. Il recorder operativo non espone un parametro
fixture: genera nonce e hash del core aggregato, scrive un evento a schema
chiuso nel log Cloud Logging dedicato e ne pretende il read-back esatto prima
di creare il ledger. La build ripete un read-back LIVE dello stesso nonce/hash;
una fixture locale che si autodichiara LIVE rimane quindi bloccata.

`SourceCommit` e' il commit completo della revisione backend LIVE che ha
prodotto i campioni. Il recorder richiede che i byte writer locali coincidano
con i blob Git di quel commit. Alla build, il gate non si fida del solo campo:
ricalcola il digest dai blob del `BackendCommit` realmente risolto dalla
revisione tagged, senza checkout, e lo confronta col record. `SourceCommit`
deve essere un antenato del `BackendCommit`: sono ammessi commit discendenti con
writer invariati, non discendenti che li cambiano. Un HEAD pulito con writer
diversi dal backend autorevole resta quindi bloccato prima di Vite, Gradle,
prenotazione versione o creazione AAB.

Il digest copre anche `audit-firestore-community-ttl.ps1`, il relativo modulo,
il recorder e il modulo evidence. Il verifier Play e' escluso deliberatamente
per evitare un auto-hash ricorsivo, ma e' coperto dai contract test. Il confronto
locale usa i byte effettivi contro i blob Git, non `git status`: anche
`assume-unchanged` e `skip-worktree` non possono nascondere un tamper. La prova
remota puo' esistere soltanto dopo il successivo passaggio LIVE autenticato;
prima di quel passaggio il gate resta fail-closed e non si genera alcun AAB.

Il gate push `FIRESTORE_PUSH_TTL_GATE.md` ha un perimetro diverso e non deve
essere usato come prova della retention community.

## 6. Privacy e Data Safety

L'audit puntuale e l'handoff per il repository landing separato sono in
`COMMUNITY_PRIVACY_DATA_SAFETY_HANDOFF.md`. Al 24 agosto 2026 le pagine IT/FUR
pubbliche descrivono ancora il contratto precedente (`IP + ID installazione`).
Le sorgenti locali contengono una bozza aggiornata, ma non ancora pubblicata e
con revisione linguistica FUR ancora bloccante; il gate privacy resta quindi
rosso.

Le informative IT/FUR devono aggiungere in modo coerente:

- categoria del fenomeno, Comune/zona canonica, orario e scadenza;
- uso temporaneo della posizione precisa per verificare la zona; nessuna
  cronologia GPS pubblicata o conservata con il report;
- `client_id` casuale conservato localmente, trasmesso nelle sole mutazioni e
  trasformato dal backend in chiavi/hash pseudonimi scoped per cooldown,
  deduplicazione, flag e prevenzione abusi;
- collegamento temporaneo tra report della stessa fonte per consentire il
  blocco, senza nome, account o profilo pubblico;
- tempi di retention dei dati prodotti dal flusso beta e cancellazione TTL
  asincrona; la collection digest dormiente non va presentata come trattamento
  attivo;
- Google Cloud/Firebase come fornitore che tratta i dati per conto del titolare;
- assenza di vendita, pubblicita' o profilazione;
- contatto `info@meteofriul.it` per privacy, segnalazioni di abuso e richiesta di
  cancellazione, quando il dato sia ancora identificabile e presente.

La dichiarazione Data Safety deve essere riesaminata almeno per:

| Tipo Google | Uso Meteo Friul | Indicazione prudenziale |
| --- | --- | --- |
| Posizione precisa | Verifica in tempo reale del Comune | Raccolta opzionale ed effimera, se resta solo in memoria |
| Posizione approssimativa | Comune/zona pubblicato con il report | Raccolta opzionale, funzionalita' app |
| Altri contenuti generati dagli utenti | Tipo di fenomeno condiviso | Raccolta opzionale, funzionalita' app |
| Altre azioni | Conferme, smentite e flag | Raccolta opzionale, funzionalita' e sicurezza |
| ID dispositivo o altri ID | ID installazione pseudonimo/hash | Raccolta opzionale, funzionalita' e prevenzione abusi |

I dati pseudonimi vanno comunque dichiarati. L'elaborazione locale dei blocchi
non e' raccolta finche' non lascia il dispositivo. Il cloud provider che tratta
per conto dello sviluppatore puo' rientrare nell'eccezione service provider, ma
la raccolta resta da dichiarare. La visibilita' pubblica del report puo' rientrare
nell'azione iniziata dall'utente solo se l'interfaccia dice chiaramente, prima
dell'invio, che il fenomeno sara' visibile agli altri utenti.

Questa tabella e' una base tecnica da riportare fedelmente in Play Console; non
sostituisce la decisione finale del titolare ne' una consulenza legale.

## 7. File da aggiornare prima dell'approvazione

### Contratto runtime

- `contracts/runtime-api/v1/manifest.json`: aggiungere
  `POST /api/community/reports/{groupId}/flags`.
- `contracts/runtime-api/v1/live/README.md`: descrivere termini v2, endpoint,
  motivi, hide locale, intervento manuale eventuale, App Check e retention.
- `contracts/runtime-api/v1/live/community-created.json`: aggiungere la chiave
  pubblica opaca `sourceKey`.
- `contracts/runtime-api/v1/live/community-confirmed.json`: aggiungere
  `sourceKey` e `sourceKeys` coerenti.
- nuovo `contracts/runtime-api/v1/live/community-flagged.json`: congelare esito
  idempotente, hide locale/globale, conteggio e retention.

### Documentazione corrente

- `README.md`: dichiarare Territorio come UGC limitato, strutturato ed
  effimero, non come sola lettura community.
- `backend/README.md`: documentare flag, moderazione, blocchi fonte, collezioni,
  TTL, App Check e procedura operatore.
- `UI3_RUNTIME_DATA_INVENTORY.md`: aggiungere rischio UGC, retention e gate
  operativo, oltre al solo controllo dello storage Firestore.
- `ANDROID_PILOT_RUNBOOK.md`: aggiungere questo gate tra i prerequisiti
  bloccanti pre-AAB.
- `frontend/android/README-PILOT.md`: rimandare a questo documento senza
  duplicarne regole e soglie.
- `../archive/ui3-migration/AUDIT_CHECKLIST.md`: registrare l'esito come nuova sezione; non riscrivere le
  sezioni storiche gia' concluse.
- privacy pubblica IT/FUR: aggiornare nel repository della landing, non in
  questo workspace se resta separato; applicare senza omissioni l'handoff
  `COMMUNITY_PRIVACY_DATA_SAFETY_HANDOFF.md`.
- eventuali pagine pubbliche `community` IT/FUR: devono riportare esattamente la
  versione v2 approvata e indicare il contatto di moderazione; non sono un
  sostituto del testo mostrato prima dell'invio.

## 8. Test e prove bloccanti

### Contratti e backend

- fixture `community-flagged.json` identica tra API e client;
- termini mancanti o versione diversa: `400`;
- motivo sconosciuto o campo extra: rifiuto;
- App Check assente/non valido: rifiuto di tutte le mutazioni, flag compreso;
- flag idempotente e self-flag rifiutato;
- piu' fonti flagganti non producono hide globale automatico; hide, restore e
  remove globali richiedono sempre una decisione operatore;
- gruppo con piu' report/fonti: target moderabile senza ambiguita';
- report gia' scaduto: nessun flag orfano non azionabile;
- blocco fonte attivo: creazione rifiutata; scadenza: creazione nuovamente
  ammessa;
- fallimento Firestore: `503` fail-closed, nessun successo solo in memoria.

### Frontend

- consenso non preselezionato e richiesto ad ogni invio;
- IT/FUR corrispondenti alla stessa versione v2;
- `Segnala contenuto` e `Nascondi questa fonte` distinti e accessibili da mappa
  ed elenco;
- flag nasconde subito il contenuto al segnalante;
- blocco nasconde tutti i contenuti della fonte, persiste dopo reload e scade;
- chiavi locali corrotte/scadute vengono eliminate senza mostrare contenuti
  bloccati per errore;
- visual QA IT/FUR, chiaro/scuro, larghezza mobile e navigazione tastiera/screen
  reader del dialogo.

### Operazioni e revisione Play

- verificare che l'API esponga soltanto gli otto fenomeni chiusi, il Comune
  canonico, l'orario, la scadenza e la `sourceKey` opaca a rotazione;
- verificare durata pubblica di 60 minuti, esclusione immediata alla scadenza e
  TTL cloud `ACTIVE` per tutte le collection del contratto, compresa quella
  dormiente se resta nello schema;
- verificare che il `client_id` casuale sia gestito localmente e trasmesso solo
  nelle mutazioni, mentre il backend conserva chiavi/hash pseudonimi scoped e
  non espone identificatori interni;
- verificare che flag e blocco locale siano distinti e che il flag nasconda
  subito il contenuto al segnalante;
- mantenere disponibile il comando privato per un intervento globale eventuale;
  non e' richiesta una revisione ordinaria di ogni flag;
- non creare per la prima beta job, scheduler, service account, policy
  Monitoring o canali email dedicati al digest di moderazione;
- il digest dormiente non e' un gate AAB. Qualunque attivazione futura richiede
  una nuova decisione, prove end to end e aggiornamento privacy/Data Safety;
- note revisore: percorso `Territorio -> segnalazione -> Segnala contenuto /
  Nascondi questa fonte`, nessun login richiesto;
- prova video/screenshot del percorso anche quando non esistono report reali,
  senza introdurre una modalita' QA nascosta nella build pubblica;
- questionario contenuti/target audience e Data Safety coerenti con UGC e
  privacy pubblica.

## 9. Criterio finale di approvazione

Il gate diventa verde soltanto quando sono vere tutte le condizioni:

1. copy IT approvato e copy FUR revisionato;
2. contratto e fixture aggiornati;
3. reporting e blocking distinti e funzionanti;
4. ogni flag resta collegato a un target moderabile;
5. lo strumento privato consente un intervento globale eventuale, senza SLA o
   circuito automatico promesso;
6. TTL cloud attivi e dati correnti conformi;
7. privacy IT/FUR e Data Safety coerenti;
8. test backend/frontend/contratto e smoke operativo verdi.

Fino ad allora il codice puo' essere provato localmente, ma questo documento non
autorizza da solo Play Console, AAB o attivazione pubblica di Territorio.

Prima di qualsiasi build Play, `build-play-aab.ps1` verifica in sola lettura il
contratto effimero dell'API: otto tipi chiusi, 215 Comuni canonici, durata di
60 minuti, posizione pubblica zonale, fonte pseudonima e assenza di
identificatori interni o contenuti liberi nelle risposte pubbliche. Restano
separati i gate TTL e privacy.
La build non deve richiedere `audit-community-moderation-runtime.ps1` e l'assenza
di job, scheduler, service account, email o policy Monitoring del digest non
blocca la prima beta.
