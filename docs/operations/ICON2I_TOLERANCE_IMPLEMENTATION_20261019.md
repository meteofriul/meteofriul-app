# ICON-2I: contratto di tolleranza integrato in locale

19 ottobre 2026, ramo `codex/local-notice-icon2i-analysis`, base `main`
`8497e773b1613312bb952236d72c074e22a7b1c6`. L'implementazione descritta
qui è ora salvata nei tre commit del [passaggio coordinato](ICON2I_COORDINATED_ROLLOUT_20261019.md),
non promossi e non distribuiti. Le verifiche sotto sono lo storico della fase
di implementazione; il piano riporta anche i successivi controlli per commit.
Nessun push, deploy, AAB, emulatore, nuova acquisizione o invio reale in questa
preparazione. La TEST è stata aggiornata separatamente, come documentato nel piano.

## Risultato pratico

Il contratto ora attraversa produttore regionale, documento pubblico,
adattatore e rilevatori del job. Il campione congelato di Ciampac passa da
neve non valutabile a valutabile senza candidato. Un caso sintetico con una
componente neve nota sufficiente e l'altra non quantificabile produce invece
un candidato neve, conservando l'evidenza della tolleranza. Il servizio di
invio è esercitato in dry-run con sorgente, audit e sender fittizi: zero invii.

Ciampac aveva neve **al suolo**, non una nevicata in corso verificata.
Il caso reale non prova quindi il riconoscimento di una nevicata significativa;
la verifica positiva è sintetica. Non attribuire al campione reale gli altri
input termici/geografici delle fixture usate dal rilevatore regionale.
La [prova originale](ICON2I_CIAMPAC_TOLERANCE_PROBE_20261019.txt) e il suo
[campione](../../experiments/weather_autonomy/fixtures/ciampac-snow-tolerance-20261019.json)
restano invariati; questo documento descrive l'integrazione successiva.

## Regola implementata

| Campo finale orario | Componenti | Budget operativo |
| --- | --- | --- |
| `precipitation_mm` | TOT_PREC | 0,1 mm/h |
| `liquid_rain_mm` | RAIN_CON + RAIN_GSP | 0,1 mm/h complessivi |
| `snow_water_equivalent_mm` | SNOW_CON + SNOW_GSP | 0,02 mm SWE/h complessivi |

Per ogni componente non quantificabile, il produttore legge la somma dei
passi di codifica dei due accumuli consecutivi. Somma questi budget solo
per le componenti incerte e applica il limite al campo finale, non a ogni
componente separatamente. Richiede inoltre `packingError` presente, finito
e non negativo per entrambi i messaggi. Q e packingError sono conservati
nella diagnostica del checkpoint: non si presenta la somma di Q come limite
certificato dell'errore, né come incertezza della previsione.

L'estensione `accumulation_quality`, versione `icon-accumulation-tolerance.v1`,
distingue `known_zero`, `quantified`, `resolution_tolerance_verified` e
`unavailable`. Conserva somma delle componenti note, numero di componenti
incerte, budget, unità e motivo di rifiuto. Si applica ai flag positivi e
negativi entro risoluzione; un mancante generico non diventa tollerato.

Il valore pubblico resta null se una componente non è quantificata.
Solo una proiezione privata dei rilevatori può usare la somma delle componenti
note e ignorare il contributo entro tolleranza. Non aggiunge il budget alle
somme e non modifica i valori condivisi con app e riepiloghi. È una scelta
operativa esplicita: vicino alle soglie può differire da un dato esatto.
Zero autentico, dato assente e dato invalido restano distinti. La prova è
validata sul JSON originale prima di adattare i numeri, così stringhe, bool,
NaN, infinito o chiavi assenti non possono diventare null tollerati.

Il rapporto neve/acqua regionale è dichiarato fisso **10:1**: 1 mm SWE
corrisponde numericamente a 1 cm di neve; 2 cm/3h corrispondono a 2 mm SWE/3h.
Non è una misura del manto né una stima dipendente dalla temperatura.

L'indicatore deterministico resta null quando TOT_PREC non è quantificato.
Il gate può ignorarlo solo per un totale con tolleranza verificata, quando
non cambia il trigger secondo questa politica. Per la pioggia, se il trigger
è possibile, occorre un indicatore noto positivo in un'ora di picco; per la
neve nel percorso sugli accumuli occorre in un'ora con neve positiva.
Il percorso tramite codice meteo resta distinto. Le soglie usate dal gate
e dai rilevatori sono condivise, senza modificarne il valore.

