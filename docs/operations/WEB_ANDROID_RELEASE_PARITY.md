# Allineamento della Web App con Android

Regola del proprietario, 20 ottobre 2026: la Web App deve seguire la AAB,
perché chi usa iPhone accede al prodotto dal browser.

## Candidata aggiornata del 23 ottobre 2026 — Tempo reale

AAB **0.1.15 / 300036** e candidata Web dalla stessa sorgente `9d5ff2f415ab8b10be510eff2a0b058a8c2408ac`,
allineata a main `2d8b0c32`. Inclusa la correzione di Tempo reale; conservate
Posizione, CAMS e configurazione nativa. AAB firmata, verificata e disponibile nel test interno dalle 13:37 del 23 ottobre;
Web compilata con `-BuildOnly` e non pubblicata. Sponsor spenti, zero campagne.
Archivio canonico `release-artifacts/web-candidates/20261023-0.1.15-9d5ff2f4/`.
[Controlli, hash e limiti](ANDROID_0.1.15_300036_BUILD_20261023.md).

La candidata `16890b8c` e quella precedente da `5e9bc7dc` restano conservate.
La AAB 300035, precedente candidata interna, non contiene il fix Tempo reale.
La 300036 è ora l'ultimo pacchetto osservato sul Galaxy: mappa e dock visibili
anche dopo avvio a freddo, Posizione conservata, aria/pollini IT/FUR e percorsi
di navigazione osservati PASS. [Prova e limiti](ANDROID_0.1.15_300036_DEVICE_CHECK_20261023.md).
Il caricamento resta attestato nel [verbale Play](ANDROID_0.1.15_300036_UPLOAD_20261023.md).
La verifica Android non sostituisce un collaudo del bundle statico Web.
Prima della pubblicazione Web restano prova del bundle statico e aggiornamento
cache; Safari/iPhone e PWA non verificati. Il sito pubblico nell'ultima lettura
del 23 ottobre rimane 0.1.14: HTML con `main-D-Nry2Xb.js` e asset SHA256
`c5ab69f0a4b63df56ea2254b60fcf829e91b30274632653f000962ac1aa010ca`,
identico alla ricevuta del 22 ottobre. La parità pubblicata non è ancora raggiunta.

## Base comune e confini

Usare lo stesso frontend approvato in main per Web e Android ufficiale. La TEST
serve al collaudo: marchio, package, simulazioni Community, endpoint locali e
servizi esclusi dalla TEST non vanno importati nella Web App pubblica.
Il numero di versione uguale è necessario ma non dimostra la parità del codice.
Una modifica solo nativa può differire: annotarne il motivo. Meteo, Eventi,
testi, temi, Community e contratti dati devono invece avere un comportamento
coerente nei due canali.

## Preparazione, prima di chiedere la pubblicazione

1. Identificare commit frontend approvato, versione, controlli Android già fatti
   e differenze rispetto al Web pubblico. Conservare manifest con hash degli
   asset e dei sorgenti; non usare una vecchia cartella dist come candidata.
2. Controllare versione frontend/lock/Android e configurazione Cloudflare:
   esperienza ufficiale, CARTO, endpoint assoluti, meteo FVG/nazionale, Eventi,
   Community e service worker. Nessuna impostazione speciale della TEST.
3. Per un candidato distribuibile usare `scripts/deploy-cloudflare-app.ps1`
   con `-BuildOnly`, passando API, revisione e commit backend verificati e,
   quando necessario, digest ed evidenza Cloud Build. L'health 200 non prova
   il legame fra immagine e sorgenti. Se tale legame manca, una compilazione
   frontend resta un'anteprima, non un pacchetto autorizzato alla pubblicazione.
4. Verificare nel browser IT/FUR, temi chiaro/scuro, selezione giorno/ora,
   aggiornamento FVG, località nazionale, catalogo Eventi, navigazione e
   Community senza invii reali. I controlli simulati vanno distinti dalle
   letture dei servizi veri. La UI pilot va avviata soltanto con il launcher
   canonico su 5174; un'anteprima statica del bundle Web va identificata come
   tale e non sostituisce la prova pilot o Android.
5. Su Safari di un iPhone reale verificare browser e Aggiungi a Home: avvio,
   safe area, barre del browser, tastiera, scorrimento, ripresa, ricaricamento,
   tema/lingua/località conservati, refresh dei dati e passaggio dalla versione
   precedente. Annotare modello e iOS. Fino ad allora: NON VERIFICATO.
6. Verificare cache HTTP, nomi asset con hash, manifest e service worker.
   Il worker Firebase attuale gestisce notifiche: non è una prova di uso
   offline. Nessuna attivazione di notifiche o iscrizione durante il collaudo
   senza autorizzazione. Non promettere servizi nativi nel browser.

## Pubblicazione coordinata, solo se autorizzata

Prima chiudere gli eventuali prerequisiti dei servizi; poi ricontrollare il
binding API subito prima della build/pubblicazione. Registrare esplicitamente
l'ordine e l'eventuale intervallo fra Web e Play. L'assenza di una nuova AAB
non impedisce di preparare il Web, ma non autorizza nessuna pubblicazione.

Per Cloudflare verificare da root `npx wrangler whoami`: profilo `meteofriul`,
account `b74cf20dd75712b35313b69c191c97d5`, email `meteofriul@gmail.com`, progetto
`meteofriul-app-bcee09e`. Non usare l'account globale o il sito `meteofriul.it`.
Usare lo script di deploy protetto, senza rimuoverne i controlli.

Conservare prima l'identità del deployment Web precedente. Dopo pubblicazione
confrontare HTML/asset realmente serviti con gli hash della candidata,
verificare una sessione esistente e una nuova, poi annotare esiti e limiti.
Un rollback Web deve ripristinare il deployment noto mantenendo la compatibilità
con i contratti dati attivi. Non è autorizzato implicitamente dalla preparazione.

## Evidenza minima per ogni aggiornamento

- Commit e versione frontend comune; AAB/versionCode solo se realmente prodotti.
- Manifest e hash del pacchetto Web, API/revisione/digest/backend verificati.
- Funzioni allineate, differenze native motivate, esiti dei controlli locali.
- Safari/iPhone e PWA: PASS, FAIL o NON VERIFICATO con evidenza.
- Deployment pubblico effettivo e precedente per rollback, dopo autorizzazione.
- Nessun riferimento a chiavi private, token o credenziali negli allegati.

Preparazioni precedenti: [300034](RELEASE_0.1.15_300034_PREPARATION_20261023.md) e [300035](ANDROID_0.1.15_300035_BUILD_20261023.md). Sono verbali storici; la candidata corrente è identificata sopra.

La Web pubblica è già stata aggiornata il 21 ottobre da `1b0287c1`, versione
0.1.14: non contiene le correzioni successive del 22 ottobre. Il precedente
[candidato del 20 ottobre](WEB_APP_CANDIDATE_20261020.md) resta un verbale storico,
non l'identità della nuova candidata o dello stato pubblico corrente.
