# Monitor ICON-2I: collaudo cloud ridotto del 16 ottobre 2026

## Perimetro autorizzato

Creare solo le risorse necessarie al monitor, eseguire un avvio manuale e una
prova email. Nessuno scheduler attivato; nessuna modifica delle acquisizioni
esistenti. GitHub, CI e promozione a main esclusi.

Progetto `meteo-friul`, regione `europe-west1`.
Branch locale `codex/icon2i-freshness-monitor`.
Codice distribuito: `35b31aef93281880f3b5e8729d5a1061d7304389`.
Il collaudo non ha richiesto correzioni al codice.

## Risorse effettivamente create

- Una build manuale Cloud Build, con 53 file tracciati (8.049.674 byte prima
  della compressione), ricavati dalle dipendenze COPY del Dockerfile.
- Immagine nel repository Artifact Registry esistente `meteofriul`.
- Un solo job `meteofriul-icon2i-freshness`: 1 CPU, 512 MiB, un task,
  timeout 120 secondi, nessun retry. Argomenti predefiniti `--help`;
  il controllo richiede parametri espliciti per ogni avvio.
- Account `icon2i-freshness-monitor@meteo-friul.iam.gserviceaccount.com`.
- Tre ruoli personalizzati: `icon2iFreshnessDataRead`,
  `icon2iFreshnessStateWrite`, `icon2iFreshnessMetrics`.
- Tre descrittori di metrica e sei serie reali del monitor.
- Due oggetti nel bucket di stato esistente:
  `monitoring/icon2i-freshness/v1/fvg.json` e `national.json`.
- Una metrica sintetica separata e una sola policy temporanea per la prova email.

Il ruolo sui dati contiene solo `storage.objects.get/list`: lettura dei due
prefissi ICON-2I e lista dei nomi nel bucket. Le scritture dello stato sono
limitate ai due oggetti esatti; `storage.objects.delete` serve anche alla
sovrascrittura condizionale GCS. Il ruolo Monitoring contiene solo
`monitoring.timeSeries.create/list`.

Non creati: dispatcher, account Scheduler, scheduler, nuove risorse Storage,
policy operative definitive, dashboard o query salvate. Sono rinviati alla
successiva eventuale attivazione, secondo il perimetro ridotto concordato.

## Identita della build

Build: `c261aacd-841b-4327-b54b-7a4e71e46192`, esito `SUCCESS`.

Immagine distribuita, fissata per digest:

```
europe-west1-docker.pkg.dev/meteo-friul/meteofriul/icon2i-freshness@sha256:db0160d88a9397ca7789fe62750158dfb424212feb7e9f8abba6bfc1cbd5db80
```

La build include la label OCI del commit. Il sorgente minimo e stato caricato
sotto `gs://run-sources-meteo-friul-europe-west1/icon2i-freshness-collaudo/`.
Non sono stati caricati l'intero workspace, chiavi locali o artefatti Android.

## Avvio manuale: superato

Esecuzione: `meteofriul-icon2i-freshness-hxlg7`.

- Slot esplicito: **2026-10-16 05:40 UTC** (07:40 Europe/Rome).
- Creazione esecuzione: 05:41:04.761 UTC.
- Start registrato da Cloud Run: 05:41:09.072 UTC.
- Completamento: 05:41:50.385 UTC; durata riportata **41,31 secondi**.
- Un task riuscito, uscita 0; una sola esecuzione.
- Nei log `basis=manual_explicit`: l'orario dello slot resta distinto dall'avvio.

| Verifica | FVG | Nazionale |
|---|---|---|
| Run attivo | 20261015T120000Z | 20261015T120000Z |
| Eta del run | circa 17,70 ore | circa 17,70 ore |
| Campioni orari futuri nel manifesto | 55 | 55 |
| Oggetti referenziati verificati tramite metadati | 216 | 644 |
| Puntatore HTTP rispetto a Storage | coerente | coerente |
| Resolver Roma, ISTAT 058091 | non applicabile | coerente |
| Esito | regolare | regolare |
| Invio delle tre metriche | tutte confermate | tutte confermate |

