# Anteprima Sagre: verifica dell'accesso dal job cloud (11 ottobre 2026)

> Stato successivo: Anteprima Sagre viene ritirata dai percorsi di raccolta
> attivi. La decisione e la verifica dell'avviso Google Cloud sono nel
> [resoconto aggiornato](EVENTI_ANTEPRIMA_ACCESSO_CLOUD_2026-10-11.md).

## Risultato

Il monitor locale ha letto l'API pubblica WordPress con HTTP 200: 419 post su
cinque pagine, nessuna data futura completa e un solo caso senza anno già noto
(Pan-Zal, ID 3673). Questo risultato **non** prova che il job cloud possa
controllare la fonte.

Nello stesso giorno, due esecuzioni di sola lettura del job Cloud Run
`meteofriul-events-refresh` hanno fallito già sulla prima pagina REST:

- `meteofriul-events-refresh-hrmvw`: HTTP 202, `text/html`, server `nginx`;
- `meteofriul-events-refresh-x72bv`: stesso HTTP 202; l'header `sg-captcha` e
  il corpo contengono l'indicazione `captcha` (registrata senza salvare il
  corpo della risposta).

La protezione CAPTCHA è compatibile con l'[Anti-bot AI di SiteGround](https://www.siteground.com/kb/seeing-captcha-website).
Il job non deve considerare l'HTML 202 come un inventario vuoto, né tentare di
superare automaticamente il CAPTCHA. La generazione del catalogo dopo le prove
è rimasta `1791707321735781`: le esecuzioni diagnostiche non lo hanno scritto.

## Regola operativa

Il monitor continua a tentare l'inventario nel ciclo ordinario, rispettando i
10 secondi fra le pagine richiesti dal `robots.txt`. Se il sito restituisce
una verifica CAPTCHA, il catalogo registra `Anteprima Sagre: unverified /
upstream_captcha`; le 15 fonti verificate continuano il loro ciclo. Anteprima
non pubblica schede finché il suo inventario e le date dell'edizione corrente
non sono verificati. Un altro errore di accesso resta `upstream_unavailable`.

`python -m app.events.pilot_cloud --check-anteprima` ripete soltanto il
monitor di questa fonte nello stesso container, senza accesso allo storage e
senza pubblicare il catalogo. È una diagnostica mirata; non sostituisce il
controllo automatico nel job completo.

## Accesso sostenibile

La soluzione definitiva richiede un percorso pubblico che il gestore della
fonte consenta al job, per esempio un feed/API dedicato oppure l'autorizzazione
del client presso il gestore o il suo hosting. Prima di attivarlo occorre
verificare nel cloud l'inventario completo, riconciliare i post e mantenere la
quarantena delle date senza anno. Non è stata chiesta alcuna modifica al sito
e non sono state pubblicate schede Anteprima Sagre.
