# Verifica locale del monitor ICON-2I con il main aggiornato

> **Stato successivo: riallineamento pubblico del 16 ottobre 2026.** Le sezioni
> sottostanti conservano le verifiche storiche sulle rispettive basi. La nuova
> candidata recupera il main approvato completo, inclusa CAMS a 36 ore, e mantiene
> le correzioni delle dipendenze. Sono stati ripetuti 207 test del monitor e dei
> contratti condivisi, senza errori o skip e con promtool reale. Nessun nuovo
> deploy o collaudo Android. Vedere il [rapporto corrente](PUBLIC_REPOSITORY_ALIGNMENT_2026-10-16.txt).

## Aggiornamento per il main ricostruito — 16 ottobre 2026, 10:25 UTC

**Esito sulla nuova base: 170 test superati, nessun errore e nessuno skip**, incluso promtool reale. Il codice del monitor rimane identico alla versione precedentemente verificata.

Dopo la verifica delle 09:52 UTC, `main` è stato ricostruito come snapshot pubblico con una storia Git separata. La nuova base della promozione locale è **`a70d3c68c8ee21f8d7938e931d5443af15574248`** (`Initial public snapshot of verified Meteo Friul main`). Al controllo locale anche `origin/main` memorizzato punta a questo SHA; non è stato eseguito un fetch.

Per mantenere il perimetro richiesto sono stati trasferiti soltanto i **25 file** del monitor e dei suoi rapporti da `835c2a66a0839310a78dbb3a9cc923e2b5814d2d`, sul ramo locale `codex/icon2i-monitor-public-main`, derivato dalla nuova base. Non è stata importata la vecchia storia Git. Dei 25 file, solo questo rapporto è aggiornato con la presente nota; gli altri 24 sono identici alla versione già verificata.

Il delta rispetto alla nuova base contiene esclusivamente aggiunte: nessun file preesistente di `main` viene modificato o eliminato. Restano quindi invariati le acquisizioni, i reader esistenti, la UI, Android e i workflow CI. Le modifiche CAMS presenti nel precedente `main` e assenti nello snapshot pubblico non fanno parte di questa consegna.

### Verifiche ripetute sulla nuova base

| Gruppo | Esito | Durata |
| --- | --- | ---: |
| Monitor, definizioni, pacchetto, dispatcher | 65/65, zero skip | 13,785 s |
| Contratti e reader regionali/nazionali | 105/105, zero skip | 86,766 s |

La prima suite include le quattro simulazioni e 17 valutazioni PromQL eseguite tramite **promtool 3.5.0**. L'eseguibile è lo stesso verificato in precedenza, con SHA-256 nuovamente controllato. Python 3.13.5, `-B` e `ICON2I_MONITOR_ALLOW_CLOUD=0`; prove locali e simulate, senza acquisizioni operative.

La seconda suite usa questi moduli, tutti già presenti nella nuova base:

```powershell
python -B -m unittest test_contract_v1 test_published_runs_reader test_http_data_plane test_serve_published_contract_v1 test_serve_national_bundle_v2 test_national_icon_bundle test_national_cloud test_cloud_reader -v
```

Il comando della suite monitor è quello riportato nella verifica precedente. La suite estesa da 142 test delle 09:52 UTC resta un'evidenza riferita alla vecchia base: non viene attribuita allo snapshot pubblico, che non contiene le successive estensioni CAMS.

Log nella cartella temporanea indicata più avanti:

| File | SHA-256 |
| --- | --- |
| `public-main-monitor-tests.log` | `63ee391bb53aa2e36b15ef28299d2ceb8e95e03dd647af3231319ec4d887bca9` |
| `public-main-readers-tests.log` | `9a25898c1fa4ccd0aa7f41193d1969c1bbabfd0ede85869e29572b98d8c8ac13` |

Verificati anche la pulizia canonica, il diff e l'identità dei file trasferiti. Questo aggiornamento documenta la validazione per la promozione sul nuovo `main` locale. Push, CI, deploy e modifiche cloud restano esclusi dalla richiesta.

## Verifica precedente sulla base 2f931e49 — evidenza storica

