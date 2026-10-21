# Eventi: correzioni locali dopo la corsa del 21 ottobre 2026

Stato: **verificato in locale, non distribuito**. Ramo
`codex/events-source-reliability`, partito da main
`057f3e816432107451ff45ab5d7a72f50b074505`.
Nessun commit, promozione, push, deploy, esecuzione Cloud Run, invio manuale,
AAB o installazione in questo intervento. Sponsor e relative configurazioni invariati.

## Problema osservato

La corsa ordinaria Eventi delle 06:00 italiane del 21 ottobre ha segnalato:

- Cinema Muto: timeout di lettura, 12 secondi.
- Barcolana: timeout di lettura, 25 secondi.
- Spazzapan: nuova notizia non ancora sottoposta a revisione.

L'incidente Monitoring si è chiuso alle 08:12 per l'uscita del fallimento dalla
finestra di due ore. Non è una prova del recupero: non è seguita una corsa verde.
I dati precedentemente verificati restano conservati; i controlli di freschezza e
revisione continuano a impedire che contenuti non verificati siano spacciati per aggiornati.
Audit originale in `.tmp/job-audit-20261021/ESITO.md` della radice canonica;
le evidenze operative grezze restano locali, fuori da Git.

## Correzione delle sorgenti

**Cinema Muto e Barcolana.** Una sola ripetizione della lettura HTTP in caso di
Timeout/ConnectionError o HTTP 408, 429, 500, 502, 503, 504, con pausa di 0,5 s.
La ripetizione comprende il corpo: i byte di una lettura interrotta non entrano
nel risultato del secondo tentativo. Le risposte vengono chiuse. Un secondo
fallimento rimane un errore; parsing, contenuti troppo grandi o stato HTTP
non transitorio non vengono aggirati con ulteriori tentativi.

I limiti complessivi del worker sorgente restano 30 s per Cinema Muto e 35 s
per Barcolana. Il secondo tentativo può quindi essere interrotto dal limite
complessivo; non vengono garantiti due timeout completi. Timeout delle singole
richieste, dimensioni massime, scheduler e budget del job restano invariati.
La funzione GET condivisa mantiene il proprio contratto per le altre sorgenti.

**Spazzapan.** Verificata la notizia 234240, pagina 174928:
[“A brene vierte”, presentazione del catalogo](https://galleriaspazzapan.regione.fvg.it/it/a-brene-vierte-174928),
21 ottobre 2026 alle 18:00, Galleria Spazzapan a Gradisca d'Isonzo.
È annunciata nelle News ma assente dall'inventario API Eventi: il codice conserva
questa distinzione e non inventa una riga nell'inventario Eventi.

Data e luogo derivano dall'introduzione e dal modulo di contenuto ufficiale,
non dalla data di pubblicazione CMS. Identità, revisione, testo, luogo, ora e
assenza di nuove date strutturate contraddittorie sono controllati. La scheda
scade il 22 ottobre; il suo riconoscimento evita che la notizia ormai nota
blocchi anche il successivo aggiornamento delle altre schede.

Una modifica della notizia già riconosciuta mette in revisione quella scheda.
Le future notizie sconosciute continuano a richiedere revisione: questo intervento
risolve il contenuto concreto del 21 ottobre, non automatizza la revisione editoriale.
Non sono stati pubblicati eventi o cambiati i dati del catalogo operativo.

## Verifiche

- 78 test delle sorgenti, trasporto e job cloud, più 61 sottocasi: PASS.
- 64 test di raccolta, catalogo e policy, più 12 sottocasi: PASS.
- Totale: **142 test distinti**. Suite locali con connessioni socket bloccate.
- Nuovi casi: evento News senza riga API; scadenza; contenuti modificati;
  inventario falsificato/incompleto; errore al secondo tentativo; dimensione
  massima; lettura streaming interrotta senza riuso dei byte parziali.
- Lettura reale separata, solo GET pubblici: 12 risposte in 3,59 s. Parsing e
  verifica locale `ok`, 3 schede, 0 revisioni richieste. Identificativi schede:
  232202 (mostra corrente), 234240 (21 ottobre), 234126 (28 ottobre).
- Questa lettura non esegue il job né scrive su Storage o Firestore. La risposta
  rapida di Spazzapan non dimostra la risoluzione dei timeout degli altri siti.

[Manifest dei controlli e hash dei sorgenti](EVENT_SOURCE_RECOVERY_20261021_checks.json).
[Fixture pubblica minima](../../backend/tests/fixtures/spazzapan_october_21_2026.json)
e [regressioni](../../backend/tests/test_event_sources_october21.py).
Le risposte pubbliche complete sono conservate localmente in
`.tmp/job-recovery-20261021/meteofriul-spazzapan-live-20261021.json` della radice
canonica, con hash nel manifest. Non contengono credenziali; la fixture versionata
conserva solo quanto serve a riprodurre il nuovo caso.

## Passaggio operativo ancora da fare

Commit e promozione delle sole modifiche Eventi, poi eventuale aggiornamento
autorizzato del job con digest e configurazione precedenti conservati per il
rollback. Il formato del catalogo resta compatibile; il campo aggiuntivo di
verifica `news_event_ids` è opzionale per i vecchi record.
Verificare la successiva corsa ordinaria: stato delle singole sorgenti,
freschezza/catalogo pubblicato e schede effettivamente disponibili. Non dichiarare
chiuso il problema dal solo incidente Monitoring chiuso o da questi test locali.
