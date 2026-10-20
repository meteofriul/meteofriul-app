# Community per la 0.1.15: preparazione locale del 20 ottobre 2026

## Esito

Pacchetto e passaggio coordinato preparati sul ramo
`codex/community-0.1.15-preparation`, dalla `main`
`5cbcd35ca88088220ff167b299cb4353ebdaf6d4`.
Il servizio da aggiornare è **`meteofriul-community` in `europe-west1`**,
progetto `meteo-friul`, account operativo `meteofriul@gmail.com`.
Non serve introdurre un job Community o migrare l'archivio per questo passaggio.
Non sono richiesti aggiornamenti degli altri backend per il solo contratto Community.

Non è un deploy né un via libera alla pubblicazione della app. Nessuna AAB,
installazione, push, build cloud, esecuzione di job o segnalazione manuale.
La preparazione Android resta sul ramo `codex/release-0.1.15`; questa attività
non cambia versione, firma, asset, configurazione TEST o preferenze del telefono.

## Perché serve

Il frontend della candidata 0.1.15 in `main` invia l'header
`X-Meteo-Community-Rules: community-reports-v3`.
Alle **22:28 Europe/Rome del 20 ottobre** il servizio pubblico è ancora sulla
revisione `meteofriul-community-00002-tt2`, 100% del traffico, immagine:

`europe-west1-docker.pkg.dev/meteo-friul/meteofriul/community@sha256:6b1476afcf5d9f2633d54231d3ceca192b4027ad6afb9e37552fcc80f1cf2fb6`

Health e lettura pubblica legacy rispondono 200. Il preflight legacy risponde
200 sia per Android (`https://localhost`) sia per `https://meteofriul.app`;
quello v3 risponde **400**, perché l'header non è ammesso dal vecchio servizio.
La rilettura usa soltanto GET e OPTIONS: nessun contributo creato.

## Cosa resta compatibile

| Client / operazione | Comportamento della candidata backend |
| --- | --- |
| 0.1.14 senza header | Regole legacy, letture, invio, conferma, modifica, ritiro e sostituzione legacy |
| 0.1.15 con header v3 | Nuove regole, ricevute, storico e conferme con GPS e osservazioni viste |
| App vecchia su gruppo v3 | Il gruppo resta leggibile; l'interazione richiede aggiornamento (426) |
| Nuova app su gruppo legacy | Controlli v3 e registro premi legacy condiviso, senza premio duplicato |
| Stessa installazione dopo un invio v3 riuscito | Non può tornare alle vecchie scritture per aggirare le regole |

Identità, punti, quote, ricevute e dati restano nello stesso archivio. Nessun
azzeramento o copia di dati TEST. L'header non sostituisce App Check.
L'allowlist delle app Android/Web e tutte le variabili esistenti coincidono
con la produzione; si aggiunge soltanto il controllo delle scritture v3.
Restano 1 CPU, 512 MiB, concurrency 4, timeout 60 s, massimo 20 istanze e
lo stesso account runtime. Nessun ampliamento IAM proposto.

## Pacchetto pronto

Sorgente fissato a `05a4fcc69969c259163eaad9bca4a4f234384e81`.
Il [manifest](../../release-history/community-preparation/0.1.15-20261020/release-manifest.json)
registra archivio, hash, configurazioni e baseline. L'archivio locale ignorato è:

`build/community-cloud/05a4fcc6-20261020T203606Z/source.tar.gz`

SHA-256: `8bf83ee888b6e9521a63ad98519d451a724a6b93118f6b77100769fd1c6add43`.
Contiene esattamente i **35 file ammessi**, tutti verificati per hash, inclusa
la geografia fissata dal contratto. Non contiene credenziali o dati utente.
L'immagine `community:compat-05a4fcc6` è soltanto il nome pianificato:
**non è stata costruita e non le viene attribuito un digest**.

Configurazioni predisposte, consultabili nella stessa directory del manifest:

- `runtime.env.yaml`: primo passaggio compatibile, scritture v3 disattivate.
- `activation.env.yaml`: cambia soltanto `COMMUNITY_V3_WRITES_ENABLED` da 0 a 1.
- `rollback-compatible.env.yaml`: uguale al primo passaggio, usa il runtime
  compatibile e ferma le scritture v3 senza ripristinare dati vecchi.
