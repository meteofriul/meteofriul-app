# Eventi: recupero del job, 19 novembre 2026

## Perimetro

Nel ramo `codex/events-source-controls-20261115`, il commit `eb9fbfcb`
corregge i lettori Eventi prima dell'attivazione del pannello online.
Non aggiunge job o pianificazioni e non modifica l'app Web o Android.
Il catalogo pubblico, il job ordinario e il lettore pubblico restano invariati
finché non sono completati la verifica sul telefono e la promozione della PR.

## Problemi riscontrati e correzioni

- Le Giornate del Cinema Muto ora pubblica il calendario sotto `/it/` e
  reindirizza la radice e la sitemap. Il lettore segue solo quel singolo
  reindirizzamento sul dominio ufficiale e il gate accetta i due percorsi
  ufficiali.
- CSS Udine indicava due repliche di *SDENG!* nella stessa riga, una sola
  data nuova per *La foresta dei no* e uno slug aggiornato per *I Sette a
  Tebe*. Il lettore conserva entrambe le ore di *SDENG!*; il gate accetta
  il cambio di data solo con una singola data esplicita nella scheda
  ufficiale e riconcilia lo slug tramite ID, stagione, giorno e sede.
  *Dialoghi Open Lab* resta in revisione perché la fonte ora rimanda la
  data a febbraio senza indicare un giorno.
- Il lettore XML del Teatro Verdi Trieste era già corretto in questo ramo.
  Azalea e Barcolana hanno superato una nuova lettura; i loro timeout erano
  intermittenti, non una prova di dati nuovi da pubblicare senza verifica.
