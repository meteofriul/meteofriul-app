# Meteo Friul - Audit automazioni produttive

Data audit: 2026-08-11
Aggiornamento: 2026-08-19
Stato: inventario completo verificato dopo il cutover UI3

## Perimetro

L'audit comprende le automazioni che possono modificare codice, Firebase
Hosting, Firestore, notifiche o stato applicativo:

- GitHub Actions della nuova repository `meteofriul/meteofriul-app`;
- GitHub Actions dell'allora repository storica
  `meteofriul/meteofriul-1.0.1`, rimossa da GitHub il 19 agosto 2026;
- Cloud Scheduler del progetto Google Cloud `meteo-friul`;
- canali temporanei Firebase Hosting usati per collaudo e rollback.

Al momento dell'audit non risultano workflow GitHub in coda o in esecuzione.

## Nuova repository

| Workflow | Stato | Trigger | Effetto |
| --- | --- | --- | --- |
| `CI` | Attivo | Push su `main`, pull request | Test, lint e build; sola lettura del repository |
| `Sync official FVG alerts` | Attivo | Solo avvio manuale | Legge la fonte ufficiale e salva in Firestore uno stato confermato |

Nella nuova repository non esistono workflow pianificati. La sincronizzazione
delle allerte non ha un trigger `schedule` e non parte automaticamente.

## Repository storica (rimossa da GitHub)

| Workflow | Stato GitHub | Trigger dichiarati | Decisione |
| --- | --- | --- | --- |
| `Update webcam JSON` | `disabled_manually` | Pianificato, push, pull request, manuale | Non riattivare: aggiorna file e ridistribuisce il vecchio Hosting |
| `Sync official FVG alerts` | `disabled_manually` | Pianificato e manuale | Non riattivare: usa il flusso legacy |
| `Send local weather notices` | `disabled_manually` | Solo manuale | Riattivare solo dentro una futura migrazione push approvata |
| `Send manual app notice` | `disabled_manually` | Solo manuale | Riattivare solo dentro una futura migrazione push approvata |
| `Dependency Graph` | Attivo | Gestito da GitHub | Nessun deploy e nessuna scrittura sul runtime |

Tutti e quattro i workflow applicativi legacy sono disattivati manualmente.
Resta attivo soltanto il Dependency Graph gestito da GitHub, che non esegue
deploy e non modifica lo stato dell'app. Android e push saranno progettati e
approvati separatamente, senza riattivare implicitamente questi flussi.

Il repository remoto e' stato eliminato il 19 agosto 2026 dopo un fetch
completo e la verifica di bundle, ripristino mirror, modifiche non committate e
metadati GitHub. La copia locale e l'archivio verificato restano disponibili;
nessuno dei workflow elencati puo' quindi essere eseguito da GitHub.

## Cloud Scheduler

Sono state enumerate tutte le regioni supportate dal progetto. Esistono solo
questi due job, entrambi in `europe-west1` ed entrambi sospesi:

| Job | Stato | Pianificazione legacy | Destinazione |
| --- | --- | --- | --- |
| `push-official-alerts-check` | `PAUSED` | Ogni 15 minuti | `/api/push/alerts/check` |
| `push-local-weather-check` | `PAUSED` | Minuti 7 e 37 di ogni ora | `/api/push/local-weather/check` |

I job restano sospesi durante la stabilizzazione. Non vanno riattivati: le
route push non appartengono ancora al contratto UI3. La cancellazione avverra'
solo dopo una decisione esplicita sulla futura architettura push.

## Rollback Firebase Hosting

| Canale | Versione | Scadenza |
| --- | --- | --- |
| `pre-ui3` | `74767fe006a3d7b5` | 26 agosto 2026, 20:58 CEST |
| `ui3-beta` | `4da1ae23ee87b142` | 18 agosto 2026 |

L'11 agosto e' stato esteso soltanto il TTL di `pre-ui3`. Versione, file e
rewrite sono rimasti invariati; il canale continua a puntare al tag API
legacy stabile `ui3-71f9d49`.

## Finestra di stabilizzazione

- osservazione intensiva: dall'11 al 17 agosto 2026 compreso;
- verifica formale: 18 agosto 2026;
- riserva tecnica del rollback: fino al 26 agosto 2026;
- cancellazione di `pre-ui3`: solo dopo decisione esplicita, mai per semplice
  decorrenza non controllata.

La verifica del 18 agosto deve confermare CI, route essenziali, Firestore,
fonti meteo, Eventi, radar, webcam e assenza di deploy legacy inattesi.

## Protezione di main

La protezione remota e i repository ruleset sono stati richiesti a GitHub ma
la piattaforma ha risposto `403`: sulla repository privata il piano corrente
richiede GitHub Pro. Rendere pubblico il codice non e' una soluzione
accettabile.

Come misura compensativa temporanea il repository contiene:

- `.githooks/pre-push`, che blocca i push locali diretti verso `main`;
- `scripts/install-git-guardrails.ps1`, che attiva il percorso hook versionato.

Il controllo locale non equivale alla protezione server-side. Prima di
aggiungere altri collaboratori o automatizzare deploy da `main`, occorre
abilitare GitHub Pro e configurare almeno pull request obbligatoria, CI verde,
blocco force-push e blocco cancellazione del branch.

## Revisione API usata da Hosting

Il rewrite Firebase Hosting continua a usare il tag stabile
`ui3-clean-1530ad0`, ma dall'11 agosto alle 21:35 circa il tag punta alla
revisione `meteofriul-api-ui3-hotfix-643096d`.

**Attenzione al nome del tag:** `ui3-clean-1530ad0` e' rimasto invariato per
non modificare il rewrite durante la stabilizzazione, ma non identifica piu'
la revisione omonima. Ogni verifica operativa deve risolvere il tag alla
revisione effettiva e non inferirla dal nome. Dopo la verifica formale del 18
agosto si valutera' se introdurre un tag allineato alla revisione, aggiornando
il rewrite e ripetendo lo smoke test.

La revisione e' stata costruita e provata a traffico zero. Il traffico Cloud
Run non taggato resta al 100% sulla revisione legacy
`meteofriul-api-00068-n7k`; nessuna automazione e' stata riattivata durante il
passaggio del tag. La configurazione UI3 corrente limita la concorrenza a 16 e
consente al massimo 5 istanze.
# Operazioni Cloud Run consolidate (2026-09-26)

- `meteofriul-cams-refresh`: `0 15,20 * * *`, fuso `Etc/UTC`;
- `meteofriul-national-official-alert-sync`: `15 */2 * * *`, fuso
  `Europe/Rome`, push disabilitato per contratto;
- tutti i job pianificati hanno una policy Cloud Monitoring dichiarata in
  `scripts/cloud-run-job-monitoring-policies.json`;
- il circuito DPC nazionale e quello OSMER/FVG restano separati.