- `validation.env.yaml`: puntatore e prefisso snapshot separati; mai usare
  questa configurazione per il servizio pubblico.

Il preparatore accetta ora il percorso esplicito della geografia già presente,
verificandone comunque l'hash. Non dipende da un vecchio checkout o da una
nuova installazione. Le configurazioni qui conservate usano gli host canonici:
un futuro tag di revisione richiede di aggiungere il suo host esatto restituito
da Cloud Run, insieme a quello canonico, e registrare l'hash della variante.

## Verifiche eseguite

- **173 test backend PASS**, offline: compatibilità, regole, reputazione,
  concorrenza, persistenza SQLite, snapshot cloud simulati e risposta persa.
- **33 test PASS sul contesto impacchettato**, con Python isolato dal backend
  del checkout. Sono una ripetizione mirata, non 33 casi aggiuntivi.
- **3 test privacy PASS**, sintassi PowerShell e pulizia workspace PASS.
- Archivio/allowlist/hash, configurazione iniziale rispetto alla produzione,
  singola differenza di attivazione e separazione dello storage QA: PASS.
- Due regressioni aggiunte: preflight e letture v3 dalle cinque origini pubbliche
  ammesse; dopo un invio v3, riavvio e blocco delle scritture conservano ricevuta,
  punti e letture, bloccano tutte le mutazioni v3 e lasciano funzionare le
  operazioni di un utente legacy non aggiornato.

I 33 file del contesto diversi dal test di compatibilità coincidono con il
sorgente QA `81a2610d98ae967822a3b536d859de3645dbccdb`, confrontando i byte con
terminatori di riga normalizzati LF. **Nessun codice applicativo, dipendenza,
Dockerfile o schema dati è cambiato rispetto a quel collaudo**; il 34° file
sorgente contiene le due nuove prove. La geografia è verificata separatamente.
Il [verbale QA del 17 ottobre](COMMUNITY_COMPATIBILITY_ACCEPTANCE_2026-10-17.txt)
rimane evidenza storica: non viene presentato come prova di una nuova revisione
in produzione o del percorso completo Play 0.1.15 → servizio aggiornato.

## Ordine del futuro passaggio, non eseguito

1. Rileggere account, digest, revisione, traffico, configurazione e sink. Se
   differiscono dalla baseline, fermare l'automatismo e aggiornare il confronto.
   Conservare la configurazione per il ripristino; nessun restore dei dati.
2. Costruire soltanto il contesto preparato con
   `backend/community-pilot-build.yaml` presente nell'archivio come
   `cloudbuild.yaml`, `_SOURCE_COMMIT=05a4fcc69969c259163eaad9bca4a4f234384e81`
   e tag pianificato. Registrare build e digest immutabile realmente ottenuti.
3. Verificare la protezione dei log descritta sotto. Distribuire il digest
   compatibile **senza traffico**, con scritture v3 a 0, conservando identità,
   storage, risorse e App Check. Il traffico pubblico deve restare esplicitamente
   sulla baseline durante il controllo, senza affidarsi al selettore LATEST.
   Il tag non separa i dati: su questa revisione usare soltanto letture.
4. Controllare health (due protocolli, default legacy, v3 off), feed legacy/v3,
   CORS Android/Web e autenticazione reale. Eventuali operazioni sintetiche
   vanno esclusivamente su storage di validazione vuoto e separato, servizio
   privato e identità autorizzate. Nessun inizializzatore sul puntatore `current`.
   I test locali non sostituiscono il controllo della configurazione distribuita.
5. Portare al traffico la revisione compatibile con v3 ancora a 0 e conservarla
   come revisione pronta al rollback. Verificare letture dell'app già installata,
   errori di storage/App Check e i controlli autenticati realmente disponibili.
6. Abilitare v3 con lo **stesso digest compatibile**, cambiando soltanto il flag;
   verificare la nuova revisione prima di indirizzarvi il traffico. Solo dopo
   questo esito la Community è pronta per il test interno della 0.1.15 e per
   una Web aggiornata che invia il protocollo v3.
