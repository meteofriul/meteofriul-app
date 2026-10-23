# 0.1.15 — preparazione del test interno personale

> Aggiornamento 21 ottobre: questa pagina conserva la preparazione storica.
> Community è stata attivata e ICON verificato; gli sponsor sono disattivati
> per ordine del proprietario, con pannello e allineamento dati sospesi.
> Vedere il [preflight corrente](ANDROID_0.1.15_BUILD_20261021.md).

20 ottobre 2026. **Preparata localmente, non generata e non caricata.**
Ramo `codex/release-0.1.15`, da main `5cbcd35c` già pubblicato e con CI verde.
La CI di quella base non certifica le modifiche locali di preparazione.
Candidato applicativo e versione: `f26ea2da`; il manifesto conserva lo SHA completo.

## Contenuto e identità

- Ufficiale `com.meteofriul.app`, versione **0.1.15**, codice proposto **300032**.
  Non è una riserva: ricontrollare Play prima della build. Ultimo massimo
  osservato il 20 ottobre: 300031; nessuna nuova lettura Console in questo giro.
- Canale interno riservato al proprietario: una lista/un account già verificati,
  riattivazione confermata dal proprietario. Ricontrollare prima dell'upload.
- Inclusi i testi IT/FUR, pill, Indietro Android, conferma No/Sì e ricevuta
  Community, «Inviata da», refresh FVG, catalogo Eventi reale, compatibilità
  tolleranze, temi e selezione previsioni, correzioni Web e dicitura «in FVG».
- Nessun marchio, package, simulazione o blocco dei servizi proprio della TEST.
- Frontend/package-lock/Android allineati a 0.1.15. Aggiornata l'attesa del test
  di versione; le verifiche di parità e i casi negativi restano invariati.
- Attestazioni del deploy FVG integrate localmente dai due commit già verificati,
  inclusa la verifica delle Cloud Build con più immagini. Nessun nuovo deploy.

Firma ufficiale verificata contro la release accettata; Firebase ufficiale e
Carto predisposti in file ignorati nel worktree. La chiave privata originale
non è stata copiata. Nessun segreto o override TEST è entrato nel commit.

## Backend: ciò che serve davvero

| Componente | Decisione per 0.1.15 |
| --- | --- |
| **Community** | **Prerequisito per il test completo.** Il client invia già `X-Meteo-Community-Rules: community-reports-v3`; il servizio attuale non lo ammette e il preflight pubblico risponde 400. Distribuire il backend compatibile v2/v3 mantenendo i vecchi client, verificare CORS, App Check, TTL e privacy dei log. Durante il primo passaggio tenere v3 writes off; per collaudare gli invii della nuova app va poi autorizzata e verificata l'abilitazione v3. Un deploy con flag off da solo non completa il lavoro. Nessun fallback silenzioso alle vecchie regole. |
| **Eventi** | Lettura attuale compatibile: Pordenone restituisce 100 elementi su 321 nel raggio richiesto. Sei moduli approvati di API/worker restano da allineare per le correzioni di date, orari e incertezza di apertura. Il catalogo è `degraded`: Spazzapan e Cinema Muto stale, altre fonti parziali. Revisione fonti separata: non promettere che aggiornare i sei moduli risolva tutti quei problemi. Non impedisce un'anteprima dichiarata, impedisce di dichiarare completo/fresco l'intero catalogo. |
| **FCM** | Correzione operativa indipendente dall'AAB: estendere la distinzione SenderIdMismatch/Unregistered già presente nel job serale agli altri runtime interessati (API, mattino, avvisi locali/nazionali e FVG). Non cambiare destinatari, deduplicazione o riattivare token; non applicare automaticamente ad altri job la politica serale sui target ritirati. |
| **ICON** | Correzione produttore già distribuita. Attendere la corsa del 21 ottobre alle 08:00 italiane e la verifica di nuova pubblicazione, 215 lettori storici e sidecar. Nessun altro deploy giustificato dal controllo attuale. Gli invii del nuovo consumatore tolleranze restano una fase backend distinta, non si attivano costruendo l'AAB. |
| **Sponsor** | Aggiornamento opzionale per questo test. Il nuovo lettore accetta il catalogo precedente senza `visibleFields`: regressioni passate. La selezione dei campi richiede il suo rollout separato; non spostare l'app sul vecchio tag sponsor che contiene retention esclusa. |
| **CAMS, reader meteo, API e serale** | Nessun nuovo deploy necessario per la sola AAB. CAMS ha pubblicato aria/pollini nuovi; compatibilità HTTP e attestazioni API/serale già verificate. Ripetere il preflight live subito prima della build autorizzata. |

I digest live confermano i runtime del precedente audit. Le undici comparazioni
selezionate riconfermano gli stessi sorgenti di main: nessuna deduzione basata
soltanto sul nome di un tag. Il catalogo Eventi è pubblico; non sono state inviate
segnalazioni Community né richieste di mutazione ai servizi applicativi.

## Allerta FVG delle 22:00: dati riusciti, invio parziale

