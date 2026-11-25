# ICON nazionale: ripresa controllata di `manual_review` — 25 novembre 2026

**Aggiornamento delle 19:41 UTC:** il protocollo della PR 63 è stato integrato
in `main` `e4b80906`, distribuito nel solo job nazionale e usato una volta
da un job operatore isolato. La fence è `completed` e Storage/HTTP servono
il ciclo `20261125T120000Z`; lo Scheduler nazionale è stato riattivato.
La telemetria delle 19:40 precedeva la pubblicazione; lo slot delle
20:10 ha poi registrato stato sano, senza criticità attive.
[Evidenza operativa e limiti](WEATHER_ICON_CAMS_RECOVERY_20261125.md).
Le sezioni sotto conservano il progetto e i gate come erano prima
dell'attivazione, non descrivono lo stato live successivo.

## Stato osservato

Alle **16:53 UTC / 17:53 CET** il record durevole
`pilot/state/icon-recovery/v1/national/active.json` è ancora in
`manual_review` sul ciclo `20261121T120000Z`, slot `20261121-pm`. La
[diagnostica della PR 61](WEATHER_ICON_CAMS_RECOVERY_20261125.md) è nel
sorgente `main` `488f7d3c`, ma il job distribuito usa ancora il digest
precedente `sha256:d062db94…`. Nessuna fence, Scheduler, immagine ICON,
puntatore pubblico o policy è stata modificata da questo ramo.

## Perché serve un protocollo distinto

Il ciclo del 21 novembre ha un intent, ma non un checkpoint completo né un
manifest pubblico. Il bundle acquisito in memoria non è recuperabile. Il
percorso automatico sostituisce un owner solo dopo un checkpoint verificato
o una pubblicazione completa, perciò gli slot successivi rileggono la
stessa fence. Cancellare `active.json` o usarne l'età come timeout potrebbe
permettere due acquisizioni concorrenti e perdere la prova dell'incidente.

Il ramo `codex/icon-manual-review-recovery-20261125`, nato dal `main`
`488f7d3c`, prepara invece una supersessione nazionale esplicita:

1. Verifica generazione e hash esatti dell'owner fallito, claim, intent,
   assenza di mapping/prepared/manifest e puntatore pubblico corrente.
2. Crea e rilegge un record di incidente immutabile che lega vecchio owner,
   prova di quiescenza, ciclo nuovo e identità dell'operatore.
3. Sostituisce l'owner solo con CAS sulla generazione letta; una risposta
   persa si riconcilia con i byte del record e della fence, senza un secondo
   claim o una seconda acquisizione.
4. Il ciclo nuovo segue il normale checkpoint durevole, manifest pubblicato
   per ultimo, lettura Storage/HTTP e completamento. Un claim senza
   checkpoint dopo un crash resta fermo per revisione, senza retry cieco.

`icon_operator_cli.py` offre `inspect` in sola lettura anche quando il
guard esecutivo non è soddisfatto. `--execute` è separato dal `run()`
schedulato e richiede un job operatore Cloud Run distinto: una workstation
non può invocarlo come recupero. Il guard legge Scheduler, job ed esecuzioni
cloud, richiede pausa dello Scheduler, zero esecuzioni nazionali attive,
immagine e commit approvati, isolamento dei writer legacy e identità del
job operatore. Il controllo è ripetuto prima del CAS e del claim. I log
emettono categorie consentite senza credenziali, URL di richieste o GRIB.

## Verifica del codice e limite operativo

L'agente METEO ha superato **95 test offline mirati** su protocollo,
wrapper, worker nazionale, store GCS e diagnostica; `compileall` e
`git diff --check` sono passati. La configurazione Cloud Build nazionale
include i nuovi test nella suite offline. Il comando aggiunto alla CI
GitHub per CLI, protocollo e worker nazionale ha superato **41 test** in
locale. Queste prove non sono una corsa
cloud e non attestano che l'invocatore sia pronto nel progetto reale.

**Alle 16:53 UTC `--execute` non era utilizzabile.** Mancavano un job operatore isolato
con immagine e commit verificati, il marker `WEATHER_SOURCE_COMMIT` nel job
nazionale distribuito, prova IAM e inventario completo degli altri writer,
una finestra con Scheduler sospeso e zero esecuzioni, e un modo affidabile
di mantenere fresco l'inventario durante l'avvio del job operatore. Il
parametro attuale contiene un'attestazione statica valida per 60 secondi:
il provisioning Cloud Run può consumarla prima del primo guard. Il codice
rifiuta l'operazione se la prova scade; non si allunga arbitrariamente
questa durata. Anche un semplice deploy dell'immagine lascerebbe quindi
intatta la fence.

## Gate per una futura attivazione

- Revisionare la PR sorgente e ottenere CI PR/`main` verde; costruire una
  candidata ICON con provenienza, inventario runtime, dipendenze e test
  offline verificati. Il piano di overlay minimo è conservato nello
  staging locale ignorato `.tmp/icon-operator-deploy-20261125/`.
- Progettare e verificare un'attestazione live degli altri writer e IAM
  che non scada durante il provisioning, e il job operatore isolato con
  service account e permessi minimi. Dimostrare in test e in cloud che
  nessuna invocazione legacy può scrivere la fence durante la manutenzione.
- Solo con un runbook completo, catturare il template e la generazione
  correnti, sospendere lo Scheduler, verificare zero esecuzioni e ciclo
  sorgente successivo, eseguire `inspect`, poi una sola `--execute` con
  evidenza immutabile. Su risposta ambigua rileggere incidente e active:
  non ripetere il comando alla cieca.
- Verificare checkpoint, manifest, puntatore Storage, HTTP e monitor di
  freschezza prima di ripristinare lo Scheduler e dichiarare recupero.

Questa sezione era un **progetto verificato localmente**; la prova del recupero
successivo è nel rapporto operativo collegato in apertura. Mercati e gli
artefatti Web/Android non sono coinvolti.
