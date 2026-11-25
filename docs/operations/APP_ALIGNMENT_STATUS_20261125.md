# Stato di repository e app — 25 novembre 2026

## Risposta sintetica

Il `main` remoto include il commit di codice `e4b80906` e la sua CI è
verde. Il
checkout canonico locale è pulito, ma resta sul ramo Mercati in pausa e non
coincide con `main`. Le app **distribuite** non sono allineate al codice
attuale: la Web pubblica serve ancora la 0.1.14; Android 0.1.15/300038 è
nel test interno Play, con una candidata Web della stessa sorgente che non
è stata pubblicata. ICON nazionale è stato recuperato alle 19:41 UTC e
CAMS aria/pollini alle 20:04 UTC; Storage e HTTP servono i cicli del 25
novembre. Questi dati sono indipendenti dalla versione installata.
[Esiti e limiti](WEATHER_ICON_CAMS_RECOVERY_20261125.md).

## Identità dei livelli

| Livello | Evidenza e stato | Limite |
| --- | --- | --- |
| Codice di `main` | `e4b80906a285fdaff72c6dc4fa32b37b97dcf20b`, dopo [PR 63](https://github.com/meteofriul/meteofriul-app/pull/63). La [CI main `45683228910`](https://github.com/meteofriul/meteofriul-app/actions/runs/45683228910) è riuscita nei tre job. | PR solo documentali successive possono avanzare la punta di `main` senza cambiare il codice; CI verde non attesta un'app pubblicata. |
| Checkout canonico locale | `codex/mercati-integration-20261028`, `8f9220fc`, pulito e uguale al proprio ramo remoto. Rispetto a `origin/main` `e4b80906`: 55 commit dal lato del checkout e 22 dal lato di main; base comune `61ca8e5e`. | È un workstream in pausa, non una copia allineata del main né la sorgente di release. Nessun file Mercati è stato modificato da questo controllo. |
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

La [PR 63](https://github.com/meteofriul/meteofriul-app/pull/63), bozza al
controllo iniziale, è stata poi integrata in `main` alle 19:14:32 UTC. Il
codice è stato distribuito al solo job ICON nazionale; non è stato inserito
in una nuova app pubblicata.

## Funzioni e dati dell'app

**Aggiornamento delle 20:04 UTC:** ICON nazionale è alla revisione 122,
ciclo `20261125T120000Z`, con fence `completed`, manifest Storage/HTTP
identico e resolver Udine HTTP 200. La prima corsa ordinaria successiva è
riuscita con `publication_already_verified`. CAMS aria/pollini è alla
revisione 73, ciclo `20261125T000000Z`, con Storage/HTTP identici e
campioni dei due prodotti controllati. Il monitor ICON delle 19:40 aveva
letto il vecchio puntatore prima della pubblicazione; quello delle 20:10
ha registrato stato sano per nazionale e FVG.
[Cronologia e prove](WEATHER_ICON_CAMS_RECOVERY_20261125.md).

**Aggiornamento dello slot ICON delle 18:00 UTC:** FVG è riuscito e
l'HTTP pubblico serve il ciclo 25 novembre 12Z (revisione 154);
nazionale è fallito ancora con `acquisition_requires_review` e mantiene
il puntatore al 21 novembre (revisione 121). CAMS restava al ciclo del
23 novembre nella lettura delle 17:57 UTC.
[Evidenza dettagliata](WEATHER_ICON_CAMS_RECOVERY_20261125.md).

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
