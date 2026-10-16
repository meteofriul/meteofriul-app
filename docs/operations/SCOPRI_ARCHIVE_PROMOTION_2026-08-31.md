# Scopri — promozione dei 17 testi d'archivio

31 agosto 2026 · Integrazione locale successiva al commit `ad78fe6`.

## Approvazione e limiti

L'utente ha risposto **«si procedi»** alla domanda: «Per renderle visibili serve una decisione esplicita: confermi di approvare queste 17 bozze sulla base della revisione assistita, senza una revisione esterna del FUR?».

La decisione autorizza l'integrazione editoriale locale dei 17 testi IT/FUR raccolti in [SCOPRI_FUR_REVIEW_2026-08-31.md](SCOPRI_FUR_REVIEW_2026-08-31.md). È registrata come `user_explicit_assisted_review_approval`, con metodo `assisted_standard_reference_review`. Non dichiara una revisione esterna, una certificazione ARLeF o una lettura professionale indipendente.

Le tre schede già integrate (cesti, latteria sociale e cartoline di Lignano) conservano integralmente l'approvazione condizionata del 30 agosto. Nessun testo è cambiato durante questa promozione: sono recepite le copie già revisionate, comprese le due modifiche FUR del 31 agosto.

## Catalogo e tracciabilità

- `institutionalArchive.json`: da 3 a **20 schede**, con le tre precedenti invariate.
- Catalogo culturale complessivo: da 71 a **88 record**.
- Rubrica Archivio e tradizioni: **69 record**, di cui 47 calendarizzabili e 22 dipendenti dal meteo, non inclusi nell'audit senza contesto meteorologico.
- Entrambi i lotti di ricerca: dieci promossi ciascuno, ma copie sempre `readyForUi: false`.
- Le copie runtime sono `readyForUi: true`, con IT/FUR approvati e identità canoniche già predisposte.
- `promotionReview` e `languageReview.fur` registrano lo stato corrente, data, base dell'approvazione e documenti di riferimento. `itCopyReview`, `furDraftReview` e `furCopyEditReview` restano snapshot storici dei passaggi precedenti.
- Fonti, geografie, titoli, corpi, anteprime e regole temporali approvati sono conservati. Nessuna fotografia, filmato o riproduzione d'archivio aggiunta.

## Schede integrate

| Testo | Identità runtime | Finestra editoriale |
| --- | --- | --- |
| Il Bacio delle Croci a Zuglio | `institutional-archive-bacio-croci-zuglio` | Pasqua +39…+42 |
| Il Capodanno dei coscritti ad Alesso | `institutional-archive-coscritti-alesso` | 12-31..01-01 |
| Il Maj di Lucinico, l'albero dei coscritti | `institutional-archive-maj-lucinico` | 04-30..05-07 |
| I cramârs partivano in autunno | `institutional-archive-cramars-carnia` | autunno, inverno, primavera |
| Un quaderno per tessere: i tacamenti | `institutional-archive-tacamenti-cavazzo` | Rotazione annuale d'archivio |
| Il frasco dell'osmiza | `institutional-archive-osmiza-frasco` | Rotazione annuale d'archivio |
| Il tòco dei pescatori maranesi | `institutional-archive-toco-marano` | Rotazione annuale d'archivio |
| I caffè come salotti di Trieste | `institutional-archive-caffe-storici-trieste` | Rotazione annuale d'archivio |
| Le regole della lippa potevano cambiare da paese a paese | `institutional-archive-lippa-regole-locali` | Rotazione annuale d'archivio |
| L'acqua portata con l'arconcello | `institutional-archive-secchi-rame-arconcello` | Rotazione annuale d'archivio |
| Il ciavedâl, più di un alare | `institutional-archive-ciavedal-alare` | Rotazione annuale d'archivio |
| I mulini lungo le risorgive | `institutional-archive-mulini-risorgive` | Rotazione annuale d'archivio |
| Un nome nella stalla, un suono al pascolo | `institutional-archive-animali-nomi-campanacci` | Rotazione annuale d'archivio |
| Pettini d'osso fra i sedonêrs di Andreis | `institutional-archive-pettini-osso-andreis` | Rotazione annuale d'archivio |
| Il bucato che poteva durare giorni | `institutional-archive-bucato-ranno` | Rotazione annuale d'archivio |
| Un ago d'osso per leggere il prosciutto | `institutional-archive-ago-osso-prosciutto` | Rotazione annuale d'archivio |
| Un archivio di oltre 2.300 racconti | `institutional-archive-teche-racconti-popolari` | Rotazione annuale d'archivio |

Le finestre del Bacio delle Croci e del Maj ripropongono racconti documentati nel 1973: **non indicano programmi o date di eventi attuali**. La rotazione di osmiza e tòco non è un calendario di aperture o di pesca. Le regole preparate in [SCOPRI_ARCHIVE_INTEGRATION_2026-08-30.md](SCOPRI_ARCHIVE_INTEGRATION_2026-08-30.md) non sono state ampliate.

## Verifiche

- Suite frontend completa: **357 file, 2.276 test superati** (`npm test`, configurazione nativa).
- Lint: superato (`npm run lint`).
- Build Web di produzione e service worker: superate in una directory temporanea esterna al progetto, con caricamento nativo delle configurazioni; controllo service worker standalone superato, enrollment Web disabilitato. Rimane il warning non bloccante sulla dimensione del bundle già noto.
- Catalogo reale simulato dal 2026 al 2031, in IT e FUR: tutte le 20 schede istituzionali vengono selezionate ogni anno; nessuna collisione visibile né violazione della precedenza delle ricorrenze; ripetizione consecutiva dell'Archivio non oltre due giorni.
- Audit 2028 senza contesto meteo: Archivio presente 366/366 giorni, 45 contenuti distinti usati su 47 idonei. Le due ricorrenze non selezionate (San Barnaba e Sant'Ermacora) sono già coperte da Memoria del giorno.
- Rendering automatico delle 20 schede nelle date reali di selezione del 2028, IT/FUR: titolo, testo, fonte e assenza dell'etichetta di revisione verificati.
- Browser locale: apertura di Scopri, cambio IT/FUR e leggibilità della pagina del 31 agosto verificati. Il controllo visivo riguarda la selezione del giorno; le 20 schede sono state verificate singolarmente dal test di rendering, senza forzare la data del browser.
- Revisione finale: corrispondenza fra dati di ricerca e runtime; prime tre schede runtime integralmente identiche al commit precedente; nessuna modifica ai meccanismi di selezione o ai controlli di pubblicazione.

## Distribuzione

Solo cataloghi, test e documentazione locali. Nessun commit, push, deploy, AAB o aggiornamento dei tester eseguito in questo passaggio. Webcam, backend e configurazione Android non modificati.
