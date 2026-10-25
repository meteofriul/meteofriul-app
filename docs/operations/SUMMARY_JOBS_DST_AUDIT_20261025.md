# Sintesi meteo e cambio d’ora — 25 ottobre 2026

Controllo in sola lettura di Scheduler, esecuzioni Cloud Run, log e metriche,
progetto `meteo-friul`. Nessuna modifica a pianificazioni, destinatari o policy;
nessun avvio manuale di sintesi o notifiche. Il refresh Eventi manuale autorizzato
è separato e descritto nel [verbale Eventi](EVENTS_PNPENSA_BARCOLANA_DEPLOY_20261025.md).

## Sintesi: esecuzioni e consegne

| Corsa italiana | Esecuzione | Idonei | Tentativi | FCM accettati | Errori | Non confermati |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| 2026-10-25T07:30:04.662334+01:00 | `meteofriul-morning-forecast-qqpdm` | 50 | 50 | 50 | 0 | 0 |
| 2026-10-24T07:30:04.610148+02:00 | `meteofriul-morning-forecast-7lrtg` | 48 | 48 | 48 | 0 | 0 |
| 2026-10-24T20:45:01.658499+02:00 | `meteofriul-evening-forecast-rwrrq` | 50 | 50 | 50 | 0 | 0 |

Tutte le corse elencate hanno riscontro Scheduler con target corretto e chiamata
completata HTTP 200. Zero retry, errori di sorgente, sicurezza, dispositivo o
persistenza; zero destinatari duplicati. FCM accettato non dimostra che ogni
telefono abbia visualizzato la notifica.

La mattutina del 25 ottobre è terminata alle 07:32:09 locali: il cambio d’ora
ha spostato l’avvio UTC da 05:30 a 06:30, mantenendo le **07:30 italiane**.
La prossima sintesi serale è programmata il 25 ottobre alle **20:45 italiane**
(19:45 UTC), ma durante questo controllo non è ancora avvenuta.

## Orari effettivi dopo il cambio

Alle 01:00 UTC del 25 ottobre l’ora locale passa da UTC+2 a UTC+1.
Le 02:00 locali esistono due volte, con offset distinti. Gli orari sotto derivano
dalle configurazioni Scheduler lette e dalla conversione Europe/Rome.

| Servizio | Fuso Scheduler | Orari italiani dal 25 ottobre |
| --- | --- | --- |
| Sintesi mattutina | Europe/Rome | 07:30, invariato |
| Sintesi serale | Europe/Rome | 20:45, invariato |
| Eventi | Etc/UTC, 04:00 | 05:00, prima erano le 06:00 |
| ICON FVG e nazionale | Etc/UTC, 06:00/18:00 | 07:00 e 19:00, prima 08:00/20:00 |
| CAMS | Etc/UTC, 09/10/11/15/20 | 10:00, 11:00, 12:00, 16:00 e 21:00 |
| Monitor ICON | UTC, minuti 10/40 | Ogni mezz’ora, minuti 10/40 |
| Avvisi locali | Europe/Rome | Ogni ora |
| Allerte FVG | Europe/Rome | Ore pari, minuto 00 |
| Allerte nazionali, lettura/invio | Europe/Rome | Ore pari, minuti 35/50 |

Lo spostamento locale delle acquisizioni in UTC è coerente con la configurazione;
non sono stati anticipati o ritardati gli scheduler. Il controllo Eventi ordinario
del 26 ottobre resta fissato alle 05:00 locali, dopo la prova manuale di oggi.

## Controllo dell’ora ripetuta

I log mostrano entrambe le 02:00, prima con UTC+2 e poi con UTC+1.
Avvisi locali, allerte FVG e allerte nazionali hanno eseguito due controlli ordinari.
In entrambi: **zero tentativi di notifica, zero invii e zero errori**.
Gli avvisi locali sono `no_candidate`, le FVG `no_active_alert`, il dispatcher
nazionale `no_candidate`. Quindi in questi passaggi non vi sono notifiche doppie;
non è una prova della deduplicazione quando esistono candidati da inviare.
Le due letture nazionali sono `already_current`.

## Allarmi delle sintesi

Le policy di assenza successi usano 25 ore, soglia inferiore a un successo,
per almeno 5 minuti; i dati metrici mancanti attivano la condizione.
Tra le due mattutine a cavallo del cambio passano circa 25 ore. La finestra è
quindi stretta rispetto al ritardo d’avvio, completamento e ingestione delle metriche.
La lettura retrospettiva alle 07:36 del 25 ottobre contiene già il successo
odierno; anche la lettura corrente lo contiene. Nei dati letti non c’è un nuovo
fallimento della mattutina del 25 o della serale del 24.

Non è stato letto lo storico degli incidenti né il corpo di nuove email:
non si può affermare che un allarme sia stato aperto o chiuso durante il cambio,
né ricostruire il ritardo d’ingestione storico dal dato ora disponibile.
Un eventuale margine maggiore o una misura basata sulla corsa attesa richiede
una decisione separata; nessuna policy è stata modificata.

## Evidenze e limiti

File privati, script e riepiloghi in `.tmp/summary-dst-audit-20261025` nella
radice canonica; nessun token salvato. Le esecuzioni delle sintesi sono limitate
al 24–25 ottobre; metriche dal 23 ottobre e invocazioni notturne nell’intervallo
23:00 UTC del 24–03:15 UTC del 25. Il controllo dei due passaggi ripetuti legge i
log applicativi 00:00–02:00 UTC. Nessuna certificazione generale di ogni job,
località o telefono. Nessuna AAB, installazione, nuovo deploy o modifica sponsor.

## Approfondimento successivo

[Incastro ICON–sintesi e proposta per i cambi d’ora](ICON_SUMMARY_DST_REVIEW_20261025.md): confermata la disponibilità della corsa nuova, documentato il massimo di 25 ore della policy e proposta una verifica della corsa attesa per data locale. Nessuna integrazione attivata.