**Quanto segue conserva il rapporto delle 09:52 UTC.** Gli SHA e le indicazioni su `main` invariato, sulla promozione non ancora eseguita e sui 98 commit rispetto al vecchio `origin/main` descrivono quella fase, non lo stato del nuovo snapshot pubblico.

Verifica completata il **16 ottobre 2026**, risultati riletti alle **09:52 UTC**.

**Esito: compatibilità locale verificata.** Integrazione senza conflitti e **207 test superati, zero errori e zero skip**, incluso il test PromQL con un eseguibile `promtool` reale. Non sono state necessarie correzioni al codice.

## Base e isolamento

| Riferimento | SHA verificato |
| --- | --- |
| `main` locale all'inizio e alla fine delle prove | `2f931e49074b7576748b06adac765adf42f5e8e4` |
| `codex/icon2i-freshness-monitor`, invariato | `4a69a3386ae70b0c05e602fc6ea75bcad838176f` |
| Base comune dei due rami | `31cca1035eb7548617bdc2875c190e0a15e9f9c8` |
| Commit locale di integrazione sottoposto ai test | `bf654f4c7cf6cd7b4b9a7e35b41b5f4e8ab2fa2f` |
| Albero Git del commit sottoposto ai test | `6bc6d6f0f773ab12857a691eef34f22aba4a11fa` |

Worktree dedicato: `C:\Users\LOCAL_USER\.codex\worktrees\icon2i-monitor-main-verification\meteo FRIUL`.

Ramo di verifica: `codex/icon2i-monitor-main-verification`. Il commit di integrazione ha come primo genitore il `main` locale indicato e come secondo il ramo del monitor indicato. La promozione a `main` non è stata eseguita.

Controlli sul contenuto:

- I due rami avevano quattro commit esclusivi di `main` e cinque esclusivi del monitor.
- Nessun percorso modificato dai quattro commit di `main` coincide con quelli aggiunti dal monitor.
- Il commit di integrazione aggiunge a `main` **24 file**, senza modificare o cancellare alcun file già presente in quella base.
- Tutti i 24 file del monitor risultano identici al ramo originale.
- I due worktree originali, di `main` e del monitor, risultano puliti. I relativi riferimenti non sono stati spostati.
- `git diff --check` e `scripts/test-canonical-workspace-cleanliness.ps1` superati. La pulizia è stata verificata prima sulla base, poi sull'integrazione.

Questo rapporto viene aggiunto dopo le prove sul solo ramo di verifica; non cambia il codice sottoposto ai test.

## Prove eseguite

Ambiente: Windows, Python **3.13.5**, bytecode disabilitato con `-B`, `ICON2I_MONITOR_ALLOW_CLOUD=0`. Dati sintetici, archivi temporanei, trasporti simulati e HTTP su loopback; nessuna acquisizione meteo operativa.

| Gruppo | Test superati | Durata |
| --- | ---: | ---: |
| Monitor, definizioni, pacchetto e dispatcher | 65 | 13,857 s |
| Contratti, reader e compatibilità con il main aggiornato | 142 | 942,113 s |
| Totale | **207** | **955,970 s** |

Il primo gruppo comprende età e copertura del run, pubblicazione invariata, indeterminati, conservazione del critico, confronti HTTP/Storage, comportamento `no-cache`, percorso nazionale `resolve.json`, ritardi, duplicati, scritture parziali e incerte, slot UTC e ora legale. Verificate anche le definizioni delle email `OPENED`/`CLOSED` e la corrispondenza dei JSON versionati.

La prova del pacchetto copia la selezione di sorgenti prevista dal Dockerfile in una cartella temporanea e verifica import, cataloghi e avvii sicuri dei due entrypoint. Non costruisce una nuova immagine Docker.

La suite condivisa comprende:

| Modulo | Test |
| --- | ---: |
| `test_contract_v1` | 10 |
| `test_contract_publisher` | 26 |
| `test_published_runs_reader` | 31 |
| `test_http_data_plane` | 15 |
| `test_serve_published_contract_v1` | 5 |
| `test_serve_national_bundle_v2` | 7 |
| `test_national_icon_bundle` | 17 |
| `test_national_cloud` | 16 |
| `test_cloud_reader` | 4 |
| `test_cams_continuity` | 10 |
| `test_production_runtime_contract` | 1 |

