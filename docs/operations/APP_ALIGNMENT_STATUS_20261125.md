# Stato di repository e app — 25 novembre 2026

## Risposta sintetica

Il `main` remoto è aggiornato e l'ultima CI sul **codice** è verde. Il
checkout canonico locale è pulito, ma resta sul ramo Mercati in pausa e non
coincide con `main`. Le app **distribuite** non sono allineate al codice
attuale: la Web pubblica serve ancora la 0.1.14; Android 0.1.15/300038 è
nel test interno Play, con una candidata Web della stessa sorgente che non
è stata pubblicata. I dati meteo nazionali e CAMS hanno inoltre problemi
operativi indipendenti dalla versione installata.

## Identità dei livelli

| Livello | Evidenza e stato | Limite |
| --- | --- | --- |
| `origin/main` | `c208c260d6915f70cea52352f8e8ef3092d2255c`, dopo PR 61 (codice) e PR 62/64/65 (documenti). La [CI main `45653497810`](https://github.com/meteofriul/meteofriul-app/actions/runs/45653497810) sul commit di codice `488f7d3c` è riuscita nei tre job. | I tre merge solo Markdown successivi non hanno avviato la CI completa, per `paths-ignore`. CI verde attesta il codice, non un'app pubblicata. |
| Checkout canonico locale | `codex/mercati-integration-20261028`, `8f9220fc`, pulito e uguale al proprio ramo remoto. Rispetto a `origin/main`: 55 commit dal lato del checkout e 13 dal lato di main; base comune `61ca8e5e`. | È un workstream in pausa, non una copia allineata del main né la sorgente di release. Nessun file Mercati è stato modificato da questo controllo. |
| Frontend su `main` | `frontend/package.json` indica 0.1.15; `frontend/android/app/build.gradle` indica ancora `versionCode 300036`. | Versione nel sorgente, artefatto Play e pubblicazione Web sono identità diverse. |
| Ramo release Android | `codex/release-0.1.15` a `22fb40d6`; AAB **0.1.15/300038** da `7130c28a`, [accettata nel test interno Play il 26 ottobre](https://github.com/meteofriul/meteofriul-app/blob/codex/release-0.1.15/docs/operations/ANDROID_0.1.15_300038_UPLOAD_20261026.md). La CI della sorgente `40293565378` è verde. | Non è integrato in `main`. Il verbale lascia il runtime della 300038 su telefono non verificato; non abbiamo una lettura Play Console successiva al 26 ottobre. La produzione era 0.1.14/300031 in quella lettura, non uno stato live confermato oggi. |
| Web candidata | Archivio `20261026-0.1.15-7130c28a`, dalla stessa sorgente della AAB 300038, [registrato nel ramo release](https://github.com/meteofriul/meteofriul-app/blob/codex/release-0.1.15/docs/operations/ANDROID_0.1.15_300038_BUILD_20261026.md). | Preparato, **non pubblicato**; non qualifica Safari/iPhone o la parità della Web live. |
| Web pubblica | `https://meteofriul.app/` ha restituito HTTP 200 il 25 novembre alle 17:41 UTC. SHA-256 HTML `cbfc53fd…a394aa`, asset principale `/assets/main-D-Nry2Xb.js` SHA-256 `c5ab69f0…010ca`: entrambi corrispondono alla [ricevuta della pubblicazione 0.1.14 del 21 ottobre](evidence/release-web-alignment-2026-10-22/verification.json), sorgente `1b0287c1`. | Questa è verifica dei byte pubblici osservati, non lettura autenticata del deployment Cloudflare. `wrangler whoami` non ha potuto aggiornare la sessione scaduta; nessuna credenziale è stata modificata. Safari/iPhone e Aggiungi a Home non verificati. |

Fra `origin/main` e il ramo release differiscono sei file nel perimetro
frontend controllato: configurazione `versionCode`, stile delle schede Home,
proiezione del programma Pordenone Pensa e relativi test/fixture. La 300038
non contiene quindi tutte le modifiche frontend oggi in `main`. La Web
pubblica è ancora precedente a entrambe. La coppia *candidata* Web/AAB
300038 nacque dalla stessa sorgente; questa parità preparata non è parità
fra gli artefatti effettivamente distribuiti.

L'unica PR aperta su GitHub al controllo del 25 novembre è la
[PR 63](https://github.com/meteofriul/meteofriul-app/pull/63), bozza del
protocollo di recupero ICON nazionale; non è nel codice `main` né in un'app.

## Funzioni e dati dell'app

Il [rapporto operativo dei job](JOBS_READONLY_AUDIT_20261125.md) separa
esecuzione, dato prodotto e lettura pubblica. Nel campione del 25 novembre:

- **Meteo FVG ordinario:** le ultime tre corse ICON FVG sono riuscite e
  Storage/HTTP mostrano il ciclo del 25 novembre. Il Bollettino e le allerte
  ufficiali usano percorsi separati; l'allerta FVG del campione era fresca.
- **Meteo nazionale:** ICON nazionale resta in `manual_review` sul ciclo del
  21 novembre e il reader pubblico restituiva 503. La diagnostica è
  distribuita al job, ma il dato non è recuperato.
- **Aria e pollini:** la correzione CAMS U11 è distribuita. Due corse hanno
  usato una sola richiesta ADS ancora in elaborazione; Storage e API HTTP
  mostravano revisione 72, ciclo del 23 novembre, anche dopo la ripresa
  delle 17:31 UTC. UV è un prodotto separato ed era corrente nel campione.
- **Eventi:** il catalogo pubblico rispondeva HTTP 200 e la ricerca campione
  per Udine trovava 88 eventi, ma il job del 25 novembre era fallito e il
  catalogo era `degraded`: Azalea e TurismoFVG `stale`, Barcolana `fresh`,
  Spazzapan in pausa. Le schede delle fonti stale sono escluse.
- **Notifiche:** i job mattutino e serale hanno registrato 68/68 accettazioni
  FCM nelle corse campionate; ricezione e visualizzazione su ogni telefono
  non sono provate da questi contatori.
- **Scopri e lingue:** l'audit delle schede Scopri nel ramo locale
  `codex/scopri-content-audit-20261125` e le correzioni UI IT/FUR nel ramo
  locale `codex/translation-audit-fixes-20261123` non sono su GitHub né
  integrati in `main` o distribuiti. L'audit Scopri segnala traduzioni
  da riallineare, fonti non puntuali e prosa
  editoriale da rivedere; la presenza tecnica di IT/FUR non certifica la
  fedeltà di ogni scheda.

Queste sono letture datate e campionate; non equivalgono a un collaudo
integrale dell'app su Android o iPhone. Il pannello amministrativo è fuori
dal perimetro di questo stato.

## Ordine pratico per riallinearsi

1. Recuperare e verificare i dati ICON nazionale e CAMS, poi chiudere le due
   fonti Eventi degradate. Non presentare una corsa riuscita come prova di
   freschezza senza puntatore e API verificati.
2. Decidere i testi Scopri e integrare le correzioni linguistiche dopo
   revisione; allineare un candidato Web/Android a **un unico commit frontend
   approvato** e aggiornare lo stato release dal ramo 300038.
3. Eseguire i gate Android obbligatori e il collaudo reale della nuova AAB,
   più Safari/iPhone per la Web. Preparazione, pubblicazione Web, AAB/Play e
   produzione sono passi distinti con autorizzazioni proprie.

Nessun deploy, build, installazione, invio o modifica dei job è stato
eseguito per questo rapporto.
