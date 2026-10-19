# Tolleranze ICON-2I: fase 01 pubblicata e verifica nazionale

Data: 19 ottobre 2026. Fase 01 completata su autorizzazione del proprietario:
lettore HTTP aggiornato, immagine di rollback compatibile pronta. Nessun nuovo
produttore o consumatore di avvisi attivato in questa fase. Alla sua chiusura
le fasi 02/03 erano ancora da autorizzare. Lo stato successivo è nel
[verbale della fase 03](ICON2I_TOLERANCE_PHASE3_DEPLOY_20261019.md).
Questo verbale integra il [piano coordinato](ICON2I_COORDINATED_ROLLOUT_20261019.md)
e la [compatibilità delle app installate](ICON2I_INSTALLED_APP_COMPATIBILITY_20261019.md).

## Identità della distribuzione

- Main verificato: `5e04343a27716c9c42a65d2a45aea0f628bbb9d8`.
- Sorgente effettiva: BASE `8497e773b1613312bb952236d72c074e22a7b1c6`
  più la sola patch 01 verificata contro main. Non è l'intero albero main.
- Patch SHA-256: `7e26e3b74c32da97387369cec2c1abaff60f3c78935db0bf7d126e1e14cd1f83`.
- Build Cloud Build: `fe6628ff-515b-4275-85ee-a3c70fc1a3b0`, esito SUCCESS.
- Immagine: `europe-west1-docker.pkg.dev/meteo-friul/meteofriul/weather-worker@sha256:3be1d207321e8ea0cee07466c9ac29fcec230ba4e10b3267647fa8f0cb2315a6`.
- Tag conservato: `icon-tolerance-readers-20261019-5e04343a`.
- Progetto `meteo-friul`, account `meteofriul@gmail.com`, regione `europe-west1`.
- Revisione HTTP: `meteofriul-weather-tol1-20261019`, creata alle 17:36 UTC;
  traffico portato al 100% dopo verifica della candidata, circa 17:41 UTC.
- URL app invariato: `https://meteofriul-weather-49007668366.europe-west1.run.app`.
  Il tag diagnostico `tolerance-phase1` resta associato alla stessa revisione.

## Controlli e risultati

| Controllo | Evidenza |
| --- | --- |
| Immagine effettivamente distribuita | 50 test passati nel container, rete disabilitata e socket bloccati; 99,846 secondi. |
| Scrittori di fase 01 | `cloud_worker.py`, `run_pilot.py`, materializzatore identici alla BASE. Il worker continua a scrivere schema 1; il lettore accetta checkpoint 1/2. |
| Vecchie app FVG | Lettori originali `2f02c8ba` (versione 0.1.14) e `8497e773`: 215/215 documenti accettati. Estensione pubblica incompatibile correttamente rifiutata dai vecchi lettori. |
| Candidata HTTP | Scaricati/verificati tutti i 215 documenti, hash e dimensioni coerenti. Corsa `20261019T000000Z`. |
| URL pubblico dopo il passaggio | Manifest invariato; Pordenone, Udine e Gradisca riscaricati e identici al prima. Gli altri 212 documenti riusati dalla verifica candidata con lo stesso manifest immutabile. |
| Android/HTTP | CORS `https://localhost`, ETag/304, HEAD 200, preflight 204; hash della famiglia/release CAMS validi. |
| Sidecar | Percorso riconosciuto e 404 `not_published`, atteso finché il produttore non lo pubblica. Il caso positivo è coperto dai test di fase 01. |
| Configurazioni | 12 job e 11 scheduler invariati; runtime HTTP salvo immagine e IAM invariati. Nessun job eseguito manualmente. |
| Log | Nessun 5xx/ERROR della nuova revisione nella finestra controllata; sei richieste Android FVG/CAMS confermate con 304. È una verifica puntuale, non monitoraggio prolungato. |

## Nazionale e app realmente installata

Il servizio nazionale è separato e non è stato distribuito: revisione
`meteofriul-national-weather-00002-fkt`. Il contratto `weather/v2/icon2i`
resta invariato. Verificati hash di manifest/indice nazionale (7.894 voci) e
sei blocchi campione: Milano, Canazei, Roma, Napoli, Palermo e Cagliari.
Per ogni località: identità ISTAT, hash/dimensioni, 73 ore; entrambi i vecchi
client producono correttamente 12 ore successive e quattro giorni di previsione.
È una verifica campionaria dei dati, non un controllo completo di tutti i blocchi nazionali.

