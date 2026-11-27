# Eventi: verifica TurismoFVG del 27 novembre 2026

**Aggiornamento successivo:** il recupero condizionale e quattro allarmi
mirati sono stati attivati dopo questa verifica. [Stato e prove finali](EVENTS_CONDITIONAL_RECOVERY_ACTIVATION_20261127.md).

## Stato osservato

Questa è evidenza datata, non un'autorizzazione a rilanciare il job. Il
controllo ha letto Cloud Run, Cloud Logging, Storage e l'API pubblica senza
modificare pianificazioni, policy o il ramo Mercati.

La struttura di osservazione esiste già: il job Eventi registra il riepilogo
`event_source_verification`, il recupero `event_source_recovered` e i guasti
`event_source_failure` in Cloud Logging. La policy del fallimento Eventi è
abilitata. Il canale di notifica è assente per scelta del riordino operativo
del 22 novembre; la presenza della policy da sola non prova un recapito.
Non è necessaria una nuova struttura generale di log per diagnosticare questo
incidente.

Le corse ordinarie del 25, 26 e 27 novembre alle 04:00 UTC sono terminate con
`Completed=False`; quella del 24 novembre era riuscita. Il 27 novembre
TurismoFVG è l'unica fonte attiva indisponibile. Galleria Spazzapan è in pausa
per controllo fonte, non è un errore nuovo. Le altre fonti attive sono `fresh`
o `partial` e le schede in revisione restano separate dai lotti `stale`.

TurismoFVG ha avuto un inventario di 1.599 dettagli il 27 novembre. Il
checkpoint del tentativo contiene 1.027 risultati e 572 non ancora verificati;
576 letture strutturate sono riuscite nella corsa, senza letture fallite, prima
della riserva del budget di 335 secondi della fonte. Il 26 novembre i dettagli
pendenti erano 98. Il checkpoint pubblicato e validato del 24 novembre resta
separato dal tentativo incompleto.

Una sola ripresa mirata con `--source TurismoFVG`, avviata il 27 novembre alle
07:31 UTC, è terminata alle 07:35 UTC con `Completed=False`: `ReadTimeout`
di 15 secondi durante la lettura della fonte. La versione corrente registra
host e tipo dell'errore, ma non la fase né il numero della pagina; perciò non
è dimostrato che il timeout riguardasse una pagina numerata del calendario.
Questo tentativo non ha sovrascritto i checkpoint: il validato resta a
1.532/1.532 del 24 novembre e il tentativo del 27 a 1.027/1.599. Le altre
fonti conservano i lotti della corsa ordinaria del 27 novembre.

L'API pubblica, provata su un punto cittadino di Udine, risponde HTTP 200 e
`ready`, ma `catalog_status=degraded` e TurismoFVG `stale`/`adapter_exception`:
le sue vecchie schede non sono esposte. Una lettura isolata della prima pagina
ufficiale dopo il timeout ha risposto HTTP 200 in circa due secondi; non prova
che tutte le pagine della ricerca siano disponibili.

Una sola riproduzione locale, senza Storage e senza dettagli, ha letto la
finestra 27 novembre–31 dicembre con quattro richieste concorrenti e limite
di 300 GET. Si è fermata dopo 218 GET in 196,7 secondi: è stato osservato un
`ReadTimeout` della pagina numerata 183, poi una `ValueError` di verifica.
L'output limitato della prova non conserva il messaggio della `ValueError`,
quindi non se ne deduce quale controllo abbia fallito. Il timeout della pagina
183 è stato seguito da un retry: la prova non dimostra che i retry siano
esauriti su quella pagina né identifica la pagina del timeout cloud.

## Candidato locale e limite

Nel ramo `codex/events-turismofvg-numbered-timeout-20261127`, da `main`
`9442ce97`, il candidato tratta un `ReadTimeout` **dopo i retry esistenti e
solo su una pagina numerata** come il 404 numerato già recuperabile tramite
partizioni di date. Restano obbligatori il confronto dei totali e l'unione
esatta; una partizione incompleta continua a fallire senza pubblicare dati.
Un timeout della pagina iniziale o dei dettagli non attiva il recupero.