Le prove CAMS sono incluse perché il `main` aggiornato modifica `contract_publisher.py`, `published_runs_reader.py` e `http_data_plane.py` e aggiunge `cams_continuity.py` nel pacchetto condiviso. Le funzioni di pubblicazione vengono esercitate soltanto su archivi locali e simulati.

## Promtool

Eseguibile ufficiale **promtool 3.5.0, Windows/amd64**, revisione `8be3a9560fbdd18a94dedec4b747c35178177202`, scaricato dalla [release ufficiale Prometheus 3.5.0](https://github.com/prometheus/prometheus/releases/tag/v3.5.0).

Archivio `prometheus-3.5.0.windows-amd64.zip`, SHA-256 verificato sia rispetto al digest della release sia rispetto al suo `sha256sums.txt` e al valore già documentato:

```text
b3c2607d1e80a277735fd3cde86432eb1b6843897cb82fb04fbf4c7ffb1d1c36
```

SHA-256 dell'eseguibile estratto:

```text
626674d5a047f2fd862a9c8678596b890a6824c76d31c33bcd6af93c1e3429d9
```

Il test `test_real_promql_windows_absence_bootstrap_and_recovery` è stato eseguito, senza skip, tramite `promtool test rules`: **quattro scenari e 17 valutazioni PromQL**, tutti riusciti.

- Critico seguito da arresto del monitor: controlli a 89, 90, 119 e 120 minuti, con sovrapposizione delle finestre dati/telemetria.
- Nuovo valore zero: rientro normale senza attendere 120 minuti.
- Assenza di una serie di stato anche con heartbeat presente.
- Bootstrap senza alcuna telemetria.

Sono prove della semantica PromQL locale; non misurano la cadenza reale di valutazione di Cloud Monitoring né la consegna delle email.

## Comandi e log

Comandi eseguiti da `experiments/weather_autonomy` nel worktree di verifica, usando l'interprete Python sopra indicato:

```powershell
$env:PROMTOOL = 'C:\Users\LOCAL_USER\AppData\Local\Temp\meteofriul-promtool-7f68d5a886a344e69b8b4268ffcff5f0\promtool.exe'
$env:ICON2I_MONITOR_ALLOW_CLOUD = '0'
$env:PYTHONDONTWRITEBYTECODE = '1'
python -B -m unittest test_freshness_monitor test_freshness_monitor_policies test_freshness_monitor_package test_freshness_monitor_dispatcher -v
python -B -m unittest test_contract_v1 test_contract_publisher test_published_runs_reader test_http_data_plane test_serve_published_contract_v1 test_serve_national_bundle_v2 test_national_icon_bundle test_national_cloud test_cloud_reader test_cams_continuity test_production_runtime_contract -v
```

Log completi conservati nella stessa cartella temporanea di `promtool`, fuori dal repository. Non sono una conservazione permanente: la cartella temporanea può essere rimossa dal sistema.

| File | SHA-256 |
| --- | --- |
| `monitor-tests.log` | `106562ba0dd3416531eebb3701e567968a8f1350a4e9b47c08a13a4dbebdb7d4` |
| `shared-tests.log` | `45e490bbe0a2c2064a59b9a1c6f991946c7718fb75609162f0e119e0b01460a4` |

## Perimetro dell'esito

Non sono emersi impedimenti locali all'integrazione del monitor con lo specifico `main` verificato. Non sono stati eseguiti push, PR, CI, deploy, modifiche cloud o cambiamenti alle acquisizioni. Nessuna build Android o installazione su dispositivo.

L'allineamento di `main` su GitHub resta un'operazione distinta. La verifica usa il `main` locale, non `origin/main`; il riferimento remoto memorizzato localmente risulta indietro di 98 commit, ma non è stato aggiornato con un fetch in questo collaudo. Nessun esito qui autorizza o certifica una futura promozione remota o un nuovo deploy.

Le precedenti prove cloud ed email restano descritte nel [rapporto di attivazione](ICON2I_FRESHNESS_MONITOR_ACTIVATION_20261016.md); non sono state ripetute in questa verifica locale.