- Una nuova notizia MESS del 19 novembre,
  [*Polverone*](https://mess.regione.fvg.it/it/not-176889), ID `236501`,
  bloccava l'intera fonte. Ora resta in revisione con il link ufficiale;
  le 10 schede già
  verificate possono continuare a essere usate. Le date della notizia non
  vengono dedotte dal testo né aggiunte al catalogo.
- SagreFVG ha impiegato 45 secondi in una lettura e il numero di pagine è
  cambiato durante un'altra. Il lettore riusa la connessione HTTP e ripete
  una sola volta l'anno il cui conteggio cambia. Il limite per questa fonte
  passa da 60 a 75 secondi; il budget massimo delle 15 fonti resta entro
  875 secondi e il timeout del job Cloud Run è 900 secondi. Una seconda
  lettura incoerente continua a fallire senza pubblicare il lotto.
- Il log di recupero distingue le fonti volutamente in pausa da quelle
  ancora indisponibili. La simulazione locale legge il file dei controlli
  separatamente dal catalogo, come fa il job reale.

## Evidenza locale

Il catalogo pubblico del 19 novembre è stato **copiato** in un file locale.
La prima simulazione mirata ha recuperato cinque delle sei fonti fallite
alle 05:00: Azalea, Barcolana, CSS Udine, Cinema Muto e Verdi Trieste;
Spazzapan è stata esclusa perché in pausa. La simulazione completa
successiva ha rivelato MESS, SagreFVG e
TurismoFVG non completi. Il secondo passaggio ha recuperato MESS e
TurismoFVG, riprendendo le letture del controllo precedente; SagreFVG ha
fallito perché il sito ha cambiato il numero di pagine durante la scansione.
Dopo la correzione, la terza simulazione mirata è riuscita.

Nel catalogo locale finale 14 fonti attive sono `fresh` o `partial`, con
1.875 schede di fonte complessive prima della composizione e deduplica.
Galleria Spazzapan è l'unica fonte in pausa, revisione controlli 1, e il
suo vecchio lotto resta conservato ma non pubblicabile. Tra gli esiti:
TurismoFVG 1.648 schede `partial` con 22 casi in revisione; CSS Udine 130
`partial` con 2; Verdi Trieste 56 `partial` con 1; MESS 10 `partial` con 1;
SagreFVG 5 `fresh`. Cinema Muto ha 0 schede correnti, coerente con la fine
dell'edizione 2026. Gli stati dei tre monitor esterni nel file finale sono
ereditati dal catalogo precedente: il retry mirato non li ha rieseguiti.

`python -m unittest discover -s tests -p 'test_pilot_*.py' -q`:
799 test PASS, 1 saltato. I 27 test mirati per controlli fonte, API e HTTP
sono PASS; `compileall` e `git diff --check` PASS. I file di prova e i log
locali sono in `.tmp/` e non entrano nel commit.

## Collaudo cloud isolato

Archivio `git archive` del commit `eb9fbfcb`: SHA256
`5f0da682d15c3516070f27ad6c6cb051a86dfe095d41c496b55ad1cc8f9ceafd`.
Cloud Build
`d97282d4-79b2-446a-a9d3-8537209b629d` `SUCCESS`, con i test del
Dockerfile passati. Digest worker QA:
`sha256:25ac80c34bf2302354f977fd55ff7995a65fd8d842cf2ebf52e12e3c664b1603`.

Il job temporaneo **senza pianificazione**
`meteofriul-events-job-qa-20261119` ha usato il solo catalogo
`pilot/events/qa/job-recovery-20261119/catalog.json`. L'esecuzione
`...-ztwms` è riuscita in 5 minuti e 54 secondi il 19 novembre; catalogo QA
generazione `1795106254080118`, revisione controlli 1. Il job QA temporaneo
è stato eliminato dopo il collaudo; catalogo, log e tag del lettore QA restano
consultabili. Le 14 fonti attive
sono `fresh` o `partial`, con 1.879 schede di fonte: TurismoFVG 1.651,
CSS Udine 130, Verdi Trieste 56, MESS 10 e SagreFVG 6. I casi non certi
restano in revisione e Spazzapan è in pausa. Il catalogo pubblico ha
mantenuto la generazione `1795061305119260` prima e dopo la prova.

Il lettore QA `meteofriul-events-00021-vex`, tag
`events-job-qa-20261119`, serve il catalogo QA a **zero traffico**.
La revisione pubblica `meteofriul-events-00018-2vz` conserva il 100%.
L'API QA da Trieste restituisce `ready`, 656 schede, 56 Verdi Trieste,
CSS `partial` e Spazzapan `paused`; l'API pubblica conserva lo snapshot
delle 05:00, Verdi e CSS `stale`. Da Udine, la paginazione QA restituisce
1.336 schede, 129 CSS e nessuna Spazzapan; *SDENG!* è presente alle 15:00
e 17:00 e le date simili di *La foresta dei no* sono schede ufficiali
distinte per ID e sede.

La [CI della PR 48](https://github.com/meteofriul/meteofriul-app/actions/runs/44567292574)
è `SUCCESS` nei tre job sul commit `eb9fbfcb`.

I monitor accessori hanno segnalato Palazzo Attems `unverified`
(`ConnectTimeout`) e GiroFVG `unverified` (`ValueError`) nel log QA. Non
producono schede e il job ha riportato la loro incertezza senza dichiararli
verificati. La lettura locale successiva ha precisato le cause: Attems
pubblica ora [pagine annidate](https://palazzoattems.regione.fvg.it/it/italia-settanta-165450/design-176458)
che il parser degli ID non riconosce; GiroFVG ha oltre 30 voci recenti di
sitemap cambiate rispetto alla base revisionata. Questi due controlli
richiedono un lavoro monitor Eventi separato, con revisione della base
GiroFVG prima di modificare la soglia. Non abbassare i controlli per
ottenere un esito verde.

## Verifiche ancora aperte

L'anteprima locale dell'app usa il lettore QA. Il 19 novembre il proprietario
l'ha provata nel browser del telefono con Udine selezionata: la scheda unica
di *SDENG!* raccoglie correttamente le repliche delle 15:00 e delle 17:00;
nel dettaglio sono leggibili entrambe, la sede Teatro Palamostre, Sala
Carmelo Bene, e il pulsante Indicazioni apre la destinazione corretta. Il
raggio dell'esperienza corrente è fisso a 20 km; il primo suggerimento di
impostarlo a 5 km era errato e non fa parte del collaudo. La prova conferma
questo percorso Web su Android, non un APK o Safari.

La PR può essere promossa dopo la CI; l'aggiornamento del job ordinario e
del lettore pubblico richiede ancora il confronto delle configurazioni e
una prova del digest combinato con il ramo monitor. I nuovi comandi Eventi
nel pannello online restano non attivati. La prima corsa ordinaria dopo un
eventuale deploy resta una verifica distinta da quella QA.
