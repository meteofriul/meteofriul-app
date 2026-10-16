# Meteo Friul - Runbook cutover web UI3

Data baseline: 2026-08-11
Stato: cutover web UI3 eseguito, smoke test superato

## Obiettivo

Pubblicare sul canale Firebase Hosting live lo stesso pacchetto gia'
collaudato nel canale `ui3-beta`, senza ricostruire il frontend e senza
spostare il traffico Cloud Run non taggato.

## Baseline verificata al cutover - 11 agosto 2026, 19:26 circa

| Elemento | Valore |
| --- | --- |
| Repository | `meteofriul/meteofriul-app` |
| Commit del pacchetto | `cfe9cf2d79e0969834c6f62d09304adc6b3f0716` |
| CI | run `31514929259`, completata con esito positivo |
| Preview Hosting | `https://meteo-friul--ui3-beta-yamdts9p.web.app` |
| Versione preview | `4da1ae23ee87b142` |
| Revisione API preview | `meteofriul-api-ui3-clean-1530ad0` |
| Tag API preview | `ui3-clean-1530ad0` |
| Live Hosting corrente | `https://meteo-friul.web.app` |
| Versione live corrente | `4da1ae23ee87b142` |
| Tag API live corrente | `ui3-clean-1530ad0` |
| Backup live | `https://meteo-friul--pre-ui3-vmis6dza.web.app` |
| Traffico Cloud Run non taggato | 100% `meteofriul-api-00068-n7k` |

Questa tabella e' una fotografia storica immutabile dello stato al momento del
cutover. Le variazioni successive devono essere registrate in sezioni separate
e datate, senza sostituire i valori della baseline.

Il canale `pre-ui3` e' temporaneo. L'11 agosto e' stato esteso fino al 26
agosto 2026 alle 20:58 CEST senza ridistribuirne il contenuto: conserva la
versione `74767fe006a3d7b5`. Non va cancellato finche' la verifica formale di
stabilizzazione non e' conclusa e il proprietario non approva la rimozione.

L'11 agosto il workflow legacy `Update webcam JSON` ha ridistribuito il
frontend precedente e ha ripinnato il rewrite live all'API UI3. Il workflow e'
stato disattivato manualmente prima del cutover. Il backup `pre-ui3` non e'
stato sovrascritto: conserva l'ultima combinazione legacy stabile, incluso il
tag API `ui3-71f9d49`, ed e' quindi il rollback corretto.

## Gate preflight superato

L'11 agosto 2026 sono stati verificati tutti i punti:

1. `main` e' pulito e sincronizzato con `origin/main`.
2. La CI dell'ultimo commit e' verde.
3. Il canale `ui3-beta` mostra il titolo `Meteo Friul UI 3.0.0`.
4. Home, Bollettino, Territorio, Eventi, Scopri, Almanacco e Impostazioni
   passano in IT/light e FUR/dark senza errori fatali o overflow.
5. `/api/healthz` risponde `status: ok` dal dominio preview.
6. Meteo, Eventi, webcam, Firestore e radar rispondono dal dominio preview.
7. La revisione API preview non contiene segreti legacy.
8. Il comportamento allerte e' accettato esplicitamente: se manca uno
   snapshot regionale, l'API restituisce `official_alerts_unavailable`, non
   cancella un'allerta attiva precedente ancora valida e non crea uno stato
   verde.
9. Il canale `pre-ui3` contiene l'ultima versione legacy stabile precedente
   alla ridistribuzione automatica del workflow webcam.

## Cutover

Non eseguire un nuovo build. Clonare la versione collaudata:

```powershell
npx firebase-tools hosting:clone meteo-friul:ui3-beta meteo-friul:live --project meteo-friul --non-interactive
```

Il comando sostituisce insieme file Hosting e rewrite API con la versione gia'
verificata. Non modificare contestualmente il traffico Cloud Run non taggato.

Cutover eseguito l'11 agosto 2026 alle 19:26 circa tramite clone del canale
`ui3-beta`. `live` e `ui3-beta` puntano alla stessa versione Hosting e allo
stesso tag API.

