# Verifica dei job del 31 ottobre 2026

Controllo richiesto dal proprietario durante il lavoro locale sui Mercati.
Agente nativo `controllo_job` disponibile e utilizzato; `build_verifica`
controlla le evidenze, il coordinatore redige questo verbale.
[Inventario](JOBS_INVENTORY.md) e
[ricevuta sanificata](evidence/JOBS_READONLY_AUDIT_20261031.json).

Solo letture: nessun job avviato o riprovato, nessun cambiamento a scheduler,
policy, servizi, dati o notifiche. Nessun commit, push o pubblicazione.
L'accesso amministrativo è stato inizialmente bloccato dalla sandbox;
la raccolta è partita dopo l'autorizzazione dalla chat principale.

## Perimetro e risultato

Account e progetto attesi verificati prima delle letture. Finestra delle
esecuzioni: **31 ottobre 00:00–16:20:50 Europe/Rome**, equivalente a
30 ottobre 23:00Z–31 ottobre 15:20:50Z. Confrontati Cloud Run nelle regioni
`europe-west1` e `europe-west8`, scheduler, policy, log e prodotti pubblicati.
I riscontri HTTP e Storage principali sono stati raccolti fino alle 16:22:51
italiane; la ricevuta distingue il successivo supplemento di log.

**14 istanze job Ready, 11 scheduler ENABLED; 83 esecuzioni odierne,
80 riuscite e 3 fallite.** Nessuna esecuzione ancora in corso e nessuna
mancanza nel confronto numerico con gli slot già dovuti dei cron letti.
Questo confronto non prova, per ogni corsa, la catena esatta di invocazione
Scheduler → Cloud Run. La query limitata agli errori Scheduler di oggi
non restituisce record.

Le liste delle esecuzioni odierne non sono troncate. I log sono invece
campioni limitati, non ricostruzioni complete di ogni corsa. Il successo
dell'esecuzione non è considerato prova di dati aggiornati o di ricezione
di una notifica.

## Esito per job

Orari italiani CET; nomi senza prefisso `meteofriul-`. Regione west1 salvo
indicazione. Conteggi riuscite/fallite entro il termine della finestra.

| Job | Pianificazione osservata | Corse | Risultato osservato |
| --- | --- | --- | --- |
| `morning-forecast` | 07:30 | 1 / 0 | 53 tentativi, 53 accettazioni FCM, zero errori; ricezione sul telefono non verificata |
| `evening-forecast` | 20:45 | 0 / 0 | Corsa di oggi non ancora dovuta; quella di ieri riuscita |
| `local-notice` | Ogni ora | 17 / 0 | Ultima corsa senza candidato, zero invii e zero gruppi con dati degradati nel riepilogo |
| `official-alert-sync` (west8) | Ore pari, minuto 00 | 9 / 0 | Allerte FVG aggiornate alle 16:00, nessuna attiva |
| `national-official-alert-sync` | Ore pari, minuto 35 | 8 / 0 | Campione pubblico Roma completo, verde, valido fino a fine giornata |
| `national-official-alert-send` | Ore pari, minuto 50 | 8 / 0 | Ultimo riepilogo senza candidato e senza invii |
| `icon` | 07:00 / 19:00 | 0 / 1 | Fallita la corsa del mattino: `SourceRunNotAdvanced`; ciclo pubblicato ancora 30 ottobre 12Z |
| `national-icon` | 07:00 / 19:00 | 1 / 0 | Esito tecnico positivo, ma `no_op` / `source_not_advanced`: ciclo pubblicato ancora 30 ottobre 12Z |
| `cams` | 10:00 / 11:00 / 12:00 / 16:00 / 21:00 | 3 / 1 | Fallimento delle 10:00, recupero negli slot successivi; famiglia e UV del 31 ottobre 00Z |
| `events-refresh` | 05:00 | 0 / 1 | Fallito il controllo di alcune fonti; catalogo comunque aggiornato in parte alle 05:10 |
| `icon2i-freshness` | Minuti 10 / 40 | 33 / 0 | Monitor eseguito correttamente, ma stato critico su FVG e nazionale |
| `official-alert-sync` (west1 storico) | Nessun target Scheduler letto | 0 / 0 | Istanza storica; assenza di corse non trattata come mancato avvio |
| `event-source-publication-control` | Nessun target Scheduler letto | 0 / 0 | Controllo storico/manuale, non eseguito dall'audit |
| `local-notice-tolerance-qa` | Nessun target Scheduler letto | 0 / 0 | Job QA, non eseguito dall'audit |

