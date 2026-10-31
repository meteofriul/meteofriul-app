# Audit costi e riuso dei dati — 31 ottobre 2026

Audit richiesto dal proprietario prima di attivare i recuperi ICON. Sono state
eseguite esclusivamente letture cloud e analisi locali: nessun job avviato,
nessuna modifica di Scheduler, risorse, policy, credenziali, deploy o codice.
Questo verbale descrive l'audit precedente all'ottimizzazione. Il successivo
[riuso della verifica FVG](ICON_VERIFICATION_REUSE_20261031.md) è incluso nel
candidato `codex/icon-automatic-recovery-20261031`, con salvataggio e PR
autorizzati. Le prove originarie rimangono datate e l'attivazione cloud separata.

## Risultato

Il numero attuale di job è compatibile con un carico piccolo. Non emerge un
motivo economico per accorpare tutte le funzioni o ridurre indiscriminatamente
allerte e controlli. Il primo intervento consigliato è eliminare le verifiche
complete ripetute nello stesso worker FVG. Un gate leggero comune può essere
una fase successiva, giustificata anche da semplicità operativa e affidabilità;
il solo risparmio stimato dei recuperi non giustifica una grande riscrittura.

I JSON sono già usati per dati, manifest, puntatori e checkpoint. Conviene
leggere un indice piccolo prima di avviare lavoro pesante, mantenendo una prova
di verifica associata alla versione dei dati e una scadenza. Non basta che il
file esista: il monitor deve ancora riconoscere dati vecchi o incompleti.

## Osservazioni e perimetro

- Configurazione riletta: **14 istanze di job, 11 Scheduler abilitati, 6 servizi
  HTTP** nelle due regioni pertinenti. Tre job sono storici/QA, senza avvii
  nella settimana analizzata. Il loro semplice mantenimento non equivale a
  una macchina accesa continuamente.
- Giornata ordinaria di 24 ore: **120 invocazioni programmate**, prima dei
  recuperi proposti. Il cambio d'ora può modificare il numero effettivo.
- Sette finestre complete: **24 ottobre 16:47:51 UTC–31 ottobre 16:47:51 UTC**.
  Osservate **845 esecuzioni, 848 tentativi**; risorse costanti per ogni job.
  I tre retry aggiuntivi riguardano ICON FVG e sono confermati dai metadati
  dei due task interessati.
- Le metriche sono aggregate per risorsa, senza contenuti di utenti. Nessun
  elenco è troncato nelle raccolte usate. I conteggi HTTP hanno sette finestre
  proprie, spostate di 185,176 secondi; lo scarto è esplicitato nel modello.
- Archivio Storage osservato: **26,33 GiB**, includendo soft delete;
  repository immagini: **3,954 GiB**. Sono fotografie, non integrali mensili.

| Funzione | Avvii programmati al giorno |
| --- | ---: |
| Monitor freschezza ICON | 48 |
| Avvisi locali | 24 |
| Sync allerte FVG, sync nazionale e invio nazionale | 36 |
| CAMS | 5 |
| ICON FVG e nazionale | 4 |
| Sintesi mattino e sera | 2 |
| Eventi | 1 |

Il monitor aggiunge anche una richiesta HTTP al proprio dispatcher per ogni
avvio. Non è un'acquisizione completa: controlla metadati e risultati pubblici.
Gli esiti `no_candidate` degli avvisi non dimostrano uno spreco: l'esito negativo
può essere precisamente il risultato atteso del controllo.

## Modello economico, non fattura

Importi **USD a listino, prima di franchigie condivise, crediti, sconti, imposte
e conversione valutaria**. Proiezione del ritmo osservato su 30 giorni;
Scheduler usa il riferimento tariffario di 31 giorni.

| Componente analizzata | Stima di riferimento |
| --- | ---: |
| Compute dei job, tenendo conto del minimo per tentativo | 4,88–6,43 USD / 30 giorni |
| Compute dei sei servizi HTTP e richieste | 3,08 USD / 30 giorni |
| Storage, a dimensioni costanti della fotografia | 0,54 USD / mese |
| Operazioni Storage riuscite classificabili | 0,91 USD / 30 giorni |
| Conservazione immagini, a dimensione costante | 0,40 USD / mese prima della quota gratuita |
| 11 Scheduler | 1,10 USD / 31 giorni; 0,80 se tutte le tre quote gratuite sono disponibili |

