# Proposta CAMS per la soglia di età — da approvare, non implementata

Base: `CAMS_MORNING_DIAGNOSIS_2026-09-10.md`. La soglia nei sorgenti resta
**30 ore**, in produttore, validatore e runtime. Nessuna release pubblicata
è modificata. Questa proposta non riguarda ICON né UV.

## Proposta operativa esplicita

Propongo di valutare **35 ore come tetto di continuità della sola corsa precedente**,
non come nuova definizione di dato fresco e non come limite scientifico certificato.
L'adozione richiede una decisione successiva sul rischio di usare queste previsioni;
non è inclusa nelle correzioni di timeout/cache/worker.

| Regola | Proposta |
|---|---|
| Freschezza | Invariata: fino a 24 ore dalla corsa, sempre entro la copertura reale |
| Età massima | Al massimo 35 ore, stato `stale` oltre 24 ore; nessun rinnovo quando viene letto dalla cache |
| Copertura necessaria | Il timestamp corrente deve essere dentro `[valid_from, valid_to]`; nessun requisito arbitrario di 12/48 ore future |
| Campione corrente | Ultimo campione orario reale con `valid_at <= now` e `now - valid_at < 1 ora`; nessuna interpolazione, riempimento o riuso dell'ultima ora dopo la sua finestra |
| Pubblicazione valida | Stessa famiglia verificata per aria/pollini: schema, hash, catalogo, comune, unità, completezza e provenienza invariati |
| Nuova corsa | Il puntatore verificato identifica la nuova famiglia; adottarla soltanto dopo validazione della release, dei due manifest e dei due payload necessari al comune |
| Risposta nuova non valida | Non sovrascrivere una precedente previsione ancora utilizzabile; nessuna deroga alla quarantena dei dati invalidi o a una revoca autorevole |
| Risposta vecchia tardiva | Non regredire dalla famiglia nuova a quella vecchia; eccezione solo per un rollback esplicito e verificato della revisione autorevole |
| Fine della continuità | Raggiunto il primo limite tra età massima, copertura, campione corrente mancante e revoca, mostrare unavailable; non attendere artificialmente la successiva finestra delle 17 |

Il valore **35** è una proposta di prodotto motivata dalla sequenza operativa
sotto, non viene dedotto dal fatto che il file contenga 96 ore. Non propongo
di accettare automaticamente tutte le previsioni fino al loro ultimo lead.

## Perché questo tetto, e che cosa non dimostra

La documentazione ufficiale descrive una corsa quotidiana alle 00 UTC, campioni
orari e disponibilità garantita dei lead 0–48 entro le 08 UTC, 49–96 entro le
10 UTC, con possibile disponibilità anticipata. La nostra acquisizione richiede
congiuntamente l'intero intervallo 0–96. Le finestre esistenti sono 05/10/15/20 UTC.
[ECMWF, documentazione CAMS regionale](https://confluence.ecmwf.int/spaces/CKB/pages/202173092/CAMS%2BRegional%2BEuropean%2Bair%2Bquality%2Banalysis%2Band%2Bforecast%2Bdata%2Bdocumentation).

Per la corsa del giorno precedente, la finestra delle 10 UTC cade a **34 ore
dalla corsa**. Un margine operativo massimo di un'ora darebbe un tetto di 35 ore:
in settembre, fino alle 13 CEST. Non richiede cambi di scheduler. Quel margine
è una scelta esplicita da approvare: non è uno SLA del fornitore né una stima
statistica della coda ADS.

Il 10 settembre il puntatore aria/pollini è cambiato alle **10:10:02.461 UTC /
12:10:02.461 CEST**: età della corsa precedente circa **34 h 10 min**. Il limite
proposto avrebbe coperto quel tratto, se il client fosse riuscito a leggere e
verificare i dati; non avrebbe da solo corretto il timeout o garantito la UI sul
Samsung. Non confondere questo evento con l'intento delle 10:01:11 UTC /
12:01:11 CEST o con la verifica conclusiva delle 10:10:37.202 UTC /
12:10:37.202 CEST.

**Accettabilità dell'età previsionale:** la continuità non dimostra accuratezza.
La documentazione descrive confronti dei modelli con osservazioni e valutazioni
per stazione/paese, non prescrive una soglia client universale di 30, 35 o 48 ore.
La rappresentatività della griglia regionale limita inoltre l'interpretazione
di fenomeni strettamente locali. I pollini della pilota restano concentrazioni
modellistiche sperimentali senza classi sanitarie.
[ECMWF, osservazioni e valutazione delle previsioni](https://confluence.ecmwf.int/spaces/CKB/pages/202173092/CAMS%2BRegional%2BEuropean%2Bair%2Bquality%2Banalysis%2Band%2Bforecast%2Bdata%2Bdocumentation).

Non sono disponibili in questo intervento una validazione locale FVG per tutte
le specie/variabili ai lead 30–35, un confronto con osservazioni dell'episodio,
né una distribuzione delle latenze ADS che certifichi il margine di un'ora.
Perciò **non dichiaro dimostrato che 35 ore siano scientificamente equivalenti
alla corsa nuova**. Prima dell'adozione va approvato l'uso informativo di una
corsa precedente entro questi limiti; per un requisito sanitario o una garanzia
di accuratezza servirebbero evidenze ulteriori, non un aumento della soglia.
Finché manca questa decisione, rimane correttamente in vigore il limite attuale.

## Implementazione successiva, solo dopo approvazione

- Allineare `local_pipeline/contract_v1.py`, contratti/freschezza di
  `weatherV1Client.js` e `localWeatherV1Runtime.js`. Usare gli stessi confini
  temporali; non cambiare soltanto `usable_until` nel manifest.
- Produrre la nuova policy soltanto per nuove release. I client nuovi devono
  riconoscere esplicitamente anche le release precedenti con policy 30 ore e
  rispettarne il limite, senza estenderle retroattivamente. I client vecchi non
  vanno presunti compatibili con manifest a 35 ore: l'attuale controllo di
  coerenza li rifiuterebbe. Pianificare quindi la compatibilità/versione del
  contratto e l'ordine delle distribuzioni prima di una pubblicazione.
- Testare età 24 h, 30 h e 35 h esatte e ±1 ms; oltre 35 h rifiuto. Per il tetto
  proposto: `usable_until = min(run + 35 h, valid_to)`, senza tolleranze nascoste.
- Testare `valid_from`, `valid_to`, buchi orari, campione di 59 min 59,999 s e di
  60 min, valori zero, cambi d'ora/data e timezone Europe/Rome/DST.
- Testare switch atomico alla nuova famiglia, risposta tardiva, errore di un
  membro, revoca/rollback, offline e cache senza rinnovo della validità.
- Nessun cambio implicito a testi, UI, notifiche, frequenze o soglia UV.

Questa proposta e le fonti sono consultate in sola lettura; nessun test di
accuratezza sul campo, nuova acquisizione o modifica delle soglie è stato eseguito.