## Anomalie sui dati

**ICON è la priorità.** Il puntatore FVG resta alla revisione 103 e al ciclo
`20261030T120000Z`, pubblicato il 30 ottobre alle 19:00:14 italiane. Quello
nazionale conserva lo stesso ciclo, pubblicato alle 19:01:34. Il monitor
delle 16:10 del 31 ottobre segnala su entrambi `critical_active=1`, con
`publication_age_critical` e `run_age_critical`: ciclo vecchio di circa
27,18 ore. Il precedente avvio locale aveva già rilevato il termine
`usable_until=2026-10-31T12:00:00Z`, cioè le 13:00 italiane.

La causa applicativa osservata è la mancata avanzata della sorgente;
l'audit non determina perché l'acquisizione non trovi un ciclo più recente.
Non è sufficiente il successo tecnico del job nazionale per considerarlo
aggiornato. Nessun controllo di freschezza è stato allentato.

**Eventi.** Catalogo Storage aggiornato il 31 ottobre alle 05:10:16 italiane:
15 fonti, **5 fresh, 6 partial, 4 stale**. Le quattro fonti conservate da
acquisizioni precedenti sono:

| Fonte | Ultimo aggiornamento disponibile | Stato dell'ultimo tentativo nel catalogo |
| --- | --- | --- |
| CSS Udine | 26 ottobre | `source_verification_failed` |
| Teatro Verdi Trieste | 30 ottobre | `adapter_exception` / `HTTPError` |
| Galleria Spazzapan | 29 ottobre | `adapter_exception` / `ValueError` |
| Barcolana | 29 ottobre | `adapter_exception` / `ValueError` |

La sonda iniziale Eventi ometteva latitudine e longitudine richieste dal
contratto: il suo errore non dimostra indisponibilità del servizio. Ripetuta
con il centro pubblico di Udine, l'API risponde **200, status ready**, totale
365 risultati e tre restituiti nel campione, snapshot odierno delle 05:01:33.
I risultati non rappresentano 365 schede editorialmente approvate né una
verifica di ogni località. Le fonti `partial` restano tali.

**CAMS.** Il puntatore della famiglia è alla revisione 49, ciclo del
31 ottobre 00Z, pubblicato alle 11:01:33 italiane; anche UV riporta il ciclo
del 31 ottobre. Il risultato dell'ultima corsa osservata è completo. Il
recupero non cancella il fallimento della mattina e non dimostra continuità
minuto per minuto.

Il supplemento dei log attribuisce il fallimento delle 10:00 al limite di
attesa ADS raggiunto: acquisizione salvata per una ripresa esplicita,
senza reinvio automatico; aria e pollini richiedevano revisione manuale in
quella corsa. Alle 16:00 aria e pollini risultano verificati con continuità
verificata dal job, UV verificato anche su Storage, tutti sul ciclo 31 ottobre
00Z. Non è stato richiesto alcun nuovo tentativo dall'audit.

**Avvisi locali.** Il riepilogo delle 16:00 riporta 22 valutati in dieci gruppi,
nessun candidato, nessun errore e `data_degraded_groups=0`. Non si attribuisce
a questo job il blocco dell'anteprima ICON sulla sola base del problema
osservato nell'altro servizio. È una lettura del riepilogo del job, non una
nuova valutazione indipendente di ogni dato utilizzato.

## Monitoraggio e limiti

Lette 23 policy, 21 abilitate e due prove disabilitate. Non individuata una
policy dedicata a `national-official-alert-send`; questo limite era già
documentato nel controllo del 28 ottobre. Nessuna policy modificata.
Incidenti Monitoring, ricezione delle email e consegna effettiva delle
notifiche sui telefoni non verificati. Il campione Roma non certifica ogni
zona del sistema nazionale.

Le eventuali correzioni richiedono un'attività distinta: `meteo` per ICON,
CAMS e qualità degli avvisi, `eventi` per le quattro fonti arretrate. Questo
verbale non autorizza retry, deploy, invii o pubblicazione dell'app.
