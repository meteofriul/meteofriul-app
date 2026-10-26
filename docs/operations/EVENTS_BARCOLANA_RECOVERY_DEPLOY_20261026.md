# Deploy Eventi: Barcolana e significato degli allarmi — 26 ottobre 2026

## Sorgenti, revisione e controlli

[PR 30](https://github.com/meteofriul/meteofriul-app/pull/30) integrata in main
`045079a0368ca4c05adabe608d27c0d3a995a9a0` dopo revisione e CI. Commit distinti: `1c302a15` per la lettura
Barcolana, `650d37d6` per diagnostica e policy. CI PR `40288990047` e
[CI main](https://github.com/meteofriul/meteofriul-app/actions/runs/40289610550) superate nei tre job. Verifica locale: 159 test Python e
contratti PowerShell produzione PASS. Il primo comando locale aveva un errore
di importazione delle fixture; ripetuto con la cartella tests nel percorso,
tutti i test sono passati senza modifiche al codice o chiamate ai fornitori.

[Correzioni e limiti della fase locale](EVENTS_BARCOLANA_RECOVERY_20261026.md).
Il recupero nel cloud non è dedotto dai test.

## Immagine e compatibilità

Cloud Build `2fb529b6-327a-48b7-aabc-ffba305759f3`: SUCCESS; Dockerfile Eventi invariato e test locali
del container superati. Archivio da git del commit esatto: SHA256
`bba969c9d45da76bdad037f8f69707c271bad6c288f2d988ec507c74a5a3a4a5`. Entrypoint confermato `python -m app.events.pilot_cloud`.

- Job `meteofriul-events-refresh`, progetto `meteo-friul`, regione `europe-west1`.
- Distribuzione attestata: `2026-10-26T08:11:32.845543+00:00`.
- Immagine: `europe-west1-docker.pkg.dev/meteo-friul/meteofriul/events-worker@sha256:1923bb40a3941d9306a7c319e0f7fc4524809f9752ec6c818bce97df5133472a`.
- Rollback: `europe-west1-docker.pkg.dev/meteo-friul/meteofriul/events-worker@sha256:074d93066cc35fa77bf193f95b8dba1163f5bb11e487dd12c12224b29ef26a26`.
- Solo immagine del job modificata; scheduler, risorse, variabili, account di
  servizio, altri job e servizi Eventi/Community invariati.
- Sponsor disattivati, zero campagne. Nessun pannello editoriale o sponsor attivato.

Rispetto alla vecchia immagine cambiano tre moduli del percorso Eventi:
`pilot_barcolana`, `pilot_cloud`, `pilot_recovery`. Il main contiene anche sei
file delle sintesi, già promossi separatamente: la verifica degli import del
percorso Eventi conferma che non sono importati; i job delle sintesi non sono
stati aggiornati. Catalogo, HTTP e contratti Web/Android restano invariati.
Letture API Pordenone/Trieste con origini Android e Web riuscite prima e dopo:
servono ancora il catalogo precedente, non provano una nuova acquisizione.

Il rollback è compatibile con lo schema dati attuale, ma reintroduce la lettura
a 8 secondi anche al secondo tentativo e rimuove la nuova diagnostica.
Comandi e fotografia della vecchia policy conservati nelle evidenze private;
nessun rollback automatico o avvio di job previsto.

## Policy aggiornata separatamente

Applicata dopo il job soltanto `events-failures`. Patch limitata al titolo della
condizione, alla documentazione e a `alertStrategy.notificationPrompts`.
Readback: `OPENED`, notifica di errore mantenuta. Soglia, finestra di due ore,
abilitazione, auto-close e canale invariati; 22 altre policy invariate.
Audit del generatore della policy: PASS. Nessun invio di prova.

La console può ancora chiudere l'incidente quando il fallimento esce dalla
finestra. Tale chiusura non significa dati recuperati e non produce più l'email
CLOSED. La nuova evidenza `event_source_recovered` riguarda solo dati nuovi
validati e salvati, espone parzialità e fonti ancora mancanti, e non certifica
da sola le API. Nessuna nuova email positiva è stata aggiunta.

## Verifica ordinaria ancora distinta dal deploy

Target: **27 ottobre 2026 alle 05:00 Europe/Rome**, `2026-10-27T04:00:00Z`.
Scheduler confermato `0 4 * * *`, `Etc/UTC`; verifica dalle 05:15 italiane.
Stato attuale: **pending**. Nessuna esecuzione manuale avviata.
Follow-up attivo: `verifica-recupero-barcolana-e-policy-eventi`; primo controllo
utile dalle 05:20, silenzioso prima della finestra e durante lo stato invariato.

Il lettore deve confermare esattamente questa corsa: identità Scheduler e digest,
completamento, catalogo della corsa, tutte le 15 fonti correnti o parziali con
motivi espliciti, recupero persistito Barcolana e premiazioni del 29 novembre
nelle API Trieste. Ricontrolla i cinque incontri ABC Pordenone Pensa e conserva
il programma Scienza discordante in revisione. Se il retry non viene esercitato,
lo dichiara: un primo tentativo riuscito conferma il recupero dei dati ma non
misura il secondo timeout. Un catalogo vecchio o una policy chiusa non basta.

Se il PC si accende più tardi, controllare sempre il target fissato il 27 ottobre.
Dopo esito conclusivo eliminare il follow-up; oltre il 27 ottobre fermarsi e
dichiarare l'eventuale limite, senza sostituire la corsa con una successiva.
Nessuna AAB, installazione, modifica Web pubblica, invio manuale o nuova
acquisizione è richiesta da questi controlli.

Evidenze private: `.tmp/events-barcolana-recovery-deploy-20261026` nella radice
canonica. Solo `verify_ordinary.py` e questo aggiornamento dei documenti sono
previsti nel follow-up. I comandi di distribuzione sono separati.

## Integrità delle ricevute locali

- `deployment-checks.json`: SHA256 `84458b7f50dd53cf678fa5c8719d9a49e3c7a67484c8e54315f64339cbbdcd94`.
- `policy-verification.json`: SHA256 `8d78101cd9f6cb08667d7aae927795afa04b89cae25af6cfb4cd60f5d984ef65`.
- `compatibility.json`: SHA256 `2ecdb4e8cf122636c8dee83e5faeb5b1ddce7043bb2e1bfd5f4d65288aac711e`.
- `ordinary-target.json`: SHA256 `13d0fde9cfb9bcd7d3c8a54737e22acbd75ca4db7c52c47211ca98c7849aaaed`.
