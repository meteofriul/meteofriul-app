# Avvisi operativi nel pannello — 22 novembre 2026

## Decisione

Il proprietario vuole ricevere email quando un servizio importante resta
indisponibile, senza un messaggio per ogni errore di fonte o singola corsa.
Il pannello mostra i controlli ordinari con una causa leggibile e un accesso
alla sezione Eventi. Non sono stati aggiunti job o pianificazioni.

## Sorgente e comportamento

- `GET /api/admin/operations` usa il login proprietario Firebase già richiesto
  dai controlli Eventi. È in sola lettura e risponde con `Cache-Control: no-store`.
- Legge i riepiloghi dei job mattutino e serale in Cloud Logging e il catalogo
  Eventi con le pause correnti. Una corsa mancata appare da controllare, due
  corse consecutive sono urgenti. Un invio riuscito successivo risolve la voce.
- Più fonti Eventi non verificate formano una sola voce nella campanella; la
  pagina Fonti Eventi mostra la causa e la verifica mirata. Le fonti candidate
  da valutare sono separate dal conteggio dei guasti.
- Se i log o il catalogo non sono leggibili, il pannello mostra la copertura
  mancante. Non trasforma un errore di lettura in un falso stato regolare.

## Prove e distribuzione isolata

- Backend: 2105 test superati e uno saltato con `lxml 6.1.0`, più `compileall`.
  CI della [PR 56](https://github.com/meteofriul/meteofriul-app/pull/56):
  backend, frontend e Hosting preview superati sul commit `1ca91fe6`.
- I riepiloghi reali serali del 20, 21 e 22 novembre contengono data locale,
  `status=failed`, zero invii e 26/24/24 errori. Il catalogo del 22 novembre
  contiene Azalea e Barcolana `stale`, Spazzapan in pausa; Palazzo Attems e
  GiroFVG richiedono revisione editoriale.
- Build Cloud Build `01921bc0-9bdb-40d3-9057-6c32e56f6a40` dal backend del
  commit `1ca91fe6`: digest API `sha256:82877df0f3eafc212213ce0f513703d0ce03e087bf80d1e1b8d43e1beeb419ea`.
  Revisione `meteofriul-api-00257-kec`, tag `ops-panel-v1`, zero traffico
  ordinario. `meteofriul-api-play-b6fbe4d-001` resta al 100%.
- Sul tag: healthcheck 200, richiesta senza login 401, preflight CORS dal
  dominio del pannello 200. Nel browser autenticato del proprietario, la
  campanella mostra 2 problemi; apre le due schede corrette, poi Eventi mostra
  le fonti e i comandi per Azalea. Prova visiva anche a 360 px. Nessuna
  verifica mirata o modifica della fonte è stata avviata durante questa prova.
- Hosting del pannello aggiornato dal commit `b6c584b` della
  [PR pannello 4](https://github.com/meteofriul/meteofriul-inserzioni/pull/4).
  HTML, JS e CSS pubblici coincidono per SHA-256 con la build locale:
  `506489C3`, `E5A397C9`, `0C0343A8`. 227 test, lint e build superati.

## Email ridotte

Le quattro policy sotto restano abilitate in Cloud Monitoring, con le stesse
condizioni e strategie, ma senza canale email. La copia completa precedente è
conservata localmente in `.tmp/ops-alert-policy-backup-20261122.json`, ignorata
da Git.

| Policy | ID | Motivo |
| --- | --- | --- |
| Revisione fonti Eventi candidate | `12442153072800978621` | Palazzo Attems e GiroFVG sono decisioni editoriali nel pannello. |
| Job Eventi, singola corsa fallita | `13483592592255950505` | Il pannello raggruppa le fonti effettivamente escluse. |
| Sintesi mattutina, singola corsa fallita | `2371451617565906357` | Resta l'email separata «senza successi». |
| Anticipazione serale, singola corsa fallita | `2746950742275723674` | Resta l'email separata «senza successi». |

Le policy «senza successi» per mattino (`4488305783558930716`) e sera
(`1111789061048675782`) hanno ancora un canale email. Restano invariati anche
gli avvisi su allerte ufficiali, DPC, avvisi locali, ICON e CAMS. Il confronto
con la copia precedente conferma che filtri, soglie, strategia e stato
`enabled` delle quattro policy modificate sono identici.

## Limiti e seguito

- Il controllo «senza successi» esistente guarda 25 ore, quindi l'email può
  arrivare dopo una corsa giornaliera mancata. Il pannello usa invece due date
  consecutive per il livello urgente. Cloud Monitoring limita l'allineamento
  delle policy metriche a 25 ore: una soglia di 48 ore richiede un disegno
  separato, non una semplice modifica numerica.
- Per Eventi un'indisponibilità totale oggi appare nel pannello, ma non ha più
  un'email dedicata. Occorre decidere un unico controllo di indisponibilità
  pubblica prima di considerare completo il riordino degli avvisi.
- Le altre policy email richiedono un'analisi distinta; non sono state
  disabilitate in blocco. L'app Web/Android, gli Scheduler, i job e i
  destinatari delle notifiche agli utenti non sono cambiati.