Esecuzione ordinaria `meteofriul-official-alert-sync-jdgwd`, avviata dallo
scheduler con il digest candidato `7364eca3…3368`. Allerta 30/2026 acquisita e
salvata alle 20:00:18 UTC, schema v3: A/B arancione, C gialla, D verde,
dalle 00:00 del 21 alle 06:00 del 22 ottobre. API Play, API predefinita,
Firestore e fonti pubbliche concordano. Il parser è ripristinato.

Il job riporta **45 tentativi, 44 inviati, 1 fallito**, zero invii non confermati:
esito `partial`, quindi esecuzione non verde. La lettura limitata a firma
dell'allerta e stesso istante di claim conferma i 45 esiti. Non usare il totale
di 48 ricevute della finestra generale: comprende altri invii automatici.
Il fallimento è `failed_invalid_token / fcm_token_invalid`. Il runtime precedente
confonde Unregistered e SenderIdMismatch: non è possibile attribuire il caso
all'una o all'altra causa dalle prove conservate. Nessun reinvio o ripristino
manuale del destinatario.

Il proprietario ha confermato in chat l'arrivo della notifica sul proprio
telefono. È una conferma umana di ricezione; package/versione e interfaccia
non sono stati riletti e non certifica la futura 0.1.15. I 44 successi sono
accettazioni FCM, non 44 prove di visualizzazione. Il controllo delle 22:15
rimane programmato; l'esito parziale è registrato, non trasformato in successo.

## Controlli e limiti

- 9 guardie release, 123 test frontend in 9 file, 35 regressioni backend: PASS.
  Vitest 4.1.12 con config loader native; Capacitor 8.5.1. Riutilizzate dipendenze
  esistenti corrispondenti al lockfile, senza installazioni.
- Contratti R8 e registro immutabile Play: PASS, 44 record, nessuna riserva nuova.
- Contratti statici del builder protetto: PASS. Esecuzione Gradle del contratto
  **NON VERIFICATA**: nel checkout pulito mancano file Cordova generati. Il primo
  tentativo si è fermato in configurazione, poi è stata eseguita esplicitamente
  la sola parte statica. Nessuna AAB e nessuna compilazione Android certificata.
- Configurazione della versione verificata byte per byte; nessuna modifica
  nativa oltre ai numeri di versione. R8/resource shrinking ottimizzato resta
  attivo, senza nuove keep rule o aggiornamenti della toolchain.
- TEST minificata su Galaxy Android 14 e Web Brave: prove precedenti pertinenti,
  non sostituiscono l'ufficiale con firma Play, App Check, push e background.
- Edge-to-edge/inset: runtime nuova ufficiale Android 15/16, gesti/tre tasti,
  temi e tastiera da verificare. API deprecate: guardie passate; avvisi delle
  dipendenze/Play non dichiarati risolti. Orientamento: telefoni portrait,
  tablet/multi-window adattivi; matrice runtime ancora aperta. R8: mapping e
  prova sul pacchetto ufficiale nuovo ancora assenti.

## Ordine del passaggio

1. Chiudere il controllo ICON e preparare il rollout Community compatibile;
   affrontare separatamente Eventi e FCM come sopra. Le azioni cloud richiedono
   una nuova autorizzazione: nessuna eseguita in questa preparazione.
2. Consolidare il ramo release e le attestazioni con PR/push e CI quando
   autorizzati. Main non è stato cambiato; queste modifiche sono solo locali.
3. Prima della build: confermare massimo Play, configurazioni e digest API live,
   chiudere o dichiarare i limiti del collaudo. Generare solo con il builder
   protetto, dopo autorizzazione esplicita; non fare prima android:sync manuale.
4. Upload interno separatamente autorizzato, solo lista personale. Verificare
   aggiornamento senza perdita dati, App Check, posizione, Community, notifiche,
   mappe, meteo FVG/nazionale, Eventi, temi, lingua e ritorno dal background.
5. Preparare Web dalla stessa 0.1.15; nessun deploy automatico. Pubblicazione
   coordinata e Safari/iPhone/PWA restano da verificare prima di dichiarare la
   parità pubblica, con gli eventuali intervalli esplicitamente concordati.

Note proposte per Play: «Previsioni più leggibili nei temi chiaro e scuro;
testi italiani e friulani migliorati; navigazione e aggiornamento meteo più
affidabili; schermate Community riordinate.» Le note non dichiarano attive
funzioni backend prima del loro collaudo.

Il [manifesto di preparazione](../../release-history/android-preparation/0.1.15-20261020/preparation.json)
non è un manifesto AAB: non esistono bundle, mapping o SHA di una nuova AAB.
[Controlli ed evidenze](../../release-history/android-preparation/0.1.15-20261020/SHA256SUMS.txt).
Nessuna AAB, installazione, push Git, deploy, esecuzione manuale, notifica manuale
o emulatore effettuati. I tool archiviati vanno ripristinati nella `.tmp` canonica
con il loro helper, non eseguiti dalla cartella del manifesto.
