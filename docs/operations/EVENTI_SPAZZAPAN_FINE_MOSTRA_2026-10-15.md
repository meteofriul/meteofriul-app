# Spazzapan: fine mostra e collaudo locale del job

15 ottobre 2026, collaudo precedente al deploy. **Correzione verificata localmente.**

Aggiornamento successivo: [distribuzione Cloud Run e ciclo completo](EVENTI_SPAZZAPAN_DEPLOY_2026-10-15.md).
Il perimetro e i risultati riportati sotto descrivono la sola fase locale.
Il passaggio di una mostra terminata all'archivio non rende più indisponibili
le altre schede Spazzapan. La raccolta reale del 15 ottobre termina con fonte
`fresh`, due schede pubblicabili e nessuna quarantena.

## Candidata e perimetro

- Ramo: `codex/events-spazzapan-lifecycle`, creato da main
  `5a68de5dc1607105f921d4d2b731170f1a8a0446`, quindi allineato con fast-forward
  alla base Eventi distribuita `f7fe8e9696f5b61a54fda27617ec99834993f8b4`.
- `70c9c894`: riconciliazione della mostra terminata, gate e regressioni.
- **Candidata completa collaudata: `223422e1045dafa0ddc32316bd6ed6ea510aa1ea`**:
  comprende anche il ritiro della notizia collegata e il nuovo incontro
  presente negli inventari ufficiali del 15 ottobre.
- Worktree separato; il checkout canonico rimane su
  `codex/community-reports-simplification`, commit `696cf0f5`.
- Nessuna modifica a main, APK, AAB o Play; nessun push, Cloud Build, deploy,
  aggiornamento di job/API/scheduler o scrittura del catalogo cloud.
- L'anteprima locale già aperta conserva il proprio backend e catalogo.
  Questo collaudo non ne sostituisce i dati e non installa nulla sul telefono.

## Problema e comportamento corretto

Il vecchio adattatore e il gate richiedevano sempre quattro record nella
categoria *Mostra in corso*. Pausig (`232607`) è terminata l'11 ottobre:
la sua uscita dalla categoria faceva fallire tutta la fonte, anche se
rimaneva nella categoria generale delle mostre. Il replay con il codice
distribuito riproduce esattamente `Spazzapan current_exhibitions inventory changed`.

Ora una delle mostre con periodo già verificato può uscire dalla categoria
corrente **soltanto dal giorno successivo alla fine**, nel calendario italiano,
e se l'inventario generale conserva ID, URL, pubblicazione e testo del periodo
coerenti. I campi CMS che riportano il periodo del progetto generale non
allungano la mostra: per Pausig vale 11 settembre–11 ottobre, per FVG70.02
23 luglio–29 novembre. Sono accettati solo i campi generici già noti o le
date proprie corrette.

Il risultato conserva gli ID correnti e la prova delle mostre archiviate;
il gate riconcilia entrambi, invece di accettare qualsiasi diminuzione del
conteggio. Una mostra ancora attiva mancante, un'identità sconosciuta,
una scheda persa anche dall'archivio o un periodo discordante rimangono errori.
Le pagine di dettaglio dei contenuti già terminati non vengono più richieste.

La lettura reale ha rilevato anche la rimozione della notizia Pausig `232257`.
È riconciliata solo con la relativa mostra archiviata e scaduta; lo stesso
legame esplicito esiste per la notizia FVG70.02 `232171`.
Non è ammessa la sparizione generica delle notizie. Se tutte le mostre
verificate sono terminate, un risultato vuoto completo è valido.

## Inventario nuovo del 15 ottobre

Rispetto al giorno precedente, il sito ha aggiunto
[Tra internazionalismo e Genius loci: artisti degli anni '70 oltre i confini](https://galleriaspazzapan.regione.fvg.it/it/eventi-collaterali-ottobre-174822),
28 ottobre alle 18:00, Via Marziano Ciotti 51, Galleria Spazzapan.
La voce API `619735`, la scheda `234126` e la notizia duplicata `234129`
sono riconciliate tramite titolo, introduzione, data, sede e dettaglio.
I vecchi inventari senza questa aggiunta restano coperti dalle regressioni.

Il modulo attuale contiene una locandina, senza prosa utilizzabile. I
metadati generici della pagina conservano ancora il testo copiato
dell'incontro del 14 ottobre: **non viene usato come anteprima**. La scheda
del 28 ottobre ha titolo, data, ora, sede e immagine, senza inventare una
descrizione. Incoerenze o modifiche non verificate di questa scheda la
mettono in quarantena lasciando pubblicabile la mostra FVG70.02.

## Verifiche sulla candidata

Ambiente: Windows, Python 3.13; commit completo `223422e1`, working tree
pulito durante la prova finale. Letture HTTPS delle API pubbliche ufficiali;
nessuna installazione di dipendenze o build Android.

| Controllo | Esito |
| --- | --- |
| Replay della rimozione di Pausig sul codice distribuito | Errore di inventario riprodotto |
| Stesso replay sulla candidata | Gate `ok`, mostra attiva conservata |
| Test Spazzapan | 23 passati, inclusi fine inclusiva, archivio, notizia ritirata, dati discordanti, scheda nuova e job |
| Suite `test_pilot_*.py` | 720 eseguiti: 719 passati, 1 saltato |
| Test Palazzo Attems | 7 passati |
| Job locale con adattatore Spazzapan reale | Completato, `fresh`, 2 schede, 0 revisioni, 4,921 secondi |
| Budget configurato della fonte | 10 secondi, invariato |
| API WSGI sul catalogo prodotto | Due pagine HTTP 200, ID `232202` e `234126`, totale 2 |
| Identità snapshot e CORS Android | Snapshot errato HTTP 409; origine `https://localhost` accettata |
| Pausig terminata nell'API | Assente |

Il test saltato riguarda l'archivio geografico ISTAT opzionale Community,
non presente nel worktree isolato: non è un controllo Spazzapan omesso.
Il Dockerfile include la nuova fixture nella suite eseguita in build;
**non è stata costruita o eseguita una nuova immagine Linux** in questo lavoro.

La prova reale usa `publish()` con il vero collector in processo separato,
il gate e la generazione del catalogo, passando un client Storage in memoria.
Verifica anche la scrittura condizionata alla generazione precedente.
Le richieste Spazzapan sono reali; il salvataggio cloud è simulato e il
catalogo risultante è scritto esclusivamente in locale.

**È una prova completa del percorso Spazzapan, non un nuovo ciclo cloud delle
15 fonti.** Gli altri fornitori e i monitor non vengono rieseguiti dal collaudo
mirato. La suite automatica copre le loro regressioni con fixture e mock.
Una nuova edizione o notizia non ancora riconciliata continua a richiedere
verifica: questa modifica non rende automaticamente accettabile qualsiasi
cambiamento del sito.

## Evidenze e ripresa

[Riepilogo della prova reale](evidence/events-spazzapan-lifecycle-2026-10-15/verification-summary.json),
[verifica API](evidence/events-spazzapan-lifecycle-2026-10-15/api-check.json),
[manifest del codice e dei log](evidence/events-spazzapan-lifecycle-2026-10-15/validation-manifest.json),
[SHA-256](evidence/events-spazzapan-lifecycle-2026-10-15/SHA256SUMS.txt).
Risposte integrali, catalogo, script di replay e log restano in
`.tmp/spazzapan-lifecycle-2026-10-15/` nel worktree.

La candidata è pronta per una successiva distribuzione Eventi separata.
Il presente esito non dichiara aggiornato il job cloud né superato un nuovo
ciclo cloud completo. Main, APK e Play restano fuori da questo intervento.