Il riferimento parziale è circa **10,91–12,46 USD**, usando Scheduler al lordo.
**Non è il totale del progetto, la fattura o un tetto di spesa.** Non sommiamo
franchigie come se ciascun job/progetto avesse una quota gratuita autonoma.

I job hanno un minimo di un minuto per istanza. La metrica osservata per il
monitor, circa 6.071 secondi in 336 esecuzioni, è inferiore a 336 minuti: usarla
direttamente come importo fatturabile sottostimerebbe il minimo. Per ciascun
job, con tempo osservato S e tentativi A, il modello condizionale applica
`max(S, 60*A) ≤ tempo con minimi ≤ S + 60*A`, assumendo telemetria completa
e risorse omogenee. I servizi usano invece direttamente vCPU-secondi e
GiB-secondi allocati, senza moltiplicare nuovamente per CPU o RAM.
[Prezzi e semantica Cloud Run](https://cloud.google.com/run/pricing);
[Tier 1 per Belgio e Milano](https://docs.cloud.google.com/run/docs/locations).

Lo Scheduler si paga per definizione, non per ogni esecuzione: cambiare il cron
dei due Scheduler esistenti non crea dodici nuovi Scheduler a pagamento.
[Prezzi Scheduler](https://cloud.google.com/scheduler/pricing).
Per gli archivi sono distinti spazio, operazioni e traffico;
[Storage](https://cloud.google.com/storage/pricing) e
[Artifact Registry](https://cloud.google.com/artifact-registry/pricing).

Le metriche dal 1 ottobre mostrano circa 0,142 GiB di log ingeriti, 112.212
letture e 14.867 scritture documentali Firestore. Non provano da sole l'addebito
effettivo, le letture di indici o l'idoneità alle quote gratuite. Il listino
inglese corrente rinvia la tariffazione delle referenze metriche nelle policy
al non prima del 1 settembre 2027; non è stata imputata una tariffa 2026
basandosi su risultati localizzati obsoleti.
[Logging e Monitoring](https://cloud.google.com/products/observability/pricing);
[Firestore](https://cloud.google.com/firestore/pricing).

## Quanto aggiungerebbero i recuperi ICON

Il piano aggiunge dodici avvii al giorno, sei FVG e sei nazionali, conservando
1 vCPU con rispettivamente 1 e 2 GiB. Non cambia il numero di acquisizioni
complete quando il ciclo è già pubblicato.

| Durata ipotizzata di ogni tentativo aggiunto | Solo compute aggiuntivo, 30 giorni |
| --- | ---: |
| Entro il minuto minimo | 0,45 USD |
| Tre minuti | 1,36 USD |
| Cinque minuti | 2,27 USD |

Sono scenari, non misure della nuova implementazione. Escludono retry,
operazioni Storage, rete e variazioni del lavoro di pubblicazione. Il nuovo
codice non è distribuito. Le franchigie possono ridurre il costo marginale,
ma non è stato verificato quanto sia già consumato nello stesso account.

## Sprechi concreti e alternative

L'analisi statica precedente all'ottimizzazione identifica:

- **FVG:** in un `no_op` con owner `completed`, tre verifiche complete di 215
  documenti, cioè 645 corpi JSON oltre a manifest e puntatori. Ogni `get` GCS
  usa metadati e download. I retry del task riusano il ticket di discovery,
  ma ripetono le letture iniziali del pubblicato.
- **Nazionale:** una verifica del bundle completo a ogni nuova invocazione.
  La cache già presente evita la ripetizione interna sullo stesso manifest
  e viene invalidata dopo pubblicazione per il readback finale.
- **CAMS:** stato e preparazione sono persistenti, ma una famiglia esistente
  comporta la verifica di 430 documenti comunali. Il recupero può ripristinare
  il GRIB prima di cercare la preparazione JSON completa.
- **Acquisizione ICON:** FVG e nazionale scaricano e decodificano separatamente
  gli stessi 14 GRIB del provider. La condivisione futura deve conservare
  metadati, punti/griglia e prove richieste dai due prodotti; il solo JSON
  pubblico nazionale non sostituisce automaticamente l'input FVG.

Riferimenti principali: `cloud_worker.py::_run_icon_automatic`,
`local_pipeline/icon_recovery.py::Recovery.run`,
`local_pipeline/contract_publisher.py::read_verified_latest/read_latest_if_etag`,
`national_cloud_worker.py::run_automatic`, `national_cloud_publication.py::load_run`,
`retrieve_remote_cams.py`, `publish_remote_cams.py`, `freshness_monitor/collect.py`.
Tutti sotto `experiments/weather_autonomy/`.

| Alternativa | Valutazione |
| --- | --- |
| Riusare nella stessa invocazione la verifica FVG, legandola alla generazione del puntatore | **Preparato e verificato dopo l'audit:** 645 → 215 letture comunali nel caso senza aggiornamento; verifica finale dopo pubblicazione preservata |
| Piccolo indice JSON privato con ciclo, manifest verificato, generazione, scadenza e stato per prodotto | Utile per evitare letture complete ripetute. Aggiornamenti condizionali e invalidazione su variazioni; la sola data di controllo non basta |
| Probe comune leggero che avvia solo i prodotti da aggiornare | Utile come seconda fase per evitare avvii dei worker pesanti. Richiede dispatch durevole, permessi limitati e riconciliazione delle risposte perse |
| Unica acquisizione interna da cui derivare FVG e nazionale | Potenziale risparmio di download/decodifica, ma maggiore lavoro e accoppiamento; progetto separato |
| Eliminare il monitor o accorpare tutte le funzioni in un unico job | Sconsigliato: risparmio limitato e perdita di isolamento/controllo indipendente |
| Sostituire tutto con eventi Storage | Non risolve da solo la scoperta del nuovo ciclo del provider: nel repository non esiste un evento in ingresso da ItaliaMeteo |

Per questo scopo non emerge la necessità di introdurre un nuovo database.
Cloud Storage è già durevole e supporta scritture condizionali; un file sul
disco temporaneo del container non sarebbe equivalente. Un servizio pubblico
di lettura non deve ricevere automaticamente privilegi di avvio dei job.

## Limiti e verifica

L'API Cloud Billing del progetto restituisce `SERVICE_DISABLED`; non è stata
abilitata. La ricerca di dataset BigQuery nel progetto è riuscita ma non ne
ha trovati; non certifica assenza di export in altri progetti. Il browser di
controllo non era disponibile. Rimangono quindi non verificabili fattura,
crediti, sconti, valuta effettiva e allocazione delle franchigie dell'account.

Il modello non valorizza completamente trasferimenti per destinazione,
Cloud Build, scansioni immagini, hosting Firebase, Actions o fornitori esterni.
Il traffico Storage non va trattato interamente come egress Internet: il
traffico nella stessa regione e quello verso Internet hanno condizioni diverse.
Le due regioni dei job con lo stesso nome restano distinte nei calcoli.

Verifica indipendente del profilo nativo `build_verifica`: **212 confronti
numerici/hash PASS**. Sono stati corretti prima della chiusura il conteggio
effettivo dei retry e l'allineamento della finestra delle richieste HTTP.
[Modello, fonti e dati derivati](evidence/JOBS_COST_AUDIT_20261031.json).
[Ricevuta della verifica indipendente](evidence/JOBS_COST_AUDIT_VERIFICATION_20261031.json).
Raccolte grezze sanificate e helper: `.tmp/jobs-cost-audit-20261031/` nella
radice canonica. Non sono state avviate nuove prove di produzione.

Seguito autorizzato: [ottimizzazione locale del riuso FVG e prove](ICON_VERIFICATION_REUSE_20261031.md)
e [indice dei report degli altri servizi](APP_SERVICE_REPORT_COVERAGE_20261031.md).
Il controllo operativo e di costo della nuova versione rimane successivo
all'eventuale attivazione autorizzata. Nessuna alternativa è stata distribuita.