Ogni rilevatore conserva i tre esiti previsti e aggiunge
`uses_operational_tolerance` / `tolerance_used`. Un candidato con un altro
fenomeno indisponibile mantiene lo stato complessivo parziale. Deduplicazione,
anticipo massimo e criteri di invio restano invariati. I riepiloghi mattutino
e serale continuano a rifiutare dati incompleti, anche con prova di tolleranza:
non descrivono come asciutta una giornata con dati mancanti.

## Diagnostica

Il produttore conta stati e rifiuti per campo con denominatore per corsa.
Nei log passano `quality_tolerance_expected_*`, `quality_tolerance_verified_*`
e `quality_guard_*` con motivi distinti: metadati assenti, budget superato,
accumulo mancante/invalido. I nuovi contatori attraversano la whitelist del
logger; non basta conservarli nel checkpoint. Aggregare per `source_run_id`,
senza sommare i retry come nuove corse.

Il job conta le valutazioni che usano tolleranza e conserva le cause dei
rilevatori non valutabili. Più dispositivi sullo stesso punto non moltiplicano
il denominatore. Non è stata creata o modificata alcuna policy di allarme.

## Verifiche locali

- **195 test backend superati**: sorgente, rilevatori, dati mancanti,
  tolleranza, servizi e repository di invio/ombra, outbox, riepiloghi e job.
  Comprendono soglie pioggia/neve appena sotto, uguali e sopra; componenti
  miste; guardia assente/superata; dati invalidi; stato parziale;
  nessun invio nel dry-run e stessa chiave di deduplicazione.
- **151 test produttore/prototipo superati**: derive, contratto, metrica,
  checkpoint, worker con adapter fittizi e campione Ciampac. Il nuovo test
  attraversa 215 comuni × 73 ore, materializza i documenti e ripristina il
  checkpoint schema 2 con le prove, entro i limiti di dimensione esistenti.
- **9 test del logger superati**, inclusa la conservazione dei nuovi contatori.
- **139 test del client frontend superati**, inclusi vecchi documenti,
  estensione valida, null conservati e prove malformate rifiutate.

I test Python sono stati eseguiti con `socket.socket.connect` bloccato.
I test frontend usano il fetch fittizio della suite, senza server o browser.
Vitest 4.1.9 è stato riutilizzato dalle dipendenze già presenti nel workspace
canonico, con `--configLoader native`; nessuna installazione. Non è una
verifica dell'intera build con il lockfile di questa worktree, che richiede
una versione più recente. Il collegamento temporaneo alle dipendenze è rimosso.

La vecchia suite `test_snapshot_materializer` non è eseguibile con gli asset
locali disponibili: manca già in setup `icon2i_integrated_report_20260903.json`
e il relativo insieme storico. Non viene dichiarata superata e non è stato
scaricato nulla per ripristinarla. Il percorso di materializzazione modificato
è coperto dal nuovo test completo descritto sopra. Il corpus delle 82 corse
non è stato ricalcolato: non contiene le prove necessarie a questa guardia.

## Prima di qualsiasi rilascio

1. Distribuire prima i **lettori compatibili**, compresi i client installati:
   il vecchio client verifica le chiavi esatte e rifiuta `accumulation_quality`.
   Il lettore frontend locale ora accetta entrambi i formati e non riempie i
   null. Predisporre anche il lettore checkpoint schema 1/2 prima dello
   scrittore schema 2. Questa revisione combinata non va distribuita come
   primo passo del rollout. La TEST .5 è compatibile; gli altri client installati
   restano da verificare/aggiornare prima del cambio dei documenti condivisi.
2. Solo successivamente attivare lo scrittore e il consumatore coordinati.
   Il rollback deve restare su una versione che sappia leggere le nuove prove
   e i checkpoint, non tornare al vecchio lettore rigido.
3. Verificare le policy di monitoraggio prima di cambiare l'exit code dei
   parziali: gli exit code qui restano invariati. Non esiste ancora una misura
   operativa del tasso di guardie rifiutate o valutazioni recuperate.
4. La nuova guardia riguarda il **produttore regionale v1**. Il percorso
   nazionale v2 non pubblica questa prova ed è invariato; i suoi null non
   ricevono automaticamente tolleranza. Ciampac è una regressione sui dati
   originali, non l'attivazione della politica in produzione fuori dal FVG.

Il lavoro locale è verificato nei limiti dichiarati; la pubblicazione resta
ferma e distinta da questo esito.