Sul Galaxy SM-A525F Android 14 è stata usata l'app ufficiale già installata,
`com.meteofriul.app`, versione 0.1.14 / 300031, proveniente dalla distribuzione
Play. Hash di base APK e dei tre split, versione e date installazione/aggiornamento
sono identici prima/dopo. Nessuna installazione, AAB o emulatore.

- Pordenone: previsioni giornaliere/orarie, UV, aria e pollini leggibili.
- Roma: ricerca e apertura riuscite, previsioni di oggi/domani e ore leggibili;
  i log del servizio nazionale confermano risposte HTTP 200 a resolver/blocco
  richiesti dalla WebView SM-A525F alle 17:49:30 UTC.
- Fuori FVG UV/aria/pollini restano non disponibili: copertura preesistente
  della versione installata, coerente con i sorgenti originali; nessun nuovo
  servizio nazionale CAMS viene introdotto da questa fase.
- Ripristinate località Pordenone e posizione automatica iniziale; la scelta
  manuale di Roma aveva sospeso automaticamente quest'ultima. Interruttore
  Avvisi mai toccato; preferenze finali verificate uguali a quelle iniziali.
- Nessun errore fatale nelle ultime 600 righe di log del processo app.

Schermate: [Roma](evidence/icon-tolerance-phase1-2026-10-19/phone-roma-forecast.png),
[Roma domani](evidence/icon-tolerance-phase1-2026-10-19/phone-roma-tomorrow.png),
[Pordenone ripristinata](evidence/icon-tolerance-phase1-2026-10-19/phone-pordenone-final.png).

## Rollback pronto, non eseguito

Prima dell'attivazione di produttore/consumatore sidecar, un problema del solo
servizio HTTP si può annullare ripristinando il traffico sulla revisione precedente:

```powershell
gcloud run services update-traffic meteofriul-weather --project=meteo-friul --region=europe-west1 --to-revisions=meteofriul-weather-00004-l72=100
```

La revisione precedente e il suo digest sono conservati nel
[manifest di distribuzione](evidence/icon-tolerance-phase1-2026-10-19/deployment-and-rollback.json).
Dopo la futura attivazione dei sidecar serve invece mantenere il lettore HTTP
compatibile: non riutilizzare automaticamente questa revisione precedente.

Per il futuro rollback del produttore è pronta l'immagine di fase 01 sopra:
legge checkpoint 1/2 e conserva il vecchio comportamento di scrittura. Nessun
job è stato aggiornato a questa immagine in questa fase. Il comando futuro
è registrato nel manifest, da usare soltanto su decisione esplicita di rollback,
senza eliminare checkpoint né riscrivere oggetti immutabili. Non è stata
provocata un'interruzione del produttore per simulare il rollback in produzione.

## Punti aperti alla chiusura della fase 01

1. Fase 02: preparare il consumatore separato in `dry_run`, con zero invii e
   senza scheduler nuovo, includendo i riepiloghi nel passaggio coordinato.
2. Fase 03: attivare il nuovo produttore soltanto su una nuova corsa e verificare
   sidecar/prove/contatori. Il contratto delle tolleranze non è ancora operativo.
3. Confrontare decisioni prima/dopo sugli stessi punti/corsa prima di abilitare
   gli invii del nuovo consumatore. Le configurazioni operative precedenti
   continuano a funzionare; non sono stati attivati invii nuovi.

Nota diagnostica: `/healthz` restituisce 404 HTML di piattaforma sia sulla
revisione precedente sia sulla nuova. La disponibilità è stata verificata
sugli URL meteo reali, oltre alle condizioni Ready del servizio.

Le evidenze compatte sono in
[evidence/icon-tolerance-phase1-2026-10-19](evidence/icon-tolerance-phase1-2026-10-19/SHA256SUMS.txt).
Le risposte complete, i log e le configurazioni prima/dopo restano nella directory
canonica `.tmp/icon-tolerance-phase1-20261019`. Nessuna credenziale copiata.
Verbale salvato localmente nel ramo del lavoro; non eseguito un nuovo push.