I 195 test regionali, `compileall` del file modificato e `git diff --check`
sono passati. I test nuovi coprono la pagina numerata, la propagazione di un
errore della partizione e il timeout della pagina iniziale. Questi test sono
offline e **non dimostrano** che il timeout cloud osservato ricada nel caso
corretto. Il candidato non è stato distribuito sul job pubblico, che non è
stato ripetuto dopo l'unico tentativo mirato; l'app non è stata pubblicata.

La suite backend completa eseguita con il Python globale 3.13.5 ha contato
2.113 test, con due fallimenti nel test di sicurezza XML di `lxml` 5.4.0.
Lo stesso test fallisce su una worktree senza il diff Eventi e con lo stesso
codice backend di `main`; non riguarda il candidato. Non è stato modificato
né sostituito `lxml` per occultare il fallimento. La
[CI della PR 69](https://github.com/meteofriul/meteofriul-app/actions/runs/45961887134)
ha poi superato backend, frontend e controlli dell'anteprima hosting con le
dipendenze prescritte. I due fallimenti locali `lxml` non compaiono in CI.

## Collaudo Cloud isolato del 27 novembre

L'immagine QA è stata costruita dal commit `83f6d372` con Cloud Build
`da843360-7935-42ec-a9a9-745800ba4339`. L'archivio Git del solo backend
aveva SHA-256 `C638C9014F23A477466AF35C0B5F2276E7D6CDD813CA5689ECFB7E1D197E2B63`;
il digest dell'immagine risultante è
`sha256:8bbafd4454450829eb61f6d6ec8e98b9a07a3757e6782bc4dd67bbce4d7ca3d0`.
La build ha superato anche i test previsti dal Dockerfile del worker Eventi.

La generazione pubblica `1795764929416428` è stata copiata nella chiave QA
`pilot/events/qa/turismofvg-timeout-83f6d372-20261127/catalog.json`.
Le due copie iniziali avevano 3.898.646 byte e lo stesso MD5 Storage.
Il job temporaneo, senza Scheduler, usava il digest QA e la sola chiave QA.
Un'unica esecuzione con `--source TurismoFVG`,
`meteofriul-events-turismo-qa-20261127-xxxhw`, è terminata con
`Completed=True` il 27 novembre alle 08:13:38 UTC, in 3 minuti e 17 secondi.

Il catalogo QA risultante, generazione `1795767215459995`, classifica
TurismoFVG `partial`: 1.573 schede, inventario di 1.603 URL, 256 pagine
di calendario, `source_complete=true`, `within_budget=true`, zero dettagli
pendenti e zero letture fallite. Venti schede sono in quarantena/revisione;
non sono state pubblicate come schede confermate. Il lotto precedente nella
copia aveva 1.498 schede e stato `stale`. Le altre fonti non sono cambiate
nel confronto dei due cataloghi. Il job QA temporaneo è stato eliminato dopo
la verifica; il catalogo QA e i log restano come evidenza.

Il successo prova che il codice candidato completa la raccolta sulla copia
realistica dei checkpoint. Non prova che il recupero delle pagine numerate
sia stato effettivamente esercitato in questa corsa: il sito può aver risposto
senza timeout. La prova offline copre quel percorso e mantiene il controllo
esatto dei totali. La causa certa dei fallimenti pubblici resta distinta:
il 26–27 novembre il budget di fonte finiva con dettagli pendenti; la ripresa
manuale del 27 si è interrotta con `ReadTimeout` non localizzato per fase.

La generazione del catalogo pubblico è rimasta `1795764929416428` dopo il
collaudo e il suo TurismoFVG è ancora `stale`. Il job pubblico è rimasto alla
generazione 49 con il precedente digest `sha256:d6ff27f2…`; Scheduler
abilitato alle 04:00 UTC. Il controllo automatico ha respinto la richiesta
di sostituire l'immagine del job pubblico perché richiede autorizzazione
esplicita al deploy e la PR è ancora in bozza. Non è stato eseguito alcun
aggiornamento o retry pubblico successivo alla prova QA.

## Promozione e ripresa pubblica del 27 novembre

Il proprietario ha autorizzato esplicitamente il merge, il deploy della sola
immagine Eventi e una ripresa mirata. La [PR 69](https://github.com/meteofriul/meteofriul-app/pull/69)
è stata unita a `main` nel commit `6675cdb4` alle 08:26 UTC. La
[CI di main](https://github.com/meteofriul/meteofriul-app/actions/runs/45965634680)
ha superato backend, frontend e controlli hosting. I file backend uniti sono
identici a quelli usati per costruire il digest QA.

Il job pubblico `meteofriul-events-refresh` è passato dalla generazione 49
alla 50 con **la sola immagine**: dal digest
`sha256:d6ff27f255a0d969883beacb485fffdb4fdfcaa715c93f4f2744e6502a7952b7`
al digest QA
`sha256:8bbafd4454450829eb61f6d6ec8e98b9a07a3757e6782bc4dd67bbce4d7ca3d0`.
Il confronto del template prima/dopo conferma invariati chiave pubblica,
identità, 1 CPU, 1 GiB, un task, zero retry e timeout 900 secondi. Lo
Scheduler resta abilitato su `0 4 * * *`, `Etc/UTC`. Il digest precedente è
il riferimento di rollback dell'immagine.

Una sola esecuzione pubblica con `--source TurismoFVG`,
`meteofriul-events-refresh-2gvzk`, ha completato con successo alle
08:34:55 UTC in 2 minuti e 51 secondi. Cloud Logging registra
`event_source_recovered` a livello INFO. Il catalogo pubblico è passato
dalla generazione `1795764929416428` alla `1795768491780598` (SHA-256 del
file letto dopo la corsa:
`435342AA089B84F05B25FFF3E7A1EDF664E79EBD258A3BBB49C9F7F1352CCDE3`).
TurismoFVG è `partial`: 1.575 schede, 1.606 URL d'inventario, 257 pagine
di calendario, `source_complete=true`, `within_budget=true`, zero dettagli
pendenti, zero letture fallite e 21 schede in quarantena. Le altre 14 fonti
sono identiche al catalogo precedente nel confronto dei lotti.

L'API pubblica ha risposto HTTP 200 e `ready` dai campioni di Udine e Trieste,
con 430 e 327 eventi nel rispettivo raggio di 20 km. TurismoFVG è `partial`
e non compare più come fonte `stale`; `catalog_status=degraded` ora comprende
le schede singole in quarantena (`quarantined_cards`). Galleria Spazzapan
resta nella lista delle fonti in pausa. Non sono cambiati il lettore API,
il frontend, la versione, gli artefatti o le pubblicazioni Web/Android.

## Perché può ripetersi e soluzione successiva

Il blocco non era una pausa amministrativa: il sito ha restituito una pagina
404 e in un'altra corsa un `ReadTimeout`; nei due giorni successivi il tempo
di 335 secondi della fonte è finito prima di completare i nuovi dettagli.
Il gate ha mantenuto il lotto validato ma ha marcato la fonte `stale` e il job
fallito, evitando schede non verificate. Il recupero della pagina numerata
copre solo uno dei modi in cui può fallire la lettura. La prova QA e la corsa
pubblica sono riuscite, ma non provano che quel percorso sia stato esercitato
in una richiesta reale: il provider può aver risposto normalmente.

Per evitare una nuova indisponibilità prolungata serve un recupero
**condizionale e limitato**: dopo il ciclo ordinario, leggere soltanto lo
stato del catalogo; se TurismoFVG è `stale` per `incomplete_source` con
checkpoint pendente, eseguire al massimo una ripresa della sola fonte per
giorno. Il controllo deve rifiutare esecuzioni sovrapposte e interrompersi
senza richieste al sito quando la fonte è già valida. Un avviso di freschezza
deve scattare se il lotto resta assente oltre la soglia pubblica di 48 ore.
Questa automazione e l'avviso **non sono stati creati**: richiedono un
workstream separato, prove su catalogo QA e una verifica del traffico/costo.
In un nuovo errore occorre registrare fase e pagina, senza URL integrali,
per distinguere calendario, sitemap e dettagli prima di cambiare altri retry.

La prima corsa ordinaria con l'immagine nuova è prevista il 28 novembre alle
04:00 UTC e non è ancora stata osservata. Il successo della ripresa mirata
del 27 novembre non attesta la continuità dei giorni successivi.