## Smoke test immediato

Entro dieci minuti dal cutover verificare:

1. `https://meteo-friul.web.app/api/healthz`;
2. Home e cambio localita;
3. Bollettino OSMER e dati locali;
4. Eventi e apertura di una card;
5. Territorio, webcam e lettura segnalazioni;
6. Scopri e Almanacco;
7. lingua FUR e tema scuro;
8. assenza di errori 5xx ripetuti.

Esito: superato. Sono state verificate tutte le sette sezioni in IT/light e
FUR/dark, anche su viewport mobile. Il controllo ha incluso ricerca localita',
apertura card Eventi, mappa Territorio, webcam, immagini, errori console e tutte
le route API runtime. Non sono stati rilevati errori, immagini interrotte o
overflow della pagina.

## Stato dopo l'hotfix - 11 agosto 2026, 21:35 circa

L'11 agosto, durante il controllo successivo al cutover, la revisione
`meteofriul-api-ui3-clean-1530ad0` ha saturato le due istanze disponibili:
letture Firestore delle allerte senza limite e richieste pubbliche forzate
occupavano i worker sincroni fino al timeout Cloud Run di 300 secondi. Anche
`/api/healthz`, allora sincrono, restava in coda.

La correzione e' stata pubblicata nella revisione a traffico zero
`meteofriul-api-ui3-hotfix-643096d` e collaudata prima di spostare il solo tag
`ui3-clean-1530ad0`. Il pacchetto Hosting e il traffico Cloud Run non taggato
non sono stati modificati. La revisione usa concorrenza 16, massimo 5 istanze,
health check asincrono, timeout Firestore di 5 secondi senza retry e
accorpamento delle letture concorrenti. Il refresh pubblico non avvia piu'
sincronizzazioni o scritture delle allerte ufficiali.

| Elemento | Stato dopo l'hotfix |
| --- | --- |
| Versione Hosting live | `4da1ae23ee87b142`, invariata |
| Tag API usato dal rewrite Hosting | `ui3-clean-1530ad0`, invariato |
| Revisione risolta dal tag | `meteofriul-api-ui3-hotfix-643096d` |
| Revisione risolta dal tag al cutover | `meteofriul-api-ui3-clean-1530ad0` |
| Traffico Cloud Run non taggato | 100% `meteofriul-api-00068-n7k`, invariato |

**Attenzione al nome del tag:** `ui3-clean-1530ad0` e' un identificatore
storico e, dopo le 21:35 circa, non corrisponde piu' al nome della revisione
che serve. Nei controlli Cloud Run occorre verificare sempre la revisione
risolta dal tag e non dedurla dal nome. Il tag non va rinominato durante la
stabilizzazione; dopo la verifica formale si valutera' un identificatore
allineato, con aggiornamento controllato del rewrite e nuovo smoke test.

Prova comparativa sulla revisione isolata:

- prima del fix completo: 12 richieste forzate, 10 risposte `200` e 2 timeout
  oltre 45 secondi;
- dopo il fix completo: 12 risposte `200`, massimo 4,70 secondi;
- health durante lo stesso carico: 12 risposte `200`, media 0,124 secondi;
- smoke live attraverso Hosting: health, allerte, bootstrap, radar, Eventi,
  webcam e segnalazioni tutte `200`, senza errori console.

## Rollback

Eseguire il rollback se il frontend non si avvia, una route essenziale produce
errori ripetuti, i dati vengono attribuiti a una localita sbagliata o Firestore
non e' raggiungibile:

```powershell
npx firebase-tools hosting:clone meteo-friul:pre-ui3 meteo-friul:live --project meteo-friul --non-interactive
```

Dopo il comando ripetere almeno Home, Bollettino, Eventi e `/api/healthz`.
Non cancellare i canali `ui3-beta` e `pre-ui3` finche' il live UI3 non e'
stabile.

## Finestra di stabilizzazione

