# ICON nazionale e CAMS: diagnosi e correzioni candidate — 25 novembre 2026

## Stato e perimetro

Base del codice `origin/main` `61ca8e5e`; workstream
`codex/weather-icon-cams-recovery-20261125`. Questo rapporto distingue
**sorgente**, **codice candidato**, **immagine distribuita**, **esecuzione del
job** e **dato pubblicato**. Al controllo live delle **15:34 UTC / 16:34 CET**
le immagini cloud non erano state aggiornate da questo workstream. Le letture
cloud e le tre richieste GET ai metadati pubblici CAMS erano in sola lettura:
nessun ADS POST, esecuzione manuale, modifica di fence, Scheduler o policy.

## CAMS: causa verificata e correzione

La [comunicazione ufficiale ECMWF del 23 novembre](https://forum.ecmwf.int/t/upgrade-u11-to-the-cams-european-air-quality-products/15596)
annuncia l'upgrade U11 dei prodotti europei e sette parametri aggiuntivi,
con prima produzione operativa prevista il 24 novembre. Il form pubblico
ADS letto via GET il 25 novembre espone **35 variabili**: le 28 richieste
dall'app più quelle sette. Il codice precedente richiedeva un'uguaglianza
esatta fra form e lista di 28, perciò gli slot 09/10/11 UTC terminavano in
`PublicMetadataError` nella validazione. Alle 15 UTC il catalogo esponeva
anche `cads:sanity_check.status="warning"`, fuori dall'insieme
`available/down` accettato; il job ha registrato
`catalogue_sanity_unavailable`. Il puntatore famiglia aria/pollini su
Storage e HTTP era ancora al run del **23 novembre, 09:01:18 UTC**.
Nello stesso slot delle 15 UTC UV è stato pubblicato separatamente con
`run_at=2026-11-25T00:00:00Z`.

La modifica a [cams_request_plan.py](../../experiments/weather_autonomy/cams_request_plan.py)
accetta **solo** le sette opzioni U11 aggiuntive nel form, senza richiederle.
Il piano resta di **28 variabili × 97 lead = 2.716 campi**; nomi mancanti o
ulteriori non approvati falliscono. `warning`, come il già tollerato `down`,
passa soltanto dopo identità, licenza, DOI, data, URL/hash e vincoli completi
con un'unica riga compatibile; un dataset esplicitamente disabilitato resta
bloccato. Il controllo pubblico GET del 25 novembre alle 15:34 UTC ha creato
in memoria un piano valido senza inviare una richiesta ADS.

La diagnostica aggiunta emette campi sicuri come `metadata_field`,
`expected_count` e `actual_count`; per il caso U11 registra 28/35 e lo stato
`warning` dopo validazione, senza URL, body o dettagli arbitrari di eccezione.
Il catalogo pubblico letto aveva DOI `10.24381/a4005cee`, licenza CC-BY-4.0
e timestamp del sanity check `2026-11-25T14:18:02.925059+00:00`.

**Limite di qualità:** U11 cambia anche la conversione upstream dei gas da
mixing ratio a concentrazione a temperatura/pressione standard. Il decoder
locale tratta i valori GRIB di massa e non ripete quella conversione;
il piano validato non dimostra comparabilità o plausibilità dei nuovi valori.
Dopo una corsa autorizzata servono controllo delle unità GRIB, dei range,
della famiglia aria/pollini e della lettura Storage+HTTP. Nessun dato CAMS
è dichiarato recuperato sulla base dei soli test o GET.

## ICON nazionale: log e stato durevole

Il controllo live delle 15:34 UTC trova ancora
`state/icon-recovery/v1/national/active.json` in `manual_review`, slot
`20261121-pm`, ciclo `20261121T120000Z`, con fence presente. L'ultimo slot
osservato, 10 UTC, è fallito; il prossimo è previsto alle 18 UTC. Il puntatore
Storage pubblico resta al run 00Z del 21 novembre e il reader HTTP restituisce
503. La prima acquisizione del 21 novembre risulta completata alle 18:02:58
UTC, seguita da `acquisition_requires_review` alle 18:03:20. Esiste
`intent.json`, ma non mapping, prepared o manifest pubblico. Il bundle GRIB
in memoria non è conservato: non è possibile riprodurre esattamente
l'eccezione originale da quel ciclo. I dodici slot falliti successivi possono
solo rileggere la stessa fence.

Il codice precedente catturava l'eccezione prima di registrare il tipo/la
fase sicuri. La modifica a
[national_cloud_worker.py](../../experiments/weather_autonomy/national_cloud_worker.py)
delimita validazione del bundle, preparazione, upload e verifica del
checkpoint; [icon_recovery.py](../../experiments/weather_autonomy/local_pipeline/icon_recovery.py)
emette un evento strutturato prima di trasformare l'errore in
`manual_review`. Il filtro in
[operational_diagnostics.py](../../experiments/weather_autonomy/local_pipeline/operational_diagnostics.py)
ammette solo nomi di file e campi controllati, non messaggi, URL o payload
arbitrari. I test simulano errori contenenti dati sensibili e verificano che
non siano stampati.

**La fence esistente non viene rimossa da questa patch.** Il contratto di
recupero permette di sostituire un owner soltanto dopo una pubblicazione
verificata o un checkpoint durevole; qui quest'ultimo manca. Per riprendere
ICON nazionale serve una procedura operativa separata, revisionata, con prova
che non vi siano esecuzioni attive, registrazione immutabile dell'incidente,
CAS esatto sullo stato, scelta di un ciclo sorgente successivo e verifica
completa di manifest, puntatore e HTTP. Una semplice cancellazione della
fence o un timeout violerebbero l'invariante di concorrenza.

## Log e monitor esistenti

I job scrivono eventi JSON strutturati in Cloud Logging: fasi, esiti,
componenti, tipi di errore, file/riga e reason code consentiti. Il monitor
ICON confronta anche puntatore Storage, HTTP, copertura e freschezza: al
controllo del 25 novembre rilevava il nazionale critico, pur con il proprio
container riuscito. CAMS ha policy sui fallimenti del job, ma quella policy
non attesta che aria e pollini siano correnti e non vede uno Scheduler che
non invoca il job. I limiti di osservabilità qui erano **specifici**:

- `Recovery.run` trasformava l'eccezione iniziale ICON in
  `acquisition_requires_review` senza emettere prima la fase e il tipo
  dell'errore; gli slot seguenti leggevano solo la fence persistente.
- La diagnostica CAMS occultava correttamente i testi non fidati, ma non
  conservava un'etichetta controllata del campo rifiutato. Gli eventi
  precedenti permettevano di distinguere `metadata_validation` e
  `catalogue_sanity_unavailable`, non la nuova lista U11.

Le correzioni aggiungono **categorie e conteggi predefiniti**, senza
registrare credenziali, URL con parametri, corpi HTTP, GRIB o messaggi
arbitrari. Occorre ancora verificare che gli eventi arrivino nel log di
una futura esecuzione cloud e che un allarme sia effettivamente ricevuto;
la presenza di una policy non è prova di recapito.

## Verifiche e prossimi gate

- **Codice candidato:** 120 test combinati ICON/CAMS/diagnostica passati in
  locale; i test CAMS includono variabili U11, `warning`, rifiuto di opzioni
  sconosciute o vincoli incompleti e indipendenza UV. Due test ICON simulano
  il primo guasto senza manifest, mantengono `manual_review` e verificano
  l'assenza di segreti nei log. La suite meteo completa è registrata dopo
  la sua conclusione; i test non sono una corsa cloud.
- **CAMS prima di dichiarare recupero:** CI e provenienza immagine, deploy
  controllato, una corsa reale, checkpoint/reader Storage+HTTP, freschezza
  delle tre componenti e plausibilità U11. Nessuna di queste prove è
  implicata dal GET di metadati.
- **ICON prima di dichiarare recupero:** definire e verificare la procedura
  sulla fence, acquisire un nuovo ciclo, completare i checkpoint e il
  manifest, verificare Storage/HTTP e il monitor di freschezza. La sola
  diagnostica migliora il prossimo errore, non ripara il ciclo 21 novembre.

Non sono state modificate le app Web/Android, i job distribuiti, Mercati o
le notifiche.
