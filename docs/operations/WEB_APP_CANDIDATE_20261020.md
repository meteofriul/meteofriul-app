# Preparazione Web dalla base Android approvata — 20 ottobre 2026

## Esito

Anteprima Web compilata e conservata, non pubblicata. Sorgenti frontend
invariati rispetto a main `bf304281aa9851369687c2dd646b8bd473c0b23d`:
la base già verificata su Galaxy con TEST `.6`, escluse le impostazioni TEST.
Ramo di preparazione: `codex/web-android-parity`.

La pubblicazione resta da autorizzare e completare: mancano il legame verificato
fra la revisione API corrente e il suo commit sorgente, e il collaudo Safari
su iPhone. Nessuna nuova AAB, push Git, modifica cloud, notifica o segnalazione
Community inviata. Nessun emulatore o installazione sul telefono.

## Cosa contiene

- Testi italiani/friulani, pill dei giorni, navigazione approvata.
- Conferma Community No/Sì, ricevuta e dicitura «Inviata da».
- Refresh FVG resistente alla pressione della cache, catalogo Eventi ufficiale,
  lettore compatibile con i metadati delle tolleranze.
- Previsioni chiare/scure, card uniformi, pioggia leggibile, giorno e ora
  selezionati con contorno e sfumatura interna uguali.
- Configurazione Web ufficiale; nessun marchio TEST, fixture o server loopback
  nel collegamento API incorporato. L'indietro nativo Android non viene
  reinterpretato come chiusura forzata del browser.

Il numero tecnico resta `0.1.14`: non è stata inventata una nuova release Play.
La versione del prossimo rilascio va coordinata prima della build definitiva.

## Artefatto ed evidenze

Archivio durevole nella root canonica:
`release-artifacts/web-candidates/20261020-bf304281/` (ignorato da Git).

- `web-preview.zip`: 503 file, 69.745.268 byte.
- SHA-256: `e81b04aaaeefdf3c7ab8356cfc31557be77ba00f7bcfb4a56d818b59a5ff32fa`.
- `manifest.json`: hash di tutti gli asset e sorgenti frontend, commit, versione,
  binding osservato, dipendenze, controlli e stato non distribuibile.
- `build.log`, `release-guards.log`, `focused-tests.log`, `dependencies.json`,
  `national-http.json`, `browser-checks.json`: risultati e limiti.
- Script locali di riproduzione inclusi nelle evidenze; contengono percorsi
  dell'ambiente ma nessuna chiave CARTO. La chiave client CARTO prevista dal
  contratto è incorporata negli asset come nelle build ufficiali.

Anteprima statica del bundle su `http://127.0.0.1:5176/`: non è il pilot su
5174 e non ne sostituisce il launcher canonico. Il pacchetto è stato compilato
in una directory temporanea del sistema e archiviato prima di concludere.

## Controlli eseguiti

| Controllo | Esito e perimetro |
| --- | --- |
| Pulizia workspace | PASS prima della preparazione e alla chiusura |
| Dipendenze | 363 pacchetti applicabili corrispondenti al lockfile, nessuno richiesto mancante; riuso delle dipendenze della TEST, nessuna installazione |
| Compilazione Web/worker | PASS, modalità cloudflare e config loader native; warning dimensione chunk non bloccante |
| Guardie locali | PASS: versione Web/Android, CARTO, endpoint incorporato, worker standalone; 9 test guardie superati |
| Test frontend mirati | PASS: 230 test in 10 file su layout, lingua/tema, refresh/meteo, Eventi, Community e Back |
| Controllo asset | PASS: nuove stringhe Community, accumulation_quality e variabili delle selezioni presenti nel bundle |
| FVG nel browser | PASS su Pordenone: previsioni e UV caricati da servizi reali, temi chiaro/scuro, IT/FUR; selezione giorno verificata |
| Eventi nel browser | PASS: 6 eventi odierni a Pordenone, catalogo e filtri in friulano |
| Layout telefono | Osservato a 390 × 844 nel browser desktop; nomi giorni leggibili e selezioni coerenti. NON è Safari/iPhone |
| Ricerca nazionale HTTP | PASS: Roma restituita da API e data plane nazionale; CORS valido per https://meteofriul.app |
| Ricerca nazionale nel browser locale | NON COMPLETA: API senza allow-origin locale e data plane nazionale 403 per 127.0.0.1:5176; nessun cambio CORS effettuato |
| Community nel browser | Invio non eseguito; flussi coperti dai test locali e dalle prove della TEST del 19 ottobre, non da un nuovo invio Web |
| Safari/iPhone e Aggiungi a Home | NON VERIFICATO: nessun iPhone disponibile |
| Aggiornamento dalla Web pubblica | NON VERIFICATO: nessun deploy e nessuna migrazione del sito esistente |

Le schermate IT chiara e FUR scura sono state osservate nel browser di questa
chat; non sono archiviate come file. Non considerarle prova durevole Safari.
Il server statico iniziale restituiva JavaScript come text/plain; corretto il
solo helper locale. La successiva porta 5176 è già ammessa dal reader FVG e
consente la verifica senza allargare i permessi dei servizi.

Il browser ha letto la corsa FVG del **19 ottobre, 12 UTC**: questo controllo
non chiude la verifica della nuova corsa delle tolleranze attesa separatamente.
Qualità dell'aria e pollini mostravano «non disponibili»: registrato il risultato,
non dichiarato risolto il dato ambientale. Notifiche non autorizzate nel browser,
nessun click su invio Community, nessuna modifica delle preferenze cloud.

## Binding API da chiudere prima della pubblicazione

Endpoint previsto nel candidato, comune alla release Android registrata:
`https://play-b6fbe4d---meteofriul-api-bx24xqvcda-ew.a.run.app/api`.

Il 20 ottobre il tag risolve a `meteofriul-api-00251-jow`, Ready, digest
`sha256:5522b4cfc15076a9f93e838e3643b35e1aa5ad4ce0bf5bca4851997ea94c2ae8`.
L'ultima attestazione AAB `300031` registrava invece la revisione
`meteofriul-api-natistat-da3e711d` e il digest `9a06a675…`.
Il cambio del tag è osservato, non effettuato da questa preparazione.

Le evidenze locali della build Cloud Build
`4f68bd0e-6494-4caa-9be2-90d60d36a92b` confermano SUCCESS e il digest corrente,
ma non dichiarano un commit sorgente. Non attribuire alla revisione il commit
main o quello storico per supposizione. Completare l'attestazione del sorgente
corrente oppure scegliere insieme una revisione già attestata e compatibile.

Per questo non è dichiarato superato il preflight protetto di pubblicazione:
il pacchetto è una **anteprima di revisione** ottenuta con i controlli frontend,
non un risultato di `deploy-cloudflare-app.ps1 -BuildOnly` approvato al deploy.
Prima di pubblicare ripetere quel percorso protetto con binding completo.
Non sono stati indeboliti i controlli dello script.

## Passaggio successivo

Chiudere attestazione API e verifica Safari/iPhone, scegliere la versione
coordinata e ricompilare con il preflight protetto. Pubblicare su Cloudflare
solo dopo autorizzazione, conservando il deployment precedente per rollback.
Il rilascio Web e quello Play vanno registrati insieme nel riepilogo canali,
con eventuali differenze esplicite. La regola permanente è nel
[runbook di allineamento](WEB_ANDROID_RELEASE_PARITY.md).
