# Anteprima Sagre — accesso automatico dal job cloud, 11 ottobre 2026

## Decisione successiva: ritirare la fonte attiva

L'utente ha scelto di non configurare un IP fisso e di togliere Anteprima Sagre
dai percorsi di raccolta attivi. La prova locale dell'11 ottobre ha letto 419
post pubblici su 5 pagine: zero candidati con una data futura esplicita e un
solo caso gia' noto senza anno confermato, la Sagra del Pan Zal. Il catalogo
pubblicato alle `2026-10-11T08:26:37Z` contiene gia' la scheda Pan Zal dal 15
al 25 ottobre, fornita da Paesi in Festa con il programma 2026.

Nel ramo vengono rimossi il monitor Anteprima dal job condiviso, il relativo
comando diagnostico e i fetcher attivi del percorso legacy. Il job non deve
piu' leggere Anteprima ne' conservare il suo vecchio tag nel catalogo dopo il
prossimo ciclo. Il parser storico resta nel codice ma non e' chiamato dai
percorsi di raccolta attivi. Questa modifica non corregge gli errori delle
altre fonti: il ciclo schedulato delle 04:00 UTC dell'11 ottobre e' fallito
per TurismoFVG e CSS Udine; un retry e' riuscito alle 08:28 UTC. L'email
"Alert recovered" segnala solo che la condizione della policy non era piu'
attiva nella sua finestra, non che ogni esecuzione sia riuscita.

La scelta di esclusione e' valida per la copertura verificata oggi; non
garantisce che un futuro articolo di Anteprima compaia nelle altre fonti.
L'eventuale reintegrazione richiedera' una sorgente accessibile e una nuova
verifica di completezza.

## Problema verificato

Il job Eventi legge l'API WordPress pubblica di Anteprima Sagre con una pausa
di 10 secondi tra le pagine e controlla date future senza pubblicare schede
di questa fonte. Dal PC, lo stesso monitor e lo stesso User-Agent
`MeteoFriulEventsWatch/1.0` leggono 419 articoli pubblici in 5 pagine.
Dal job Cloud Run in `europe-west1` la prima richiesta riceve invece
`HTTP 202 text/html`, intestazione `sg-captcha` e una pagina CAPTCHA;
non e' un risultato WordPress vuoto.

## Prove isolate del giorno

| Prova | Risultato | Risorsa temporanea |
| --- | --- | --- |
| Stessa immagine e monitor in `europe-west4` | `HTTP 202`, `sg-captcha`, prima pagina | Esecuzione `meteofriul-events-anteprima-diagnostic-ew4-hkbdq` |
| Una richiesta in `europe-west1` con User-Agent Chrome desktop | `HTTP 202` | Esecuzione `meteofriul-events-anteprima-ua-diagnostic-9ckr5` |

La seconda prova usa l'immagine Eventi con una singola richiesta GET pubblica
e stampa soltanto il codice HTTP. Entrambe
le risorse temporanee sono state eliminate. Il catalogo GCS e' rimasto alla
generazione `1791707321735781`, dimensione `2983575` byte.

Questi due esiti escludono come correzione sufficiente sia il cambio del solo
User-Agent, sia lo spostamento del job in un'altra regione Google Cloud.
Non dimostrano che ogni rete cloud sia bloccata o identificano con certezza
il criterio usato da SiteGround. Il suo [sistema Anti-Bot AI](https://www.siteground.com/kb/seeing-captcha-website)
puo' sfidare indirizzi IP o User-Agent.

## Percorso affidabile

1. Chiedere al gestore di Anteprima un feed pubblico stabile (JSON, RSS o
   calendario) per gli articoli/eventi futuri oppure una modalita'
   autorizzata di accesso server-to-server alla REST API. Il feed deve
   permettere inventario completo, identificatori, modifica, titolo, URL,
   date dell'edizione e paginazione o controllo del totale. Solo i contenuti
   pubblici sono in perimetro.
2. Se la soluzione concordata richiede un indirizzo IP autorizzato, preparare
   un'uscita fissa per il job con Direct VPC e Cloud NAT, poi provarla prima
   di cambiare il job ufficiale. Google Cloud documenta che l'uscita normale
   di Cloud Run e' dinamica; l'IP fisso richiede risorse di rete aggiuntive:
   https://docs.cloud.google.com/run/docs/configuring/static-outbound-ip .
   Nel progetto `meteo-friul` l'API Compute Engine non e' attiva al momento
   della verifica. Un IP fisso da solo non garantisce che il CAPTCHA sparisca.
3. Solo dopo una scansione completa ripetibile, verificare date future,
   deduplicazione contro le 15 fonti e possibilmente pagina ufficiale
   dell'organizzatore; poi integrare Anteprima nel job unico e promuovere
   il cambiamento con test e controllo del catalogo.

Una newsletter, un indice di ricerca o un relay sul PC possono segnalare
nuovi articoli, ma non dimostrano che l'inventario pubblico sia completo a
ogni ciclo. Non sono sostituti della sorgente verificata.

Il monitor cloud deve restare `unverified` finche' non ottiene una risposta
valida; il codice corrente assegnerebbe il tag `upstream_captcha` al prossimo
ciclo completo, mentre il catalogo pubblicato conserva ancora il vecchio
tag `upstream_unavailable`.

## Richiesta pronta per il gestore — non inviata

> Buongiorno, curiamo la sezione Eventi di Meteo Friul e vorremmo
> verificare automaticamente le sagre pubbliche presenti su Anteprima
> Sagre, citando e collegando le vostre pagine. La vostra REST API WordPress
> risponde dal nostro PC, ma dal job Cloud Run restituisce `HTTP 202` con
> intestazione `sg-captcha`, anche con una sola richiesta. Rispettiamo la
> pausa di almeno 10 secondi tra le pagine e non accediamo ai contenuti
> riservati. Potete indicarci un feed completo e stabile oppure una
> modalita' autorizzata per consentire questa lettura server-to-server?
> Possiamo fornire URL richiesti, User-Agent e altri dettagli tecnici.

L'invio della richiesta richiede autorizzazione esplicita dell'utente.