Le sei serie sono state rilette da Cloud Monitoring: una sola osservazione
per serie, con risorsa `global` e sola label metrica `product`. Valori:
`check_state=0`, `critical_active=0`, `check_completed=1` per entrambi i prodotti.
I log sono presenti in `jsonPayload`, compresi slot, cause e confronti HTTP.
Gli aggiornamenti condizionali dei due stati sono riusciti con l'account dedicato.

I 55 campioni sono quelli del manifesto, non il numero mostrato dal frontend.
Alla prima osservazione `publication_time_verified=false`: il monitor non
inventa la data dell'ultima nuova pubblicazione. Questo segnale si inizializza
osservando una successiva pubblicazione nuova. L'eta del run e gia misurabile.

## Prova email

Destinazione: canale esistente `info@meteofriul.it`, non modificato.
Titolo: **PROVA EMAIL - monitor ICON2I - collaudo 2026-10-16**.

Metrica isolata: `custom.googleapis.com/meteofriul/icon2i_collaudo/email_probe`.
Policy: `17329223989625799110`.
Incidente: `0.odvt3g7mi5vv`.

- Valore sintetico 1 scritto alle 05:42:33.056 UTC.
- Query PromQL verificata sul servizio Google: restituisce 1.
- Incidente aperto alle **05:45:06 UTC** (07:45:06 italiane).
- Valore riportato a 0 alle 05:47:07.704 UTC.
- Conferma di ricezione nella casella: **ricevuta**, confermata dal titolare in chat.
- Policy temporanea **disabilitata**, verificato `enabled=false`.
- All'ultima lettura l'incidente risultava ancora `OPEN`, mentre la query dopo il valore 0 non era piu violata. La chiusura automatica dell'incidente non e certificata da questo collaudo ridotto.

La ricezione e attestata dal riscontro del titolare, oltre all'apertura dell'incidente.
La prova usa dati sintetici distinti dalle sei serie operative.

## Controllo del perimetro

Confronto prima/dopo: gli 11 job e i servizi preesistenti sono invariati;
i 10 scheduler preesistenti e le 18 policy preesistenti sono invariati.
Le assegnazioni IAM precedenti di progetto e bucket sono state preservate:
sono aggiunte solo quelle del nuovo account del monitor.
Nessun dato previsionale, reader o acquisizione e stato modificato.

## Limiti e prossimo passo

Questo e il collaudo ridotto, non l'attivazione del monitor periodico.
Non verifica la consegna reale degli header da Cloud Scheduler, il dispatcher,
i casi di assenza a 90/120 minuti o due settimane di osservazione.
Le prove locali precedenti su ritardi e duplicati restano quelle gia registrate.

Non e disponibile ancora un importo fatturato definitivo: il lavoro comprende
una build breve e un solo task. L'ordine di grandezza previsto resta di pochi
centesimi per il collaudo, oltre alla conservazione dell'immagine; non e un
consuntivo della fatturazione.

Evidenze strutturate: [JSON del collaudo](ICON2I_FRESHNESS_MONITOR_CLOUD_COLLAUDO_20261016.json).

## Stato finale

**Avvio manuale e prova email superati.** Il job e predisposto ma non pianificato;
le policy operative definitive non sono attive. La regola della prova e disabilitata.
Nessun servizio dispatcher o scheduler del monitor e stato creato.
Ultimo controllo risorse: `2026-10-16T05:52:23.786616Z`.

## Riscontro successivo prima dell'attivazione

Alla lettura del 16 ottobre 2026, ore 06:46 UTC, l'incidente della prova
email risulta `CLOSED`, con `closeTime=2026-10-16T05:53:49Z`.
Questo aggiorna il solo riscontro ancora aperto alla chiusura del collaudo.
