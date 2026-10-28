# CSS Udine: riconoscimento dello spettacolo dopo un cambio di URL

28 ottobre 2026. Intervento locale sul ramo `codex/events-css-stable-identity`.
**Correzione e verifiche locali completate; non promossa in main o distribuita.**
Base main `9f81253e6b1832816e4032930b7b5eb64ebff6ad`, allineata a origin/main;
prima delle modifiche il ramo ha conservato con fast-forward i commit
documentali e di profilo fino a `7257d22b781ef9f88f3b0c5eb2d2fb5b81448927`.
Il precedente ramo `codex/job-control-inventory` resta disponibile.

`eventi` è l'unico autore della modifica al gate CSS e delle regressioni;
`build_verifica` rivede i controlli e le prove; il coordinatore aggiorna i
documenti e prepara il commit locale. Nessun deploy o avvio di job è compreso.

## Problema dimostrato

Le corse Eventi del 27 e 28 ottobre, `meteofriul-events-refresh-ntm55` e
`meteofriul-events-refresh-kps9r`, riportano CSS `source_verification_failed`.
Il catalogo della corsa del 28 conserva i precedenti 146 record CSS come
`stale`; il lettore esclude subito la fonte dalle API. Quel conteggio non
equivale a 146 appuntamenti correnti mancanti nella UI.

Nel programma ufficiale, il record **2905** cambia titolo nella lista e slug:

- precedente: `I Sette a Tebe`, percorso finale `/2905/i-sette-a-tebe`;
- attuale: `Giovanni Ortoleva / I Sette a Tebe`, percorso finale
  `/2905/giovanni-ortoleva-i-sette-a-tebe`.

Restano identici il contesto `/stagione-contatto/2026/`, le date **19 e 20
marzo 2027** e la sede **Teatro Palamostre, Udine**. La
[pagina ufficiale letta il 28 ottobre](https://www.cssudine.it/stagione-contatto/2026/2905/giovanni-ortoleva-i-sette-a-tebe)
risponde HTTP 200 e conferma entrambe le date alle 20:30. Il titolo del dettaglio
rimane `I Sette a Tebe`, mentre il collector assegna agli eventi il titolo
della lista ufficiale.

Il confronto precedente usa URL oppure titolo, insieme a data e comune:
il cambio contemporaneo di URL e titolo fa apparire scomparse le due date
future e rifiuta la fonte. L'analisi dei dati completi dimostra questo
predicato sufficiente al rifiuto; non è un replay dell'intero batch remoto
fallito, i cui corpi evento del tentativo non sono persistiti.
La pagina 2940 con calendario ambiguo era già in revisione nel batch precedente
riuscito e non spiega questo nuovo blocco.

Prove locali sanificate: `tmp/events-source-diagnosis-20261028/`, in particolare
`css-retention-predicate-evidence.json`, SHA256
`806b8396ee962fae3ab8521c5ae3c218ebbfd49e6b7790c42f612c8be5862bdc`.
I moduli analizzati coincidono con quelli della base del deploy del 26 ottobre;
il digest del job letto nel cloud è
`sha256:1923bb40a3941d9306a7c319e0f7fc4524809f9752ec6c818bce97df5133472a`.

## Correzione e confini

La riconciliazione delle date future aggiunge l'identità ufficiale stabile CSS,
vincolata alla fonte e al percorso di stagione/anno, con data, comune e sede
coerenti. Non cambia le identità pubblicate, la deduplicazione o il contratto
delle schede. Un identificativo diverso, una sede discordante o un appuntamento
futuro realmente scomparso non devono diventare equivalenti per somiglianza
del titolo. Restano attive le verifiche di completezza e attribuzione.

La nuova equivalenza richiede URL HTTPS canonica su `www.cssudine.it`, senza
credenziali, porta, query o frammento; stagione ammessa, anno e ID numerico
canonico devono coincidere. Comune e sede sono obbligatori: si normalizzano
soltanto spazi e maiuscole. I confronti precedenti restano disponibili; non si
aggiunge alcuna equivalenza fuori dal confronto di conservazione CSS.

File applicativi modificati: `backend/app/events/pilot_source_policy.py` e
`backend/tests/test_pilot_css.py`. Il collector e il parser restano invariati.

La regressione rappresenta le due date del record 2905 e una scheda ancora in
revisione. Il risultato atteso del gate corretto è **`partial`**, non `fresh`:
gli appuntamenti verificati sono utilizzabili e la scheda ambigua resta separata.
Non si modifica il parser del calendario ambiguo per risolvere questo difetto.

## Verifiche locali

Python **3.13.5**, coerente con il requisito 3.13. Usato l'interprete di sistema
già disponibile: `backend/venv` non è presente; nessuna dipendenza installata.
Test da `backend/`, `-B` per evitare cache nel repository; compileall con
`pycache_prefix` in una directory temporanea univoca del sistema operativo.

| Controllo | Esito |
| --- | --- |
| Regressione del record 2905 prima della correzione | Fallimento atteso: `error` al posto di `partial` |
| Stessa regressione dopo la correzione | PASS: entrambe le date conservate, pagina 2940 ancora in revisione |
| Modulo `tests.test_pilot_css` | 16 test PASS |
| Moduli condivisi source_policy, collection, cloud, catalog, HTTP e catalog_health | 111 test PASS, zero errori, saltati o warning |
| Compilazione dei due file Python modificati | PASS |
| Revisione indipendente `build_verifica` e `git diff --check` | PASS |
| Controllo canonical workspace | PASS |

**127 test distinti** complessivi: la regressione singola eseguita prima/dopo
non viene sommata nuovamente. Le prove negative conservano il rifiuto per ID,
stagione o anno diversi, data futura realmente persa, comune/sede/fonte diversi
o mancanti e URL non attendibili su entrambi i lati del confronto.

[Ricevuta delle verifiche](evidence/events-css-stable-identity-20261028/verification.json):
comandi, conteggi, versioni, hash dei due file verificati e dei log. Identifica
la patch tramite hash prima del commit; lo stato Git successivo è distinto.
Log di sviluppo in `tmp/events-css-stable-identity-20261028/`; i log dei controlli
comuni e compileall sono nella directory temporanea indicata nella ricevuta.
Non sono stati ripetuti lint, test frontend, build Android o l'intera suite
backend: la modifica riguarda soltanto il gate CSS e i suoi confini condivisi.

## Stato della distribuzione

L'ultima lettura del job remoto attesta l'immagine indicata sopra, non modificata
da questo intervento. Una correzione locale verificata
non dimostra il recupero della fonte: dopo una distribuzione separatamente
autorizzata serviranno una nuova esecuzione, il catalogo persistito e il
riscontro nelle API. Non basta il successo dei test o del container.
Il recupero della sola CSS può essere valido anche se il job continua a
segnalare altre fonti fallite: vanno letti stato della fonte, pubblicazione
persistita e risultati HTTP, senza richiedere o inventare un verde complessivo.

Nessuna nuova AAB, modifica frontend, pubblicazione Web, cambio di versione,
orario, policy o destinatario. La qualificazione della AAB 300038 resta invariata.
Barcolana (ciclo annuale e timeout) e Magazzino delle Idee restano interventi
distinti; questo lavoro non dichiara recuperate le altre fonti.