7. Generazione AAB, caricamento Play, installazione e prova personale end-to-end
   restano azioni distinte, non autorizzate da questa preparazione. Il gruppo
   Play con un solo tester non rende il backend privato: il backend pubblico
   continua a servire le app già installate e non limita v3 al solo tester.

### Privacy da completare nel rollout

Inventario letto il 20 ottobre: solo `_Default` e `_Required`, nessun parent
di progetto e nessuna esclusione HTTP Community. Il filtro di
`logging-exclusion.proposed.json` è **preparato, non applicato**.
Prima dell'attivazione pubblica va aggiunto al sink `_Default` preservando le
altre impostazioni; `_Required` instrada audit, non richieste Cloud Run, e non
va alterato. Ricontrollare l'inventario al momento dell'operazione.
La prova di propagazione deve conservare i controlli sui log applicativi e
le metriche aggregate; esito positivo dell'API non basta. Nessuna cancellazione
retroattiva prevista. Procedura completa: [Community log privacy](COMMUNITY_LOG_PRIVACY.md).

### Rollback compatibile

Prima di qualsiasi operazione v3 riuscita si può tornare alla baseline legacy,
senza riavvolgere lo storage. **Dopo una scrittura v3 non usare la vecchia
immagine**: riportare il traffico alla revisione compatibile con il flag a 0.
I vecchi client non aggiornati continuano con le proprie regole; i nuovi possono
leggere dati e ricevute ma ricevono `community_v3_rollout_pending` sulle nuove
scritture. Punti, segnalazioni e guardia contro il ritorno al protocollo legacy
restano conservati. Questo blocco è una misura temporanea, non il normale
stato in cui distribuire la 0.1.15.

## Limiti e prossima decisione

Preparazione locale completata. Il passaggio cloud sopra descritto, la verifica
della nuova revisione e il percorso reale Play Integrity della 0.1.15 restano
da eseguire. L'app pubblicata non è stata modificata o reinstallata; sono state
verificate le sue richieste in regressione e le letture pubbliche attuali.
Non si attribuisce a queste prove la chiusura del 503 isolato del 15 ottobre.
Alla chiusura della preparazione `main` e GitHub erano invariati. La successiva
verifica per la promozione locale è registrata sotto. Eventi, FCM, ICON e gli
altri lavori mantengono le proprie attestazioni e gli eventuali punti aperti separati.


## Ultimi controlli per la promozione locale su main

Il 20 ottobre il proprietario ha autorizzato la promozione locale, senza push
né operazioni di rilascio. Candidato ricontrollato:
`013f694649f5f3e372ac8b90d05806a3e1003a68`, discendente diretto della baseline
`5cbcd35ca88088220ff167b299cb4353ebdaf6d4`; non occorre risolvere conflitti.

Ripetuti con esito PASS: 173 test backend, 33 test del pacchetto isolato
(sottoinsieme), 3 test privacy, sintassi, pulizia, diff, hash dell'archivio e
byte delle evidenze salvate in Git. Le prove confermano le operazioni legacy,
la lettura dei gruppi misti e il blocco compatibile senza perdita di ricevute
oppure punti. Rimane il requisito di aggiornamento per votare un gruppo v3.

Nessuna differenza in `backend/app`, frontend, configurazione di produzione,
Dockerfile o dipendenze runtime rispetto a `main`. Il collaudo reale precedente
mantiene il proprio perimetro; nessuna nuova prova Android o cloud viene
attribuita a questa promozione di preparazione, script e regressioni.
L'archivio pronto resta quello del sorgente `05a4fcc6`, con hash invariato:
il commit documentale finale non richiede una nuova immagine.

[Attestazione dei controlli](../../release-history/community-preparation/0.1.15-20261020/promotion-checks.json).
Procedura autorizzata: fast-forward locale del ramo verificato su `main`,
poi verifica dei riferimenti e dello stato pulito. Il remote resta fermo e la CI
non viene avviata. La promozione non attiva v3 e non distribuisce il backend.
