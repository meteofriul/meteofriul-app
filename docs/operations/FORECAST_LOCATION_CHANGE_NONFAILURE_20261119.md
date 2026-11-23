# Sintesi mattutina e serale: cambio di posizione durante l'invio

## Caso osservato il 19 novembre 2026

La corsa ordinaria mattutina delle 07:30 italiane ha valutato 66 destinatari:
65 invii accettati, uno respinto dal controllo di sicurezza, nessun errore
della fonte meteo, del dispositivo o dello storage. Il riepilogo precedente
registrava `security_failed=1`, `failed=1`, `status=partial` e faceva uscire il
job con errore. L'allarme operativo era quindi coerente con il codice allora
distribuito, pur in presenza di 65 invii riusciti.

La ricerca nell'outbox della data ha trovato 65 record `sent`, senza un record
per il destinatario respinto: non risulta un tentativo FCM per quel target. Un
dispositivo si e registrato nuovamente durante la corsa e al controllo
successivo non aveva piu un comune valido. Questo rende plausibile un cambio
di posizione o della sua evidenza durante il claim, ma il vecchio log non
conserva lo stato specifico del rifiuto: **la causa esatta del singolo caso
resta un'inferenza**. Non si e ricostruita la posizione del dispositivo e
non sono riportati identificativi personali.

## Regola corretta

Se, tra la selezione e il claim finale, cambiano il comune o la sua evidenza,
il servizio continua a **non inviare** a quella destinazione. Ora conta il
caso come `location_changed`, cioe invio saltato, senza incrementare `failed`
o `security_failed`. Se e l'unico esito, il job termina con stato
`location_changed` e codice zero; se altri destinatari ricevono la notifica,
il riepilogo mantiene `sent` e mostra separatamente il numero saltato.

La stessa regola vale per sintesi mattutina e anticipazione serale, che
condividono il servizio. Restano errori gli invii FCM falliti, i problemi di
fonte o storage e gli altri cambiamenti di sicurezza (app, versione, target,
generazione di iscrizione o schema). Le policy di Cloud Monitoring non sono
state modificate: un vero fallimento del job continua a produrre l'allarme.

## Provenienza e verifiche

- Sorgente: commit `ac91c848`, [PR 53](https://github.com/meteofriul/meteofriul-app/pull/53), merge `05030561` in `main`.
- Test locali: 41 test mirati mattino/sera PASS, `compileall` PASS e `git diff --check` PASS. Coperti invio riuscito accanto a posizione cambiata, solo evidenza cambiata, job serale e un altro stato di sicurezza che resta errore.
- CI della PR `44608625451` e CI di `main` `44609538770`: backend, frontend e hosting-preview-tool PASS.
- Immagine backend costruita con Cloud Build `040f81a2-fdd9-4279-b74d-384516aeeb10` dal contenuto esatto del commit `ac91c848`, digest `sha256:3811ae86d2026d43869b0869e52c225e3c32e57b06783c5aae80567e31bb2b38`. Archivio sorgente prima dell'estrazione: SHA256 `1D996A4631EEAD1B4AADD782019F112CF2179CDE95BA4201427A35AAB0420503`.

## Distribuzione del 19 novembre

Aggiornata **solo l'immagine** dei job Cloud Run esistenti; nessuna esecuzione
manuale o notifica di prova inviata:

| Job | Generazione prima → dopo | Digest precedente | Nuovo digest | Scheduler |
| --- | --- | --- | --- | --- |
| `meteofriul-morning-forecast` | 9 → 10 | `sha256:6c2b64c8c52e3f613aea406214b54da955e38330862abcb95c30845ea1aa20c5` | `sha256:3811ae86d2026d43869b0869e52c225e3c32e57b06783c5aae80567e31bb2b38` | 07:30 Europe/Rome |
| `meteofriul-evening-forecast` | 6 → 7 | `sha256:68ce70252ae27a33a5bbd628984727fc993a9be09295777d945108441bf773c5` | `sha256:3811ae86d2026d43869b0869e52c225e3c32e57b06783c5aae80567e31bb2b38` | 20:45 Europe/Rome |

Readback di entrambi i job: `Ready=True`, comando Python originale, zero
retry, timeout 300 secondi, account di servizio originale e 17 variabili
d'ambiente ciascuno. Le impronte SHA256 dell'ambiente prima e dopo
l'aggiornamento sono identiche per ogni job. Scheduler `ENABLED`, URI e
fuso/orario invariati. Le destinazioni e i consensi degli utenti non sono
stati modificati.

**Verifica ancora aperta:** osservare i riepiloghi delle prime corse ordinarie
dal 20 novembre. Il nuovo contatore deve comparire se un cambio di posizione
si ripete; non e stato prodotto un caso reale dopo la distribuzione. Il
fallimento del 19 novembre resta storico e l'eventuale incidente di
Monitoring va valutato secondo il suo stato, non cancellato retroattivamente.
Nessuna versione o artefatto Web/Android, AAB, pubblicazione dell'app o policy
di Monitoring e cambiata.