La finestra di osservazione intensiva va dall'11 al 17 agosto 2026 compreso.
Il 18 agosto si esegue una verifica formale di CI, route essenziali, Firestore,
fonti meteo, Eventi, radar, webcam e assenza di deploy legacy inattesi.

Il rollback `pre-ui3` resta disponibile fino al 26 agosto come riserva tecnica
successiva alla verifica. La sua eliminazione richiede una decisione
esplicita: non deve sparire per una scadenza dimenticata.

L'inventario completo e lo stato delle automazioni sono registrati in
`PRODUCTION_AUTOMATION_AUDIT.md`.

## Protezione del branch durante la stabilizzazione

La protezione server-side di `main` e' stata richiesta subito dopo il cutover,
ma GitHub la rifiuta sulla repository privata con il piano corrente: richiede
GitHub Pro. La repository non va resa pubblica come soluzione alternativa.

Nel frattempo e' attivo il guardrail locale versionato `.githooks/pre-push`,
installabile con `scripts/install-git-guardrails.ps1`. Blocca i push diretti a
`main`; resta una misura compensativa e non sostituisce la futura protezione
remota con pull request e CI obbligatorie.

## Dopo la stabilizzazione

- mantenere la revisione precedente per la finestra di rollback concordata;
- abilitare GitHub Pro e sostituire il guardrail locale con la protezione
  server-side di `main`;
- valutare un nuovo tag Cloud Run coerente con la revisione servita, aggiornare
  il rewrite Hosting in modo controllato, ripetere lo smoke test e ritirare il
  vecchio alias solo dopo aver verificato che non abbia altri consumatori;
- separare i workflow di deploy API e Hosting;
- migrare l'aggiornamento webcam nel nuovo repository senza deploy implicito
  del frontend;
- decidere e implementare il canale di ingestione delle allerte FVG;
- monitorare il live durante la finestra di stabilizzazione;
- generare il wrapper Android soltanto dopo il completamento del web e una
  conferma esplicita del proprietario dell'app; permessi e push reale restano
  fasi successive.

## Gate corrente per gli aggiornamenti successivi

La baseline Firebase sopra resta una fotografia storica. Per le distribuzioni
Cloudflare e Android successive e' obbligatorio usare
`scripts/deploy-cloudflare-app.ps1` e
`scripts/build-play-aab.ps1` indicando quattro identita' distinte:

1. URL API Cloud Run tagged incorporato nel pacchetto;
2. URL del servizio Community ufficiale separato incorporato nel pacchetto;
3. revisione Cloud Run che il tag deve risolvere realmente;
4. commit backend identificato nel nome della revisione.

Gli script interrogano Cloud Run prima e dopo la build, verificano account,
servizio, URL risolto, revisione `Ready`, digest immagine e `/api/healthz`, e
bloccano il rilascio in caso di discrepanza. Il Web ripete il controllo dopo il
deploy; l'AAB registra anche hash, firma e versione. Worktree sporchi, commit
non inviati al remoto, `versionCode` non incrementati e riuso di `versionCode`
o `versionName` sono bloccanti. Ogni candidato AAB e' accompagnato dalla
prenotazione e dal manifesto immutabili in `release-history/android-play` e
archiviato in `release-artifacts/android-play`; nessun output versionato viene
sovrascritto. I record vanno committati e pushati, con CI verde, prima del
caricamento manuale in Play Console. Firebase App Distribution e il relativo
script APK restano soltanto nello storico congelato. La CI parte anche sui push
dei branch `codex/**`, oltre che su `main` e sulle pull request, così il commit
candidato ha sempre una run identificabile.

Un tag esistente non costituisce prova della versione servita. Prima di
spostarlo si collauda la nuova revisione a traffico zero; dopo lo spostamento si
ripete il gate usando la nuova revisione attesa. In caso di errore si conserva
il pacchetto precedente, si registra il codice fail-closed mostrato dallo
script e si corregge l'incoerenza senza forzare o saltare il controllo.
