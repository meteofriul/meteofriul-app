# Barcolana: verifica del timeout e letture pubbliche — 28 ottobre 2026

## Esito

Le tre risposte pubbliche acquisite sono complete e coerenti. Il replay locale
del collector e del gate reali passa, anche confrontando gli appuntamenti futuri
con il precedente catalogo obsoleto. **Questa prova non identifica la causa dei
precedenti timeout e non certifica il recupero del job remoto.**

Non emerge una correzione del lettore giustificata dalle prove attuali. Sorgenti
applicativi, timeout, retry, scheduler, monitoraggio e dipendenze restano invariati.
Sono aggiornate soltanto documentazione ed evidenze. Nessun push, deploy,
esecuzione manuale di job o controllo periodico aggiunto. AAB 300038, Web e
qualificazioni immutate.

Ramo: `codex/events-barcolana-seasonality`, prosecuzione dell'intervento Barcolana.
Codice verificato: `6eb9cc01acdf831468dccee46f62d7332b814784`.
Il coordinatore ha acquisito le pagine pubbliche; `eventi` ha eseguito il replay
offline; `build_verifica` ha revisionato integrità, risultati e limiti.

## Confronto delle prove

I log già raccolti delle corse del 27 e 28 ottobre riportano `ReadTimeout` nello
stadio `calendar`: due tentativi in circa 24,69 secondi, ultimo timeout di lettura
16 secondi, circa 3,3 secondi ancora disponibili nel budget condiviso.
Una prova locale archiviata del 28 ottobre alle 17:59 UTC non riceveva byte entro
22 secondi. Nessuna di queste prove attestava una risposta valida senza eventi.

Le nuove GET sono dirette agli stessi indirizzi ufficiali previsti dal collector:

| Lettura del 28 ottobre, UTC | HTTP | Prima risposta | Totale | Byte decodificati |
| --- | --- | --- | --- | --- |
| [Calendario](https://www.barcolana.it/it/calendario-eventi?search=1&_ds=0:Eventi&_cids=0:i1g43), 19:43:47 | 200 | 2,991 s | 3,069 s | 1.383.006 |
| [Sitemap](https://www.barcolana.it/sitemap-0.xml), 20:09:39 | 200 | 0,305 s | 0,404 s | 1.061.919 |
| [Notizia dell'edizione](https://www.barcolana.it/it/news/2026/barcolana58-presented-by-generali-tutto-pronto-per-la-grande-regata), 20:09:47 | 200 | 0,589 s | 0,630 s | 332.772 |

Tre GET distinte con `curl 8.13.0`, User-Agent `MeteoFriulEvents/1.0`, risposta
compressa, nessun retry o redirect seguito. Scadenza di ciascuna prova 28 secondi;
limiti di trasferimento 3/2/1 MiB. Anche i corpi decodificati rispettano i limiti
del collector. Tempi, dimensioni, hash e riferimenti alle prove locali sono nella
[ricevuta](evidence/events-barcolana-timeout-20261028/verification.json).

Una precedente prova nel sandbox falliva prima della connessione, in 0,041 s:
è un limite dell'ambiente locale, escluso dal giudizio sul sito. Le letture
effettive sono state eseguite dopo l'autorizzazione all'accesso esterno.

## Replay sui documenti acquisiti

Python `3.13.5` e Requests `2.33.1`, coerenti con i requisiti del progetto.
Il replay usa `collect_barcolana` e `gate_batch` reali, con risposte in memoria
provenienti esclusivamente dai tre corpi acquisiti. Richieste a URL non catturate
falliscono; nessuna rete, scrittura cloud o pubblicazione durante il replay.

- 682 righe del calendario e 682 URL nella sitemap; nessuno scarto fra inventari.
- 672 sessioni, 10 duplicati riconosciuti, 233 collegamenti univoci ai dettagli.
- L'orfano noto non è nella sitemap: nessun HTTP 404 è stato simulato.
- Collector e gate: `ok`; fase `post_regatta_events`, un appuntamento futuro.
- Premiazioni del 29 novembre, 10–13 al Rossetti, conservate rispetto al precedente
  lotto del 25 ottobre, ancora presente nelle evidenze con stato `stale`.

Le letture sono separate nel tempo e usano curl dalla macchina locale. Il replay
non misura un'acquisizione reale Requests concorrente, non esercita la rete
Cloud Run e non dimostra il rispetto del budget complessivo da quella rete.
La validazione dei dati acquisiti è distinta dalla disponibilità del servizio.

## Decisione e verifiche ancora aperte

Le prove sono compatibili con lentezza intermittente o dipendente da rete/orario;
non permettono di scegliere una causa precisa. Non c'è evidenza di un indirizzo
definitivamente rotto o di un errore del parser sui documenti appena letti.
Non è giustificato aumentare i timeout né usare un calendario giornaliero o un
vecchio programma come sostituto della fonte completa.

Restano i limiti esistenti: 28 secondi per le letture condivise, 35 per il processo
Barcolana, 860 complessivi per le fonti contro il limite applicativo di 875.
Lo streaming potrebbe migliorare il controllo del corpo durante il download,
ma non risolverebbe da solo l'attesa della prima risposta: non introdotto qui.

Per chiudere il problema occorre verificare una corsa ordinaria del job con
esecuzione, data del lotto persistito e riscontro nelle API. Se il timeout si
ripete, serve distinguere attesa della risposta e trasferimento del corpo dalla
stessa rete e nello stesso contesto del job. Nessuna nuova automazione pianificata.
Le correzioni locali CSS e stagionalità restano separate dalla loro futura
promozione e distribuzione; questo verbale non le dichiara pubblicate.

Prove locali: `tmp/events-barcolana-timeout-20261028/`; diagnosi precedente:
`tmp/events-source-diagnosis-20261028/`. I corpi HTML/XML rimangono fuori dai file
versionati. I test del precedente intervento stagionale non sono stati ripetuti:
nessuna modifica applicativa in questo passaggio. Diff, JSON e collegamenti locali
aggiunti: PASS. Controllo canonico dopo staging: PASS, 4006 file tracciati;
nessun output generato, segreto locale o riferimento operativo obsoleto tracciato.

Riferimenti: [stagionalità](EVENTS_BARCOLANA_SEASONALITY_20261028.md),
[budget e retry distribuiti](EVENTS_BARCOLANA_RECOVERY_20261026.md),
[audit job del 28 ottobre](JOBS_READONLY_AUDIT_20261028.md).
