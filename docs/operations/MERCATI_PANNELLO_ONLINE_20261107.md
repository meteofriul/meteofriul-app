# Mercati: pannello online del 7 novembre 2026

## Esito

Il pannello di gestione è stato distribuito su
`https://meteofriul-inserzioni.web.app/` per la prova del proprietario. La
sezione Mercati usa il login Firebase esistente e l'API dedicata. Il servizio
Mercati è in modalità **solo pannello**: `MARKETS_PUBLIC_CATALOGUE_ENABLED=false`,
catalogo pubblico assente (404), pubblicazione bloccata lato server e nel
client. Nessuna release della Web app o di Android è stata prodotta.

## Identità e artefatti

| Componente | Identità verificata |
| --- | --- |
| Progetto Firebase/Google Cloud | `meteo-friul`, numero `49007668366`; account CLI del progetto verificato prima delle operazioni |
| Backend Mercati | Sorgente `fa7f704249f9958d9ebb1c326571bd12f78637f8`; Cloud Build `e00f5149-93cd-4602-be41-fe6383f9f1ee` riuscita, con test nel container |
| Immagine immutabile | `europe-west1-docker.pkg.dev/meteo-friul/meteofriul/markets@sha256:1bc8197b8097d5431e3e39c8baaf0bd0c12678567bf7317098593a15676c094f` |
| Cloud Run | `meteofriul-markets`, `europe-west1`, revisione `meteofriul-markets-source-fa7f7042`; endpoint `https://meteofriul-markets-bx24xqvcda-ew.a.run.app/api` |
| Pannello | Sorgente funzionale `fbf8191`; Hosting `meteofriul-inserzioni`, versione `ca3b2cbd48231cfd` |
| File Web serviti | `index.html` SHA-256 `fe75d46e7ab7b9d511eb7b216770c86d8af4d86e404036004c8dd6b045744b56`; `/assets/index-CiI6soyW.js` SHA-256 `cd9daa8503fbd49f3c09e3b5f784e1d02b297104ca8ab49d0173f5b655f8dd4e` |

La build del backend contiene 36 file ammessi, controllati con hash prima
dell'invio, senza archivio locale o credenziali. Il deploy Firebase ha usato
soltanto `hosting:inserzioni`; regole Storage, altri siti e altri servizi non
sono stati distribuiti da questo intervento.

## Archivio e controlli

Prima del trasferimento, l'archivio Firestore aveva revisione amministrativa
0 e lo stesso snapshot pubblico locale di base; è stata conservata una copia
privata della revisione remota precedente. Il trasferimento una tantum ha
salvato lo stato editoriale locale alla revisione cloud **1**: 100 schede,
219 edizioni e 59 pratiche, con 16 schede selezionate, 37 sospese e 47 bozze.
La provenienza originaria conservata dal server è rimasta invariata. La
revisione pubblica è **0** e lo snapshot pubblico interno è identico a quello
precedente; la route pubblica resta disattivata. La coda della prossima
verifica manuale comprende tutte le 100 schede, incluse le 37 sospese; il
primo promemoria è il 7 febbraio 2027 alle 09:00 Europe/Rome.

Letture HTTPS: `/api/admin/markets/state` senza token restituisce 401; la
preflight CORS dal dominio del pannello restituisce 200, dall'origine dell'app
400; `/api/markets/catalogue` restituisce 404. Il bundle online include
l'endpoint Mercati corretto e `VITE_MARKETS_PUBLICATION_ENABLED=false`;
gli hash dei file serviti corrispondono alla build locale. La route `/healthz`
restituisce una pagina 404 del frontend Google pur con revisione Cloud Run
pronta; lo stesso comportamento è stato osservato sul servizio Sponsor già
esistente. Le route API sopra raggiungono il container e rispondono secondo
il contratto. La liveness HTTP non è quindi attestata da questa route esterna;
le richieste amministrative sono state verificate direttamente.

Resta la prova interattiva con la sessione Firebase del proprietario: apertura
del pannello, lettura dell'archivio, modifica e salvataggio di una bozza,
ricaricamento e verifica della revisione, inclusa la resa su telefono. Non è
stata eseguita una prova di scrittura attraverso l'interfaccia autenticata.
La pubblicazione delle 16 schede nell'app richiede una decisione e una verifica
separate dopo questa prova. [Selezione e fonti](MERCATI_AUDIT_EDITORIALE_20261107.md).
