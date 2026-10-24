# Recupero pagine 404 del calendario TurismoFVG — 24 ottobre 2026

Stato: correzione locale sul ramo `codex/events-turismofvg-404`, da main `eb109518`. Revisione locale completata per il commit e la promozione autorizzati il 24 ottobre. Deploy e recupero del catalogo da attestare separatamente.

## Problema ed evidenza

La corsa ordinaria Eventi del 24 ottobre ha escluso TurismoFVG dopo un HTTP 404; le altre 14 fonti sono state aggiornate. Il log oscura l'URL, quindi non permette di identificare la precisa pagina che fallì nel cloud.

La riproduzione locale della sola lettura pubblica ha trovato un 404 persistente sulla pagina numerata 46 della ricerca 24 ottobre–8 dicembre. Il fornitore redirige a `/StaticPage/404?aspxerrorpath=/eventi`; pagina iniziale, pagine vicine e sitemap rispondono. Il codice precedente interrompe la raccolta anche quando una ricerca per intervalli differenti può recuperare tutte le schede.

## Correzione

- Il 404 di una pagina numerata sul dominio e percorso attesi diventa un motivo esplicito per recuperare l'intera finestra tramite le partizioni già presenti.
- Per questo caso si usa il limite esistente di 512 risultati per partizione. Il recupero preesistente per variazione del totale mantiene 128. Non si aumentano parallelismo, limiti di pagine, finestre o tempo del job.
- Dopo un errore vengono annullate le richieste ancora in coda della scansione fallita; quelle già in corso terminano entro i timeout esistenti.
- Restano obbligatorie corrispondenza dei totali, unione esatta, confronto iniziale/finale e validazione delle singole pagine. Nessuna pagina mancante diventa una lista vuota; nessun dato stale viene promosso. Se il recupero fallisce, il job resta in errore.
- Un 404 della pagina iniziale, un errore di permessi o una destinazione inattesa non attivano questo recupero. Il retry HTTP generale delle altre fonti non cambia.

## Verifiche

Comando dalla cartella backend: `python -m unittest discover -s tests -p 'test_pilot_regional*.py'`: **193 test superati**. Inclusi recupero del 404, errore iniziale, sorgente inattesa, unione incompleta, isolamento dei dettagli e conservazione delle regole di freschezza.

Riproduzione offline completa con risposte reali salvate: il 404 della pagina 46 viene incontrato, il recupero produce **1.677 schede su 1.677 dichiarate**, 410 pagine contate dalla scansione partizionata, zero nuove richieste di rete. La scansione diretta precedente si interrompeva con HTTPError. Questo replay usa due insiemi di risposte successivi: la scansione diretta fallita e le partizioni complete più recenti. Non è un confronto sullo stesso snapshot immutabile del fornitore.

La verifica online delle partizioni è stata limitata inizialmente a 400 richieste per tentativo. Completata poi riusando le risposte già salvate, ha incontrato una variazione reale del totale da 1.677 a 1.678 ed è stata correttamente rifiutata. Il replay offline congela la prima risposta per URL e verifica la riconciliazione; **non dimostra che il catalogo pubblico sia già recuperato**. Nessuna nuova lettura è stata fatta dopo il replay.

Il recupero a partizioni da 128 è stato valutato localmente e risulta troppo oneroso per i numerosi eventi di lunga durata ripetuti nelle finestre giornaliere; il candidato usa il limite ordinario 512. Non è stato eseguito un job completo con verifica dei dettagli e pubblicazione entro i 335 secondi: resta da attestare sulla prossima corsa ordinaria dopo eventuale deploy.

Controllo finale prima della promozione: 843 test locali eseguiti (766 pilot, 70 trasporto/fonti, 7 Attems), 842 superati e 1 saltato; nessun fallimento. La suite del monitor separata esegue 90 test, 89 superati e 1 saltato. Pulizia della baseline canonica e diff Git verificati. Nessuna modifica frontend: non è richiesta una nuova AAB per queste correzioni.

## Evidenze e passo successivo

Evidenza sintetica versionabile: `evidence/turismofvg-404-20261024/checks.json`. Risposte pubbliche, replay e diagnostica sono conservati nella cartella locale ignorata `.tmp/turismofvg-404-20261024` della radice canonica; non vanno inclusi nel commit.

Dopo revisione: commit separato, integrazione su main e CI, quindi eventuale deploy autorizzato del solo job Eventi. Verificare una corsa ordinaria e il ritorno di TurismoFVG nelle API, non soltanto l'exit code. Il rollback può usare l'immagine precedente: nessun cambio di schema o checkpoint; reintroduce però il limite sul 404.

Nessuna modifica ad app, sponsor, destinatari, scheduler, API o altre fonti. Nella fase locale descritta non sono stati eseguiti job cloud manuali, invii, push, deploy, AAB o installazioni. Il successivo push/CI e deploy dei soli Eventi e monitor ICON sono autorizzati dal proprietario; l’esito operativo resta da registrare.
